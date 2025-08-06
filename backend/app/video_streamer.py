import cv2
import numpy as np
# watershed + SORT
from skimage.feature import peak_local_max
from skimage.segmentation import watershed
from scipy import ndimage
from sort.sort import Sort  # your local sort.py

class VideoStreamer:
    def __init__(self, source=0, trigger_line_y=120, quality=50):
        self.current_count = 0
        self.processing    = False
        self.cap           = None
        self.source        = source  # can be webcam index or video file path
        self.trigger_line_y = trigger_line_y
        self.encode_param  = [int(cv2.IMWRITE_JPEG_QUALITY), quality]

        # init SORT
        self.tracker = Sort(max_age=5, min_hits=2, iou_threshold=0.3)
        self.counted_ids = set()
    
    def reset(self):
        self.current_count = 0
        self.counted_ids.clear()
        self.tracker = Sort(max_age=5, min_hits=2, iou_threshold=0.3)

    def read_frame(self):
        "Grab one frame, process it, return count, jpeg_bytes"
        if not self.cap: 
            self.cap = cv2.VideoCapture(self.source)  
        if not self.cap.isOpened():
            raise RuntimeError("Video source not opened")
        ret, raw_frame = self.cap.read()
        if not ret:
            return None, None
        
        resized_frame = cv2.resize(raw_frame, (320, 240)) # frame.shape == (480, 640, 3) for webcam
        annotated_frame = self._process_frame_logic(resized_frame) # return annotated frame and count
        success, buffer = cv2.imencode('.jpg', annotated_frame, self.encode_param)
        return self.current_count, buffer.tobytes()
    
    def _process_frame_logic(self, frame: np.ndarray) -> np.ndarray:
        annotated = frame.copy() #copy to be drawn on
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        lower_brown = np.array([8, 50, 40])
        upper_brown = np.array([30, 255, 255])

        lower_light = np.array([0, 0, 160])
        upper_light = np.array([40, 60, 255])

        outer_mask = cv2.inRange(hsv, lower_brown, upper_brown)
        inner_mask = cv2.inRange(hsv, lower_light, upper_light)

        final_mask = cv2.bitwise_or(outer_mask, inner_mask)
        eroded_mask = cv2.erode(final_mask, None, iterations=3)

        D = ndimage.distance_transform_edt(eroded_mask)
        localMax = peak_local_max(D, min_distance=20, labels=eroded_mask)

        marker_mask = np.zeros(D.shape, dtype=bool)
        if localMax.shape[0] > 0:
            marker_mask[tuple(localMax.T)] = True

        markers, _ = ndimage.label(marker_mask)
        labels = watershed(-D, markers, mask=eroded_mask) 

        detections = []

        for label in np.unique(labels):
            if label == 0:
                continue

            mask = np.zeros(eroded_mask.shape, dtype="uint8")
            mask[labels == label] = 255

            cnts = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cnts = cnts[0] if len(cnts) == 2 else cnts[1]
            if len(cnts) == 0:
                continue

            c = max(cnts, key=cv2.contourArea)

            if cv2.contourArea(c) < 1100:
                continue

            #(optional) draw contours and labels
            ((xa, ya), ra) = cv2.minEnclosingCircle(c)
            cv2.circle(annotated, (int(xa), int(ya)), int(ra), (255, 0, 0), 2)

            (x, y, w, h) = cv2.boundingRect(c)
            detections.append([x, y, x + w, y + h, 1.0])  # last value is a confidence score
        
        #if no detections, create an empty array of shape (0, 5)
        if len(detections) > 0:
            detections_np = np.array(detections, dtype=np.float32)
        else:
            detections_np = np.empty((0, 5), dtype=np.float32)
                    
        tracked_objects = self.tracker.update(detections_np)

        # 4) draw tracked objects
        for d in tracked_objects:
            x1, y1, x2, y2, obj_id = d.astype(int)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
            # cv2.putText(annotated, f"ID {int(obj_id)}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            #computer the center of the bounding box
            center_x, center_y = (x1 + x2) // 2, (y1 + y2) // 2
            #if it has not been counted yet and is above the trigger line
            if(obj_id not in self.counted_ids and center_y < self.trigger_line_y):
                self.current_count += 1
                self.counted_ids.add(obj_id)
            # cv2.putText(annotated, f"Count: {self.current_count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
        # 5) draw trigger line & total
        cv2.line(annotated, (0, self.trigger_line_y), (annotated.shape[1], self.trigger_line_y), (0,0,255), 2)
        # cv2.putText(annotated, f"Count: {self.current_count}", (10,30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)
        return annotated

    def release(self):
        if self.cap:
            self.cap.release()
            self.cap = None
        print("Released video capture resource.")
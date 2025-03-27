import cv2
import math
import time

# Global variables
current_count = 0
processing = True

def reset_coconut_count():
    global current_count
    current_count = 0

def run_coconut_counter_stream(video_path="../videos/vid4.mp4"):
    global current_count, processing
    current_count = 0  # reset on start
    processing = True  # ensure processing flag is True on start

    # --- Setup Video Capture ---
    cap = cv2.VideoCapture(video_path) #replace with video_path to use the video
    if not cap.isOpened():
        print("Error: Could not open video.")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print("FPS:", fps)
    print("Video Width:", width)
    print("Video Height:", height)

    # --- ROI and Color Thresholding Parameters ---
    x1, y1, x2, y2 = 0, 205, 478, 709
    lower_brown = (8, 50, 50)
    upper_brown = (30, 255, 255)
    min_contour_area = 2500

    # --- Trigger Line and Counting ---
    trigger_line_x = width - 50

    # --- Tracker Initialization ---
    tracked_objects = {}
    next_object_id = 0
    distance_threshold = 50
    max_disappeared = 5

    while processing:
        ret, frame = cap.read()
        if not ret:
            print("End of video reached or an error occurred")
            break
        
        # Flip the frame horizontally to correct mirroring
        # frame = cv2.flip(frame, 1)

        # Define ROI and draw its rectangle
        roi = frame[y1:y2, x1:x2]
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

        # Convert ROI to HSV and threshold for brown color
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, lower_brown, upper_brown)

        # Find contours and filter small ones
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        filtered_contours = [c for c in contours if cv2.contourArea(c) > min_contour_area]

        # Compute centroids and draw bounding boxes
        current_centroids = []
        for contour in filtered_contours:
            M = cv2.moments(contour)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                current_centroids.append((cx, cy))
                x, y, w, h = cv2.boundingRect(contour)
                cv2.rectangle(roi, (x, y), (x+w, y+h), (255, 0, 0), 2)

        # --- Update Tracker ---
        assigned = set()
        for object_id, data in list(tracked_objects.items()):
            object_centroid = data["centroid"]
            best_match = None
            best_distance = float("inf")

            for i, centroid in enumerate(current_centroids):
                if i in assigned:
                    continue
                distance = math.hypot(centroid[0] - object_centroid[0],
                                      centroid[1] - object_centroid[1])
                if distance < best_distance:
                    best_distance = distance
                    best_match = i

            if best_distance < distance_threshold:
                new_centroid = current_centroids[best_match]
                data["previous_centroid"] = data["centroid"]
                data["centroid"] = new_centroid
                data["disappeared"] = 0
                assigned.add(best_match)
            else:
                data["disappeared"] += 1

        for i, centroid in enumerate(current_centroids):
            if i not in assigned:
                tracked_objects[next_object_id] = {
                    "centroid": centroid,
                    "previous_centroid": centroid,
                    "counted": False,
                    "disappeared": 0
                }
                next_object_id += 1

        # Remove objects that have disappeared for too long
        remove_ids = [obj_id for obj_id, data in tracked_objects.items() if data["disappeared"] > max_disappeared]
        for obj_id in remove_ids:
            del tracked_objects[obj_id]

        # --- Check for Trigger Line Crossing ---
        for object_id, data in tracked_objects.items():
            cx, cy = data["centroid"]
            prev_cx, prev_cy = data["previous_centroid"]
            actual_cx = cx + x1
            actual_prev_cx = prev_cx + x1

            if not data["counted"] and actual_prev_cx <= trigger_line_x and actual_cx > trigger_line_x:
                current_count += 1
                data["counted"] = True
                # print(f"Object {object_id} crossed the trigger line. Total count: {current_count}")

            cv2.circle(roi, (cx, cy), 4, (0, 0, 255), -1)
            cv2.putText(roi, str(object_id), (cx - 10, cy - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        cv2.line(frame, (trigger_line_x, 0), (trigger_line_x, height), (0, 0, 255), 2)
        cv2.putText(frame, f"Coconuts: {current_count}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        # Encode frame as JPEG
        ret2, buffer = cv2.imencode('.jpg', frame)
        if not ret2:
            continue
        frame_bytes = buffer.tobytes()

        # Yield the frame in MJPEG format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n'
               b'X-Count: ' + str(current_count).encode() + b'\r\n')

        time.sleep(0.03)  # Control stream frame rate

    cap.release()

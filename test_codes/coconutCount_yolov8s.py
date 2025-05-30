import cv2
import numpy as np
from ultralytics import YOLO
from sort import Sort    # your cleaned‐up sort.py that only defines the classes

def main(video_path, model_path, line_y=200):
    # load
    model   = YOLO(model_path)
    tracker = Sort(max_age=5, min_hits=3, iou_threshold=0.3)
    counted_ids = set()

    cap = cv2.VideoCapture(video_path)
    count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # --- 1) run detection ---
        results = model(frame, imgsz=640, conf=0.3)[0]
        dets = []
        for *box, conf, cls in results.boxes.data.tolist():
            x1, y1, x2, y2 = map(int, box)
            dets.append([x1, y1, x2, y2, conf])

        # --- 2) prep detections as (N,5) array ---
        if dets:
            dets_np = np.array(dets, dtype=float).reshape(-1,5)
        else:
            dets_np = np.empty((0,5), dtype=float)

        # --- 3) feed to SORT ---
        tracks = tracker.update(dets_np)  # shape (M,5): x1,y1,x2,y2,track_id

        # --- 4) draw & count crosses ---
        for x1, y1, x2, y2, tid in tracks:
            x1,y1,x2,y2,tid = map(int,(x1,y1,x2,y2,tid))
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2

            # draw
            cv2.rectangle(frame, (x1,y1), (x2,y2), (0,255,0), 2)
            cv2.putText(frame, f"ID{tid}", (x1,y1-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)

            # count once when it crosses above the line
            if tid not in counted_ids and cy < line_y:
                count += 1
                counted_ids.add(tid)

        # --- 5) overlay count & line ---
        h, w = frame.shape[:2]
        cv2.line(frame, (0, line_y), (w, line_y), (0,0,255), 2)
        cv2.putText(frame, f"Count: {count}", (10,30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)

        cv2.imshow("Coconut Counter", frame)
        if cv2.waitKey(1) == 27:  # ESC to quit early
            break

    cap.release()
    cv2.destroyAllWindows()
    print("Final count:", count)

if __name__ == "__main__":
    main(
      video_path = "../videos/250_coconut.mp4",
      model_path = "../runs/detect/train2/weights/best.pt",
      line_y = 200
    )


'''from ultralytics import YOLO
import cv2

# Load your trained model
model = YOLO("../runs/detect/train2/weights/best.pt")

# Open camera or video
cap = cv2.VideoCapture("../videos/250_coconut.mp4")  # or use a video file path

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Run inference
    results = model(frame)

    # Draw the results on the frame
    annotated_frame = results[0].plot()

    # Count coconuts (number of bounding boxes)
    coconut_count = len(results[0].boxes)

    # Display the count
    cv2.putText(annotated_frame, f'Coconut Count: {coconut_count}', (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    # Show the annotated frame
    cv2.imshow("Coconut Detection", annotated_frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
'''
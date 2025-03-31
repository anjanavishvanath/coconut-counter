import cv2
import math

# --- Setup Video Capture ---
vid_path = "videos/vid4.mp4"
cap = cv2.VideoCapture(0)  # Capture video from file

if not cap.isOpened():
    print("Error: Could not open video.")
    exit()

fps = cap.get(cv2.CAP_PROP_FPS)
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

print("FPS:", fps)
print("Video Width:", width)
print("Video Height:", height)

output = cv2.VideoWriter('output.mp4',
                         cv2.VideoWriter_fourcc(*'mp4v'),
                         fps,
                         (width, height))

# --- ROI and Color Thresholding Parameters ---
x1, y1, x2, y2 = 0, 205, 478, 709  # ROI coordinates
# (Note: our ROI is defined from y1:y2 and x1:x2)
roi_width = x2 - x1
roi_height = y2 - y1

# Color range for brown coconuts in HSV
lower_brown = (8, 50, 50)  
upper_brown = (30, 255, 255)

min_contour_area = 2500  # Filter out small contours

# --- Trigger Line and Counting ---
# Note: The trigger line is defined in the full frame coordinates.
trigger_line_x = width - 50  
coconut_count = 0

# --- Tracker Initialization ---
# Each tracked object is stored as:
#   { "centroid": (x,y), "previous_centroid": (x,y), "counted": bool, "disappeared": int }
tracked_objects = {}
next_object_id = 0
distance_threshold = 50  # Maximum distance to consider the same object
max_disappeared = 5      # Number of frames an object can disappear before we remove it

while True:
    ret, frame = cap.read()
    if not ret:
        print("End of video reached or an error occurred")
        break

    # Define the ROI from the frame and draw its rectangle
    roi = frame[y1:y2, x1:x2]
    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

    # Convert ROI to HSV and threshold for brown color
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_brown, upper_brown)
    segmented = cv2.bitwise_and(roi, roi, mask=mask)

    # Find contours in the mask and filter small ones
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filtered_contours = [c for c in contours if cv2.contourArea(c) > min_contour_area]

    # Draw bounding boxes for visualization and compute centroids
    current_centroids = []
    for contour in filtered_contours:
        M = cv2.moments(contour)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            print(cx,cy)
            current_centroids.append((cx, cy))
            x, y, w, h = cv2.boundingRect(contour)
            cv2.rectangle(roi, (x, y), (x+w, y+h), (255, 0, 0), 2)

    # --- Update Tracker with Current Centroids ---
    # For each tracked object, try to match with a detected centroid.
    assigned = set()
    # Update existing tracked objects:
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
            # Found a matching detection: update the object's position
            new_centroid = current_centroids[best_match]
            data["previous_centroid"] = data["centroid"]
            data["centroid"] = new_centroid
            data["disappeared"] = 0
            assigned.add(best_match)
        else:
            # No match found: increase the disappeared count
            data["disappeared"] += 1

    # Add new objects for detections that weren't assigned to any tracked object
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
    # (Convert ROI coordinates to full frame coordinates by adding x1)
    for object_id, data in tracked_objects.items():
        cx, cy = data["centroid"]
        prev_cx, prev_cy = data["previous_centroid"]
        actual_cx = cx + x1
        actual_prev_cx = prev_cx + x1

        # Check if object has moved from before the trigger line to after it
        if not data["counted"] and actual_prev_cx <= trigger_line_x and actual_cx > trigger_line_x:
            coconut_count += 1
            data["counted"] = True
            # print(f"Object {object_id} crossed the trigger line. Total count: {coconut_count}")

        # Optionally draw the centroid and ID for visualization:
        cv2.circle(roi, (cx, cy), 4, (0, 0, 255), -1)
        cv2.putText(roi, str(object_id), (cx - 10, cy - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

    # Draw the trigger line on the full frame
    cv2.line(frame, (trigger_line_x, 0), (trigger_line_x, height), (0, 0, 255), 2)
    cv2.putText(frame, f"Coconuts: {coconut_count}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

    cv2.imshow("Frame", frame)
    # Press 'q' to quit (waitKey of 1 is typical for video; here 0 is used for debugging)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

    # Optionally write the frame to the output video
    output.write(frame)

cap.release()
output.release()
cv2.destroyAllWindows()

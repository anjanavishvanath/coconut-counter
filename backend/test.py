from onnxruntime.quantization import quantize_dynamic, QuantType

# paths
fp32_model = "../runs/detect/train2/weights/best.onnx"
int8_model = "../runs/detect/train2/weights/best_int8.onnx"

# quantize
quantize_dynamic(
    model_input=fp32_model,
    model_output=int8_model,
    weight_type=QuantType.QInt8,    # or QuantType.QUInt8
    per_channel=True                # per-channel gives better accuracy
)
print("✅ Dynamic INT8 quantization complete!")


'''
# Convert to ONNX
from ultralytics import YOLO

# load your best weights
model = YOLO('../runs/detect/train2/weights/best.pt')

# export to ONNX (you can tweak dynamic=True if you want variable input sizes)
model.export(format='onnx', dynamic=False, imgsz=640)
'''

'''
import cv2
import numpy as np

# --- 1. Load image and build your coconut mask ---
img = cv2.imread('coconuts.png')                # color image
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
lower_brown = np.array([8, 40, 50])
upper_brown = np.array([30, 180, 255])
mask = cv2.inRange(hsv, lower_brown, upper_brown)  # 0=bg,255=fg

# clean small noise
kernel = np.ones((5,5), np.uint8)
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)

# --- 2. Find the largest contour (should be the two coconuts) ---
cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
if not cnts:
    raise RuntimeError("No contours found!")
# pick the biggest contour by area
contour = max(cnts, key=cv2.contourArea)

# --- 3. Compute the convex hull and convexity defects ---
hull_idxs = cv2.convexHull(contour, returnPoints=False)
defects = cv2.convexityDefects(contour, hull_idxs)

if defects is None:
    raise RuntimeError("No convexity defects found — objects may not indent!")

# find the defect with the largest depth (farthest point from hull)
max_defect = max(defects, key=lambda d: d[0][3])
start_idx, end_idx, far_idx, depth = max_defect[0]
start_pt = tuple(contour[start_idx][0])
end_pt   = tuple(contour[end_idx][0])
far_pt   = tuple(contour[far_idx][0])

print(f"Deepest defect depth = {depth}, start={start_pt}, end={end_pt}, farthest={far_pt}")

# --- 4. Draw a “cut” line between start_pt and end_pt on the mask ---
split_mask = mask.copy()
cv2.line(split_mask, start_pt, end_pt, 0, thickness=5)  
# zero-out a 5-px thick line so that the single blob is split into two

# --- 5. Find the two new contours on the split mask ---
new_cnts, _ = cv2.findContours(split_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
print(f"Found {len(new_cnts)} contours after splitting")

# Draw results for visualization
output = img.copy()
cv2.drawContours(output, [contour], -1, (0,255,255), 2)             # original big contour
cv2.line(output, start_pt, end_pt, (0,0,255), 2)                   # splitting line

# Color each new coconut region
for i, c in enumerate(new_cnts):
    color = tuple(int(x) for x in np.random.randint(0,255,3))
    cv2.drawContours(output, [c], -1, color, 2)
    # optionally fill:
    cv2.drawContours(output, [c], -1, color, cv2.FILLED)

# --- 6. Show everything ---
cv2.imshow("Original Mask", mask)
cv2.imshow("Split Mask", split_mask)
cv2.imshow("Result: Split Coconuts", output)
cv2.waitKey(0)
cv2.destroyAllWindows()
'''
'''
import cv2
import numpy as np

cap = cv2.VideoCapture("../videos/250_coconuts.mp4")

while cap.isOpened():
    ret, frame = cap.read()
    frame = cv2.resize(frame, (640, 480))
    if not ret:
        print("End of video")
        break

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    #brown ranges
    lower_brown = np.array([8, 40, 50])  
    upper_brown = np.array([30, 255, 255])

    # Create a mask for brown color
    mask = cv2.inRange(hsv, lower_brown, upper_brown)

    # do morphologiccal opoerations to remove noise
    kernel = np.ones((8,8), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_ERODE, kernel, iterations=2)
    # mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, kernel)

    #find contours
    contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    #draw contours
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > 1500:  # Filter out small areas
            x, y, w, h = cv2.boundingRect(cnt)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

    cv2.imshow("Frame", frame)
    cv2.imshow("Mask", mask)
    if cv2.waitKey(0) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
'''
'''
# Video rotation test
import cv2

input_path = "../videos/vid4.mp4"
output_path = "../videos/rotated_vid.mp4"

# open input vid
cap = cv2.VideoCapture(input_path)

#check if the video opened successfully
if not cap.isOpened():
    print("Error: Cannot open the video file")
    exit()

#get original video properties
fps = cap.get(cv2.CAP_PROP_FPS)
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

#swap height and width for rotation
rotated_width = height
rotated_height = width

# define the codec and create a VideoWrite object
fourcc = cv2.VideoWriter_fourcc(*'mp4v')  
out = cv2.VideoWriter(output_path, fourcc, fps, (rotated_width, rotated_height))

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Rotate the frame 90 degrees clockwise
    rotated_frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

    # write the rotated frame
    out.write(rotated_frame)

# release everything
cap.release()
out.release()
cv2.destroyAllWindows()  

print("Video rotation complete. Saved as", output_path)
'''
'''
# GPIO test
import lgpio
import time

# BCM pin numbers
START_BUTTON_PIN    = 16
STOP_BUTTON_PIN     = 12
CONVEYOR_RELAY_PIN  = 23

# Setup
chip = lgpio.gpiochip_open(0)

# Inputs with pull-ups
lgpio.gpio_claim_input(chip, START_BUTTON_PIN, lgpio.SET_PULL_UP)
lgpio.gpio_claim_input(chip, STOP_BUTTON_PIN,  lgpio.SET_PULL_UP)

# Relay output, start LOW (1 = off)
lgpio.gpio_claim_output(chip, CONVEYOR_RELAY_PIN, 1)

running = False

try:
    while True:
        start_state = lgpio.gpio_read(chip, START_BUTTON_PIN)
        stop_state  = lgpio.gpio_read(chip, STOP_BUTTON_PIN)
        print(f"Start: {start_state}, Stop: {stop_state}, Running: {running}")
        # If not already running, a press of Start (HIGH->LOW) turns it on
        if not running and start_state == 0:
            lgpio.gpio_write(chip, CONVEYOR_RELAY_PIN, 0)
            running = True
            print("Conveyor STARTED")
            # wait for button release
            while lgpio.gpio_read(chip, START_BUTTON_PIN) == 0:
                time.sleep(0.01)

        # If running, a press of Stop turns it off
        if running and stop_state == 0:
            lgpio.gpio_write(chip, CONVEYOR_RELAY_PIN, 1)
            running = False
            print("Conveyor STOPPED")
            # wait for button release
            while lgpio.gpio_read(chip, STOP_BUTTON_PIN) == 0:
                time.sleep(0.01)

        time.sleep(0.05)

except KeyboardInterrupt:
    pass

finally:
    # cleanup
    lgpio.gpiochip_close(chip)
'''
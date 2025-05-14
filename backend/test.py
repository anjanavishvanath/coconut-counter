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
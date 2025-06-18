
import cv2
import asyncio
from fastapi import FastAPI, WebSocket, HTTPException, BackgroundTasks, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import numpy as np
# import base64
import struct

# Moduoles for report generation and file handling
import csv
from datetime import datetime
from pathlib import Path
from typing import List
from pydantic import BaseModel

# Libraries for email
from dotenv import load_dotenv
import os
import smtplib
from email.message import EmailMessage

# Modules for GPIO simulation
import sys
# Add stubs/ to the front of module search path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'stubs'))
# Modules for GPIO manipulation in Raspberry Pi 
import RPi.GPIO as GPIO 
import lgpio
import time

# watershed + SORT
from skimage.feature import peak_local_max
from skimage.segmentation import watershed
from scipy import ndimage
from sort import Sort  # your local sort.py


# ─── GPIO setup ─────────────────────────────────────────────────────
# BCM pin numbers
START_BUTTON_PIN = 16
STOP_BUTTON_PIN  = 12
CONVEYOR_RELAY_PIN = 23
BUZZEER_PIN = 24

# Open the GPIO chip (always 0 on Pi)
chip = lgpio.gpiochip_open(0)

# Claim the output pins (default LOW/off)
lgpio.gpio_claim_output(chip, CONVEYOR_RELAY_PIN)
lgpio.gpio_claim_output(chip, BUZZEER_PIN)
lgpio.gpio_write(chip, CONVEYOR_RELAY_PIN, 0)
lgpio.gpio_write(chip, BUZZEER_PIN, 0)

# ─── RPi.GPIO setup for the button ────────────────────────────────────────
GPIO.setmode(GPIO.BCM)
GPIO.setup(START_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(STOP_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def start_button_pressed(channel):
    """Callback: button pressed → turn conveyor on."""
    print("Button pressed, starting conveyor…")
    lgpio.gpio_write(chip, CONVEYOR_RELAY_PIN, 1)
    lgpio.gpio_write(chip, BUZZEER_PIN, 0)  # turn off buzzer
    
def stop_button_pressed(channel):
    """Callback: button pressed → turn conveyor off."""
    print("Button pressed, stopping conveyor…")
    lgpio.gpio_write(chip, CONVEYOR_RELAY_PIN, 0)

# ─── Install a falling-edge interrupt with 200 ms debounce ─────────────────
GPIO.add_event_detect(
    START_BUTTON_PIN,
    GPIO.FALLING,              # detect HIGH → LOW transitions
    callback=start_button_pressed,
    bouncetime=200             # debounce in milliseconds
)

GPIO.add_event_detect(
    STOP_BUTTON_PIN,
    GPIO.FALLING,              # detect HIGH → LOW transitions
    callback=stop_button_pressed,
    bouncetime=200             # debounce in milliseconds
)

# ─── Video Processing Classes ────────────────────────────────────────
class VideoStreamer:
    def __init__(self):
        self.current_count = 0
        self.processing    = False
        self.cap           = None
        self.trigger_line_y = 120
        self.encode_param  = [int(cv2.IMWRITE_JPEG_QUALITY), 50]

        # init SORT
        self.tracker = Sort(max_age=5, min_hits=1, iou_threshold=0.25)
        self.counted_ids = set()
    
    def reset(self):
        self.current_count = 0
        self.counted_ids.clear()
        self.tracker = Sort(max_age=5, min_hits=1, iou_threshold=0.25)

    async def video_stream(self, websocket: WebSocket):
        self.cap = cv2.VideoCapture("../videos/250_coconuts.mp4") #"../videos/250_coconuts.mp4"
        self.processing = True


        if not self.cap.isOpened():
            raise HTTPException(status_code=500, detail="Could not open video source")
        
        while self.processing:
            try:
                while self.cap.isOpened():
                    ret, frame = self.cap.read() 
                    # frame.shape == (480, 640, 3) for webcam
                    frame = cv2.resize(frame, (320, 240))  
                    if not ret:
                        break

                    original = frame.copy()  # Keep original frame for drawing

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

                        if cv2.contourArea(c) < 1000:
                            continue

                        #(optional) draw contours and labels
                        ((xa, ya), ra) = cv2.minEnclosingCircle(c)
                        cv2.circle(original, (int(xa), int(ya)), int(ra), (255, 0, 0), 2)

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
                        cv2.rectangle(original, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        # cv2.putText(original, f"ID {int(obj_id)}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                        #computer the center of the bounding box
                        center_x, center_y = (x1 + x2) // 2, (y1 + y2) // 2

                        #if it has not been counted yet and is above the trigger line
                        if(obj_id not in self.counted_ids and center_y < self.trigger_line_y):
                            self.current_count += 1
                            self.counted_ids.add(obj_id)

                        # cv2.putText(original, f"Count: {self.current_count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

                    # 5) draw trigger line & total
                    cv2.line(original, (0, self.trigger_line_y), (frame.shape[1], self.trigger_line_y), (0,0,255), 2)
                    # cv2.putText(original, f"Count: {self.current_count}", (10,30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)

                    _, buffer = cv2.imencode('.jpg', original, self.encode_param)
                    
                    jpg_bytes = buffer.tobytes()
                    #pack the 32 bit count as a 4 byte binary string
                    count_header = struct.pack("!I", self.current_count)

                    # send a single binary frame: [4-byte count][jpeg…]
                    await websocket.send_bytes(count_header + jpg_bytes)
                                        
                    await asyncio.sleep(1/100)  # Control FPS (60 fps)
                    
            except Exception as e:
                print(f"Error in video stream: {e}")
            finally: 
                self.stop_streaming()

    def stop_streaming(self):
        self.processing = False
        if self.cap:
            self.cap.release()
        
        print("Stopped: Video capture released and windows destroyed.")

# ─── load .env ─────────────────────────────────────────────────────
load_dotenv()
# Data is pulled from a .env file in the same directory as this script.
SMTP_HOST     = os.getenv("SMTP_HOST")
SMTP_PORT     = int(os.getenv("SMTP_PORT", 587))   # typically 587 or 465
SMTP_USER     = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM    = os.getenv("EMAIL_FROM")
EMAIL_TO      = os.getenv("EMAIL_TO")

# ─── fastapi setup ─────────────────────────────────────────────────
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#─── Pydantic model for your payload ────────────────────────────────
class BucketReport(BaseModel):
    id: int
    set_value: int
    count: int

class ReportPayload(BaseModel):
    buckets: List[BucketReport]

# ─── helper to send email ───────────────────────────────────────────
def send_report_email(report_path: Path):
    msg = EmailMessage()
    msg["Subject"] = f"Coconut Report {datetime.now():%Y-%m-%d %H:%M:%S}"
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO
    msg.set_content("Please find attached the latest coconut count report.")
    with report_path.open("rb") as f:
        data = f.read()
    msg.add_attachment(data, maintype="text", subtype="csv", filename=report_path.name)

    # implicit SSL on 465, STARTTLS on others (e.g. 587)
    if SMTP_PORT == 465:
        smtp = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT)
    else:
        smtp = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        smtp.starttls()

    smtp.login(SMTP_USER, SMTP_PASSWORD)
    smtp.send_message(msg)
    smtp.quit()

# ─── HTTP functions ──────────────────────────────────────────────
@app.post("/save_report")
async def save_report(payload: ReportPayload, background_tasks: BackgroundTasks):
    """
    Accepts JSON { buckets: [ {id, set_value, count}, … ] }
    Appends one timestamped row to reports.csv.
    """
    report_file = Path(__file__).parent / "reports.csv"
    try:
        report_file.parent.mkdir(parents=True, exist_ok=True)
        with report_file.open("a", newline="") as csvfile:
            writer = csv.writer(csvfile)
            # write header if file was empty
            if csvfile.tell() == 0:
                header = ["timestamp"]
                header += [f"bucket{b.id}_count" for b in payload.buckets]
                writer.writerow(header)
            # write data row
            now = datetime.now().isoformat(sep=" ", timespec="seconds")
            row = [now] + [b.count for b in payload.buckets]
            writer.writerow(row)
    except Exception as e:
        # return a JSON 500 (with CORS headers!)
        raise HTTPException(status_code=500, detail=f"Could not write report: {e}")
    
    # schedule the email to be sent in the background
    # background_tasks.add_task(send_report_email, report_file) # uncomment to send email

    return {"status": "ok", "saved_to": str(report_file)}

# ─── Websocket functions ──────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    video_streamer = VideoStreamer()
    stream_task = None
    
    try:
        while True:
            data = await websocket.receive_text()
            print(f"[WS] got command ➞ {data!r}")

            if data == "start":
                if stream_task is None or stream_task.done():
                    stream_task = asyncio.create_task(video_streamer.video_stream(websocket))
                await websocket.send_text("started")
                lgpio.gpio_write(chip, CONVEYOR_RELAY_PIN, 1)

            elif data in ("stop", "bucket_full", "reset"):
                lgpio.gpio_write(chip, CONVEYOR_RELAY_PIN, 0)
                if data == "stop":
                    video_streamer.stop_streaming()
                    if stream_task and not stream_task.done():
                        stream_task.cancel()
                    await websocket.send_text("stopped")

                elif data == "bucket_full":
                    print("Bucket full: Stopping Conveyor")
        
                elif data == "reset":
                    video_streamer.stop_streaming()
                    if stream_task and not stream_task.done():
                        stream_task.cancel()
                    video_streamer.reset()
                    await websocket.send_text("reset")
                # lgpio.gpio_write(chip, BUZZEER_PIN, 1)
                # await asyncio.sleep(3)
                # lgpio.gpio_write(chip, BUZZEER_PIN, 0)
            else:
                print(f"[WS] Unknown command: {data!r}")


    except WebSocketDisconnect:
        print("Client disconnected")
    
    finally:
        # clean up
        video_streamer.stop_streaming()
        GPIO.cleanup()
        print("Process Ended")

# ─── WebSocket connection handler ────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)

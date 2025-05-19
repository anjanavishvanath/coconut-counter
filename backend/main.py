import cv2
import math
import asyncio
from contextlib import suppress
from fastapi import FastAPI, WebSocket, HTTPException, BackgroundTasks, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
# import base64
import struct

# Testing
from scipy.optimize import linear_sum_assignment
import numpy as np


# Moduoles for report generation and file handling
import csv
from datetime import datetime
from pathlib import Path
from typing import List
from pydantic import BaseModel

# Modules for SORT tracker
from sort import Sort

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

# ─── GPIO setup ─────────────────────────────────────────────────────
# BCM pin numbers
START_BUTTON_PIN = 16
STOP_BUTTON_PIN  = 12
CONVEYOR_RELAY_PIN = 23

# Open the GPIO chip (always 0 on Pi)
chip = lgpio.gpiochip_open(0)

# Claim the relay pin as an output (default HIGH/off)
lgpio.gpio_claim_output(chip, CONVEYOR_RELAY_PIN)
lgpio.gpio_write(chip, CONVEYOR_RELAY_PIN, 1)

# ─── RPi.GPIO setup for the button ────────────────────────────────────────
GPIO.setmode(GPIO.BCM)
GPIO.setup(START_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(STOP_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def start_button_pressed(channel):
    """Callback: button pressed → turn conveyor on."""
    print("Button pressed, starting conveyor…")
    lgpio.gpio_write(chip, CONVEYOR_RELAY_PIN, 0)
    
def stop_button_pressed(channel):
    """Callback: button pressed → turn conveyor off."""
    print("Button pressed, stopping conveyor…")
    lgpio.gpio_write(chip, CONVEYOR_RELAY_PIN, 1)

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
        self.processing = False
        self.cap = None

        # Color threshold for contours (tuned for brown coconuts)
        self.lower_brown = (8, 50, 50)
        self.upper_brown = (30, 255, 255)
        self.min_contour_area = 1250 # 2500 for application

        # Trigger line coordinates
        # self.trigger_line_x = 190 # 190 for webcam, 428 for application
        self.trigger_line_y = 150

        self.encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 50]

        self.tracker = Sort(max_age=5, min_hits=1, iou_threshold=0.3)
        self.counted_ids  = set()

    def reset(self):
        self.processing = False
        self.current_count = 0
        self.tracker      = Sort(max_age=5, min_hits=1, iou_threshold=0.3)
        self.counted_ids.clear()
        

    def process_frame(self, frame):
        roi = frame.copy()
        # 1) DETECTION via HSV threshold + contours
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.lower_brown, self.upper_brown)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        filtered_contours = [c for c in contours if cv2.contourArea(c) > self.min_contour_area]

        dets = []
        for c in filtered_contours:
            if cv2.contourArea(c) < self.min_contour_area: 
                continue
            x,y,w,h = cv2.boundingRect(c)
            dets.append([x, y, x+w, y+h, 1.0])  # last element is dummy “confidence”

        # 2) TRACKING
        tracks = self.tracker.update(np.array(dets))

        # 3) COUNTING logic (same as before)
        for x1,y1,x2,y2,tid in tracks:
            cx, cy = int((x1+x2)/2), int((y1+y2)/2)
            if tid not in self.counted_ids and cy < self.trigger_line_y:
                self.counted_ids.add(tid)
                self.current_count += 1

            # draw for debug
            cv2.rectangle(roi, (int(x1),int(y1)), (int(x2),int(y2)), (0,255,0),2)
            cv2.putText(roi, f"{int(tid)}", (int(x1),int(y1)-5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0),1)

       # draw line + count
        cv2.line(frame, (0, self.trigger_line_y),(frame.shape[1], self.trigger_line_y), (0,0,255),2)
        cv2.putText(frame, f"Count: {self.current_count}", (10,30),cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,0,255),2)
        return roi

    async def video_stream(self, websocket: WebSocket):
        self.cap = cv2.VideoCapture("../videos/real_vid.mp4") #../videos/rotated_vid.mp4
        self.processing = True
        try:
            while self.cap.isOpened() and self.processing:
                ret, frame = self.cap.read() 
                # frame.shape == (480, 640, 3) for webcam
                frame = cv2.resize(frame, (320, 240)) #compensated for rotaed frame
                if not ret:
                    break

                processed_frame = self.process_frame(frame)
                _, buffer = cv2.imencode('.jpg', processed_frame, self.encode_param)
                    
                jpg_bytes = buffer.tobytes()
                #pack the 32 bit count as a 4 byte binary string
                count_header = struct.pack("!I", self.current_count)

                # send a single binary frame: [4-byte count][jpeg…]
                await websocket.send_bytes(count_header + jpg_bytes)
                    
                await asyncio.sleep(1/24)  # Control FPS (24 fps)
                    
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
                lgpio.gpio_write(chip, CONVEYOR_RELAY_PIN, 0)

            elif data in ("stop", "bucket_full", "reset"):
                lgpio.gpio_write(chip, CONVEYOR_RELAY_PIN,1)
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
            
            else:
                print(f"[WS] Unknown command: {data!r}")


    except WebSocketDisconnect:
        print("Client disconnected")
        #stop conveyor?
    
    finally:
        # clean up
        video_streamer.stop_streaming()
        GPIO.cleanup()
        print("Process Ended")

# ─── WebSocket connection handler ────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)

        
		
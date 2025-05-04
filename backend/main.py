import cv2
import math
import asyncio
from fastapi import FastAPI, WebSocket, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
# import base64
import struct

# Libraries for reports
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

# GPIO libraries
import lgpio
import threading
import time

# ─── GPIO setup ─────────────────────────────────────────────────────
# BCM pin numbers
START_BUTTON_PIN = 16
CONVEYOR_RELAY_PIN = 23

# Open the GPIO chip (always 0 on Pi)
chip = lgpio.gpiochip_open(0)

# Claim the relay pin as an output (default low/off)
lgpio.gpio_claim_output(chip, CONVEYOR_RELAY_PIN)
lgpio.gpio_write(chip, CONVEYOR_RELAY_PIN, 0)

# Claim the button pin as an input with pull-up enabled
lgpio.gpio_claim_input(chip, START_BUTTON_PIN, lgpio.SET_PULL_UP)

# spawn a background thread to monitor the button state
def monitor_start_button():
    last_state = 1
    while True:
        state = lgpio.gpio_read(chip, START_BUTTON_PIN)
        #button is pulled up (1) when not pressed
        if state == 0 and last_state == 1:
            # Button pressed, start the conveyor
            lgpio.gpio_write(chip, CONVEYOR_RELAY_PIN, 1)
            print("Button pressed, starting conveyor...")
            time.sleep(0.5)
        last_state = state

# run as a daemon so it stops when your app exits
threading.Thread(target=monitor_start_button, daemon=True).start()

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

        # Tracker parameters
        self.tracked_objects = {}
        self.next_object_id = 0
        self.distance_threshold = 50 #make 120 for application
        self.max_disappeared = 5

        # Trigger line coordinates
        self.trigger_line_x = 190 # 190 for webcam, 428 for application

        self.encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 50]

    def reset(self):
        self.current_count = 0
        self.tracked_objects = {}
        self.next_object_id = 0

    def process_frame(self, frame):
        roi = frame.copy()
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.lower_brown, self.upper_brown)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        filtered_contours = [c for c in contours if cv2.contourArea(c) > self.min_contour_area]

        current_centroids = []
        for contour in filtered_contours:
            M = cv2.moments(contour)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                current_centroids.append((cx, cy))
                x, y, w, h = cv2.boundingRect(contour)
                cv2.rectangle(roi, (x, y), (x + w, y + h), (255, 0, 0), 2)

        assigned = set()
        for object_id, data in list(self.tracked_objects.items()):
            object_centroid = data["centroid"]
            best_match = None
            best_distance = float("inf")

            for i, centroid in enumerate(current_centroids):
                if i in assigned:
                    continue
                distance = math.hypot(centroid[0] - object_centroid[0], centroid[1] - object_centroid[1])
                if distance < best_distance:
                    best_distance = distance
                    best_match = i

            if best_distance < self.distance_threshold:
                new_centroid = current_centroids[best_match]
                data["previous_centroid"] = data["centroid"]
                data["centroid"] = new_centroid
                data["disappeared"] = 0
                assigned.add(best_match)
            else:
                data["disappeared"] += 1

        remove_ids = [obj_id for obj_id, data in self.tracked_objects.items() if data["disappeared"] > self.max_disappeared]
        for obj_id in remove_ids:
            del self.tracked_objects[obj_id]

        for i, centroid in enumerate(current_centroids):
            if i not in assigned:
                self.tracked_objects[self.next_object_id] = {
                    "centroid": centroid,
                    "previous_centroid": centroid,
                    "disappeared": 0,
                    "counted": False
                }
                self.next_object_id += 1

        for object_id, data in self.tracked_objects.items():
            cx, cy = data["centroid"]
            prev_cx, prev_cy = data["previous_centroid"]
            if not data["counted"] and prev_cx <= self.trigger_line_x < cx:
                self.current_count += 1
                data["counted"] = True
            cv2.circle(roi, (cx, cy), 4, (0, 0, 255), -1)
            cv2.putText(roi, str(object_id), (cx - 10, cy - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 0, 255), 1)

        cv2.line(roi, (self.trigger_line_x, 0), (self.trigger_line_x, roi.shape[0]), (0, 0, 255), 2)
        cv2.putText(roi, f"Coconuts: {self.current_count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        return roi

    async def video_stream(self, websocket: WebSocket):
        self.cap = cv2.VideoCapture(0) #../videos/vid4.mp4
        self.reset()
        try:
            while self.cap.isOpened():
                ret, frame = self.cap.read() 
                # frame.shape == (480, 640, 3) for webcam
                frame = cv2.resize(frame, (320, 240))
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
        
        print("Video capture released and windows destroyed.")

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

# ─── Websocket functions ──────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    video_streamer = VideoStreamer()
    try:
        while True:
            #wait for start command
            data = await websocket.receive_text()
            if data == "start":
                await video_streamer.video_stream(websocket)
            elif data == "stop":
                video_streamer.stop_streaming()
                break
            elif data == "/bucket_full":
                # operator wants to stop when a bucket fills
                lgpio.gpio_write(chip, CONVEYOR_RELAY_PIN, 0)
                print("Conveyor stopped: bucket full")
                # return {"message": "Conveyor stopped: bucket full"}
            elif data == "reset":
                video_streamer.reset() #reset the count
    except Exception as e:
        print(f"Connection closed: {e}")
    finally:
        video_streamer.stop_streaming()

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
    background_tasks.add_task(send_report_email, report_file)

    return {"status": "ok", "saved_to": str(report_file)}

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)
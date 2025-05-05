import cv2
import math
import asyncio
from contextlib import suppress
from fastapi import FastAPI, WebSocket, HTTPException, BackgroundTasks, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import struct
import csv
from datetime import datetime
from pathlib import Path
from typing import List
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import smtplib
from email.message import EmailMessage
import lgpio
import RPi.GPIO as GPIO

# ─── Global placeholders ───────────────────────────────────────────
loop = None
start_event = None

# ─── GPIO pins ──────────────────────────────────────────────────────
START_BUTTON_PIN   = 16
STOP_BUTTON_PIN    = 12
CONVEYOR_RELAY_PIN = 23

# ─── Setup lgpio for relay ─────────────────────────────────────────
chip = lgpio.gpiochip_open(0)
lgpio.gpio_claim_output(chip, CONVEYOR_RELAY_PIN)
lgpio.gpio_write(chip, CONVEYOR_RELAY_PIN, 1)  # off

# ─── FastAPI app & config ──────────────────────────────────────────
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Pydantic models ────────────────────────────────────────────────
class BucketReport(BaseModel):
    id: int
    set_value: int
    count: int

class ReportPayload(BaseModel):
    buckets: List[BucketReport]

# ─── Email/report helper ────────────────────────────────────────────
load_dotenv()
SMTP_HOST     = os.getenv("SMTP_HOST")
SMTP_PORT     = int(os.getenv("SMTP_PORT", 587))
SMTP_USER     = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM    = os.getenv("EMAIL_FROM")
EMAIL_TO      = os.getenv("EMAIL_TO")

def send_report_email(report_path: Path):
    msg = EmailMessage()
    msg["Subject"] = f"Coconut Report {datetime.now():%Y-%m-%d %H:%M:%S}"
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO
    msg.set_content("Please find attached the latest coconut count report.")
    with report_path.open("rb") as f:
        data = f.read()
    msg.add_attachment(data, maintype="text", subtype="csv", filename=report_path.name)
    if SMTP_PORT == 465:
        smtp = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT)
    else:
        smtp = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        smtp.starttls()
    smtp.login(SMTP_USER, SMTP_PASSWORD)
    smtp.send_message(msg)
    smtp.quit()

# ─── VideoStreamer class (unchanged) ─────────────────────────────
class VideoStreamer:
    def __init__(self):
        self.current_count = 0
        self.cap = None
        # thresholds & tracker params...
        self.lower_brown = (8, 50, 50)
        self.upper_brown = (30, 255, 255)
        self.min_contour_area = 1250
        self.tracked_objects = {}
        self.next_object_id = 0
        self.distance_threshold = 50
        self.max_disappeared = 5
        self.trigger_line_x = 190
        self.encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 50]
    def reset(self):
        self.current_count = 0
        self.tracked_objects.clear()
        self.next_object_id = 0
    def process_frame(self, frame):
        # contour detection & counting logic...
        return frame  # placeholder
    async def video_stream(self, websocket: WebSocket):
        self.cap = cv2.VideoCapture(0)
        self.reset()
        try:
            while self.cap.isOpened():
                ret, frame = self.cap.read()
                frame = cv2.resize(frame, (320, 240))
                if not ret: break
                processed = self.process_frame(frame)
                _, buf = cv2.imencode('.jpg', processed, self.encode_param)
                jpg_bytes = buf.tobytes()
                header = struct.pack("!I", self.current_count)
                await websocket.send_bytes(header + jpg_bytes)
                await asyncio.sleep(1/24)
        finally:
            if self.cap: self.cap.release()

# ─── Configure GPIO interrupts ──────────────────────────────────────
def gpio_setup():
    global loop, start_event
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(START_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(STOP_BUTTON_PIN,  GPIO.IN, pull_up_down=GPIO.PUD_UP)
    def _on_start(ch):
        print("Button pressed, starting conveyor…")
        lgpio.gpio_write(chip, CONVEYOR_RELAY_PIN, 0)
        loop.call_soon_threadsafe(start_event.set)
    GPIO.add_event_detect(START_BUTTON_PIN, GPIO.FALLING, callback=_on_start, bouncetime=200)

# ─── FastAPI startup to bind loop & events ─────────────────────────
@app.on_event("startup")
async def on_startup():
    global loop, start_event
    loop = asyncio.get_running_loop()
    start_event = asyncio.Event()
    gpio_setup()
    print("Server startup complete. GPIO and events initialized.")

# ─── WebSocket endpoint ─────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    streamer = VideoStreamer()
    task = None
    try:
        while True:
            recv = asyncio.create_task(websocket.receive_text())
            hw   = asyncio.create_task(start_event.wait())
            done, pending = await asyncio.wait([recv, hw], return_when=asyncio.FIRST_COMPLETED)
            if hw in done:
                start_event.clear()
                cmd = "start"
            else:
                cmd = recv.result()
            for t in pending:
                t.cancel()
                with suppress(asyncio.CancelledError):
                    await t
            print(f"[WS] cmd: {cmd!r}")
            if cmd == "start":
                if task is None or task.done():
                    await websocket.send_text("started")
                    task = asyncio.create_task(streamer.video_stream(websocket))
            elif cmd in ("stop","bucket_full","reset"):
                await websocket.send_text("stopped")
                lgpio.gpio_write(chip, CONVEYOR_RELAY_PIN, 1)
                if cmd == "reset":
                    streamer.reset()
                if task and not task.done():
                    task.cancel()
                    with suppress(asyncio.CancelledError): await task
                if cmd == "stop": break
    except WebSocketDisconnect:
        print("Client disconnected")
    finally:
        if task and not task.done(): task.cancel()
        streamer.stop_streaming()

# ─── HTTP report endpoint ──────────────────────────────────────────
@app.post("/save_report")
async def save_report(payload: ReportPayload, background_tasks: BackgroundTasks):
    report_file = Path(__file__).parent / "reports.csv"
    with report_file.open("a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        if csvfile.tell() == 0:
            writer.writerow(["timestamp"] + [f"bucket{b.id}_count" for b in payload.buckets])
        now = datetime.now().isoformat(sep=" ", timespec="seconds")
        writer.writerow([now] + [b.count for b in payload.buckets])
    background_tasks.add_task(send_report_email, report_file)
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
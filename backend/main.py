import cv2
import math
import asyncio
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import base64
import json

class VideoStreamer:
    def __init__(self):
        self.current_count = 0
        self.processing = False
        self.cap = None

        # Color threshold for contours (tuned for brown coconuts)
        self.lower_brown = (8, 50, 50)
        self.upper_brown = (30, 255, 255)
        self.min_contour_area = 2500

        # Tracker parameters
        self.tracked_objects = {}
        self.next_object_id = 0
        self.distance_threshold = 50 #make 120 for application
        self.max_disappeared = 5

        # Trigger line coordinates
        self.trigger_line_x = 428

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
            cv2.putText(roi, str(object_id), (cx - 10, cy - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        cv2.line(roi, (self.trigger_line_x, 0), (self.trigger_line_x, roi.shape[0]), (0, 0, 255), 2)
        cv2.putText(roi, f"Coconuts: {self.current_count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        return roi

    async def video_stream(self, websocket: WebSocket):
        self.cap = cv2.VideoCapture('../videos/vid4.mp4')
        self.reset()
        try:
            while self.cap.isOpened():
                ret, frame = self.cap.read()
                if not ret:
                    break

                processed_frame = self.process_frame(frame)
                _, buffer = cv2.imencode('.jpg', processed_frame)
                jpg_as_text = base64.b64encode(buffer).decode('utf-8')
                
                # Send both count and frame as JSON
                await websocket.send_json({
                    "count": self.current_count,
                    "frame": jpg_as_text
                })
                
                await asyncio.sleep(1/30)  # Control FPS (30 fps)
                
        except Exception as e:
            print(f"Error in video stream: {e}")
        finally:
            self.stop_streaming()

    def stop_streaming(self):
        self.processing = False
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()
        print("Video capture released and windows destroyed.")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
            elif data == "reset":
                video_streamer.reset() #reset the count
    except Exception as e:
        print(f"Connection closed: {e}")
    finally:
        video_streamer.stop_streaming()
    
    
    # video_streamer = VideoStreamer()
    # try:
    #     await video_streamer.video_stream(websocket)
    # except Exception as e:
    #     print(f"Connection closed: {e}")
    # finally:
    #     video_streamer.stop_streaming()

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)
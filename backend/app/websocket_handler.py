import asyncio
from fastapi import WebSocket, WebSocketDisconnect
import struct

from app.video_streamer import VideoStreamer
from app.gpio_controller import GPIOController  # GPIO controller class

async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    streamer = VideoStreamer(source="../videos/250_coconuts.mp4")
    gpio_controller = GPIOController()
    send_task = None
    try:
        while True:
            cmd = await websocket.receive_text()
            if cmd == "start":
                #launch a background task to pump frames
                if send_task is None or send_task.done():
                    send_task = asyncio.create_task(pump_frames(websocket, streamer))
                gpio_controller.start_conveyor() 
                await websocket.send_text("started")
            elif cmd =="stop":
                if send_task and not send_task.done():
                    send_task.cancel()
                gpio_controller.stop_conveyor()
                streamer.release()
                await websocket.send_text("stopped")
            elif cmd == "bucket_full":
                print("Bucket full: Stopping Conveyor")
                gpio_controller.stop_conveyor()
                await websocket.send_text("bucket_stopped")
            elif cmd == "reset":
                if send_task and not send_task.done():
                    send_task.cancel()
                gpio_controller.stop_conveyor()
                streamer.release()
                streamer.reset()
                await websocket.send_text("reset")
            else:
                print("Unknown command, ignoring:", cmd)
            
    except WebSocketDisconnect:
        print("Client disconnected")
    finally:
        if send_task and not send_task.done():
            send_task.cancel()
        streamer.release()
        try:
            gpio_controller.cleanup()
        except AttributeError:
            pass
        print("WebSocket connection closed, resources cleaned up.")

async def pump_frames(ws: WebSocket, vs: VideoStreamer):
    "Continuously read frames from the video source and send them to the WebSocket until canceled."
    try:
        while True:
            count, jpeg_bytes = vs.read_frame()
            if jpeg_bytes is None:
                break # no more frames to read
            # 4-byte network byte order count + JPEG bytes
            header = struct.pack('!I', count)
            await ws.send_bytes(header + jpeg_bytes)
            await asyncio.sleep(1/60)
    except asyncio.CancelledError:
        print("Frame pumping task cancelled")
    except Exception as e:
        print(f"Error in frame pumping: {e}")
        return
    
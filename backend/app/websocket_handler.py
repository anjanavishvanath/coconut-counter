# app/websocket_handler.py
import asyncio
from fastapi import WebSocket, WebSocketDisconnect
import struct
import json
import traceback

from app.video_streamer import VideoStreamer
from app.gpio_controller import GPIOController  # GPIO controller class

async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()

    # Per-connection offset (starts 0 until client sends set_offset)
    offset = 0

    streamer = VideoStreamer(source="../videos/250_coconuts.mp4")
    gpio_controller = GPIOController()
    send_task = None

    # pump_frames is an inner coroutine that captures `offset` by closure
    async def pump_frames():
        try:
            while True:
                count, jpeg_bytes = streamer.read_frame()
                if jpeg_bytes is None:
                    break  # end of file / no frame
                # add the per-connection offset
                total_to_send = (offset or 0) + (count or 0)
                header = struct.pack('!I', total_to_send)
                await websocket.send_bytes(header + jpeg_bytes)
                await asyncio.sleep(1/60)
        except asyncio.CancelledError:
            print("Frame pumping task cancelled")
        except Exception as e:
            print("Error in frame pumping:", e)
            traceback.print_exc()
            return

    try:
        while True:
            cmd = await websocket.receive_text()

            # try parse JSON (client sends {"type":"set_offset","offset":123})
            parsed = None
            try:
                parsed = json.loads(cmd)
            except Exception:
                parsed = None

            if parsed and isinstance(parsed, dict) and parsed.get("type") == "set_offset":
                # set per-connection offset
                try:
                    offset_val = int(parsed.get("offset", 0))
                    offset = offset_val
                    print(f"[WS] offset set to {offset} for client")
                    # optional acknowledgement
                    await websocket.send_text("offset_set")
                except ValueError:
                    await websocket.send_text("offset_invalid")
                # continue the loop to wait for the next command
                continue

            # plain string commands:
            if cmd == "start":
                if send_task is None or send_task.done():
                    send_task = asyncio.create_task(pump_frames())
                gpio_controller.start_conveyor()
                await websocket.send_text("started")

            elif cmd == "stop":
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
                # reset per-connection offset and streamer
                if send_task and not send_task.done():
                    send_task.cancel()
                gpio_controller.stop_conveyor()
                offset = 0
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

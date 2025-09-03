# app/websocket_handler.py
import asyncio
from fastapi import WebSocket, WebSocketDisconnect
import struct
import json
import traceback
import subprocess

from app.video_streamer import VideoStreamer
from app.gpio_controller import GPIOController  # GPIO controller class

async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()

    # Per-connection offset (starts 0 until client sends set_offset)
    offset = 0

    streamer = VideoStreamer(source=0) #"../videos/250_coconuts.mp4"
    gpio_controller = GPIOController()
    send_task = None

    #helper to perform the actual shutdown sequence (background)
    async def do_shutdown_sequence():
        # notify connected client (best effort)
        try:
            await websocket.send_text(json.dumps({"type":"info","message":"shutdown_in_progress"}))
        except Exception:
            pass

        # stop conveyor and other hardware
        try:
            gpio_controller.stop_conveyor()   
            await asyncio.sleep(0.3)  # wait a moment
            gpio_controller.cleanup()
        except Exception:
            print("Error cleaning GPIO:", e)

        # releas camera resources
        try:
            streamer.release()
            streamer.close()
        except Exception:
            pass

        # give the UI a moment to receive the message, then call system shutdown
        await asyncio.sleep(0.5)

        #use sudo to run poweroff
        try:
            subprocess.run(["sudo", "systemctl", "poweroff"], check=False)
        except Exception as e:
            print("Error during system shutdown:", e)

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
                await asyncio.sleep(1/20)
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
                # Try to open the camera before starting
                ok = streamer.open(retries=3, delay=0.25)
                if not ok:
                    # send a clear JSON error to the client and do NOT start the conveyor/pump
                    await websocket.send_text(json.dumps({"type": "error", "code": "camera_not_found", "message": "Could not open camera"}))
                    continue
                # camera OK -> spawn pump and start conveyor
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
                streamer.close()
                await websocket.send_text("reset")

            elif cmd == "shutdown":
                # launch the shutdown sequence as a background task so current handler can finish
                asyncio.create_task(do_shutdown_sequence())
                # respond immediately
                await websocket.send_text(json.dumps({"type":"info","message":"shutdown_queued"}))
                continue

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

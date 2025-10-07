# app/websocket_handler.py
import asyncio
import json
import struct
import traceback
import subprocess
from pathlib import Path

from fastapi import WebSocket, WebSocketDisconnect

from app.video_streamer import VideoStreamer
from app.gpio_controller import GPIOController  # your existing GPIO controller

# --- Bucket persistence/configuration ---
BUCKET_COUNT = 14
DEFAULT_SET_VALUE = 800
BUCKETS_FILE = Path(__file__).parent / "buckets.json"

# In-memory authoritative buckets (will be loaded from disk at import)
def _default_buckets():
    return [
        {"id": i + 1, "count": 0, "set_value": DEFAULT_SET_VALUE, "filled": False}
        for i in range(BUCKET_COUNT)
    ]

def load_buckets_from_disk():
    try:
        if BUCKETS_FILE.exists():
            raw = BUCKETS_FILE.read_text(encoding="utf-8")
            data = json.loads(raw)
            # basic validation: ensure list length matches BUCKET_COUNT
            if isinstance(data, list) and len(data) == BUCKET_COUNT:
                return data
    except Exception as e:
        print("Error loading buckets.json:", e)
    return _default_buckets()

def save_buckets_to_disk(buckets):
    try:
        BUCKETS_FILE.write_text(json.dumps(buckets, indent=2), encoding="utf-8")
    except Exception as e:
        print("Could not save buckets to disk:", e)

# load at module import
BUCKETS = load_buckets_from_disk()
BUCKETS_LOCK = asyncio.Lock()  # protect concurrent access if multiple clients connect


async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()

    # Per-connection variables
    offset = 0  # kept for legacy compatibility (frontend may send set_offset)
    selected_bucket = None  # bucket id (1..BUCKET_COUNT) or None
    streamer = VideoStreamer(source=0) # "../videos/250_coconuts.mp4"
    gpio_controller = GPIOController()
    send_task = None

    # Helper: send the authoritative buckets state to this client (text JSON)
    async def send_buckets_update():
        try:
            async with BUCKETS_LOCK:
                await websocket.send_text(json.dumps({"type": "buckets_update", "buckets": BUCKETS}))
        except Exception as e:
            # likely client disconnected
            print("send_buckets_update error:", e)

    # Helper: persist buckets and broadcast update to current websocket client
    async def persist_and_send_buckets():
        try:
            async with BUCKETS_LOCK:
                save_buckets_to_disk(BUCKETS)
                await websocket.send_text(json.dumps({"type": "buckets_update", "buckets": BUCKETS}))
        except Exception as e:
            print("persist_and_send_buckets error:", e)

    # shutdown sequence (unchanged behaviour)
    async def do_shutdown_sequence():
        try:
            await websocket.send_text(json.dumps({"type": "info", "message": "shutdown_in_progress"}))
        except Exception:
            pass
        try:
            gpio_controller.stop_conveyor()
            await asyncio.sleep(0.3)
            gpio_controller.cleanup()
        except Exception as e:
            print("Error cleaning GPIO:", e)
        try:
            streamer.release()
            streamer.close()
        except Exception:
            pass
        await asyncio.sleep(0.5)
        try:
            subprocess.run(["sudo", "systemctl", "poweroff"], check=False)
        except Exception as e:
            print("Error during system shutdown:", e)

    # pump_frames: reads frames and attributes delta counts to server BUCKETS
    async def pump_frames():
        prev_count = 0
        try:
            while True:
                count, jpeg_bytes = streamer.read_frame()
                if jpeg_bytes is None:
                    # end of file or no frame -> stop
                    break

                # compute delta (new counts since last frame)
                new_count = int(count or 0)
                delta = new_count - prev_count
                prev_count = new_count

                # Attribution change: always attribute deltas to selected bucket (if any),
                # even if that bucket was already marked "filled". We still mark "filled"
                # the first time count >= set_value and stop the conveyor then, but we
                # keep incrementing the bucket's count on subsequent frames so overfill
                # is captured until operator selects another bucket.
                if delta > 0 and selected_bucket is not None:
                    async with BUCKETS_LOCK:
                        idx = selected_bucket - 1
                        if 0 <= idx < len(BUCKETS):
                            b = BUCKETS[idx]
                            # remember whether this bucket was filled before adding new items
                            was_filled = bool(b.get("filled", False))
                            # always add the delta to the current bucket (capture overfill)
                            b["count"] = int(b.get("count", 0)) + int(delta)

                            # If this is the first time we cross or reach the set_value, mark filled
                            # and stop conveyor (but do NOT prevent further increments)
                            if (not was_filled) and b["count"] >= int(b.get("set_value", DEFAULT_SET_VALUE)):
                                b["filled"] = True
                                try:
                                    gpio_controller.stop_conveyor()
                                except Exception as e:
                                    print("Error stopping conveyor on bucket full:", e)
                                # notify client that conveyor stopped for this bucket
                                try:
                                    await websocket.send_text(json.dumps({"type": "bucket_stopped", "bucket": b["id"]}))
                                except Exception as e:
                                    print("Error sending bucket_stopped:", e)

                            # persist and push updated buckets (will show overfill counts to client)
                            try:
                                save_buckets_to_disk(BUCKETS)
                                await websocket.send_text(json.dumps({"type": "buckets_update", "buckets": BUCKETS}))
                            except Exception as e:
                                print("Error sending buckets_update after attributing delta:", e)

                # send binary frame: 4-byte BE unsigned total count + JPEG bytes
                header = struct.pack("!I", new_count + (offset or 0))
                try:
                    await websocket.send_bytes(header + jpeg_bytes)
                except Exception as e:
                    # sending failed (client disconnected) — stop pumping
                    print("Error sending frame to client, stopping pump:", e)
                    break

                # pace frames
                await asyncio.sleep(1 / 60)

        except asyncio.CancelledError:
            print("Frame pumping task cancelled")
        except Exception as e:
            print("Unhandled error in pump_frames:", e)
            traceback.print_exc()
        finally:
            print("pump_frames exiting")

    # Send initial authoritative buckets to client
    await send_buckets_update()

    try:
        while True:
            cmd = await websocket.receive_text()

            # try parse JSON message (we use JSON for control messages)
            parsed = None
            try:
                parsed = json.loads(cmd)
            except Exception:
                parsed = None

            # Legacy: set_offset messages still supported
            if parsed and isinstance(parsed, dict) and parsed.get("type") == "set_offset":
                try:
                    offset_val = int(parsed.get("offset", 0))
                    offset = offset_val
                    print(f"[WS] offset set to {offset} for client")
                    await websocket.send_text("offset_set")
                except Exception:
                    await websocket.send_text("offset_invalid")
                continue

            # Select bucket (client informs which bucket to attribute future counts to)
            if parsed and isinstance(parsed, dict) and parsed.get("type") == "select_bucket":
                try:
                    sb = parsed.get("bucket", None)
                    selected_bucket = int(sb) if sb is not None else None
                except Exception:
                    selected_bucket = None
                print(f"[WS] client selected bucket {selected_bucket}")
                # ack and send current buckets
                await websocket.send_text(json.dumps({"type": "selected_bucket", "bucket": selected_bucket}))
                await send_buckets_update()
                continue

            # Set a single bucket's set_value
            if parsed and isinstance(parsed, dict) and parsed.get("type") == "set_bucket_value":
                try:
                    bid = int(parsed.get("bucket"))
                    val = int(parsed.get("set_value"))
                    async with BUCKETS_LOCK:
                        if 1 <= bid <= len(BUCKETS):
                            BUCKETS[bid - 1]["set_value"] = int(val)
                            # if lowering threshold may unfill
                            if BUCKETS[bid - 1]["count"] < BUCKETS[bid - 1]["set_value"]:
                                BUCKETS[bid - 1]["filled"] = False
                            save_buckets_to_disk(BUCKETS)
                    await send_buckets_update()
                except Exception as e:
                    print("Error in set_bucket_value:", e)
                continue

            # Set all buckets set_value
            if parsed and isinstance(parsed, dict) and parsed.get("type") == "set_all":
                try:
                    val = int(parsed.get("set_value", DEFAULT_SET_VALUE))
                    async with BUCKETS_LOCK:
                        for b in BUCKETS:
                            b["set_value"] = int(val)
                            if b["count"] < b["set_value"]:
                                b["filled"] = False
                        save_buckets_to_disk(BUCKETS)
                    await send_buckets_update()
                except Exception as e:
                    print("Error in set_all:", e)
                continue

            # plain string commands for start/stop/reset/shutdown
            if cmd == "start":
                ok = streamer.open(retries=3, delay=0.25)
                if not ok:
                    await websocket.send_text(json.dumps({"type": "error", "code": "camera_not_found", "message": "Could not open camera"}))
                    continue
                if send_task is None or send_task.done():
                    send_task = asyncio.create_task(pump_frames())
                try:
                    gpio_controller.start_conveyor()
                except Exception as e:
                    print("Error starting conveyor:", e)
                await websocket.send_text("started")
                continue

            if cmd == "stop":
                if send_task and not send_task.done():
                    send_task.cancel()
                try:
                    gpio_controller.stop_conveyor()
                except Exception as e:
                    print("Error stopping conveyor:", e)
                streamer.release()
                await websocket.send_text("stopped")
                continue

            if cmd == "reset":
                if send_task and not send_task.done():
                    send_task.cancel()
                try:
                    gpio_controller.stop_conveyor()
                except Exception as e:
                    print("Error stopping conveyor during reset:", e)
                async with BUCKETS_LOCK:
                    for b in BUCKETS:
                        b["count"] = 0
                        b["filled"] = False
                    save_buckets_to_disk(BUCKETS)
                offset = 0
                try:
                    streamer.release()
                except Exception:
                    pass
                try:
                    streamer.reset()
                    streamer.close()
                except Exception:
                    pass
                await websocket.send_text("reset")
                await send_buckets_update()
                continue

            if cmd == "shutdown":
                asyncio.create_task(do_shutdown_sequence())
                await websocket.send_text(json.dumps({"type": "info", "message": "shutdown_queued"}))
                continue

            # unknown command
            print("Unknown command received, ignoring:", cmd)

    except WebSocketDisconnect:
        print("Client disconnected")
    finally:
        if send_task and not send_task.done():
            send_task.cancel()
        try:
            streamer.release()
        except Exception:
            pass
        try:
            gpio_controller.cleanup()
        except Exception:
            pass
        print("WebSocket connection closed, resources cleaned up.")

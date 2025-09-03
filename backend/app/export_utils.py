# app/export_utils.py
from pathlib import Path
from datetime import datetime
import shutil
import os
from fastapi import APIRouter, HTTPException

router = APIRouter()

def _find_writable_usb_mounts():
    """
    Return a list of candidate mount points that look like removable media
    and are writable by the current process.
    We look for mountpoints under /media, /run/media, /mnt whose device looks like /dev/sd*
    """
    mounts = []
    try:
        with open("/proc/mounts", "r", encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 2:
                    continue
                dev, mnt = parts[0], parts[1]
                # Quick heuristic: device name starts with /dev/sd (USB), or /dev/mmcblk (SD cards)
                if not (dev.startswith("/dev/sd") or dev.startswith("/dev/mmcblk") or dev.startswith("/dev/mapper/")):
                    continue
                # Only consider typical mount base paths
                if not (mnt.startswith("/media/") or mnt.startswith("/run/media/") or mnt.startswith("/mnt/")):
                    continue
                # must be writable by this process
                if os.access(mnt, os.W_OK):
                    mounts.append(mnt)
    except FileNotFoundError:
        # Not a linux-like system or /proc not available
        pass
    return mounts

def _get_reports_file() -> Path:
    """
    Return Path to your reports.csv (adjust if your file lives somewhere else).
    This assumes reports.csv lives two levels up from this file at backend/reports.csv.
    """
    # file layout: backend/app/export_utils.py -> backend/reports.csv
    return Path(__file__).resolve().parents[1] / "reports.csv"

@router.post("/export_report")
def export_report():
    report_file = _get_reports_file()
    if not report_file.exists():
        raise HTTPException(status_code=404, detail=f"Report file not found: {str(report_file)}")

    mounts = _find_writable_usb_mounts()
    if not mounts:
        raise HTTPException(status_code=404, detail="No writable USB mount found. Please insert and mount a USB drive.")

    # choose the first candidate. If you prefer, you can surface a list to the client.
    dest_mount = Path(mounts[0])

    # create destination filename with timestamp
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest_name = f"reports_{ts}.csv"
    dest_path = dest_mount / dest_name

    try:
        shutil.copy2(str(report_file), str(dest_path))
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"Permission denied copying to {dest_mount}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to copy file: {e}")

    return {"status": "ok", "dest": str(dest_path)}

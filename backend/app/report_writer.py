# Modules for report generation and file handling
import csv
from datetime import datetime
from pathlib import Path
from fastapi import HTTPException

def write_report(payload, report_file: Path):
    """
    Appends one timestamped row to reports.csv.
    :param payload: List of bucket reports with id, set_value, and count.
    :param report_file: Path to the report file.
    """
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
        # raise an HTTPException with a 500 status code and error message
        raise HTTPException(status_code=500, detail=f"Could not write report: {e}")
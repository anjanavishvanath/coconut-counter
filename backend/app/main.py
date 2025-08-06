
import uvicorn
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from app.websocket_handler import ws_endpoint
from app.email_utils import send_report_email  # Function to send email with report
from app.report_writer import write_report  # Function to write report to CSV
from app.email_utils import send_report_email # Function to send email with report
from app.models import ReportPayload  # Pydantic model for report payload


# ─── fastapi setup ─────────────────────────────────────────────────
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── HTTP functions ──────────────────────────────────────────────
@app.post("/save_report")
async def save_report(payload: ReportPayload, background_tasks: BackgroundTasks):
    """
    Accepts JSON { buckets: [ {id, set_value, count}, … ] }
    Appends one timestamped row to reports.csv.
    """
    report_file = Path(__file__).parent / "reports.csv"
    write_report(payload, report_file)
    background_tasks.add_task(send_report_email, report_file)
    return {
        "status": "ok",
        "saved_to": str(report_file),
        "email_queued": True
    }

# ─── WebSocket connection handler ────────────────────────────────
app.websocket("/ws")(ws_endpoint)

# ─── FastAPI application entry point ─────────────────────────────
if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)

// src/App.jsx
import { useState, useEffect, useRef } from "react";
import Bucket from "./components/Bucket";
import KeyboardComponent from "./components/KeyboardComponent";
import "./App.css";

const STORAGE_KEY = "coconut_State_v1"; // still used for saving frontend metadata (optional)
const SELECTED_BUCKET_KEY = "coconut_selected_bucket_v1";

function loadLocalState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (e) {
    console.error("Failed to load local state:", e);
    return null;
  }
}

function saveLocalState(payload) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  } catch (e) {
    console.error("Failed to save local state:", e);
  }
}

function loadSelectedBucket() {
  try {
    const raw = localStorage.getItem(SELECTED_BUCKET_KEY);
    if (!raw) return null;
    return parseInt(raw, 10);
  } catch (e) {
    return null;
  }
}

function saveSelectedBucket(b) {
  try {
    if (b === null || b === undefined) {
      localStorage.removeItem(SELECTED_BUCKET_KEY);
    } else {
      localStorage.setItem(SELECTED_BUCKET_KEY, String(b));
    }
  } catch (e) {
    console.warn("Failed to persist selected bucket:", e);
  }
}

export default function App() {
  // General States and Refs
  const ws = useRef(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const isStreamingRef = useRef(isStreaming);
  const [totalCoconutCount, setTotalCoconutCount] = useState(0);
  const [imgSrc, setImgSrc] = useState("");

  // Bucket related states (will be populated from server)
  const defaultBuckets = Array.from({ length: 14 }, (_, i) => ({ id: i + 1, count: 0, set_value: 800, filled: false }));
  const [buckets, setBuckets] = useState(defaultBuckets);

  // Keyboard related states
  const [isKeyboardVisible, setIsKeyboardVisible] = useState(false);
  const [selectedBucket, setSelectedBucket] = useState(() => loadSelectedBucket());
  const selectedBucketRef = useRef(selectedBucket);
  const [keyboardValue, setKeyboardValue] = useState(0);

  // export state
  const [isExporting, setIsExporting] = useState(false);

  const timeZone = "Asia/Colombo";
  const [now, setNow] = useState(() => new Date());

  // formatted pieces
  const dateStr = new Intl.DateTimeFormat("en-GB", {
    timeZone,
    weekday: "short",
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(now);

  const timeStr = new Intl.DateTimeFormat("en-GB", {
    timeZone,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(now);

  useEffect(() => { const t = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(t); }, []);

  // Keep refs in sync
  useEffect(() => { selectedBucketRef.current = selectedBucket; saveSelectedBucket(selectedBucket); }, [selectedBucket]);
  useEffect(() => { isStreamingRef.current = isStreaming; }, [isStreaming]);

  // revoke old image URL when imgSrc changes or on unmount
  useEffect(() => {
    return () => {
      if (imgSrc) {
        try { URL.revokeObjectURL(imgSrc); } catch (e) {}
      }
    };
  }, [imgSrc]);

  // WebSocket setup on mount — sends "start" automatically on open
  useEffect(() => {
    ws.current = new WebSocket("ws://localhost:8000/ws");
    ws.current.binaryType = "blob";

    ws.current.onopen = () => {
      console.log("WS connected");

      // If we had a selected bucket stored locally, notify server
      const stored = loadSelectedBucket();
      if (stored !== null && ws.current && ws.current.readyState === WebSocket.OPEN) {
        ws.current.send(JSON.stringify({ type: "select_bucket", bucket: stored }));
      }

      // Send initial offset and start command automatically when connection opens
      try {
        const initMsg = JSON.stringify({ type: "set_offset", offset: totalCoconutCount });
        ws.current.send(initMsg);
      } catch (e) {
        console.warn("Could not send offset to server on open:", e);
      }
      try {
        ws.current.send("start");
        setIsStreaming(true);
      } catch (e) {
        console.warn("Could not send start command on open:", e);
      }
    };

    ws.current.onclose = () => {
      console.log("WS closed", ws.current ? ws.current.readyState : "no-ws");
      setIsStreaming(false);
    };

    ws.current.onerror = (e) => {
      console.error("WS error", e);
      setIsStreaming(false);
    };

    ws.current.onmessage = (event) => {
      if (typeof event.data === "string") {
        let parsed = null;
        try {
          parsed = JSON.parse(event.data);
        } catch (e) {
          parsed = null;
        }

        if (parsed && parsed.type === "error") {
          console.error("Server error:", parsed);
          alert(`Error from server: ${parsed.message || parsed.code}`);
          setIsStreaming(false);
          return;
        }

        if (parsed && parsed.type === "buckets_update") {
          // authoritative state from server
          setBuckets(parsed.buckets);
          return;
        }

        if (parsed && parsed.type === "selected_bucket") {
          setSelectedBucket(parsed.bucket);
          return;
        }

        if (parsed && parsed.type === "bucket_stopped") {
          console.log("Server reports bucket stopped:", parsed.bucket);
          setIsStreaming(false);
          return;
        }

        // legacy textual responses
        if (event.data === "reset") {
          setTotalCoconutCount(0);
          setImgSrc("");
          setSelectedBucket(null);
          return;
        }

        // other plain text may be "started" / "stopped"
        return;
      }

      // binary frames: header + jpeg
      const reader = new FileReader();
      reader.onload = () => {
        const buffer = reader.result;
        const view = new DataView(buffer);
        const count = view.getUint32(0, false);
        const jpegBytes = buffer.slice(4);
        const blob = new Blob([jpegBytes], { type: "image/jpeg" });
        const url = URL.createObjectURL(blob);

        setTotalCoconutCount(count);
        setImgSrc((prev) => {
          try { if (prev) URL.revokeObjectURL(prev); } catch (e) {}
          return url;
        });

        // Do not modify buckets here — server is authoritative and will push buckets_update messages
      };
      reader.readAsArrayBuffer(event.data);
    };

    return () => {
      console.log("Unmounting: closing WS");
      try {
        if (ws.current && (ws.current.readyState === WebSocket.OPEN || ws.current.readyState === WebSocket.CONNECTING)) {
          ws.current.close();
        }
      } catch (e) {
        console.warn("Error closing websocket on unmount:", e);
      }
    };
  }, []); // <-- empty deps: run once at mount

  // Persist frontend metadata if you want
  useEffect(() => {
    saveLocalState({ ts: Date.now(), selectedBucket });
  }, [selectedBucket]);

  const handleSetAll = () => {
    setIsKeyboardVisible(!isKeyboardVisible);
    // set selected bucket to null to indicate "apply to all"
    setSelectedBucket(null);
  };

  const handleFinish = async () => {
    if (!ws.current || ws.current.readyState !== WebSocket.OPEN) {
      alert("WebSocket is not open. Cannot save report.");
      return;
    }

    // Use frontend buckets (authoritative because server sent them)
    try {
      const response = await fetch("http://localhost:8000/save_report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ buckets }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error("Server error saving report:", errorText);
        alert(`❌ Failed to save report: ${response.status} ${response.statusText}`);
        return;
      }

      const data = await response.json();
      console.log("Report saved:", data);
      alert(`✅ Report saved successfully to:\n${data.saved_to}`);
    } catch (e) {
      console.error("Error saving report:", e);
      alert(`❌ Error saving report: ${e.message}`);
    }
  };

  const handleReset = () => {
    if (!confirm("Reset all data?")) return;
    try { if (ws.current && ws.current.readyState === WebSocket.OPEN) ws.current.send("reset"); } catch(e){}
    setIsStreaming(false);
    setTotalCoconutCount(0);
    setImgSrc("");
    setBuckets(defaultBuckets);
    setIsKeyboardVisible(false);
    setSelectedBucket(null);
    setKeyboardValue(0);
  };

  const handleExportToUSB = async () => {
    if (!confirm("Copy reports.csv to USB drive now?")) return;
    setIsExporting(true);
    try {
      const resp = await fetch("http://localhost:8000/export_report", { method: "POST" });
      const data = await resp.json();
      if (!resp.ok) {
        console.error("Export failed:", data);
        alert(`Export failed: ${data.detail || "unknown error"}`);
      } else {
        alert(`Report copied to USB:\n${data.dest}`);
      }
    } catch (e) {
      console.error("Export error:", e);
      alert(`Export error: ${e.message}`);
    } finally {
      setIsExporting(false);
    }
  };

  const handleShutdown = () => {
    if (!confirm("Shutdown Raspberry Pi now? Make sure you saved everything.")) return;
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send("shutdown");
      alert("Shutdown requested. The device will power off shortly.");
      return;
    }
  };

  // ------- Keyboard functions (send commands to server) -------
  const handleKeyboardInput = (input) => {
    const v = parseInt(input) || 0;
    setKeyboardValue(v);
  };

  const handleKeyboardChange = () => {
    // if selectedBucket === null -> set all
    const payload = selectedBucket === null
      ? { type: "set_all", set_value: keyboardValue }
      : { type: "set_bucket_value", bucket: selectedBucket, set_value: keyboardValue };

    try {
      if (ws.current && ws.current.readyState === WebSocket.OPEN) {
        ws.current.send(JSON.stringify(payload));
      }
    } catch (e) {
      console.warn("Could not send set value:", e);
    }

    setKeyboardValue(0);
    setIsKeyboardVisible(false);
  };

  const handleKeyboardAdd = () => {
    // compute new value client-side as convenience, but server is authoritative and will respond with buckets_update
    let currentVal = 0;
    if (selectedBucket !== null) {
      const b = buckets.find((x) => x.id === selectedBucket);
      currentVal = b ? b.set_value : 0;
    }
    const newVal = currentVal + keyboardValue;
    const payload = selectedBucket === null
      ? { type: "set_all", set_value: newVal }
      : { type: "set_bucket_value", bucket: selectedBucket, set_value: newVal };

    try {
      if (ws.current && ws.current.readyState === WebSocket.OPEN) {
        ws.current.send(JSON.stringify(payload));
      }
    } catch (e) {
      console.warn("Could not send add value:", e);
    }

    setKeyboardValue(0);
    setIsKeyboardVisible(false);
  };

  // Called when user clicks a bucket in UI
  const onBucketClicked = (id) => {
    // toggle keyboard for same bucket, else set selected and open keyboard
    if (selectedBucket === id) {
      setIsKeyboardVisible((prev) => !prev);
    } else {
      setSelectedBucket(id);
      // notify server
      try {
        if (ws.current && ws.current.readyState === WebSocket.OPEN) {
          ws.current.send(JSON.stringify({ type: "select_bucket", bucket: id }));
        }
      } catch (e) {
        console.warn("send select_bucket failed", e);
      }
      setIsKeyboardVisible(true);
    }
  };

  //-------------------------------------------//
  return (
    <>
      <header>
        <h1>Coconut Counter</h1>
        <nav>
          <button className="setBtn" onClick={handleSetAll}>Set All</button>
          <button className="finishButton" onClick={handleFinish}>Finish</button>
          <button className="resetBtn" onClick={handleReset}>Reset</button>
        </nav>
      </header>
      <div className="main_container">
        <div className="video_container">
          {isKeyboardVisible && (
            <KeyboardComponent
              handleInput={handleKeyboardInput}
              handleClose={() => setIsKeyboardVisible(false)}
              value={keyboardValue}
              handleChange={handleKeyboardChange}
              handleAdd={handleKeyboardAdd}
            />
          )}
          <h2>Total Coconuts: {totalCoconutCount}</h2>
          <h2>Active Bucket: {selectedBucket ?? "—"}</h2>
          <div className="vidandtime">
            {imgSrc && <img className="video_frame" src={imgSrc} alt="Stream" />}
            <div className="clock">
              <div className="clock-date">{dateStr}</div>
              <div className="clock-time">{timeStr}</div>
              <button
                className="exportBtn"
                onClick={handleExportToUSB}
                disabled={isExporting}
                title="Copy reports.csv to first detected USB drive"
              >
                {isExporting ? "Copying…" : "Copy CSV to USB"}
              </button>
              <button className="shutdownBtn" onClick={handleShutdown}>Shutdown</button>
            </div>
          </div>
        </div>
        <div className="buckets_container">
          {buckets.map((bucket) => (
            <Bucket
              key={bucket.id}
              id={bucket.id}
              count={bucket.count}
              set_value={bucket.set_value}
              isFilled={bucket.count >= bucket.set_value || !!bucket.filled}
              isSelected={bucket.id === selectedBucket}
              handleClick={() => onBucketClicked(bucket.id)}
            />
          ))}
        </div>
      </div>
    </>
  );
}

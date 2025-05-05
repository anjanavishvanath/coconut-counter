import { useState, useEffect, useRef } from "react";
import Bucket from "./components/Bucket";
import KeyboardComponent from "./components/KeyboardComponent";
import "./App.css";

export default function App() {
  const [totalCoconutCount, setTotalCoconutCount] = useState(0);
  const [imgSrc, setImgSrc] = useState("");
  const ws = useRef(null);
  const [isStreaming, setIsStreaming] = useState(false);

  // Buckets
  const [buckets, setBuckets] = useState(
    Array.from({ length: 14 }, (_, i) => ({ id: i + 1, count: 0, set_value: 2 }))
  );
  const [activeBucket, setActiveBucket] = useState(1);
  const [filledBucketsCount, setFilledBucketsCount] = useState(0);
  const activeBucketRef = useRef(activeBucket);
  const filledBucketsCountRef = useRef(filledBucketsCount);

  // Refill mode
  const [refillingMode, setRefillingMode] = useState(false);
  const refillingModeRef = useRef(refillingMode);

  // Keyboard
  const [isKeyboardVisible, setIsKeyboardVisible] = useState(false);
  const [selectedBucket, setSelectedBucket] = useState(null);
  const selectedBucketRef = useRef(selectedBucket);
  const [keyboardValue, setKeyboardValue] = useState(0);

  // Keep refs in sync
  useEffect(() => { activeBucketRef.current = activeBucket; }, [activeBucket]);
  useEffect(() => { filledBucketsCountRef.current = filledBucketsCount; }, [filledBucketsCount]);
  useEffect(() => { refillingModeRef.current = refillingMode; }, [refillingMode]);
  useEffect(() => { selectedBucketRef.current = selectedBucket; }, [selectedBucket]);

  useEffect(() => {
    ws.current = new WebSocket("ws://localhost:8000/ws");
    ws.current.binaryType = "blob";

    ws.current.onopen = () => {
      console.log("WS connected");
    };

    ws.current.onmessage = (event) => {
      // Distinguish control messages (strings) from video frames (Blob)
      if (typeof event.data === "string") {
        switch (event.data) {
          case "started":
            setIsStreaming(true);
            break;
          // case "stopped":
          //   setIsStreaming(false);
          //   break;
        }
        return;
      }

      // Read the incoming Blob as an ArrayBuffer
      const reader = new FileReader();
      reader.onload = () => {
        const buffer = reader.result;
        const view = new DataView(buffer);

        // first 4 bytes = big-endian unsigned count
        const count = view.getUint32(0, false);
        // the rest = JPEG data
        const jpegBytes = buffer.slice(4);
        const blob = new Blob([jpegBytes], { type: "image/jpeg" });
        const url = URL.createObjectURL(blob);

        setTotalCoconutCount(count);
        setImgSrc(url);

        // bucket logic
        const active = activeBucketRef.current;
        const filledCount = filledBucketsCountRef.current;
        const isRefill = refillingModeRef.current;
        const sel = selectedBucketRef.current;

        setBuckets((prev) => {
          let newActive = active;
          const updated = prev.map((b) => {
            if (b.id === active) {
              const newCount = Math.max(0, count - filledCount);
              // initial fill mode: move to next bucket
              if (!isRefill && newCount >= b.set_value) {
                newActive = Math.min(prev.length, b.id + 1);
              }
              // stop conveyor when full
              if (newCount >= b.set_value) {
                console.log("Bucket full, stopping conveyor");
                ws.current.send("bucket_full");
              }
              // refill mode: jump to selected bucket
              if (isRefill && sel != null) {
                newActive = sel;
              }
              // when last bucket full => enter refill mode
              if (b.id === prev.length && newCount >= b.set_value) {
                setRefillingMode(true);
              }
              return { ...b, count: newCount };
            }
            return b;
          });

          if (newActive !== active) {
            setActiveBucket(newActive);
            // recalc filledBucketsCount
            const newFilled = !isRefill
              ? updated
                .filter((x) => x.id < newActive)
                .reduce((s, x) => s + x.count, 0)
              : updated.reduce((s, x) => s + x.count, 0) - updated[newActive - 1].count;
            setFilledBucketsCount(newFilled);
          }

          return updated;
        });
      };
      reader.readAsArrayBuffer(event.data);
    };

    return () => {
      if (ws.current?.readyState === WebSocket.OPEN) {
        ws.current.send("stop");
        ws.current.close();
      }
      ws.current = null;
    };
  }, []);

  // watch for when the user uses the UI to toggle streaming
  useEffect(() => {
    if (!ws.current || ws.current.readyState !== WebSocket.OPEN) return;

    if (isStreaming) {
      ws.current.send("start");
    } else {
      ws.current.send("stop");
    }
  }, [isStreaming]);

  const handleStartStop = () => {
    if (!isStreaming) filledBucketsCountRef.current = 0;
    setIsStreaming(!isStreaming);
    setRefillingMode(false);
  };

  const handleReset = () => {
    if (!confirm("Reset all data?")) return;
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send("stop");
      ws.current.send("reset");
      ws.current.close();
    }
    setIsStreaming(false);
    setTotalCoconutCount(0);
    setImgSrc("");
    setBuckets(Array.from({ length: 14 }, (_, i) => ({ id: i + 1, count: 0, set_value: 2 })));
    setActiveBucket(1);
    setFilledBucketsCount(0);
    setRefillingMode(false);
    setIsKeyboardVisible(false);
    setSelectedBucket(null);
    activeBucketRef.current = 1;
    filledBucketsCountRef.current = 0;
    refillingModeRef.current = false;
    selectedBucketRef.current = null;
  };

  const handleKeyboardInput = (input) => {
    const v = parseInt(input) || 0;
    setKeyboardValue(v);
  };
  const handleKeyboardChange = () => {
    setBuckets((prev) =>
      prev.map((b) =>
        selectedBucket === null || b.id === selectedBucket
          ? { ...b, set_value: keyboardValue }
          : b
      )
    );
    setKeyboardValue(0);
    setIsKeyboardVisible(false);
  };
  const handleKeyboardAdd = () => {
    if (selectedBucket !== null) {
      setBuckets((prev) =>
        prev.map((b) =>
          b.id === selectedBucket
            ? { ...b, set_value: b.set_value + keyboardValue }
            : b
        )
      );
    }
    setKeyboardValue(0);
    setIsKeyboardVisible(false);
  };

  const handleFinish = async () => {
    try {
      await fetch("http://localhost:8000/save_report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ buckets }),
      });
    } catch (e) {
      console.error("Error saving report:", e);
    }
  };

  return (
    <>
      <header>
        <h1>Coconut Counter</h1>
        <nav>
          <button className="startBtn" onClick={handleStartStop}>
            {isStreaming ? "Stop" : "Start"}
          </button>
          <button className="setBtn"
            onClick={() => {
              setIsKeyboardVisible(!isKeyboardVisible);
              setSelectedBucket(null);
            }}
          >
            Set All
          </button>
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
          <h2>Active Bucket: {activeBucket}</h2>
          {imgSrc && <img className="video_frame" src={imgSrc} alt="Stream" />}
        </div>
        <div className="buckets_container">
          {buckets.map((bucket) => (
            <Bucket
              key={bucket.id}
              id={bucket.id}
              count={bucket.count}
              set_value={bucket.set_value}
              isFilled={bucket.count >= bucket.set_value}
              isActive={bucket.id === activeBucket}
              isSelected={bucket.id === selectedBucket}
              handleClick={() => {
                if (selectedBucket === bucket.id) {
                  setSelectedBucket(null);
                  setIsKeyboardVisible(false);
                } else {
                  setSelectedBucket(bucket.id);
                  setIsKeyboardVisible(true);
                }
              }}
            />
          ))}
        </div>
      </div>
    </>
  );
}

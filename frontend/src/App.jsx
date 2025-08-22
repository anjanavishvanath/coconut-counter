import { useState, useEffect, useRef } from "react";
import Bucket from "./components/Bucket";
import KeyboardComponent from "./components/KeyboardComponent";
import "./App.css";

const STORAGE_KEY = "coconut_State_v1";

function loadLocalState(){
  try{
    const raw = localStorage.getItem(STORAGE_KEY);
    if(!raw) return null;
    return JSON.parse(raw);
  }catch (e){
    console.error("Failed to load local state:", e);
    return null;
  }
}

function saveLocalState(buckets, total){
  try{
    const payload = { buckets,total, ts: Date.now()};
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  }catch (e){
    console.error("Failed to save local state:", e);
  }
}

function cleanLocalState(){
  try{
    localStorage.removeItem(STORAGE_KEY);
  }catch (e) {
    console.error("Failed to clean local state:", e);
  }
}

export default function App() {
  // General States and Refs
  const ws = useRef(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const isStreamingRef = useRef(isStreaming);
  const [totalCoconutCount, setTotalCoconutCount] = useState(0);
  const [imgSrc, setImgSrc] = useState("");

  // Bucket related states
  const bktsA = Array.from({ length: 14 }, (_, i) => ({ id: i + 1, count: 0, set_value: 800 }));
  const [buckets, setBuckets] = useState(bktsA);
  const [filledBucketsCount, setFilledBucketsCount] = useState(0);
  const filledBucketsCountRef = useRef(filledBucketsCount);
  const bucketFullSendRef = useRef(false);

  // Keyboard related states
  const [isKeyboardVisible, setIsKeyboardVisible] = useState(false);
  const [selectedBucket, setSelectedBucket] = useState(1);
  const selectedBucketRef = useRef(selectedBucket);
  const [keyboardValue, setKeyboardValue] = useState(0);

  // Keep refs in sync
  useEffect(() => { filledBucketsCountRef.current = filledBucketsCount; }, [filledBucketsCount]);
  useEffect(() => { selectedBucketRef.current = selectedBucket; }, [selectedBucket]);
  useEffect(() => { isStreamingRef.current = isStreaming }, [isStreaming]);
  useEffect(() => {
    return () => {
      if (imgSrc) URL.revokeObjectURL(imgSrc);
    };
  }, [imgSrc]); //revoke old object URLs to free memory

  //----------Resetting Coconut count for new bucket selection----------//
  useEffect(() => {
    const prevCount = buckets.find(b => b.id === selectedBucket)?.count ?? 0;
    const baseline = totalCoconutCount - prevCount;
    setFilledBucketsCount(baseline);
    filledBucketsCountRef.current = baseline;
    bucketFullSendRef.current = false;
  }, [selectedBucket]);

  //----------on mount: restore local state (if any)----------//
  useEffect(() => {
    const saved = loadLocalState();
    if (saved) {
      setBuckets(saved.buckets);
      setTotalCoconutCount(saved.total);

      // restoring selected bucket and filled bucket baseline
      const prevCount = saved.buckets.find(b => b.id === selectedBucket)?.count ?? 0;
      const baseline = saved.total - prevCount;
      setFilledBucketsCount(baseline);
      filledBucketsCountRef.current = baseline;
    }
  }, []);

  // persist whenever the buckets or total change
  useEffect(() => {
    saveLocalState(buckets, totalCoconutCount);
  }, [buckets, totalCoconutCount]);


  //Establish web socket at page load
  useEffect(() => {
    ws.current = new WebSocket("ws://localhost:8000/ws");
    ws.current.binaryType = "blob";

    ws.current.onopen = () => console.log("WS connected");
    ws.current.onclose = () => console.log("WS closed", ws.current.readyState);
    ws.current.onerror = (e) => console.error("WS error", e);

    ws.current.onmessage = (event) => {
      if (typeof event.data === "string") {
        console.log("Control message:", event.data);
        if (event.data === "reset") {
          // clear any lingering UI
          setTotalCoconutCount(0);
          setImgSrc("");
          setSelectedBucket(1);
          setFilledBucketsCount(0);
        }
      } else if (isStreamingRef.current) {
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

          const currentBucket = selectedBucketRef.current;
          const filledCount = filledBucketsCountRef.current;

          setBuckets((prevBuckets) => {
            const updatedBuckets = prevBuckets.map((bucket) => {
              if (bucket.id === currentBucket) {
                const newCount = Math.max(0, count - filledCount);

                // stop the conveyor when the bucket is full
                if (newCount >= bucket.set_value && !bucketFullSendRef.current) {
                  // console.log(`Bucket ${bucket.id} is full, stopping conveyor.`);
                  ws.current.send("bucket_full");
                  bucketFullSendRef.current = true;
                }

                return { ...bucket, count: newCount };
              }
              return bucket;
            });
            return updatedBuckets;
          });
        };
        reader.readAsArrayBuffer(event.data);
      }
    };


    //end of useEffect
    return () => {
      console.log("Unmounting: closing WS");
      ws.current.close();
    };
  }, []);

  console.log("bucketRefillSent: ", bucketFullSendRef.current)

  //-------Button Functions ------------------------------------//
  const handleStartStop = () => {
    // console.log("WS readyState:", ws.current?.readyState); // 0=CONNECTING, 1=OPEN, 2=CLOSING, 3=CLOSED

    if (!ws.current || ws.current.readyState !== WebSocket.OPEN) {
      alert("Waiting for server connection...");
      return;
    }

    if (selectedBucketRef.current === null) {
      alert("Please select a bucket first.");
      return;
    }

    // if (!isStreaming) {
    //   ws.current.send("start");
    //   setIsStreaming(true);
    // } else {
    //   ws.current.send("stop");
    //   setIsStreaming(false);
    // }

    // send the initial offset as JSON, then the "start" command
    if (!isStreaming) {
      try {
        const initMsg = JSON.stringify({ type: "set_offset", offset: totalCoconutCount });
        ws.current.send(initMsg);
      }catch (e){
        console.warn("Could not send offset to server:", e);
      }
      ws.current.send("start");
      setIsStreaming(true);
    }else {
      ws.current.send("stop");
      setIsStreaming(false);
    }
  }

  const handleSetAll = () => {
    setIsKeyboardVisible(!isKeyboardVisible);
    setSelectedBucket(null);
  }

  const handleFinish = async () => {
    if (!ws.current || ws.current.readyState !== WebSocket.OPEN) {
      alert("WebSocket is not open. Cannot save report.");
      return;
    }

    cleanLocalState();

    try {
      const response = await fetch("http://localhost:8000/save_report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ buckets }),
      });

      if (!response.ok) {
        // Server returned a non-2xx status
        const errorText = await response.text();
        console.error("Server error saving report:", errorText);
        alert(`❌ Failed to save report: ${response.status} ${response.statusText}`);
        return;
      }

      // Parse the JSON if you want the saved path back
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
    cleanLocalState();
    ws.current.send("reset");

    setIsStreaming(false);
    setTotalCoconutCount(0);
    setImgSrc("");

    setBuckets(bktsA);

    setFilledBucketsCount(0);

    setIsKeyboardVisible(false);
    setSelectedBucket(null);
    setKeyboardValue(0);

    filledBucketsCountRef.current = 0;
    selectedBucketRef.current = null;
  }

  //-------Keyboard Functions ------------------------------------//
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
    setBuckets((prev) =>
      prev.map((b) =>
        selectedBucket === null || b.id === selectedBucket
          ? { ...b, set_value: b.set_value + keyboardValue }
          : b
      )
    );
    setKeyboardValue(0);
    setIsKeyboardVisible(false);
  };


  //-------------------------------------------//
  return (
    <>
      <header>
        <h1>Coconut Counter</h1>
        <nav>
          <button className="startBtn" onClick={handleStartStop}>{isStreaming ? "Stop" : "Start"}</button>
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
          <h2>Active Bucket: {selectedBucket}</h2>
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
              isSelected={bucket.id === selectedBucket}
              handleClick={() => {
                if (selectedBucket === bucket.id) {
                  setIsKeyboardVisible(prev => !prev);
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
  )
}
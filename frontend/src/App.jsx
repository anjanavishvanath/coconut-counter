import { useState, useEffect, useRef } from "react";
import Bucket from "./components/Bucket";
import KeyboardComponent from "./components/KeyboardComponent";
import './App.css'

export default function App() {
  // Initializing states for total coconut count, image source, WebSocket connection, and streaming status
  const [totalCoconutCount, setTotalCoconutCount] = useState(0);
  const [imgSrc, setImgSrc] = useState("");
  const ws = useRef(null);
  const [isStreaming, setIsStreaming] = useState(false);

  //initializing bucket related states
  const [buckets, setBuckets] = useState(Array.from({ length: 14 }, (_, i) => ({ id: i + 1, count: 0, set_value: 2 })));
  const [activeBucket, setActiveBucket] = useState(buckets[0].id);
  const [filledBucketsCount, setFilledBucketsCount] = useState(0);
  const activeBucketRef = useRef(activeBucket);
  const filledBucketsCountRef = useRef(filledBucketsCount);

  //initializing keyboard related states
  const [isKeyboardVisible, setIsKeyboardVisible] = useState(false);
  const [selectedBucket, setSelectedBucket] = useState(null);
  const selectedBucketRef = useRef(selectedBucket);

  //states for refilling
  const [refillingMode, setRefillingMode] = useState(false);
  const refillingModeRef = useRef(refillingMode);
  const [keyboardValue, setKeyboardValue] = useState(0);

  // keep the ref in sync with state
  useEffect(() => {
    selectedBucketRef.current = selectedBucket;
  }, [selectedBucket]);

  useEffect(() => {
    refillingModeRef.current = refillingMode;
  }, [refillingMode]);

  // keep these refs in sync with their states
  useEffect(() => {
    activeBucketRef.current       = activeBucket;
    filledBucketsCountRef.current = filledBucketsCount;
  }, [activeBucket, filledBucketsCount]);

  useEffect(() => {
    if (!isStreaming) return;

    //update refs
    activeBucketRef.current = activeBucket;
    filledBucketsCountRef.current = filledBucketsCount;

    // Create a WebSocket connection
    ws.current = new WebSocket("ws://localhost:8000/ws");

    //send start message to server once the connection is open
    ws.current.onopen = () => {
      console.log("WebSocket connection opened");
      ws.current.send('start');
    }

    // Handle incoming messages
    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setTotalCoconutCount(data.count);
      setImgSrc(`data:image/jpeg;base64,${data.frame}`); // Assuming the server sends a base64 encoded image

      const active = activeBucketRef.current;
      const filledCount = filledBucketsCountRef.current;
      const isRefill = refillingModeRef.current;
      const sel = selectedBucketRef.current;

      setBuckets(prevBuckets => {
        let newActiveBucket = active;
        const updatedBuckets = prevBuckets.map(bucket => {
          if (bucket.id === active) {
            let newCount = 0;
            if (data.count) {
              newCount = data.count - filledCount; // Calculate the new count for the active bucket
            } 
            //check if the newCount reached the set value of active bucket
            if (!refillingMode && newCount >= bucket.set_value) {
              newActiveBucket = newActiveBucket < prevBuckets.length ? bucket.id + 1 : newActiveBucket; // Move to the next bucket
            }

            //stop the conveyor when a bucket is full
            if(newCount >= bucket.set_value){
              console.log("Bucket is full, stopping conveyor...");
              ws.current.send("bucket_full");
            }

            prevBuckets.forEach(b => {
              if (b.id === newActiveBucket && isRefill && sel != null) {
                newActiveBucket = sel;
              }
            });

            if (bucket.id === buckets.length && newCount >= bucket.set_value) {
              setRefillingMode(true);
            }
            console.log("incoming data", data.count, "newCount", newCount);
            return { ...bucket, count: newCount }; //update the active bucket
          }
          return bucket; //return the rest of the buckets unchanged
        });

        // update active bucket
        if (newActiveBucket !== active) {
          setActiveBucket(newActiveBucket);
          activeBucketRef.current = newActiveBucket;

          setFilledBucketsCount(() => {
            if(!isRefill){
              // if in intial loading, count the coconuts in filled buckets
              const newFilled = updatedBuckets
                .filter(bucket => bucket.id < newActiveBucket)
                .reduce((sum, bucket) => sum + bucket.count, 0);
              filledBucketsCountRef.current = newFilled;
              return newFilled;
            }else{
              // if in refilling mode, count the coconuts in all the buckets before moving to this bucket
              const newFilled = updatedBuckets.reduce((sum, bucket) => sum+bucket.count, 0) -  (updatedBuckets[newActiveBucket - 1].count);
              return newFilled;
            }
          });
        }

        return updatedBuckets;
      })
    }

    return () => {
      if (ws.current && ws.current.readyState === WebSocket.OPEN) {
        ws.current.send("stop");
        ws.current.close();
      }
      ws.current = null; // Close the WebSocket connection when the component unmounts
    }
  }, [isStreaming])

  //start stop function
  const handleStartStop = () => {
    isStreaming ? filledBucketsCountRef.current = 0 : null; //reset the filled buckets count when starting the stream
    setIsStreaming(!isStreaming);
    setRefillingMode(false);
  }

  //reset function
  const handleReset = () => {
    if (!window.confirm("Are you sure you want to reset all data?")) {
      return;
    }

    // 1) Stop streaming & tell server to reset its counter
    if (isStreaming && ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send("stop");
      ws.current.send("reset");
      ws.current.close();
    }
    setIsStreaming(false);

    // 2) Reset all React state
    setTotalCoconutCount(0);
    setImgSrc("");
    setBuckets(Array.from(
      { length: 14 },
      (_, i) => ({ id: i + 1, count: 0, set_value: 2 })
    ));
    setActiveBucket(1);
    setFilledBucketsCount(0);
    setRefillingMode(false);
    setIsKeyboardVisible(false);
    setSelectedBucket(null);

    // 3) Reset refs to match
    activeBucketRef.current = 1;
    filledBucketsCountRef.current = 0;
    refillingModeRef.current = false;
    selectedBucketRef.current = null;
  };


  //keyboard function
  const closeKeyboard = () => {
    setIsKeyboardVisible(false);
  }

  const handleKeyboardInput = (input) => {
    const newValue = parseInt(input) ? parseInt(input) : 0;
    setKeyboardValue(newValue);
  }

  const handleKeyboardChange = () => {
    if (selectedBucket !== null) { //if a bucket is selected
      setBuckets(prevBuckets => prevBuckets.map(bucket => {
        if (bucket.id === selectedBucket) {
          return { ...bucket, set_value: keyboardValue }
        }
        return bucket;
      }))
    } else { //if no bucket is selected, update set_value for all buckets
      setBuckets(prevBuckets => prevBuckets.map(bucket => {
        return { ...bucket, set_value: keyboardValue }
      }))
    }
    setKeyboardValue(0);
    setIsKeyboardVisible(false);
  }

  const handleKeyboardAdd = () => {
    if(selectedBucket !== null) {
      setBuckets(prevBuckets => prevBuckets.map(bucket => {
        if (bucket.id === selectedBucket){
          return { ...bucket, set_value: bucket.set_value + keyboardValue }
        }
        return bucket;
      }))
    }
    setKeyboardValue(0);
    setIsKeyboardVisible(false);
  }

  //creating set of buckets
  const bucketElements = buckets.map(bucket => (
    <Bucket
      key={bucket.id}
      id={bucket.id}
      count={bucket.count}
      set_value={bucket.set_value}
      isFilled={bucket.count >= bucket.set_value}
      isActive={bucket.id === activeBucket}
      isSelected={bucket.id === selectedBucket}
      handleClick={() => {
        if(selectedBucket === bucket.id ){
          setSelectedBucket(null);
          setIsKeyboardVisible(false);
        }else{
          setSelectedBucket(bucket.id);
          setIsKeyboardVisible(true);
        }
      }}
    />
  ));

  //Finish button functionality
  const handleFinish = async () => {
    try {
      const payload = { buckets };
      const res = await fetch ("http://localhost:8000/save_report", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      })
    }catch (err) {
      console.error("Error saving report:", err);
    }
  };

  // console.log("refillingtMode", refillingMode, "| Selected Bucket", selectedBucket, "| Active Bucket", activeBucket);
  // console.log("filled buckets count", filledBucketsCountRef.current);

  return (
    <>
      <header>
        <h1>Coconut Counter</h1>
        <nav>
          <button className="startBtn" onClick={handleStartStop} >{isStreaming ? "Stop" : "Start"}</button>
          <button className="setBtn" onClick={() => {
            setIsKeyboardVisible(!isKeyboardVisible)
            setSelectedBucket(null);
          }}>Set All</button>
          <button className="finishButton" onClick={handleFinish}>Finish</button>
          <button className="resetBtn" onClick={handleReset}>Reset</button>
        </nav>
      </header>
      <div className="main_container">
        <div className="video_container">
          {isKeyboardVisible &&
            <KeyboardComponent
              handleInput={handleKeyboardInput}
              handleClose={() => closeKeyboard()}
              value={keyboardValue}
              handleChange={handleKeyboardChange}
              handleAdd={handleKeyboardAdd}
            />}
          <h2>Total Coconuts: {totalCoconutCount}</h2>
          <h2>Active Bucket: {activeBucket}</h2>
          {imgSrc && <img className="video_frame" src={imgSrc} alt="Conveyor Video Stream" />}
        </div>
        <div className="buckets_container">
          {bucketElements}
        </div>
      </div>
    </>
  )

}
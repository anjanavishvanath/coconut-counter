import React, { useState, useEffect } from 'react';
import Bucket from './components/Bucket';

function App() {
  const [count, setCount] = useState(0);
  const [streamStarted, setStreamStarted] = useState(false);
  const [buckets, setBuckets] = useState([
    {
      id: 1,
      count: 0,
      set_value: 500
    },
    {
      id: 2,
      count: 0,
      set_value: 500
    },
    {
      id: 3,
      count: 0,
      set_value: 500
    },
  ])

  const bucketElements = buckets.map(bucket => {
    return (
      <Bucket 
      key={bucket.id} 
      >
        <div>Bucket No: {bucket.id}</div>
        <div>Set Value: {bucket.set_value}</div>
        <div>Count: {bucket.count}</div>
      </Bucket>
    )
  })

  const toggleCounting = async () => {
    // If currently running, stop the stream by calling the stop endpoint
    if (streamStarted) {
      try {
        await fetch("http://localhost:5000/stop_stream", {
          method: "POST",
        });
      } catch (error) {
        console.error("Error stopping stream:", error);
      }
      setStreamStarted(false);
    } else {
      setStreamStarted(true);
    }
  };

  // Poll the backend for the current count every second only when the stream is active
  useEffect(() => {
    let interval = null;
    if (streamStarted) {
      interval = setInterval(async () => {
        try {
          const response = await fetch("http://localhost:5000/current_count");
          const data = await response.json();
          setCount(data.count);
        } catch (error) {
          console.error("Error fetching count:", error);
        }
      }, 1000);
    } else {
      setCount(0);
    }
    return () => clearInterval(interval);
  }, [streamStarted]);

  return (
    <div className='App'>
      <h1 className='poppins-extrabold'>Coconut Counter</h1>
      <button onClick={toggleCounting} className='.poppins-regular button'>
        {streamStarted ? "Stop Counting" : "Start Counting"}
      </button>
      {streamStarted && (
        <div className='video-feed-container'>
          <div className='video-feed-overlay'>
            <img 
              id="video-feed" 
              src="http://localhost:5000/video_feed" 
              alt="Video Stream" 
              style={{ width: '600px', height: '400px', border: '1px solid #ccc' }} 
              />
          </div>
          <div>
            <h2>Total Coconuts: {count}</h2>
          </div>
        </div>
      )}
      <div className='bucket-container'>
        {bucketElements}
      </div>
    </div>
  );
}

export default App;

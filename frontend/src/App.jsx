import React, { useState, useEffect } from 'react';
import Bucket from './components/Bucket';

export default function App() {

    const [streamStarted, setStreamStarted] = useState(false);
    const [totalCount, setTotalCount] = useState(0);
    const [activeBucket, setActiveBucket] = useState(0);
    const [filledBucketsCount, setFilledBucketsCount] = useState(0);
    const [buckets, setBuckets] = useState(Array.from({ length: 14 }, (_, i) => (
        { id: i + 1, count: 0, set_value: 5 })))

    //start and stop the stream. Attached to the button
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

    const resetCount = async () => {
        try {
            await fetch("http://localhost:5000/reset_count", { method: "POST" });
            setTotalCount(0);
            setFilledBucketsCount(0);
            setActiveBucket(0);
            setBuckets(prevBuckets => prevBuckets.map(bucket => ({ ...bucket, count: 0 })));
        } catch (error) {
            console.error("Error resetting count:", error);
        }
    };

    // Convert the state to Bucket components
    const bucketElements = buckets.map(bucket => {
        return (
            <Bucket key={bucket.id} isFilled={bucket.count >= bucket.set_value ? "filled": ""} isActive={bucket.id === activeBucket+1 ? "active" : ""}>
                <div>
                    <div>Bucket No: {bucket.id}</div>
                    <span>{bucket.count}</span>
                    <span>/<input
                    value={bucket.set_value !== undefined ? bucket.set_value : "0"}
                    type='number'
                    inputMode="numeric"
                    name="set_value"
                    onChange={(e) => handlePresetValueChange(e, bucket.id)} 
                    disabled={bucket.count >= bucket.set_value}/></span>
                </div>
            </Bucket>
        )
    })

    //handle input change for the set value of the bucket
    function handlePresetValueChange(event, id) {
        const { value } = event.target
        const numericValue = value === "" ? 0 : parseInt(value, 10)
        setBuckets(prevBuckets => prevBuckets.map(bucket =>
            bucket.id === id ? { ...bucket, set_value: numericValue } : bucket
        ))
    }

    // Poll the backend for the current count every second only when the stream is active
    useEffect(() => {
        if (streamStarted) {
            const countInterval = setInterval(async () => {
                try {
                    const response = await fetch("http://localhost:5000/current_count")
                    const data = await response.json();
                    const currentTotal = data.count
                    setTotalCount(currentTotal) //update the total count

                    //set the count of the active bucket
                    setBuckets(prevBuckets => {
                        let newActiveBucket = activeBucket
                        //creating the new bucket array with the updated count
                        const updated = prevBuckets.map((bucket, index) => {
                            //only modify the active bucket
                            if (index === activeBucket) {
                                let newCount = currentTotal - filledBucketsCount //calculate the count of the active bucket
                                //check if the newCount reached the set value of the bucket
                                if (newCount >= bucket.set_value) {
                                    newActiveBucket = activeBucket < prevBuckets.length - 1 ? activeBucket + 1 : 0 //switch to the next bucket or the first bucket
                                }
                                return { ...bucket, count: newCount } //update the count of the active bucket
                            }
                            return bucket //return the bucket as it is
                        })

                        //check if all buckets are filled: completion condition
                        const allFilled = updated.every(bucket => bucket.count >= bucket.set_value)
                        if (allFilled) {
                            setStreamStarted(false) //all buckets are filled. Stop the stream
                        } else if (newActiveBucket !== activeBucket) {
                            setActiveBucket(newActiveBucket) //update the active bucket
                            console.log("Switching to bucket", newActiveBucket + 1)
                            //stop the conveyor belt and update the filled buckets count
                            fetch("http://localhost:5000/stop_conveyor", {
                                method: "POST",
                            }).catch(error => console.error("Error stopping conveyor:", error))

                            setFilledBucketsCount(prevVal => {
                                let currentTotal = 0
                                for (let i = 0; i < newActiveBucket; i++) {
                                    currentTotal += prevBuckets[i].set_value
                                }
                                return currentTotal //All the coconuts counted so far in filled buckets
                            })
                        }
                        return updated //return the updated bucket array to buckets state
                    })

                } catch (error) {
                    console.error("Error fetching count:", error);
                }
            }, 1000)
            return () => clearInterval(countInterval)
        }
    }, [streamStarted, activeBucket])

    // console.log(activeBucket, JSON.stringify(buckets))

    return (
        <div className="App">
            <header>
                <h1 className='poppins-extrabold'>Coconut Counter</h1>
                <nav>
                    <button onClick={toggleCounting} className='poppins-regular button'>
                        {streamStarted ? "Stop Counting" : "Start Counting"}
                    </button>
                    <button onClick={resetCount} className='poppins-regular button reset'>Reset Count</button>  
                </nav>
            </header>
            <div className='main-container'>
                {streamStarted && (
                    <div className='video-feed-container'>
                        <div className='video-feed-overlay'>
                            <img
                                id="video-feed"
                                src="http://localhost:5000/video_feed"
                                alt="Video Stream"
                                style={{ width: '320px', height: '240px', border: '1px solid #ccc' }}
                            />
                        </div>
                        <div className='poppins-regular'>
                            <h2>Total Coconuts: {totalCount}</h2>
                            <h3>Active Bucket: {buckets[activeBucket + 1] && buckets[activeBucket].id}</h3>
                        </div>

                    </div>
                )}
                <div className='bucket-container'>
                    {bucketElements}
                </div>
            </div>
        </div>
    )
}
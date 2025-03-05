# 🍈 Coconut Counter

A computer vision-based project that counts coconuts moving on a conveyor using OpenCV.

## 📌 Features
✅ Detects coconuts in a specific region of interest (ROI)  
✅ Counts coconuts crossing a trigger line  
✅ Uses color thresholding and contour detection  
✅ React Front end to start and stop processing
✅ Display a live video stream from the backend.
✅ Fetch and display the real-time count of detected coconuts.

## 📂 Project Structure
```
root/
├── backend/                # Flask application for processing
│   ├── app.py             # Main backend server
│   ├── video_processing.py # Video processing logic
│   ├── static/            # Static assets (if needed)
│   └── templates/         # HTML templates (if needed)
│
├── frontend/              # React application for UI
│   ├── src/
│   │   ├── components/
│   │   │   ├── Bucket.jsx # Bucket component
│   │   ├── App.jsx       # Main React component
│   │   ├── index.js      # Entry point
│   ├── .gitignore        # React-specific ignored files
│   └── package.json      # React dependencies
│
├── .gitignore             # Global ignored files (integrated from frontend and backend)
├── README.md              # Project documentation
└── requirements.txt       # Backend dependencies
```

## 🛠 Installation
### Backend Setup (Flask)
1. Navigate to the backend folder:
   ```sh
   cd backend
   ```
2. Create a virtual environment (optional but recommended):
   ```sh
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```
4. Run the backend server:
   ```sh
   python main.py
   ```
### Frontend Setup (React)
1. Navigate to the frontend folder:
   ```sh
   cd frontend
   ```
2. Install dependencies:
   ```sh
   npm install
   ```
3. Start the React development server:
   ```sh
   npm start
   ```
## 🌟 Future Improvements
- Organize detected coconut counts into buckets based on predefined thresholds.
- Allow users to change the thresholds for buckets
- Add database storage for historical coconut counts.

## 💂️ Usage
Modify the `vid_path` variable inside `backend/coconut_counter.py` to use your own video.

## 👤 Author
**Anjana Vishvanath**  
[GitHub](https://github.com/anjanavishvanath)

## License
This project is licensed under the MIT License.
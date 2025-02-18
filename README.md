# 🍈 Coconut Counter

A computer vision-based project that counts coconuts moving on a conveyor using OpenCV.

## 📌 Features
✅ Detects coconuts in a specific region of interest (ROI)  
✅ Counts coconuts crossing a trigger line  
✅ Uses color thresholding and contour detection  

## 📸 Demo
![Coconut Counter Demo](docs/demo.gif)

## 🛠 Installation

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/yourusername/coconut-counter.git
cd coconut-counter
```

### 2️⃣ Install Dependencies
Ensure you have Python installed, then run:
```bash
pip install -r requirements.txt
```

### 3️⃣ Run the Script
```bash
python coconut_counter.py
```

## 💂️ Usage
Modify the `vid_path` variable inside `coconut_counter.py` to use your own video.

```python
vid_path = "videos/my_video.mp4"
```

## 👤 Author
**Anjana Vishvanath**  
[GitHub](https://github.com/yourusername) | [LinkedIn](https://linkedin.com/in/yourprofile)

## 🌟 Future Improvements
- [ ] Implement tracking to avoid double counting  
- [ ] Improve robustness against lighting changes  

## 📂 Project Structure
```
coconut-counter/
│── videos/              # Sample videos
│── docs/                # Documentation, images, and GIFs
│── coconut_counter.py   # Main script
│── requirements.txt     # Required dependencies
│── README.md            # Project documentation
```

---

### 🏆 Contributions
Feel free to open an issue or submit a pull request for improvements!


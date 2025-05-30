import sys
import cv2
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import QTimer

class CoconutCounterApp(QWidget):
    def __init__(self):
        super().__init__()

        # Window properties
        self.setWindowTitle("Coconut Counter")
        self.setGeometry(100, 100, 800, 600)

        # Video display
        self.video_label = QLabel(self)
        self.video_label.setFixedSize(640, 480)

        # Coconut count label
        self.count_label = QLabel("Coconuts Counted: 0", self)

        # Start button
        self.start_button = QPushButton("Start Processing", self)
        self.start_button.clicked.connect(self.start_processing)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.video_label)
        layout.addWidget(self.count_label)
        layout.addWidget(self.start_button)
        self.setLayout(layout)

        # OpenCV Video Capture
        self.cap = None
        self.coconut_count = 0

        # Timer for video processing
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)

    def start_processing(self):
        """Start processing the video when the button is clicked."""
        if not self.cap:
            self.cap = cv2.VideoCapture("videos/vid4.mp4")  # Change path if needed
            if not self.cap.isOpened():
                self.count_label.setText("Error: Could not open video.")
                return
            self.timer.start(30)  # Update every 30ms

    def update_frame(self):
        """Process and display frames from OpenCV in PyQt6."""
        ret, frame = self.cap.read()
        if not ret:
            self.timer.stop()
            self.cap.release()
            self.cap = None
            return

        # Process the frame (same as your coconut detection logic)
        x1, y1, x2, y2 = 0, 205, 478, 709
        trigger_line_y = (y2 - y1) - 100

        roi = frame[y1:y2, x1:x2]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        lower_brown = (8, 50, 50)
        upper_brown = (30, 255, 255)

        mask = cv2.inRange(hsv, lower_brown, upper_brown)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        filtered_contours = [c for c in contours if cv2.contourArea(c) > 2500]

        current_centroids = []
        for contour in filtered_contours:
            M = cv2.moments(contour)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                current_centroids.append((cx, cy))

                x, y, w, h = cv2.boundingRect(contour)
                cv2.rectangle(roi, (x, y), (x+w, y+h), (255, 0, 0), 2)

        for (cx, cy) in current_centroids:
            if cx >= trigger_line_y:
                self.coconut_count += 1
        
        # Draw trigger line
        cv2.line(frame, (trigger_line_y-100, 0), (trigger_line_y-100, frame.shape[0]), (0, 0, 255), 2)

        # Display updated coconut count
        self.count_label.setText(f"Coconuts Counted: {self.coconut_count}")

        # Convert frame to QImage and display in QLabel
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        q_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        self.video_label.setPixmap(QPixmap.fromImage(q_img))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CoconutCounterApp()
    window.show()
    sys.exit(app.exec())

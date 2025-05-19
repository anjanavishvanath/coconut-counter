import sys
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QPushButton

app = QApplication(sys.argv) # Create the application object for the event loop 
window = QWidget() # Create a main window
window.setWindowTitle('PyQt6 App')
window.resize(300, 200)

def button_clicked():
    label.setText('Button clicked!')

#create a layout and add widgets
layout = QVBoxLayout()
label = QLabel('Hello, World!')
button = QPushButton('Click me!')
button.clicked.connect(button_clicked)
layout.addWidget(label)
layout.addWidget(button)

#set the layout for the window
window.setLayout(layout)

#show the window
window.show()
sys.exit(app.exec())
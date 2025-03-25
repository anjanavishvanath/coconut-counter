from flask import Flask, Response, jsonify
from flask_cors import CORS
from coconut_counter import run_coconut_counter_stream, processing
# import RPi.GPIO as GPIO
import threading


app = Flask(__name__)
CORS(app)

# GPIO configuration
STOP_CONVEYOR_PIN = 17
RESUME_CONVEYOR_PIN = 27

# GPIO.setmode(GPIO.BOARD)
# GPIO.setup(STOP_CONVEYOR_PIN, GPIO.OUT)
# GPIO.setup(RESUME_CONVEYOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

@app.route('/video_feed')
def video_feed():
    return Response(run_coconut_counter_stream(), 
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/stop_stream', methods=['POST'])
def stop_stream():
    # Set the global processing flag to False to stop the stream
    global processing
    processing = False
    return jsonify({"message": "Stream stopped."})

@app.route('/current_count', methods=['GET'])
def get_current_count():
    from coconut_counter import current_count
    return jsonify({"count": current_count})

@app.route('/stop_conveyor', methods=['POST'])
def stop_conveyor():
    print("Conveyor stopped.")
    # GPIO.output(STOP_CONVEYOR_PIN, GPIO.HIGH) #send stop signal
    return jsonify({"message": "Conveyor stopped."})

@app.route('/resume_conveyor', methods=['POST'])
def resume_conveyor():
    # GPIO.output(STOP_CONVEYOR_PIN, GPIO.LOW) #send resume signal
    return jsonify({"message": "Conveyor resumed."})

#Automatically resume when an external signal is received
def monitor_resume_signal():
    while True:
        # if GPIO.input(RESUME_CONVEYOR_PIN) == GPIO.LOW: #assume low signal means resume
        #     GPIO.output(STOP_CONVEYOR_PIN, GPIO.LOW) #resume conveyor
        print("Conveyor resumed.")
        break

#Run the monitor_resume_signal function in a separate thread
threading.Thread(target=monitor_resume_signal, daemon=True).start()

if __name__ == "__main__":
    app.run(debug=True, port=5000)

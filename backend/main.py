from flask import Flask, Response, jsonify
from flask_cors import CORS
from coconut_counter import run_coconut_counter_stream, processing

app = Flask(__name__)
CORS(app)

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

if __name__ == "__main__":
    app.run(debug=True, port=5000)

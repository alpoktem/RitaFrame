from flask import Flask, render_template, session, jsonify
from photosapi import GooglePhotosApi
from motionio import MotionDetector
import threading, os
import config
import logging
from logging.handlers import RotatingFileHandler

# Default to debug mode if no environment variable is set
DEBUG_MODE = os.getenv('DEBUG_MODE', 'True') == 'True'

# Create log directory
os.makedirs('logs', exist_ok=True)

# Create a logger object
logger = logging.getLogger()
logger.setLevel(logging.INFO)  # Set the logging level

# Create formatter
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', '%Y-%m-%d %H:%M:%S')

# Create a file handler for writing logs to a file
file_handler = RotatingFileHandler('logs/app.log', maxBytes=1024*1024*5, backupCount=5)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Create a stream handler for writing logs to console on debug mode
if DEBUG_MODE:
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'supersecretkey')

ALBUM_NAME = config.ALBUM_NAME
FRAME_LONG_EDGE = config.FRAME_LONG_EDGE
FRAME_SHORT_EDGE = config.FRAME_SHORT_EDGE
SLEEP_ON_SECS = config.SLEEP_ON_SECS
CLIENT_SECRET_PATH = config.CLIENT_SECRET_PATH
RUN_MOTION_DETECTION = config.RUN_MOTION_DETECTION
PIR_PIN = config.PIR_PIN
TRANSITION_TIME_MS = config.TRANSITION_TIME_MS
DISPLAY_DURATION_MS = config.DISPLAY_DURATION_MS

# initialize photos api and create service
google_photos_api = GooglePhotosApi(client_secret_file=CLIENT_SECRET_PATH)


def get_next_image_url():
    try:
        session['display_photo_no'] = session.get('display_photo_no', 0)
        items_list_dict = google_photos_api.get_album_dict(ALBUM_NAME)

        if not items_list_dict or not items_list_dict["items"]:
            raise Exception("No items found in the album.")

        if session['display_photo_no'] >= len(items_list_dict["items"]):
            session['display_photo_no'] = 0

        
        item = items_list_dict["items"][session['display_photo_no']]
        photo_url = item["baseUrl"]

        is_horizontal = int(item["width"]) > int(item["height"])
        resolution = f"=w{FRAME_LONG_EDGE}-h{FRAME_SHORT_EDGE}" if is_horizontal else f"=h{FRAME_LONG_EDGE}-w{FRAME_SHORT_EDGE}"
        complete_url = photo_url + resolution

        logging.info(f"DISPLAY: {session['display_photo_no']} {item['filename']} {item['width']}x{item['height']} {'horizontal' if is_horizontal else 'vertical'}")

        session['display_photo_no'] += 1
        session.modified = True  # Ensure session is marked as modified
        return complete_url
    except Exception as e:
        # Log the error and provide a fallback or error message
        logging.error(f"Failed to fetch the next image URL: {e}")
        # Optionally, return None or a default image URL
        return None

@app.route('/')
def index():
    photo_url = get_next_image_url()
    return render_template('index.html', 
                           photo=photo_url if photo_url else "",
                           transition_time_ms=TRANSITION_TIME_MS,
                           display_duration_ms=DISPLAY_DURATION_MS)

@app.route('/next-image')
def next_image():
    image_url = get_next_image_url()
    if image_url:
        return jsonify(imageUrl=image_url)
    else:
        return jsonify(error="No images available"), 404

if __name__ == '__main__':


    if RUN_MOTION_DETECTION:
        pir_pin = config.PIR_PIN  # Make sure this is defined in your config
        sleep_on_secs = config.SLEEP_ON_SECS  # Also defined in your config
        motion_detector = MotionDetector(pir_pin, sleep_on_secs)

        # Start the motion detection thread
        motion_thread = threading.Thread(target=motion_detector.detect_motion)
        motion_thread.daemon = True  # Set the thread as daemon to automatically exit on program exit
        motion_thread.start()
        logging.info("Motion detection thread started.")
        logging.info("Sleep in secs: %i"%SLEEP_ON_SECS)

    app.run(port=8000, debug=DEBUG_MODE)



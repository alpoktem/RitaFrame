from flask import Flask, render_template
from photosapi import GooglePhotosApi, get_album_dict
import RPi.GPIO as GPIO
import threading, time, subprocess, os
import uvicorn

app = Flask(__name__)
# socketio = SocketIO(app)

#initialize gpio connection
GPIO.setmode(GPIO.BCM)
pir_pin = 17 #TODO: get this from a config file
GPIO.setup(pir_pin, GPIO.IN)

# initialize photos api and create service
google_photos_api = GooglePhotosApi()
creds = google_photos_api.run_local_server()

#TODO: get these from a config file
ALBUM_NAME = "RitaFrame"
FRAME_LONG_EDGE = "800"
FRAME_SHORT_EDGE = "480"

show_photo_no = 0 

def motion_detection_thread():
    while True:
        motion_detected = GPIO.input(pir_pin)
        if motion_detected:
            print("Motion detected!", end=' ')
            try:
                env = os.environ.copy()
                env['DISPLAY'] = ":0"
                subprocess.run(["xset", "dpms", "force", "on"], env=env, check=True)
                print("Screen waking up...")
            except subprocess.CalledProcessError as e:
                print("Error waking up screen:", e)
        # else:
        #     print("No motion")
        time.sleep(1)  # Adjust the sleep duration as needed

@app.route('/')
def index():
    global show_photo_no
    # Fetch photos from Google Photos album
    items_list_dict = get_album_dict(ALBUM_NAME, creds)

    if show_photo_no >= len(items_list_dict["filename"]):
        show_photo_no = 0

    if items_list_dict["filename"]:
        photo_url = items_list_dict["baseUrl"][show_photo_no]

        is_horizontal = int(items_list_dict["width"][show_photo_no]) > int(items_list_dict["height"][show_photo_no])
        print("SHOW:", show_photo_no, items_list_dict["filename"][show_photo_no],
              items_list_dict["width"][show_photo_no], 'x', items_list_dict["height"][show_photo_no],
              "horizontal" if is_horizontal else "vertical")

        resolution = f"=w{FRAME_LONG_EDGE}-h{FRAME_SHORT_EDGE}" if is_horizontal else f"=h{FRAME_LONG_EDGE}-w{FRAME_SHORT_EDGE}"

        complete_url = photo_url + resolution

        show_photo_no += 1
    else:
        complete_url = None

    # Render the HTML template and pass the photo URL to it
    return render_template('index.html', photo=complete_url)

if __name__ == '__main__':
    # app.run(port=8000, debug=True)
    # socketio.run(app, port=8000, debug=True)

    motion_status = "No motion"  # Initialize motion status
    # Start the motion detection thread
    motion_thread = threading.Thread(target=motion_detection_thread)
    motion_thread.daemon = True  # Set the thread as daemon to automatically exit on program exit
    motion_thread.start()

    # app.run(port=8000, debug=True)
    uvicorn.run(app, host='0.0.0.0', port=8000)



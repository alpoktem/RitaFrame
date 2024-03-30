# Configuration settings for the photo frame app

#Photos API
ALBUM_NAME = "RitaFrame" #Google photos album name
CLIENT_SECRET_PATH = './credentials/client_secret.json' #Path of Google cloud Api credentials

#Screen size
FRAME_LONG_EDGE = "800"
FRAME_SHORT_EDGE = "480"

#Motion detection
RUN_MOTION_DETECTION = True
PIR_PIN = 17
SLEEP_ON_SECS = 500 #Seconds counted to sleep the screen in case of inactivity 

#Photo display settings
TRANSITION_TIME_MS = 1000  # Transition time between photos in milliseconds
DISPLAY_DURATION_MS = 10000  # Time each photo is displayed in milliseconds
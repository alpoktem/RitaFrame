from flask import Flask, render_template
from photosapi import GooglePhotosApi, get_album_df
import pandas as pd

app = Flask(__name__)

# initialize photos api and create service
google_photos_api = GooglePhotosApi()
creds = google_photos_api.run_local_server()

#TODO: get these from a config file
ALBUM_NAME = "RitaFrame"
FRAME_LONG_EDGE = "800"
FRAME_SHORT_EDGE = "480"

show_photo_no = 0 

@app.route('/')
def index():
    global show_photo_no
    # Fetch photos from Google Photos album
    items_list_df = get_album_df(ALBUM_NAME, creds)

    if show_photo_no >= items_list_df.shape[0]:
        show_photo_no = 0

    if not items_list_df.shape[0] == 0:
        photo = items_list_df.iloc[show_photo_no]
        photo_url = photo['baseUrl']

        is_horizontal = int(photo['width']) > int(photo['height'])
        print("SHOW:", show_photo_no, photo['filename'], photo['width'], 'x', photo['height'], "horizontal" if is_horizontal else "vertical")

        resolution = f"=w{FRAME_LONG_EDGE}-h{FRAME_SHORT_EDGE}" if is_horizontal else f"=h{FRAME_LONG_EDGE}-w{FRAME_SHORT_EDGE}"

        complete_url = photo_url + resolution 

        # density = "-p-k-nu"
        # if not photo['mimeType'] == 'image/gif':
        #     complete_url += density

        show_photo_no += 1
    else:
        complete_url = None
    
    # Render the HTML template and pass the photos to it
    # print("URL:", complete_url)
    return render_template('index.html', photo=complete_url)

if __name__ == '__main__':
    app.run(port=8000, debug=True)





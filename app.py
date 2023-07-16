from flask import Flask, render_template
from photosapi import GooglePhotosApi, get_album_dict

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
    app.run(port=8000, debug=True)





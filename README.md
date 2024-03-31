
# RitaFrame - Cloud-based Photo Frame for Raspberry Pi

This project turns a Raspberry Pi into a dynamic digital photo frame, capable of displaying images live from a Google Photos album on the browser with a Flask-based app. Optionally, it utilizes motion detection to conserve energy, turning the display off when no activity is detected and on when someone is nearby. 

### Why RitaFrame?

I created this during my paternity leave so that my parents who live abroad can see the latest photos of their granddaughter on a frame in the living room. I especially wanted to be the one managing the photos, uploading new ones and removing the old ones. To avoid burning the LCD running all day, I attached a motion sensor and a timer module which controls the screen so that the moment my parents walk in the room, the frame gets activated. 

## Hardware Setup

- Raspberry Pi (any model with network connectivity)
- MicroSD card (8 GB or more recommended) with Raspberry Pi OS
- Power supply for the Raspberry Pi
- HDMI-compatible display monitor
- PIR motion sensor
- Jumper wires (for connecting the PIR sensor to the Raspberry Pi)

### PIR motion sensor setup

PIR sensors come with three pins: GND, OUT and VIN. Use the jumper wires to connect GND to a ground pin (e.g. 2), VIN to a power pin (e.g. 6) and OUT to a GPIO pin (e.g. 11, which is GPIO 17). For further information on GPIO pins [check here](https://randomnerdtutorials.com/raspberry-pi-pinout-gpios/).

## Software Setup

1. **Prepare Raspberry Pi OS**: Flash Raspberry Pi OS onto your microSD card using the [Raspberry Pi Imager](https://www.raspberrypi.org/software/) and boot up your Raspberry Pi.

2. **Clone the Repository**:
    ```bash
    git clone https://github.com/alpoktem/RitaFrame.git
    cd RitaFrame
    ```

3. **Install Required Packages**:

    Raspberry Pi OS should come with Python3 installed. If not:
    ```bash
    sudo apt-get update
    sudo apt-get install -y python3-pip
    ```

    To install required Python libraries:
    ```bash
    pip3 install -r requirements.txt
    ```
4. **Get a Google Photos client secret file**:
    The photos are pulled from the cloud using Google's [Photos Library API](https://developers.google.com/photos/library/reference/rest). To enable the app accessing your photos, you need to download a credentials file from Google Cloud console. There's a good tutorial to do that [here](https://github.com/polzerdo55862/google-photos-api/blob/main/Google_API.ipynb). 

5. **Configure Application**:

    Edit the `config.py` file to set up the path to your Google Photos API credentials, album name, and other configurations like display and transition times. You can also enable and disable the motion detection here. 

6. **Run the Application**:
        For development with debugging:
    ```bash
    python3 app.py
    ```
     For production:
     ```bash
     ./run.sh
   ```
    
    You might need to give run access to run.sh by: 
    ```bash
    chmod +x run.sh
    ```
    
7. **View the app on browser**:

    Open your browser and direct it to [localhost:8000](http://localhost:8000) to start viewing the photos on loop. 

## Autostart Setup

To have your Raspberry Pi photo frame application start automatically on boot, copy the file `etc/autostart` to `.config/lxsession/LXDE-pi`:

```bash
sudo cp etc/autostart_chromium /home/pi/.config/lxsession/LXDE-pi/autostart
   ```

Now, when Raspberry Pi boots up, it will open up Chromium browser on kiosk-mode showing the Flask web app.

## Raspberry Pi Zero setup

If you want to run RitaFrame on a lower-spec RaspberryPi like Zero, instead of Chromium you can use Midori. To install Midori:

```bash
sudo apt-get update
sudo apt-get install midori
```

Now, to make your system boot up with Midori directed at the app page, use the Midori autostart script in `etc`:

```bash
sudo cp etc/autostart_midori /home/pi/.config/lxsession/LXDE-pi/autostart
   ```

## References
I got inspired and built on top of the work below:

- [samuelclay/Raspberry-Pi-Photo-Frame](https://github.com/samuelclay/Raspberry-Pi-Photo-Frame)
- [polzerdo55862/google-photos-api](https://github.com/polzerdo55862/google-photos-api)
- [Google Photos Library API](https://developers.google.com/photos/library/reference/rest)

## If you like this project

<a href="https://www.buymeacoffee.com/alpoktem" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="41" width="174"></a>

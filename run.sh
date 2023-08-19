#!/bin/bash
cd /home/pi/Documents/RitaFrame
sleep 10

# Start unclutter to hide the cursor
unclutter -idle 0.1 -root &

#Set screen sleep time (seconds)
export DISPLAY=:0; xset s on s 120

# TODO: Somehow the sensor thread doesn't work with gunicorn
# gunicorn app:app --access-logfile access.log --error-logfile error.log

python app.py >> run.log
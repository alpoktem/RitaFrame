#!/bin/bash
cd /home/pi/Documents/RitaFrame
sleep 10

# Start unclutter to hide the cursor
unclutter -idle 0.1 -root &

# gunicorn app:app --access-logfile access.log --error-logfile error.log
python app.py >> run.log
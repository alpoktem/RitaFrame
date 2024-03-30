#!/bin/bash
cd /home/pi/Documents/RitaFrame

# Disable screen blanking
xset s off
xset -dpms
xset s noblank

# Set the environment to production
export DEBUG_MODE=False

# Run the app
python -u app.py


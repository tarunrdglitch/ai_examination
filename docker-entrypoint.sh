#!/bin/sh
# object_detect.py imports pyautogui, which needs an X display even on a headless server.
Xvfb :99 -screen 0 1024x768x16 >/dev/null 2>&1 &
sleep 1
# Few workers + many threads: the app keeps ML models in memory per worker.
exec gunicorn app:app --bind 0.0.0.0:5000 --workers "${WEB_WORKERS:-2}" --threads "${WEB_THREADS:-16}" --timeout 120

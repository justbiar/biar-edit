#!/bin/bash
# biar-edit: double-click to start the editor and open it in the browser.
cd "$(dirname "$0")"
export PATH="/opt/homebrew/opt/ffmpeg-full/bin:$PATH"
PORT=8790
if ! lsof -i :$PORT >/dev/null 2>&1; then
  .venv/bin/python -I biaredit/server.py $PORT &
  sleep 1
fi
open "http://localhost:$PORT"
wait

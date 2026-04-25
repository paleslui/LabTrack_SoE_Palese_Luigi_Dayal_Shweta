#!/bin/zsh
# LabTrack HTTPS launcher
# Starts Flask + Cloudflare tunnel together
# Usage: ./start_https.sh

echo "Starting LabTrack with HTTPS..."
echo ""

# Kill anything on port 5001 first
lsof -ti:5001 | xargs kill -9 2>/dev/null

# Start Flask in background
python3 run.py &
FLASK_PID=$!

# Wait for Flask to be ready
sleep 2

echo "Flask running (PID $FLASK_PID)"
echo "Starting HTTPS tunnel..."
echo "Your public HTTPS URL will appear on the line that says 'trycloudflare.com'"
echo "Share that URL — it works from anywhere in the world with a real certificate."
echo ""

# Start tunnel (blocking — Ctrl+C to stop everything)
cloudflared tunnel --url http://localhost:5001

# Cleanup when tunnel exits
echo ""
echo "Tunnel closed. Stopping Flask..."
kill $FLASK_PID 2>/dev/null
echo "Done."

"""
run.py — LabTrack application entry point.

Starts the Flask development server on port 5001, accessible on all
network interfaces (0.0.0.0) so other devices on the same network
can connect.

Usage:
    python3 run.py          # HTTP — http://localhost:5001
    ./start_https.sh        # HTTPS via Cloudflare Tunnel

For production deployment, use a WSGI server (e.g. gunicorn) instead.
"""
from app.app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)

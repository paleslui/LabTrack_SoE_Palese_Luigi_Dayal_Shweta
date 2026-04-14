"""
run.py — project-root entry point
Run from the LabTrack root folder with:  python3 run.py
"""
from app.app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

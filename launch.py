import threading
import webbrowser
import time
import sys
import os

if getattr(sys, 'frozen', False):
    app_dir = sys._MEIPASS
else:
    app_dir = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, app_dir)
os.chdir(app_dir)

import insight_engine

# ── Banner ─────────────────────────────────────────────────────
print("=" * 54)
print("  MechAI — Assembly Line Efficiency Analyzer")
print("  Lean Manufacturing · ML Predictions · AI Chat")
print("=" * 54)

# ── Model bootstrap ────────────────────────────────────────────
def _pull_model():
    if insight_engine.model_exists():
        print("\nLoading MechAI Intelligence model...")
        insight_engine.load_model()
    else:
        print("\nFirst-run setup: MechAI Intelligence model")
        print("    Model : SmolLM2-360M-Instruct (HuggingFace)")
        print("    Size  : ~720 MB")
        print("    Source: https://huggingface.co/HuggingFaceTB/SmolLM2-360M-Instruct")
        print("    Note: Internet required for this one-time download.")
        print("    After download the app runs fully offline.\n")
        insight_engine.download_model()

model_thread = threading.Thread(target=_pull_model, daemon=True)
model_thread.start()

# ── Open browser ───────────────────────────────────────────────
from app import app

def open_browser():
    time.sleep(1.5)
    webbrowser.open('http://localhost:5000')

if __name__ == '__main__':
    print("\n  Starting local server...")
    print("  Browser: http://localhost:5000")
    print("=" * 54 + "\n")
    t = threading.Thread(target=open_browser, daemon=True)
    t.start()
    app.run(host='127.0.0.1', port=5000, debug=False)

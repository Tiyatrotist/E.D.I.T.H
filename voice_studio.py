"""
voice_studio.py — EDITH Zarif Ses Stüdyosu Kısayolu

tools/voice_studio.py uygulamasını başlatır.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.voice_studio import open_voice_studio

if __name__ == "__main__":
    open_voice_studio()

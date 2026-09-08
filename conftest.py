import sys
from pathlib import Path

# EDITH kök dizinini sys.path'e ekler (tüm pytest testleri için)
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

"""Build this episode with the shared daily pipeline."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'videos'))
from daily_composition import build  # noqa: E402
if __name__ == '__main__':
    build('ST001', Path('videos/ep001'))

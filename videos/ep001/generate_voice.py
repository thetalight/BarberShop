"""Generate voices with the shared daily pipeline."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'videos'))
from daily_voice import main  # noqa: E402
if __name__ == '__main__':
    sys.argv[1:1] = ['--story-id', 'ST001', '--project', 'videos/ep001']
    main()

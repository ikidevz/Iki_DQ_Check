from Iki_DQ_Check.app import main
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

sys.path.insert(0, str(SRC))


if __name__ == "__main__":
    main()

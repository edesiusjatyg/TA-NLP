"""CLI yang dapat dijalankan langsung tanpa pip install -e ."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from bnpb_corpus.cli import main

if __name__ == "__main__":
    raise SystemExit(main())

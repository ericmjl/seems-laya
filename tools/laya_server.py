"""Kept for the docker compose command: identical to ``python -m seems serve``."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from seems.serve import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())

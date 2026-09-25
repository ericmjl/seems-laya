"""marimo with judgment-syntax cells:  ``python -m seems.marimo edit notebook.py``

or the ``seems-marimo`` console script. This runs marimo's own CLI in this
process with the in-process compiler patch applied first, so notebook cells can
contain judgment syntax directly:

```python
# a marimo cell, no run_source needed:
if amount > 500 and ticket asks for a refund:
    call = "manager"
unsure:
    call = "human review"
```

Notebooks saved this way keep their judgment syntax on disk; run them with the
same wrapper (or import them, which goes through the import hook).
"""
from __future__ import annotations

import os
import sys

from ._marimo_patch import install


def main(argv=None):
    # Kernel processes are multiprocessing-spawned children: they inherit this
    # env var and apply the same patch at their own interpreter startup.
    os.environ["SEEMS_COMPILE_PATCH"] = "1"
    install()
    from marimo._cli.cli import main as marimo_main

    args = list(sys.argv[1:] if argv is None else argv)
    sys.argv = ["marimo", *args]
    return marimo_main(args)


if __name__ == "__main__":
    sys.exit(main())

"""Canonical project directories.

Directories only. Append your own filename at the call site:

    from paths import DATA
    df = pd.read_csv(DATA / "accepted_36_month_population.csv")

The project is installed editable (``pip install -e .``) with ``src`` as the
import root, so ``import paths`` works from any notebook, script or test with no
``sys.path`` handling.

Modules have ``__file__``, so the repo root is derived from this file's own
location rather than from a marker walk or the working directory. That makes it
correct no matter where a notebook, script or test is launched from.

Nothing here contains a username, a drive letter or a path separator, so the
project moves between machines unchanged.
"""

from pathlib import Path

# src/paths.py -> src -> repo root
ROOT = Path(__file__).resolve().parents[1]

SRC = ROOT / "src"
DOCS = ROOT / "docs"

# Where the Lending Club files live. Append a filename, or a further subpath -
# the raw exports sit one level deeper, in directories named like files:
#   DATA / "accepted_2007_to_2018q4.csv" / "accepted_2007_to_2018Q4.csv"
DATA = SRC / "data" / "datasets" / "wordsforthewise" / "lending-club" / "versions" / "3"

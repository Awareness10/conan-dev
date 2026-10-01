"""run.py with Conan running on Python 3.12.7 instead of the project's Python.

    uv run parallel-demo/run-3.12.7.py [run.py options]

The project needs Python >= 3.12.12, so this runs run.py in a throwaway
`uv run --python 3.12.7` environment, with the same Conan version as the project:
only the Python version differs. Python 3.12 can't write .tzst archives, so
compression goes through the pre-3.14 tarfile path.
"""

import subprocess
import sys
from importlib import metadata
from pathlib import Path

PYTHON = "3.12.7"

try:
    conan = f"conan=={metadata.version('conan')}"
except metadata.PackageNotFoundError:
    conan = "conan"

run_py = Path(__file__).with_name("run.py")
cmd = ["uv", "run", "--quiet", "--no-project", "--python", PYTHON, "--with", conan]
sys.exit(subprocess.call([*cmd, "python", str(run_py), *sys.argv[1:]]))

"""claude-packs — Claude Code skill & agent bundles, packaged for PyPI.

This package wraps the bash CLI (shipped in claude_packs/data/) so the tool can
be installed with uv/pipx/pip and run without any access to the source repo.
"""

from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"

try:
    __version__ = (DATA_DIR / "VERSION").read_text().strip()
except OSError:  # building from a source tree where data isn't vendored yet
    __version__ = "0.0.0"

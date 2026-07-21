"""Entry point for the `claude-packs` console script (PyPI install).

The real CLI is the battle-tested bash script vendored at claude_packs/data/bin/
claude-packs — this shim just points it at the vendored registry and execs it.
CLAUDE_PACKS_PYTHON tells the CLI which interpreter has Textual (this venv ships
it as a dependency), so `claude-packs tui` gets the rich UI with no extra setup.
"""

import os
import shutil
import subprocess
import sys

from . import DATA_DIR


def main() -> None:
    cli = DATA_DIR / "bin" / "claude-packs"
    if not cli.is_file():
        print("claude-packs: packaging error — vendored CLI missing "
              f"({cli})", file=sys.stderr)
        raise SystemExit(2)
    bash = shutil.which("bash")
    if bash is None:
        print("claude-packs: bash is required but was not found on PATH "
              "(on Windows, run inside Git Bash or WSL).", file=sys.stderr)
        raise SystemExit(127)

    env = dict(os.environ)
    env.setdefault("CLAUDE_PACKS_HOME", str(DATA_DIR))
    env.setdefault("CLAUDE_PACKS_DIST", "pypi")
    env.setdefault("CLAUDE_PACKS_PYTHON", sys.executable)

    try:
        raise SystemExit(
            subprocess.call([bash, str(cli), *sys.argv[1:]], env=env)
        )
    except KeyboardInterrupt:
        raise SystemExit(130)


if __name__ == "__main__":
    main()

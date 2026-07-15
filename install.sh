#!/usr/bin/env bash
# Bootstrap installer for claude-packs — Claude Code skill/agent bundles.
#
# Preferred usage (from a clone of this repo):
#   ./install.sh <command> [bundles...] [options]     # forwards to the claude-packs CLI
#
# Examples:
#   ./install.sh list
#   ./install.sh install aws-connect                  # user-level (~/.claude)
#   ./install.sh install aws-connect --project .      # into ./.claude
#   ./install.sh uninstall aws-connect
#
# If Node.js is available this delegates to bin/claude-packs.js (full-featured).
# Without Node it falls back to a plain bash copy of the requested bundle(s).
#
# You can also skip cloning entirely and run the CLI straight from GitHub:
#   npx github:OWNER/REPO install aws-connect
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLI="${REPO_ROOT}/bin/claude-packs.js"

# --- Prefer the Node CLI ------------------------------------------------------
if command -v node >/dev/null 2>&1 && [[ -f "$CLI" ]]; then
  exec node "$CLI" "$@"
fi

# --- Bash fallback (no Node) ---------------------------------------------------
echo "Node.js not found — using the bash fallback installer." >&2
echo "(Install Node.js for list/info/uninstall/update and multi-bundle support.)" >&2
echo >&2

BUNDLES_DIR="${REPO_ROOT}/bundles"
TARGET="${HOME}/.claude"
FORCE=0
BUNDLES=()

# Parse a reduced arg set: [install] <bundle...> [--project [dir]] [--force]
while [[ $# -gt 0 ]]; do
  case "$1" in
    install|add) shift ;;
    --project|-p)
      shift
      if [[ $# -gt 0 && "$1" != -* ]]; then TARGET="$(cd "$1" && pwd)/.claude"; shift
      else TARGET="$(pwd)/.claude"; fi
      ;;
    --user|-u) TARGET="${HOME}/.claude"; shift ;;
    --force|-f) FORCE=1; shift ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//' | head -20; exit 0 ;;
    -*) echo "Unknown option: $1" >&2; exit 1 ;;
    *) BUNDLES+=("$1"); shift ;;
  esac
done

if [[ ${#BUNDLES[@]} -eq 0 ]]; then
  echo "Available bundles:" >&2
  for d in "${BUNDLES_DIR}"/*/; do [[ -f "${d}bundle.json" ]] && echo "  - $(basename "$d")" >&2; done
  echo >&2
  echo "Usage: ./install.sh install <bundle...> [--project [dir]] [--force]" >&2
  exit 1
fi

# Minimal JSON list extraction (no jq dependency): pull "skills" / "agents" arrays.
json_array() { # $1=file $2=key
  awk -v key="\"$2\"" '
    $0 ~ key"[[:space:]]*:" { grab=1 }
    grab { buf = buf $0; if ($0 ~ /\]/) { grab=0 } }
    END {
      sub(/.*\[/, "", buf); sub(/\].*/, "", buf)
      n = split(buf, a, ",")
      for (i=1;i<=n;i++) { gsub(/[[:space:]"]/, "", a[i]); if (a[i] != "") print a[i] }
    }' "$1"
}

mkdir -p "${TARGET}/skills" "${TARGET}/agents"

for bundle in "${BUNDLES[@]}"; do
  bdir="${BUNDLES_DIR}/${bundle}"
  manifest="${bdir}/bundle.json"
  if [[ ! -f "$manifest" ]]; then echo "Unknown bundle: ${bundle}" >&2; exit 1; fi
  echo "Installing ${bundle} -> ${TARGET}"

  while IFS= read -r s; do
    [[ -z "$s" ]] && continue
    src="${bdir}/skills/${s}"; dest="${TARGET}/skills/${s}"
    [[ ! -d "$src" ]] && { echo "  ! skill ${s} missing, skipping"; continue; }
    if [[ -e "$dest" && $FORCE -ne 1 ]]; then echo "  - skill ${s} exists (use --force)"; continue; fi
    rm -rf "$dest"; cp -R "$src" "$dest"; echo "  + skill ${s}"
  done < <(json_array "$manifest" skills)

  while IFS= read -r a; do
    [[ -z "$a" ]] && continue
    src="${bdir}/agents/${a}.md"; dest="${TARGET}/agents/${a}.md"
    [[ ! -f "$src" ]] && { echo "  ! agent ${a} missing, skipping"; continue; }
    if [[ -e "$dest" && $FORCE -ne 1 ]]; then echo "  - agent ${a} exists (use --force)"; continue; fi
    cp "$src" "$dest"; echo "  + agent ${a}"
  done < <(json_array "$manifest" agents)
done

echo
echo "Done. Restart Claude Code — skills and agents load at session start."

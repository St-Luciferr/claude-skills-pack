#!/usr/bin/env bash
# Install the Amazon Connect skill pack into Claude Code.
#
# Usage:
#   ./install.sh                  # install user-level (~/.claude) — available in all projects
#   ./install.sh --project [DIR]  # install into DIR/.claude (default: current directory)
#   ./install.sh --force          # overwrite existing installs without prompting
#   ./install.sh --uninstall      # remove previously installed skills/agents from the target
#
# Options combine: ./install.sh --project ~/my-app --force
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS=(aws-connect aws-connect-build aws-connect-update)
AGENTS=(aws-connect-architect aws-connect-flow-builder aws-connect-backend-dev aws-connect-frontend-dev)

TARGET="${HOME}/.claude"
FORCE=0
UNINSTALL=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)
      shift
      if [[ $# -gt 0 && "$1" != --* ]]; then
        TARGET="$(cd "$1" && pwd)/.claude"; shift
      else
        TARGET="$(pwd)/.claude"
      fi
      ;;
    --force) FORCE=1; shift ;;
    --uninstall) UNINSTALL=1; shift ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//' | head -9; exit 0 ;;
    *) echo "Unknown option: $1 (see --help)" >&2; exit 1 ;;
  esac
done

if [[ "$UNINSTALL" -eq 1 ]]; then
  for s in "${SKILLS[@]}"; do
    if [[ -d "${TARGET}/skills/${s}" ]]; then rm -rf "${TARGET}/skills/${s}"; echo "removed ${TARGET}/skills/${s}"; fi
  done
  for a in "${AGENTS[@]}"; do
    if [[ -f "${TARGET}/agents/${a}.md" ]]; then rm -f "${TARGET}/agents/${a}.md"; echo "removed ${TARGET}/agents/${a}.md"; fi
  done
  echo "Uninstalled from ${TARGET}."
  exit 0
fi

for s in "${SKILLS[@]}"; do
  if [[ ! -d "${REPO_ROOT}/skills/${s}" ]]; then
    echo "ERROR: ${REPO_ROOT}/skills/${s} not found — run install.sh from a full clone of the repo." >&2
    exit 1
  fi
done

confirm_overwrite() {
  local path="$1"
  if [[ "$FORCE" -eq 1 ]]; then return 0; fi
  if [[ ! -t 0 ]]; then
    echo "ERROR: ${path} already exists. Re-run with --force to overwrite." >&2
    exit 1
  fi
  read -r -p "${path} already exists. Overwrite? [y/N] " answer
  [[ "$answer" == "y" || "$answer" == "Y" ]]
}

mkdir -p "${TARGET}/skills" "${TARGET}/agents"

installed=()
skipped=()

for s in "${SKILLS[@]}"; do
  dest="${TARGET}/skills/${s}"
  if [[ -e "$dest" ]]; then
    if confirm_overwrite "$dest"; then rm -rf "$dest"; else skipped+=("skill ${s}"); continue; fi
  fi
  cp -R "${REPO_ROOT}/skills/${s}" "$dest"
  installed+=("skill ${s} -> ${dest}")
done

for a in "${AGENTS[@]}"; do
  src="${REPO_ROOT}/agents/${a}.md"
  dest="${TARGET}/agents/${a}.md"
  if [[ -e "$dest" ]]; then
    if confirm_overwrite "$dest"; then rm -f "$dest"; else skipped+=("agent ${a}"); continue; fi
  fi
  cp "$src" "$dest"
  installed+=("agent ${a} -> ${dest}")
done

chmod +x "${TARGET}/skills/aws-connect/scripts/fetch-whats-new.sh" 2>/dev/null || true

echo
echo "Installed to ${TARGET}:"
for line in "${installed[@]}"; do echo "  + ${line}"; done
if [[ "${#skipped[@]}" -gt 0 ]]; then
  echo "Skipped (already present, not overwritten):"
  for line in "${skipped[@]}"; do echo "  - ${line}"; done
fi
echo
echo "Done. Restart Claude Code (skills load at session start), then try:"
echo "  /aws-connect-build   — generate a deployable Connect solution from requirements"
echo "  /aws-connect-update  — sync the reference docs with new AWS announcements"

---
name: aws-connect-update
description: >
  Refresh the aws-connect skill with the latest Amazon Connect changes. Pulls new
  AWS "What's New" announcements and doc-history entries since the skill's changelog
  baseline, researches significant changes, updates the affected reference files, and
  prepends changelog entries. Use when the user asks to update/refresh the aws-connect
  skill or sync it with recent Amazon Connect releases.
---

# Update the aws-connect skill

Skill root (`$SKILL_ROOT` below): the directory containing the aws-connect skill —
`.claude/skills/aws-connect/` in the project root, or
`~/.claude/skills/aws-connect/` if installed user-level.

Follow these steps in order:

## 1. Determine the baseline

Read the header of `references/changelog.md`. The `> Baseline research:` /
`> Covers:` lines give the last date the skill was synced. Call it `SINCE`.

## 2. Collect what changed

- Run: `$SKILL_ROOT/scripts/fetch-whats-new.sh <SINCE> 200`
  (AWS What's New API filtered to Amazon Connect, newest first).
- Also WebFetch the admin-guide doc history:
  `https://docs.aws.amazon.com/connect/latest/adminguide/doc-history.html`
  and skim for entries after `SINCE`.
- Optionally check release pages of the frontend repos if frontend work matters:
  `https://github.com/amazon-connect/amazon-connect-streams/releases`,
  `https://github.com/amazon-connect/amazon-connect-chatjs/releases`.

If nothing new: update the `> Covers:` end date in `changelog.md` to today, report
"already current", and stop.

## 3. Triage

Classify each announcement:
- **Significant** (new API/flow block/channel/AI capability, changed limits or
  pricing, deprecations, new IaC resources) → needs research + reference update.
- **Minor** (single-region expansion, small console tweak) → changelog entry only,
  or skip entirely for region expansions of existing features.

## 4. Research & patch reference files

For each significant item, WebFetch its announcement + linked docs, then edit the
affected file(s) under `references/` (see the routing table in the aws-connect
SKILL.md to pick the file). Integrate facts into the existing sections — do not
append a "news" blob at the bottom of topic references. If many items need deep
research, fan out parallel research agents, one per topic area, each instructed to
edit its reference file in place.

Update the `> Last updated:` line of every file you touch to today's date.

## 5. Update the changelog

Prepend new entries to `references/changelog.md` (keep its reverse-chronological,
grouped-by-quarter format: `- **YYYY-MM** — Title: 1-2 sentences, URL`). Update the
`> Baseline research:` date to today and extend the `> Covers:` range.

## 6. Verify & report

- Confirm every touched file still has valid structure and an updated date line.
- Report to the user: number of announcements found, which were significant, which
  reference files changed, and anything that looked like a breaking change or
  deprecation affecting their projects.

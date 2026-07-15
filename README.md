# claude-packs

A central registry of **[Claude Code](https://claude.com/claude-code) skill & agent
bundles** for different stacks and technologies, plus a small CLI to install the ones
you want — into a single project or your user config.

Each **bundle** groups the skills and subagents for one stack (e.g. Amazon Connect).
The CLI copies a bundle's skills into `<target>/.claude/skills/` and its agents into
`<target>/.claude/agents/`, tracks what it installed, and can cleanly remove it later.

## Install the CLI

One command, no clone needed:

```bash
curl -fsSL https://raw.githubusercontent.com/OWNER/REPO/main/install.sh | bash
```

Or from a clone:

```bash
git clone https://github.com/OWNER/REPO && cd REPO && ./install.sh
```

This puts a managed copy of the registry in `~/.claude-packs` and a `claude-packs`
command in `~/.local/bin` (the installer tells you if that's not on your `PATH`).

**Requirements: bash and the usual coreutils — that's it.** No Node, no npm, no runtime
to install. `git` is needed to install from a URL and to `self-update`. `jq` is used for
manifest parsing when present, with an awk/sed fallback when it isn't. Works on bash 3.2,
so stock macOS is fine.

> Replace `OWNER/REPO` with this repository's path once it's pushed to GitHub.

## Use it

```bash
claude-packs list                            # see available bundles
claude-packs install aws-connect             # into ~/.claude (all projects)
claude-packs install aws-connect --project . # into ./.claude (this project only)
claude-packs update                          # refresh installed bundles
claude-packs uninstall aws-connect           # remove a bundle
claude-packs self-update                     # pull the latest CLI + bundles
claude-packs self-uninstall                  # remove the CLI from this device
```

Skills and agents load at session start — **restart Claude Code** after installing.

### Keeping up to date

Two levels, deliberately separate:

- `claude-packs self-update` — `git pull`s the registry in `~/.claude-packs`, so you get
  new bundles and new versions of existing ones.
- `claude-packs update` — copies that newer content into a target's `.claude`, upgrading
  what you've already installed there. `list` flags installs that are behind
  (`✓ installed (1.0.0 → 1.1.0 available)`).

### Uninstalling

- `claude-packs uninstall <bundle>` removes a bundle from a project or `~/.claude`.
- `claude-packs self-uninstall` (or `./install.sh --uninstall`) removes the CLI and the
  `~/.claude-packs` registry. It deliberately leaves bundles you installed into projects
  alone — remove those first if you want them gone.

**Environment overrides** (for the installer): `CLAUDE_PACKS_HOME` (registry location,
default `~/.claude-packs`), `CLAUDE_PACKS_BIN` (launcher dir, default `~/.local/bin`),
`CLAUDE_PACKS_REPO` (git URL to install from).

## Command reference

```
claude-packs list                    list bundles + install status
claude-packs info <bundle>           show a bundle's skills, agents, description
claude-packs install <bundle...>     install one or more bundles
claude-packs uninstall <bundle...>   remove installed bundles (only files it added)
claude-packs update [bundle...]      re-copy latest bundle content over installs
claude-packs installed               list what's installed at the target
claude-packs self-update             update the CLI + registry itself (git pull)
claude-packs self-uninstall          remove the CLI from this device
```

**Target flags** (apply to install/uninstall/update/list/installed):

| Flag | Target | Scope |
| --- | --- | --- |
| `--user` / `-u` *(default)* | `~/.claude` | every project on this machine |
| `--project [dir]` / `-p` | `<dir>/.claude` (default: cwd) | that one project |

Other flags: `--force`/`-f` (overwrite without prompting), `--help`, `--version`.

The CLI records installs in a `<target>/.claude/.claude-packs` receipt (a simple
tab-separated `bundle / version / kind / item` file), so `uninstall` removes exactly the
files a bundle added and leaves your other skills/agents untouched. It won't silently
clobber an untracked skill/agent of the same name — it prompts (or skips in
non-interactive mode unless `--force`).

## Available bundles

| Bundle | What it covers |
| --- | --- |
| **aws-connect** | Amazon Connect (AWS cloud contact center): contact flows & flow-language JSON, routing, CCP/Streams/ChatJS frontends, Lambda/Lex/Q in Connect integrations, Contact Lens, CTR & metrics pipelines, and CloudFormation/CDK/Terraform IaC. Ships 3 skills (incl. `/aws-connect-build` and `/aws-connect-update`) and 4 specialist agents. |

Run `claude-packs info <bundle>` for the full skill/agent list of any bundle.

## Repository layout

```
install.sh                 # installs the CLI onto a device (curl-able); --uninstall removes it
bin/claude-packs           # the CLI — pure bash, no runtime dependencies
VERSION                    # CLI version
bundles/
└── aws-connect/
    ├── bundle.json         # manifest: name, version, description, skills[], agents[]
    ├── skills/             # one directory per skill (each with a SKILL.md)
    └── agents/             # one <agent-name>.md per agent
CONTRIBUTING.md            # how to add a new bundle
```

## Add a new bundle

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: create `bundles/<name>/` with a
`bundle.json`, drop your skills under `skills/` and agents under `agents/`, and the CLI
picks it up automatically — no code changes needed.

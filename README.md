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
curl -fsSL https://raw.githubusercontent.com/St-Luciferr/claude-skills-pack/main/install.sh | bash
```

Or from a clone:

```bash
git clone https://github.com/St-Luciferr/claude-skills-pack
cd claude-skills-pack && ./install.sh
```

This puts a managed copy of the registry in `~/.claude-packs` and a `claude-packs`
command in `~/.local/bin` (the installer tells you if that's not on your `PATH`).

**Requirements: bash and the usual coreutils — that's it.** No Node, no npm, no runtime
to install. `git` is needed to install from a URL and to `self-update`. `jq` is used for
manifest parsing when present, with an awk/sed fallback when it isn't. Works on bash 3.2,
so stock macOS is fine.

Both forms above install the **published** repo, so you get a git-backed registry that
`claude-packs self-update` can pull into. Contributors testing local changes should run
`./install.sh --local` to install the checkout they're sitting in instead (self-update is
then unavailable, since there's no git remote behind it).

## Use it

The quickest way in is the **interactive menu** — run `claude-packs` with no arguments
(or `claude-packs tui`) and browse, select, and manage bundles from one screen:

```tui
claude-packs                                 # opens the interactive menu

  claude-packs v1.5.0  — interactive
  Target ~/.claude (user)   (press t to change)

 ❯ ◉ aws-connect          v1.3.0  ◑ partial (2/8)
       Amazon Connect contact center skills + agents

  ↑/↓ move   space select   a all   enter/→ pick items
  i install   x uninstall   u update   t target   q quit
```

Navigate with the arrow keys (or `k`/`j`), multi-select with `space` (or `a` for all),
then press `i`/`x`/`u` to install, uninstall, or update the selection — with nothing
selected, the action applies to the highlighted row. Press `q` to quit.

**Want just some of a bundle?** Press `enter` (or `→`) on a bundle to drill into its
individual skills and agents, tick the ones you want with `space`, and press `i` to
install (or `x` to remove) only those. Partly-installed bundles show `◑ partial (n/total)`
in the list.

**Choosing where it goes.** When you press `i` to install, the menu asks for a target —
`~/.claude` (user, all projects), the **current directory**, or a **manual path** — so
you pick the destination as part of each install. (`t` sets the target the list is shown
against and the default for uninstall/update.)

Prefer one-shot commands? Every action has a non-interactive equivalent:

```bash
claude-packs list                            # see available bundles
claude-packs install aws-connect             # whole bundle → ~/.claude (all projects)
claude-packs install aws-connect --project . # whole bundle → ./.claude (this project)
claude-packs install aws-connect:aws-connect-build,aws-connect-verify   # just these two
claude-packs uninstall aws-connect:aws-connect-build                    # remove one item
claude-packs update                          # refresh installed bundles (keeps selections)
claude-packs uninstall aws-connect           # remove a bundle
claude-packs self-update                     # pull the latest CLI + bundles
claude-packs self-uninstall                  # remove the CLI from this device
```

Append `:item,item` to a bundle name to install or remove specific skills/agents instead
of the whole bundle. Selective installs are **additive** (adding more items later keeps
the ones already there), and `update` refreshes only what you picked — it never silently
re-expands a selection back to the full bundle. Run `claude-packs info <bundle>` to see
the exact item names.

Skills and agents load at session start — **restart Claude Code** after installing.

### Keeping up to date

One command: **`claude-packs update`**. On a normal (git-backed) install it refreshes the
registry first (`git pull`), then re-copies the latest bundle content into the target's
`.claude` — upgrading what's installed, pruning skills/agents a newer bundle version
dropped, and printing each version transition (`↑ aws-connect v1.1.0 → v1.2.0`).

- `claude-packs self-update` still exists to refresh only the CLI/registry without
  touching any install (and is the fallback for updating the CLI itself).
- **Upgrading from a CLI older than v1.2.0**: run `claude-packs self-update` once
  first — older CLIs don't refresh the registry on `update` and would silently
  re-install stale content.
- Installs made with `install.sh --local` have no git registry — `update` says so and
  re-copies from the local content instead.
- `list` flags installs that are behind (`✓ installed (1.1.0 → 1.2.0 available)`).

### Uninstalling

- `claude-packs uninstall <bundle>` removes a bundle from a project or `~/.claude`.
- `claude-packs self-uninstall` (or `./install.sh --uninstall`) removes the CLI and the
  `~/.claude-packs` registry. It deliberately leaves bundles you installed into projects
  alone — remove those first if you want them gone.

**Environment overrides** (for the installer): `CLAUDE_PACKS_HOME` (registry location,
default `~/.claude-packs`), `CLAUDE_PACKS_BIN` (launcher dir, default `~/.local/bin`),
`CLAUDE_PACKS_REPO` (git URL to install from).

## Command reference

```bash
claude-packs tui                     interactive menu to browse + manage bundles
claude-packs list                    list bundles + install status
claude-packs info <bundle>           show a bundle's skills, agents, description
claude-packs install <bundle[:item,...]>  install a bundle, or just specific skills/agents
claude-packs uninstall <bundle[:item,...]> remove a bundle, or just specific items
claude-packs update [bundle...]      refresh the registry + upgrade installs to latest
claude-packs installed               list what's installed at the target
claude-packs self-update             update the CLI + registry itself
claude-packs self-uninstall          remove the CLI from this device
claude-packs help [command]          detailed help (also: claude-packs <command> --help)
```

Every command answers `--help` with its own detailed usage and examples.
`self-update` works on any install: git-backed registries `git pull`; `--local`
installs are offered a re-run of the installer, which switches them to git-backed.

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

| Bundle | What it covers | Guide |
| --- | --- | --- |
| **aws-connect** | Amazon Connect (AWS cloud contact center): contact flows & flow-language JSON, routing, CCP/Streams/ChatJS frontends, Lambda/Lex/Q in Connect integrations, Contact Lens, CTR & metrics pipelines, and CloudFormation/CDK/Terraform IaC. Ships 4 skills (incl. `/aws-connect-build`, `/aws-connect-verify`, `/aws-connect-update`) and 4 specialist agents. | [Build a contact center from scratch](bundles/aws-connect/GUIDE.md) |

Run `claude-packs info <bundle>` for the full skill/agent list, and the path to its guide.

**Guides aren't installed.** A bundle's guide is documentation for *you* and stays in the
registry (`~/.claude-packs/bundles/<name>/`) — only skills and agents are copied into
`.claude/`, so guides never consume Claude's context.

## Repository layout

```tree
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

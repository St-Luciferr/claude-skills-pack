# claude-packs

A central registry of **AI-assistant skill & agent bundles** for different stacks and
technologies, plus a small CLI to install the ones you want — into a single project or
your user config. Built for **[Claude Code](https://claude.com/claude-code)** first,
and installable for **GitHub Copilot** and **Cursor** too.

Each **bundle** groups the skills and subagents for one stack (e.g. Amazon Connect).
The CLI copies a bundle's skills into `<target>/.claude/skills/` and its agents into
`<target>/.claude/agents/`, tracks what it installed, and can cleanly remove it later —
and can emit the same content in each assistant's native format (see
[Other assistants](#other-assistants-github-copilot--cursor)).

## Install the CLI

Pick whichever package manager you already have — every method gives you the same
`claude-packs` command with the CLI, the interactive UI, and **all bundles included**
(no repo access needed):

```bash
# Python / uv — recommended: rich UI works out of the box
uvx claude-packs                       # run once, nothing installed
uv tool install claude-packs           # install the command
pipx install claude-packs              # same, via pipx
pip install claude-packs               # plain pip

# Node / npm  (package name differs — "claude-packs" was taken on npm)
npx claude-skills-pack                 # run once, nothing installed
npm install -g claude-skills-pack      # install the command

# No Python or Node? The pure-bash installer:
curl -fsSL https://raw.githubusercontent.com/St-Luciferr/claude-skills-pack/main/install.sh | bash
```

Or from a clone: `git clone https://github.com/St-Luciferr/claude-skills-pack && cd
claude-skills-pack && ./install.sh`.

Package installs are fully self-contained (bundles ship inside the package) and update
through their own manager — `claude-packs self-update` tells you the exact command.
The curl installer instead puts a git-backed registry in `~/.claude-packs` and a
launcher in `~/.local/bin`, and updates itself via `claude-packs self-update`.
Tagged releases with prebuilt artifacts are on the
[releases page](https://github.com/St-Luciferr/claude-skills-pack/releases).

**Requirements: bash and the usual coreutils — that's it.** No Node, no npm, no runtime
to install. `git` is needed to install from a URL and to `self-update`. `jq` is used for
manifest parsing when present, with an awk/sed fallback when it isn't. Works on bash 3.2,
so stock macOS is fine. The interactive UI is nicest with `python3`+Textual or `uv` on
the machine (see [Use it](#use-it)), but degrades gracefully to pure bash without them.

Both forms above install the **published** repo, so you get a git-backed registry that
`claude-packs self-update` can pull into. Contributors testing local changes should run
`./install.sh --local` to install the checkout they're sitting in instead (self-update is
then unavailable, since there's no git remote behind it).

## Use it

The quickest way in is the **interactive UI** — run `claude-packs` with no arguments
(or `claude-packs tui`) for a genuinely GUI-feeling app in your terminal:

```tui
claude-packs                                 # opens the interactive UI

  claude-packs  v1.9.0  skill & agent bundles for Claude Code
  target  ~/.claude  (user — all projects)

 ╭──────────────────────────────────────────────────────────╮
 │  aws-connect  v1.3.0   ◑ partial (2/8)                   │
 │  Amazon Connect contact center   4 skills · 4 agents     │
 ╰──────────────────────────────────────────────────────────╯

     [ Open ] [ Install… ] [ Update ] [ Uninstall ] [ Target… ] [ Quit ]
```

Bundles are **clickable cards**; opening one shows its skills and agents as
**checkboxes** with on-screen buttons. Installing pops a **target dialog** — pick
`~/.claude` (user), the current project, or another folder. Actions confirm in
**dialogs** and report in **toast notifications**; every control also has a key
(shown in the footer), so keyboard-only use is first-class.

**Installing is point-and-click:**

1. **Open** a bundle — click its card (or press `enter`).
2. **Tick** the skills/agents you want — click rows or press `space` (`a` = all).
   The `Install…` button / `i` key on the bundle list opens the same picker with
   everything pre-ticked, for a whole-bundle install.
3. Press **`Install selected`** and choose the target in the dialog. Done — a toast
   reminds you to restart Claude Code.

Partly-installed bundles show `◑ partial (n/total)` on their card; the `Target…`
button switches which install target the statuses (and update/uninstall) apply to.

The rich UI runs on Python + [Textual](https://textual.textualize.io/), auto-detected:
it launches if `python3` has Textual **or** if [`uv`](https://docs.astral.sh/uv/) is
installed (uv provisions it on first run, cached afterwards). No Python? No problem —
the CLI falls back to its **built-in pure-bash menu** with the same flow (also
reachable explicitly via `claude-packs tui --basic`).

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

### Other assistants: GitHub Copilot & Cursor

Bundles are authored in Claude Code format, and the CLI **translates them on install**
for other assistants — pick providers with `--provider` (or tick them in the
interactive UI's install dialog):

```bash
claude-packs install aws-connect --project . --provider copilot          # just Copilot
claude-packs install aws-connect --project . --provider claude,copilot,cursor
claude-packs uninstall aws-connect --project .   # removes it for every provider
```

What each provider gets (all project-scoped, inside your repo):

| Provider | Skills become | Agents become |
| --- | --- | --- |
| `claude` *(default)* | `.claude/skills/<name>/` | `.claude/agents/<name>.md` |
| `copilot` | `.github/prompts/<name>.prompt.md` (+ full skill dir in `.github/skills/`) | `.github/agents/<name>.md` |
| `cursor` | `.cursor/commands/<name>.md` (+ full skill dir in `.cursor/skills/`) | `.cursor/rules/<name>.mdc` |

Multi-file skills keep their reference files — the generated prompt/command entry
points at the copied skill directory. Each provider root keeps its **own receipt**, so
`update` refreshes and `uninstall` cleans every provider you installed for (narrow
either with `--provider`). Copilot/Cursor installs are **project-only** — only Claude
Code has a standard user-level location (`~/.claude`).

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
claude-packs tui                     interactive UI (rich if Python/uv available; --basic for bash)
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

`--provider <list>` / `-P` picks the AI assistants: `claude`, `copilot`, `cursor`
(comma-separated). Install defaults to `claude`; uninstall/update/installed default to
every provider they find installed.

Other flags: `--force`/`-f` (overwrite without prompting), `--basic`/`-b` (tui: use the
built-in bash menu instead of the rich UI), `--help`, `--version`.

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
bin/claude-packs-tui.py    # the rich interactive UI (Textual) — optional, auto-detected
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

## License

[MIT](LICENSE)

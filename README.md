# claude-packs

A central registry of **[Claude Code](https://claude.com/claude-code) skill & agent
bundles** for different stacks and technologies, plus a small CLI to install the ones
you want — into a single project or your user config.

Each **bundle** groups the skills and subagents for one stack (e.g. Amazon Connect).
The CLI copies a bundle's skills into `<target>/.claude/skills/` and its agents into
`<target>/.claude/agents/`, tracks what it installed, and can cleanly remove it later.

## Quick start

Run it straight from GitHub — no clone, no global install (needs Node ≥ 16):

```bash
npx github:OWNER/REPO list                          # see available bundles
npx github:OWNER/REPO install aws-connect           # into ~/.claude (all projects)
npx github:OWNER/REPO install aws-connect --project .   # into ./.claude (this repo)
```

Or install the CLI globally:

```bash
npm install -g github:OWNER/REPO
claude-packs list
claude-packs install aws-connect --project ~/my-app
```

Or clone and use the bootstrap script (delegates to the CLI; has a Node-free fallback):

```bash
git clone https://github.com/OWNER/REPO && cd REPO
./install.sh install aws-connect            # user-level
./install.sh install aws-connect --project . # per-project
```

> Replace `OWNER/REPO` with this repository's path once it's pushed to GitHub.

Skills and agents load at session start — **restart Claude Code** after installing.

## Commands

```
claude-packs list                    list bundles + install status
claude-packs info <bundle>           show a bundle's skills, agents, description
claude-packs install <bundle...>     install one or more bundles
claude-packs uninstall <bundle...>   remove installed bundles (only files it added)
claude-packs update [bundle...]      re-copy latest bundle content over installs
claude-packs installed               list what's installed at the target
```

**Target flags** (apply to install/uninstall/update/list/installed):

| Flag | Target | Scope |
| --- | --- | --- |
| `--user` / `-u` *(default)* | `~/.claude` | every project on this machine |
| `--project [dir]` / `-p` | `<dir>/.claude` (default: cwd) | that one project |

Other flags: `--force`/`-f` (overwrite without prompting), `--help`, `--version`.

The CLI records installs in `<target>/.claude/.claude-packs.json`, so `uninstall`
removes exactly the files a bundle added and leaves your other skills/agents untouched.
It won't silently clobber an untracked skill/agent of the same name — it prompts (or
skips in non-interactive mode unless `--force`).

## Available bundles

| Bundle | What it covers |
| --- | --- |
| **aws-connect** | Amazon Connect (AWS cloud contact center): contact flows & flow-language JSON, routing, CCP/Streams/ChatJS frontends, Lambda/Lex/Q in Connect integrations, Contact Lens, CTR & metrics pipelines, and CloudFormation/CDK/Terraform IaC. Ships 3 skills (incl. `/aws-connect-build` and `/aws-connect-update`) and 4 specialist agents. |

Run `claude-packs info <bundle>` for the full skill/agent list of any bundle.

## Repository layout

```
bin/claude-packs.js        # the CLI (zero dependencies, Node built-ins only)
package.json               # bin entry + files whitelist for npx/npm install
install.sh                 # bootstrap: delegates to the CLI, bash fallback if no Node
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

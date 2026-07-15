# Adding a bundle

A **bundle** is a self-contained folder under `bundles/` that groups the Claude Code
skills and agents for one stack or technology. The CLI discovers bundles automatically
by scanning `bundles/*/bundle.json` — you don't touch any CLI code to add one.

## Layout

```
bundles/<bundle-name>/
├── bundle.json            # manifest (required)
├── GUIDE.md               # end-user walkthrough (optional, NOT installed)
├── skills/
│   └── <skill-name>/
│       └── SKILL.md       # + any references/, scripts/, assets the skill needs
└── agents/
    └── <agent-name>.md
```

**Only what's listed in `skills[]` and `agents[]` gets installed.** Anything else at the
bundle root — guides, examples, notes, screenshots — stays in the registry and is never
copied into a user's `.claude/`. That's the place for human-facing docs: they'd only
burn context if they landed in `.claude/`. Point at one with the `guide` field and
`claude-packs info <bundle>` will print its path.

Note the boundary: a skill directory is copied **whole**, so anything you put inside
`skills/<skill>/` *does* get installed. Docs go at the bundle root, not in a skill.

- **`<bundle-name>`** is what users type: `claude-packs install <bundle-name>`.
- Each entry in `skills[]` must match a directory under `skills/` containing a `SKILL.md`.
- Each entry in `agents[]` must match a file `agents/<agent-name>.md`.
- The whole `skills/<skill>/` tree is copied as-is (subdirectories, executable scripts,
  and file permissions are preserved), so keep a skill's references/scripts inside its
  own directory.

## `bundle.json`

```json
{
  "name": "my-stack",
  "title": "My Stack",
  "version": "1.0.0",
  "description": "One-paragraph summary shown by `info` and `list`.",
  "tags": ["keyword", "another"],
  "skills": ["my-stack", "my-stack-build"],
  "agents": ["my-stack-architect", "my-stack-dev"]
}
```

| Field | Required | Notes |
| --- | --- | --- |
| `name` | yes | Must match the folder name; the install identifier. |
| `version` | recommended | Bump it on changes; `list` flags installs that are behind. |
| `title` | no | Short human label. |
| `description` | no | Shown by `info`/`list`. |
| `tags` | no | Searchable keywords shown in `list`. |
| `guide` | no | Path (relative to the bundle) to a user-facing guide; shown by `info`. Not installed. |
| `skills` | no | Skill directory names; omit or `[]` for an agents-only bundle. |
| `agents` | no | Agent file basenames (without `.md`). |

> **Keep manifest values simple.** The CLI uses `jq` when it's installed, but falls back
> to awk/sed parsing when it isn't. For the fallback to work, write each string value on
> a single line with no embedded double quotes or escapes, and one `"key": "value"` per
> line. Plain prose and kebab-case identifiers are fine — that covers every real case.
> Always verify with `./bin/claude-packs info <name>` on a machine without `jq`
> (or temporarily rename it) if your description is unusual.

## Checklist

1. Create `bundles/<name>/` with the layout above.
2. Write `bundle.json`; make sure every `skills[]`/`agents[]` entry has a matching file.
3. Verify locally (run the CLI straight from the clone — no install needed):
   ```bash
   ./bin/claude-packs list
   ./bin/claude-packs info <name>
   ./bin/claude-packs install <name> --project /tmp/try   # inspect /tmp/try/.claude
   ./bin/claude-packs uninstall <name> --project /tmp/try
   ```
   To exercise the real installed command against your local changes, use
   `./install.sh --local` — plain `./install.sh` clones the published repo and would
   ignore your working tree.
4. Add a row to the "Available bundles" table in `README.md`.
5. Bump `version` in the bundle's `bundle.json` so existing installs are flagged as
   outdated by `list` and picked up by `claude-packs update`.
6. Push to `main` — users get it with `claude-packs self-update`.

## Skill & agent format

Bundles carry standard Claude Code assets — this repo doesn't invent a new format:

- **Skills**: a directory with a `SKILL.md` whose front matter has `name:` and
  `description:`. See any skill under `bundles/aws-connect/skills/` for a reference.
- **Agents**: a single markdown file with `name:` and `description:` front matter
  defining a subagent. See `bundles/aws-connect/agents/` for examples.

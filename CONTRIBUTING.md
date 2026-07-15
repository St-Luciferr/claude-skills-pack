# Adding a bundle

A **bundle** is a self-contained folder under `bundles/` that groups the Claude Code
skills and agents for one stack or technology. The CLI discovers bundles automatically
by scanning `bundles/*/bundle.json` — you don't touch any CLI code to add one.

## Layout

```
bundles/<bundle-name>/
├── bundle.json            # manifest (required)
├── skills/
│   └── <skill-name>/
│       └── SKILL.md       # + any references/, scripts/, assets the skill needs
└── agents/
    └── <agent-name>.md
```

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
| `skills` | no | Skill directory names; omit or `[]` for an agents-only bundle. |
| `agents` | no | Agent file basenames (without `.md`). |

## Checklist

1. Create `bundles/<name>/` with the layout above.
2. Write `bundle.json`; make sure every `skills[]`/`agents[]` entry has a matching file.
3. Verify locally:
   ```bash
   node bin/claude-packs.js list
   node bin/claude-packs.js info <name>
   node bin/claude-packs.js install <name> --project /tmp/try   # inspect /tmp/try/.claude
   node bin/claude-packs.js uninstall <name> --project /tmp/try
   ```
4. Add a row to the "Available bundles" table in `README.md`.
5. Bump the version in the root `package.json` if you want `npx github:...` users to
   pull the change.

## Skill & agent format

Bundles carry standard Claude Code assets — this repo doesn't invent a new format:

- **Skills**: a directory with a `SKILL.md` whose front matter has `name:` and
  `description:`. See any skill under `bundles/aws-connect/skills/` for a reference.
- **Agents**: a single markdown file with `name:` and `description:` front matter
  defining a subagent. See `bundles/aws-connect/agents/` for examples.

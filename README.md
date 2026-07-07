# Amazon Connect Skill for Claude Code

A [Claude Code](https://claude.com/claude-code) skill pack for building anything on
**Amazon Connect** (AWS cloud contact center): contact flows, CCP/Streams/ChatJS
frontends, Lambda/Lex/Q in Connect integrations, Contact Lens, contact-record and
metrics pipelines, and CloudFormation/CDK/Terraform IaC.

The reference material was deep-researched from official AWS documentation
(baseline: **2026-07**) and ships with an update workflow to keep it current as
Amazon Connect evolves.

## What's inside

```
install.sh                           # installer (user-level or per-project)
skills/
├── aws-connect/                     # main skill (auto-activates on Connect tasks)
│   ├── SKILL.md                     # entry point + routing table + hard-won rules
│   ├── references/                  # ~2,900 lines of researched documentation
│   │   ├── core-concepts.md         # instances, routing, queues, quotas, IAM
│   │   ├── contact-flows.md         # flow language JSON, block catalog, attributes
│   │   ├── apis-sdks.md             # all 10 API namespaces, TPS limits, code examples
│   │   ├── frontend-streams.md      # CCP, Streams, ChatJS, chat widget, workspace apps
│   │   ├── ai-integrations.md       # Lambda, Lex V2, Q in Connect / AI agents, Contact Lens
│   │   ├── data-analytics.md        # CTRs, event streams, GetMetricDataV2, data lake
│   │   ├── iac-devops.md            # CFN/CDK/Terraform, flow-content-as-code, CI/CD
│   │   └── changelog.md             # notable Connect changes 2025-01 → 2026-07
│   └── scripts/
│       └── fetch-whats-new.sh       # pulls Connect announcements from AWS What's New
├── aws-connect-build/               # /aws-connect-build — requirements → deployable package
└── aws-connect-update/              # /aws-connect-update — refreshes the references
agents/
├── aws-connect-architect.md         # solution & routing design
├── aws-connect-flow-builder.md      # authors/validates flow-language JSON
├── aws-connect-backend-dev.md       # APIs, Lambdas, event/data pipelines
└── aws-connect-frontend-dev.md      # CCP/Streams/ChatJS/workspace UIs
```

## Install

```bash
git clone <this-repo-url>
cd <repo>
./install.sh              # user-level (~/.claude) — available in every project
```

Or install into a single project instead:

```bash
./install.sh --project /path/to/your/project
```

Other flags: `--force` (overwrite an existing install, e.g. when pulling a newer
version of this repo), `--uninstall` (remove the skills/agents from the target;
combine with `--project` for project installs).

Skills load at session start — restart Claude Code after installing.

## Use

Just ask Claude Code for Amazon Connect work — the skill activates on its own
(e.g. "build an inbound flow with a Lambda customer lookup", "embed a custom CCP
in our React app", "set up a CTR → Athena pipeline"). Reference files are loaded
selectively per task, and the specialized agents can be delegated to by name.

## Generate a full solution

Run `/aws-connect-build` to go from requirements to a deployable package. It
interviews you (channels, routing, AI/self-service scope, integrations,
environments), writes `REQUIREMENTS.md` and `DESIGN.md`, then generates:
CloudFormation template(s), `flows/*.flow.json` with per-environment ARN
placeholders, Lambda functions with tests, OpenAPI schemas for MCP tool
integrations, AI prompt/agent definitions, per-env config, and an idempotent
`deploy.sh` — plus explicit instructions for the steps AWS doesn't let you
automate (number claiming, SAML setup, approved origins).

## Keep it current

Run `/aws-connect-update` in Claude Code (monthly is a good cadence). It:

1. reads the baseline date from `references/changelog.md`,
2. fetches newer Amazon Connect announcements via `scripts/fetch-whats-new.sh`
   (AWS What's New API) and the admin-guide doc history,
3. researches significant changes and patches the affected reference files,
4. prepends changelog entries and bumps the `> Last updated:` dates.

Each reference file carries a `> Last updated:` line — treat quotas, pricing, and
region availability newer than that date as facts to verify against live AWS docs.

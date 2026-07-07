---
name: aws-connect-build
description: >
  End-to-end Amazon Connect solution generator. Collects requirements from the user,
  produces a design, then generates a complete deployable package: CloudFormation
  template(s), contact flow JSON files with environment-portable ARN placeholders,
  Lambda function code, OpenAPI schemas for MCP tool integrations, AI prompt/agent
  definitions for Q in Connect, per-environment config, and a deploy.sh. Use when the
  user wants to build/scaffold/generate a new Amazon Connect solution, IVR, contact
  center, or AI agent deployment from requirements.
---

# Build a deployable Amazon Connect solution

You will take the user from requirements → design → a complete, deployable project.
Load the aws-connect skill's references as you go (routing table in
`.claude/skills/aws-connect/SKILL.md`); delegate heavy lifting to the
`aws-connect-*` agents.

## Phase 1 — Collect requirements

Interview the user (use AskUserQuestion when interactive; batch related questions,
max 4 at a time). Do NOT skip this phase unless the user already supplied the
answers. Cover:

1. **Channels**: voice / chat / tasks / email / SMS-WhatsApp; inbound, outbound, or both.
2. **Instance**: create new via IaC, or target an existing instance (get instance
   alias/ID and region)? Identity model (Connect-native / SAML / directory)?
3. **Routing**: queues, agent groups/hierarchies, business hours + timezone,
   after-hours behavior, overflow/escalation rules, callbacks?
4. **Self-service & AI**: IVR menu structure; Lex bot or Connect AI agents for
   self-service? Q in Connect agent assist? Which tasks should AI resolve without an
   agent, and what tools/data does it need (→ drives MCP tool schemas)?
5. **Integrations & data**: CRMs, internal APIs, databases the flows/Lambdas must
   call; what customer data to look up/write; existing MCP servers or APIs to expose
   as AI tools?
6. **Recording & analytics**: call/chat recording, Contact Lens (real-time or
   post-contact), evaluation, CTR pipeline (Kinesis→S3→Athena)?
7. **Environments & tooling**: dev/stage/prod account+region matrix; CloudFormation
   (default here) vs CDK vs Terraform; naming prefix; KMS requirements.
8. **Compliance/misc**: PII redaction, data residency, languages/voices, expected
   volumes (quota check).

Write the answers to `docs/REQUIREMENTS.md` in the target project. Confirm the
summary with the user before generating.

## Phase 2 — Design

Delegate to the `aws-connect-architect` agent with REQUIREMENTS.md. Output
`docs/DESIGN.md`: flow inventory (which flow types), queue/routing-profile/hours
model, Lambda inventory (purpose, trigger, data contract), AI agents + their MCP
tools, data/analytics pipeline, and everything that CANNOT be automated (see
"Manual steps" below). Get user sign-off on the design if anything is ambiguous.

## Phase 3 — Generate the package

Produce this layout (adapt names to the project):

```
<solution>/
├── README.md                     # what it is, prerequisites, deploy runbook
├── docs/REQUIREMENTS.md, DESIGN.md
├── infra/
│   └── template.yaml             # CloudFormation (or cdk/ / terraform/ if chosen)
├── flows/
│   └── <name>.flow.json          # flow-language JSON, ARNs as ${Placeholders}
├── lambdas/
│   └── <name>/index.(py|ts) + tests
├── openapi/
│   └── <tool-group>.yaml         # OpenAPI 3.x schemas for MCP tool integrations
├── ai-prompts/
│   └── <name>.yaml               # Q in Connect AI prompt / AI agent definitions
├── config/
│   └── dev.env, prod.env         # per-env: instance ARN/ID, region, KMS, prefixes
└── deploy.sh
```

Generation rules (non-negotiable):

- **Flows** (`aws-connect-flow-builder` agent): valid flow-language JSON
  (Version 2019-10-30), every fallible action has an Errors transition, channel
  support checked per block. NO hard-coded ARNs — use `${QueueArn_Support}`-style
  placeholders and record every placeholder in a manifest comment block in
  deploy.sh. Structurally lint each flow (unique Identifiers, one StartAction,
  transitions resolve, no orphans) before finishing.
- **CloudFormation** (`aws-connect-backend-dev` agent, `iac-devops.md` reference):
  parameterize the instance ARN (existing instance) or create
  `AWS::Connect::Instance` (new); queues, hours, routing profiles, contact flows
  (content inlined ≤256 KB, post-substitution), `AWS::Connect::IntegrationAssociation`
  / `AssociateLambdaFunction` for Lambdas, Lambda functions + least-privilege IAM,
  Kinesis/S3/Athena resources if the CTR pipeline is in scope. Note (don't fake)
  resources CFN can't manage.
- **Lambdas**: honor the flow-Lambda contract — respond < 8 s, flat string map (or
  JSON mode, then say so in the flow block), never throw for business "not found";
  include unit tests for the handler's happy path and timeout/error shape.
- **OpenAPI schemas for MCP tools** (`ai-integrations.md` reference): one OpenAPI
  3.x document per tool group, `operationId` = tool name the AI agent sees, tight
  request/response schemas with `description` on every field (the AI agent reads
  these), auth scheme matching the gateway (AgentCore Gateway / API key / SigV4).
  Keep tool descriptions action-oriented ("Look up order status by order ID").
- **AI prompts** (`ai-prompts/`): system prompt per AI agent — role, scope, the
  tools available and when to use each, escalation-to-human rules (Return to
  Control), guardrails (never reveal PII, stay on domain), and the `<message>`
  formatting requirement where applicable. Store as YAML with fields:
  name, type (ANSWER_RECOMMENDATION / SELF_SERVICE / orchestrator), model config,
  prompt text, tool list.
- **deploy.sh**: idempotent, `set -euo pipefail`, takes `ENV` arg sourcing
  `config/$ENV.env`. Order: package/upload Lambdas → `aws cloudformation deploy`
  → resolve real ARNs (by resource NAME lookups via `aws connect list-*`) →
  substitute placeholders into flow JSON (envsubst/jq) → `aws connect
  update-contact-flow-content` per flow → create/update AI prompts & agents and
  MCP tool registrations via CLI where CFN has no coverage → smoke checks
  (describe each resource, validate flow content accepted). Print a post-deploy
  checklist of the manual steps.
- Run whatever verification is cheap and available: `jq` every JSON artifact,
  `cfn-lint`/`aws cloudformation validate-template`, `shellcheck deploy.sh`,
  Lambda unit tests.

## Manual steps (always surface these in README + deploy.sh output)

Phone number claiming/porting, SAML IdP setup, approved origins for embedded CCP,
instance creation limits (30-day create/delete quota), hosted widget snippet
placement, Contact Lens enablement toggles not covered by the chosen IaC, and any
console-only AI agent features — generate instructions, not fake automation.

## Phase 4 — Handoff

Summarize: what was generated, how to deploy (`./deploy.sh dev`), what remains
manual, and suggested next iteration (e.g. add CI pipeline per `iac-devops.md`
promotion patterns).

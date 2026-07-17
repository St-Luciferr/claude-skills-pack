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
3. **Routing & agents**: queues, business hours + timezone, after-hours behavior,
   overflow/escalation rules, callbacks? Which agent groups exist, which queues does each
   serve, and per-channel concurrency (voice is always 1; chat up to 10)? Where does the
   agent roster come from — a checked-in file, an IdP/HR system, or hand-managed? (The
   identity model from Q2 decides whether users need passwords at all.)
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
│   ├── dev.env, prod.env         # per-env: instance ARN/ID, region, KMS, prefixes
│   └── agents.yaml               # agent roster — operational data, not IaC
├── scripts/
│   └── provision-agents.sh       # idempotent roster → Connect reconciler
├── tags.json                     # stack-level cost/ownership tags, applied via --tags
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
- **Agent provisioning** (`aws-connect-backend-dev` agent; `core-concepts.md` §Users +
  §Routing, `apis-sdks.md` §Admin CRUD). Split by lifetime, not by convenience:
  - **Infrastructure → CloudFormation**: security profiles, routing profiles, hierarchy
    groups, queues, hours. Stable, few, shared.
  - **Users → NOT CloudFormation.** `AWS::Connect::User` exists, but users churn: every
    joiner becomes a stack deploy, console fixes surface as drift, and a stack delete
    mass-offboards. Treat users and hierarchy assignments as operational data.
  Generate `config/agents.yaml` (roster) + `scripts/provision-agents.sh` (idempotent
  reconciler: `SearchUsers` → diff vs desired → `CreateUser` /
  `UpdateUserRoutingProfile` / `UpdateUserSecurityProfiles` / `UpdateUserHierarchy`).
  Non-negotiable:
  - **Reference routing/security profiles and hierarchy by NAME, never by ID** — IDs
    differ per instance, so a dev roster must replay against prod unchanged. Resolve
    names→IDs at runtime (`SearchRoutingProfiles`, `ListSecurityProfiles`,
    `ListUserHierarchyGroups`). This is the flow-ARN portability problem again.
  - **Rate-limit to ≤2 TPS with exponential backoff on ThrottlingException.** Admin CRUD
    is 2/5 TPS *shared account-wide per region* — a parallel loop just collects
    throttles. 500 users (the default per-instance quota) takes 4+ minutes; that is
    expected, not a bug. Never "speed it up" with concurrency.
  - **Passwords**: SAML/directory → omit entirely, and the Connect username MUST equal
    the IdP `RoleSessionName` **exactly, case-sensitive** (a mismatch fails at sign-in
    with a misleading "session expired"). Connect-native → generate a random password
    and force reset; never write one into the repo or the roster file.
  - **`--dry-run` prints the diff and changes nothing**; make it the default for any env
    whose name looks like prod.
  - **Leavers**: report users present in Connect but absent from the roster. Do NOT
    `DeleteUser` unless the user explicitly asked — deleting affects historical
    reporting attribution; confirm the impact against live docs before automating it.
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
- **tags.json** (always generated): a top-level JSON array of `{"Key":..,"Value":..}`
  objects — the CloudFormation `--tags` / `create-stack --tags` shape — carrying
  cost-allocation and ownership tags (at minimum `Name`, `Project`, `Creator`,
  `Deletable`). Ask the user for the values (project name, creator, whether the stack
  is deletable) and fall back to sensible defaults from the solution name. Keep it as a
  single canonical artifact and reference it from deploy.sh (see below) rather than
  hard-coding tags in the script. Example:
  ```json
  [
    { "Key": "Name",      "Value": "evoke-poc" },
    { "Key": "Creator",   "Value": "jenish" },
    { "Key": "Deletable", "Value": "false" },
    { "Key": "Project",   "Value": "evoke-poc" }
  ]
  ```
- **deploy.sh**: one idempotent, re-runnable entrypoint. `set -euo pipefail`. Sources
  per-env `config/$ENV.env` (keep multi-env — do NOT hard-code a single `ENVIRONMENT`).
  **Dispatch subcommands**: `deploy` (default), `cleanup`, `status` (add a domain verb
  like `dial`/`send` only if a demo driver is genuinely useful). Honor env-var overrides
  that let CI skip interactive/creation steps (`CONNECT_INSTANCE_ID`, `AI_ASSISTANT_ID`,
  `AWS_DEFAULT_REGION`, `AUTO_CONFIRM`). Before mutating anything, echo account / region /
  caller ARN and — when interactive and `AUTO_CONFIRM` is unset — prompt to confirm the
  target account+region; a wrong-account deploy is expensive to undo.
  - **deploy order**: seed any SSM params CFN reads at deploy time (see SSM bullet) →
    upload template to S3 + create/update the stack (see CFN bullet) → update Lambda code
    **with retry** (`ResourceConflictException` is normal mid-update; retry ×3 then
    `aws lambda wait function-updated`) → resolve real ARNs/IDs by **NAME** lookup
    (`aws connect list-*`, `list-instances`, `qconnect list-*`) → substitute placeholders
    into flow JSON (envsubst/jq) → `aws connect update-contact-flow-content` per flow →
    **publish** the flows (logs and runtime only see published content) → **associate the
    inbound flow to the claimed number** (`associate-phone-number-contact-flow` — CFN has
    no resource for this, so without it the number rings into nothing) → create/reconcile
    the CLI-only resources (AI prompts & agents, Q assistant, knowledge base, AgentCore
    gateway/target, integration associations) → inject real IDs into the tool Lambdas' env
    and `put-parameter --overwrite` the SSM placeholders → `scripts/provision-agents.sh` →
    smoke checks (describe each resource, validate flow content accepted). Print the
    manual-steps checklist.
  - **Every create step is create-or-select, keyed by NAME**: list existing → reuse and
    capture its id/arn if found → else create and wait for `ACTIVE`/`READY`. This is what
    makes re-runs safe and is the CLI-side analogue of the flow-ARN-by-name rule; never
    assume a resource is absent.
  - **cleanup** mirrors deploy in **reverse dependency order**: gateway target → gateway →
    credential provider → gateway IAM role → assistant associations → assistant →
    knowledge base → integration associations → empty S3 buckets → `delete-stack`
    (`wait stack-delete-complete`) → delete the template bucket. **Never delete resources
    deploy did not create** — above all a pre-existing/shared Connect instance (print the
    manual `delete-instance` command instead). Guard cleanup behind an explicit `yes`
    confirmation.
- **CloudFormation — upload to S3, branch create vs update, recover from wedged states.**
  Connect templates cross the **51,200-byte inline limit** almost immediately
  (`AWS::Connect::ContactFlow`/`ContactFlowModule` embed the whole flow JSON in
  `Content` — `Templates with a size greater than 51,200 bytes must be deployed via an S3
  Bucket`), so the generated deploy.sh must never pass the template inline. Two acceptable
  shapes; **prefer the first** for anything that must survive partial failures and re-runs:
  - **Recommended — explicit S3 upload + create/update-stack** (what real deployers
    converge on). Ensure a **versioned, region-correct** template bucket exists —
    `create-bucket` needs `--create-bucket-configuration LocationConstraint=$REGION` in
    **every region except us-east-1**, which *rejects* that flag → `aws s3 cp` the template
    under a **timestamped key** (`infrastructure-<ts>.yaml`; avoids stale-object confusion)
    → build the `https://s3.$REGION.amazonaws.com/$BUCKET/$KEY` URL → branch: if the stack
    exists, `update-stack --template-url …` (swallow the `No updates are to be performed`
    nonzero exit so `set -e` doesn't abort a no-op deploy), else `create-stack
    --template-url …`; then the matching `aws cloudformation wait
    stack-{create,update}-complete`. **Before that branch, clear a wedged prior attempt:**
    a stack in `ROLLBACK_COMPLETE`/`ROLLBACK_FAILED`/`CREATE_FAILED`/`DELETE_FAILED` cannot
    be updated — `delete-stack` + wait, then create fresh; if the delete itself stalls on
    `DELETE_FAILED` resources (e.g. a custom resource whose Lambda never responded), re-issue
    `delete-stack --retain-resources <LogicalIds>` for exactly those. The
    ROLLBACK_COMPLETE trap bites essentially every first deploy whose initial create
    failed, and `aws cloudformation deploy` is stuck by it just the same — handling it is
    the main reason to prefer this explicit path.
  - **Simpler alternative — `aws cloudformation deploy`**: `--template-file … --s3-bucket
    $BUCKET --capabilities CAPABILITY_NAMED_IAM …`. It uploads the template for you and is
    create-or-update in one call, but it does **not** auto-recover from `ROLLBACK_COMPLETE`
    and returns nonzero on "no changes". Fine for small, low-churn stacks.
- **Tagging — `--tags file://tags.json` on BOTH create and update.** On the recommended
  path, `create-stack`/`update-stack` take the `tags.json` array **directly**
  (`--tags file://tags.json`) — no conversion, spaces in values are fine. **Pass it on
  `update-stack` too, not only `create-stack`:** CloudFormation *replaces* the tag set on
  update, so omitting `--tags` on a later deploy silently strips every tag from the stack
  and its resources. (Only if you fall back to `aws cloudformation deploy` do you need the
  `Key=Value` form — `--tags $(jq -r '.[]|"\(.Key)=\(.Value)"' tags.json)`, values
  space-free.) Stack-level tags propagate to every taggable resource CloudFormation creates.
- **SSM seed-then-overwrite for deploy-time param resolution.** When the template reads a
  value via a `{{resolve:ssm:…}}` reference or an SSM-typed parameter that only *exists
  after* a CLI-created resource (the Connect instance id, a Bedrock KB id), seed that SSM
  parameter with a `PENDING` placeholder **before** the stack step so create/update doesn't
  fail on a missing param, then `put-parameter --overwrite` the real value once the CLI
  resource exists (and inject the same value into the tool Lambdas' env). Call out service
  mismatches in the output — e.g. a `qconnect` knowledge-base id is NOT a
  `bedrock-agent-runtime` KB id and won't work in a `searchKnowledgeBase` Lambda.
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

Point the user at **`/aws-connect-verify`** to confirm the deployment actually works
(flow published & associated to the number, Lambda associations, agents on the right
routing profile) and to trace a test contact through the flow logs. A deploy that
succeeds is not the same as a contact center that answers.

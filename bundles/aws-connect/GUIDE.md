# Build an Amazon Connect contact center from scratch

An end-to-end walkthrough: from an empty AWS account to a contact center that answers
a real phone call, routes it to a logged-in agent, and records what happened.

This guide lives in the bundle and is **not** installed into your `.claude/` — it's
documentation for you, not context for Claude. Read it here (or on GitHub); the skills
do the work once installed.

**Worked example used throughout — "Acme Support":** inbound voice + chat, an IVR menu
(1 = Sales, 2 = Support), two queues, business hours with an after-hours message, a
Lambda that looks the caller up by phone number, two agents, and a CTR pipeline. Dev and
prod environments.

---

## 0. Prerequisites

| Need | Check |
| --- | --- |
| AWS account with admin-ish rights | `aws sts get-caller-identity` |
| AWS CLI v2 configured | `aws --version` |
| A Connect-supported region | Connect is **not** in every region — pick e.g. `us-east-1`, `us-west-2`, `eu-west-2` |
| The bundle installed | `claude-packs install aws-connect --project .` then **restart Claude Code** |

Two quotas that bite before you start (see `references/core-concepts.md`):

- **2 Connect instances per region per account** (adjustable).
- **100 instance creations + deletions per rolling 30 days** — a hard limit. Don't
  script create/destroy loops while experimenting.

Budget note: a claimed DID costs a few $/month and stays billable until you *release* it,
not merely when you delete the stack.

---

## 1. Point Claude Code at the work

The `aws-connect` skill auto-activates on any Amazon Connect task — you don't invoke it.
Just describe what you want. For a from-scratch build, use the generator skill:

```
/aws-connect-build
```

It runs four phases: **interview → design → generate → handoff**. Don't skip the
interview; every later artifact keys off it.

---

## 2. Phase 1 — The interview

It asks about channels, instance, routing, self-service/AI, integrations, recording,
environments, and compliance. Answering "I don't know" is fine — it'll suggest defaults.
For Acme Support, the answers are:

| Question | Answer |
| --- | --- |
| Channels | Voice + chat, inbound only |
| Instance | Create new via IaC; Connect-native identity |
| Routing | Queues `Sales`, `Support`; Mon–Fri 09:00–17:00 `America/New_York`; after-hours → message + disconnect |
| Self-service & AI | IVR menu only for now (no Lex/AI yet) |
| Integrations | One Lambda: customer lookup by caller number |
| Recording & analytics | Call recording on; CTR → Kinesis → S3 |
| Environments | `dev` + `prod`, same account, `us-east-1`, prefix `acme` |
| Compliance | None special |

Output: `docs/REQUIREMENTS.md`. **Read it before continuing** — everything downstream
inherits its mistakes.

---

## 3. Phase 2 — Design

Delegates to the `aws-connect-architect` agent → `docs/DESIGN.md`: flow inventory,
queue/routing-profile/hours model, Lambda contracts, and — importantly — the list of
things that **can't** be automated.

Sanity-check the design against your mental model. Cheap to fix here, expensive after
deploy. Ask follow-ups in plain language:

```
In DESIGN.md, what happens to a caller who picks Sales at 2am?
```

---

## 4. Phase 3 — Generate

Delegates flows to `aws-connect-flow-builder` and IaC/Lambdas to
`aws-connect-backend-dev`. You get:

```
acme-support/
├── docs/REQUIREMENTS.md, DESIGN.md
├── infra/template.yaml          # CloudFormation
├── flows/*.flow.json            # ARNs as ${Placeholders}, never hard-coded
├── lambdas/customer-lookup/     # + unit tests
├── config/dev.env, prod.env
├── tags.json                    # cost/ownership tags, applied via CFN --tags
└── deploy.sh
```

**Why the placeholders matter:** exported flow JSON embeds environment-specific ARNs
(queues, prompts, Lambdas). Flow JSON is *not* portable between instances — `deploy.sh`
resolves real ARNs by name lookup and substitutes them per environment. This is the
single most common way hand-built Connect deployments break.

Verify before deploying:

```bash
jq . flows/*.flow.json                              # valid JSON
aws cloudformation validate-template --template-body file://infra/template.yaml
shellcheck deploy.sh
```

---

## 5. Deploy

```bash
./deploy.sh dev              # deploy (default)
./deploy.sh dev status       # what's currently deployed
./deploy.sh dev cleanup      # tear it all down in reverse order
```

Deploy packages Lambdas → uploads the CFN template to S3 and creates/updates the stack →
resolves ARNs by name → substitutes placeholders into flow JSON → pushes & publishes flow
content → associates the flow to the number → reconciles CLI-only resources (Q assistant,
KB, gateway) → smoke-checks → prints a manual-steps checklist. Every step is
create-or-select, so re-running is safe.

> **CFN template over 51,200 bytes?** CloudFormation refuses an *inline* template larger
> than that. Connect stacks hit it fast because flow JSON is embedded inline in
> `AWS::Connect::ContactFlow.Content`. The generated `deploy.sh` sidesteps it by uploading
> the template to S3 (a versioned bucket it creates) and calling `create-stack`/
> `update-stack --template-url`, which also lets it **auto-recover a stack wedged in
> `ROLLBACK_COMPLETE`** from a failed first create — delete-and-recreate rather than
> erroring out. (The simpler `aws cloudformation deploy --s3-bucket` works too but can't
> unstick a rolled-back stack.)

**Turn on flow logs now**, before you need them. This takes **two** steps — missing the
second is a classic dead end:

1. Enable flow logging on the instance (creates log group `/aws/connect/<instance-alias>`), **and**
2. add a **Set logging behavior** block (`UpdateFlowLoggingBehavior: Enabled`) inside the flow.

Logs are only emitted for **published** flows. Ask:

```
Enable flow logging on the acme dev instance and make sure each flow sets logging behavior
```

---

## 6. The manual steps AWS won't let you automate

The generated README lists these; here's why each is manual.

**Claim a phone number.** CloudFormation's `AWS::Connect::PhoneNumber` gives you a
*random* number matching country/type/prefix. To choose a specific one you must use the
API:

```bash
aws connect search-available-phone-numbers \
  --target-arn <instance-arn> --phone-number-country-code US \
  --phone-number-type DID --phone-number-prefix +1206

aws connect claim-phone-number \
  --target-arn <instance-arn> --phone-number "+1206XXXXXXX"
```

⚠️ Deleting the CFN resource **releases** the number back to the pool — usually
unrecoverable. Set `DeletionPolicy: Retain` on prod numbers.

**Associate the number with your inbound flow.** CFN has *no* resource for this:

```bash
aws connect associate-phone-number-contact-flow \
  --phone-number-id <id> --instance-id <id> --contact-flow-id <inbound-flow-id>
```

**Also manual:** SAML IdP setup, approved origins for an embedded CCP, number porting,
and some Contact Lens/telephony toggles. Ask Claude for exact steps:

```
Walk me through the manual steps for the acme dev deployment
```

---

## 7. Create your agents

Every instance ships with defaults: **BasicQueue**, **Basic routing profile**, default
flows, and security profiles **Admin / Agent / CallCenterManager / QualityAnalyst**.

The model, in dependency order:

```
Security profile  (what they can do in the UI)   ─┐
Routing profile   (which queues they receive)    ─┼─→  User (agent)
Hierarchy group   (optional, for reporting)      ─┘
```

A user has **exactly one routing profile** and **one or more security profiles**. The
routing profile is the lever: it links queues → agents, sets per-channel concurrency
(voice is always 1; chat up to 10), and changing it instantly re-scopes the whole group.

`/aws-connect-build` generates this for you — the profiles go in CloudFormation, and the
roster lands in `config/agents.yaml` with an idempotent reconciler:

```yaml
# config/agents.yaml
users:
  - username: jdoe@acme.com        # with SAML: MUST equal the IdP RoleSessionName, exactly
    first_name: Jane
    last_name: Doe
    routing_profile: Acme Agents   # by NAME — IDs differ per environment
    security_profiles: [Agent]
```

```bash
./scripts/provision-agents.sh dev --dry-run   # show the diff
./scripts/provision-agents.sh dev             # apply
```

Re-run it any time; it reconciles rather than recreates. `deploy.sh` calls it for you.

Three things that surprise people:

- **Why users aren't in CloudFormation.** `AWS::Connect::User` exists, but
  `references/iac-devops.md` advises treating users and hierarchy assignments as
  **operational data, not infrastructure**. Otherwise every joiner is a stack deploy,
  every console fix is drift, and a stack delete mass-offboards your agents.
- **SAML doesn't skip this step.** Federation handles *authentication*; Connect still
  needs a user record, and the username must equal the IdP `RoleSessionName`
  **exactly, case-sensitive**. A mismatch fails at sign-in with a misleading
  "session expired".
- **Provisioning is slow on purpose.** Admin APIs are throttled at 2/5 TPS shared
  account-wide, so ~500 agents takes 4+ minutes. The script rate-limits and backs off;
  don't "fix" it with parallelism.

---

## 8. Test it end to end

Start with the automated wiring check — it catches the majority of "deployed but dead"
cases before you pick up a phone:

```
/aws-connect-verify
```

It confirms the flow is **published** and associated to your number, Lambda/Lex
associations exist, the routing profile serves the queue, agents are on it, hours/timezone
are right, and logging is on. Then, by hand:

1. **Call the number.** Confirm the IVR answers and the menu works.
2. **Log an agent in** to the CCP (Connect console → *Access URL*), set status
   **Available**, pick Sales, confirm the call arrives.
3. **After hours?** Temporarily narrow the hours of operation rather than waiting until
   2am.
4. **Check the contact record.** CTRs land in your Kinesis→S3 pipeline within a couple of
   minutes — but they're **re-emitted on update** and aren't final until the agent leaves
   ACW. Dedupe by `ContactId`, keeping the greatest `LastUpdateTimestamp`.

```
Place a test contact through the acme dev inbound flow and show me its CTR
```

---

## 9. When it breaks

```
/aws-connect-verify
```

Give it the symptom and the ContactId if you have one ("the 2pm call to Sales dropped
after the menu"). It runs the wiring checks, traces the contact through the flow logs,
and names the block that failed.

The usual suspects, if you'd rather look yourself:

| Symptom | Cause to check first |
| --- | --- |
| Call connects then drops instantly | An action with **no `Errors` transition**. Unhandled error = disconnect. |
| Lambda data missing later in the flow | `$.External.*` is **wiped by the next Lambda invocation** — copy it to contact attributes with *Set contact attributes*. |
| Lambda times out | Flow-invoked Lambdas must answer in **~8 s** and return a flat string map (unless JSON mode is on). |
| Call never reaches an agent | Routing profile doesn't include the queue, or no agent is **Available**. |
| Block missing / behaves oddly in chat | Many blocks are **voice-only** — check channel support per block. |
| Flow works in dev, breaks in prod | An ARN was hard-coded instead of substituted. |

Flow logs are the ground truth. Each entry is JSON with `ContactId`, flow name, block
type, parameters, and results — trace one contact across flows in CloudWatch Logs
Insights:

```
Trace ContactId <id> through the flow logs and tell me which block failed
```

---

## 10. Iterate

The generator is for scaffolding; day-two work is conversational — the skill stays active
and the agents are delegated to automatically:

```
Add a Lex bot to the IVR so callers can say "order status" instead of pressing a key
Add a callback option when the Support queue wait exceeds 5 minutes
Embed the CCP in our React admin app
Add Q in Connect agent assist with an MCP tool that reads our order API
Promote the dev flows to prod
```

Those route to `aws-connect-flow-builder`, `aws-connect-backend-dev`, and
`aws-connect-frontend-dev` respectively.

---

## 11. Keep the knowledge current

Amazon Connect ships constantly. The reference files carry a `> Last updated:` line, and
anything volatile (quotas, pricing, region availability) newer than that date should be
confirmed against live AWS docs before it's load-bearing.

```
/aws-connect-update
```

Monthly is a good cadence. It pulls new announcements since the changelog baseline,
patches the affected references, and prepends changelog entries.

---

## Where things live

| You want | Look at |
| --- | --- |
| Instances, users, queues, routing, quotas, IAM | `references/core-concepts.md` |
| Flow JSON, block catalog, attributes, flow logs | `references/contact-flows.md` |
| APIs/SDKs, TPS limits, code examples | `references/apis-sdks.md` |
| CCP, Streams, ChatJS, widget, workspace apps | `references/frontend-streams.md` |
| Lambda, Lex, Q in Connect, Contact Lens, Cases | `references/ai-integrations.md` |
| CTRs, event streams, metrics, data lake | `references/data-analytics.md` |
| CFN/CDK/Terraform, flow-as-code, CI/CD | `references/iac-devops.md` |

Installed at `.claude/skills/aws-connect/references/` (project) or
`~/.claude/skills/aws-connect/references/` (user-level). You rarely need to open them —
the skill loads the right one per task.

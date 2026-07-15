---
name: aws-connect-verify
description: >
  Verify and troubleshoot a deployed Amazon Connect solution. Checks that a deployment is
  actually wired up (flow published & associated to the number, Lambda/Lex associations,
  routing profiles, agents, hours, flow logging), traces a contact through CloudWatch flow
  logs by ContactId, inspects the contact record (CTR), and diagnoses why a call dropped,
  never reached an agent, lost Lambda data, or behaved differently in prod than dev. Use
  after deploying a Connect solution, or when a contact did the wrong thing.
---

# Verify / troubleshoot an Amazon Connect deployment

Two modes: **verify** ("did the deploy actually work?") and **diagnose** ("this contact
misbehaved — why?"). Work top-down; most failures are wiring, not flow logic, and the
static checks in Phase 1 are far cheaper than reading logs.

Load `references/contact-flows.md` (§11 flow logs, §12 best practices) and
`references/data-analytics.md` (CTR semantics) from the aws-connect skill as needed.
Establish the target first: which environment, instance ID/alias, and region
(`config/<env>.env` if the project came from `/aws-connect-build`).

## Phase 1 — Static wiring checks

Run these before touching logs. Each maps to a real failure mode; report ✅/❌ per line.

| Check | How | Fails when |
|---|---|---|
| Flow exists and is **published** | `aws connect describe-contact-flow` | Flow logs are only emitted for published flows; an unpublished edit is invisible at runtime |
| Number → flow association | `aws connect describe-phone-number`, `aws connect get-flow-association` | CFN has **no** resource for this — a claimed number is wired to nothing until `associate-phone-number-contact-flow` runs |
| Lambda associations | `aws connect list-lambda-functions` | A flow's Invoke Lambda fails unless the ARN is associated with the instance (≤50/instance) |
| Lex bot associations | `aws connect list-bots` | Get customer input with a bot fails |
| Routing profile → queues | `aws connect describe-routing-profile` | Contacts queue forever: the profile doesn't serve that queue |
| Agents exist on that profile | `aws connect search-users` | Nobody can receive the contact |
| Hours of operation | `aws connect get-effective-hours-of-operations` | After-hours branch taken unexpectedly (check the **timezone**) |
| Flow logging enabled | `aws connect describe-instance` → attribute `CONTACTFLOW_LOGS` | Phase 2 has nothing to read |
| Recording / CTR storage | `aws connect list-instance-storage-configs` | No CTRs, no recordings |

If the project has flow JSON in the repo, diff deployed content against it
(`describe-contact-flow` → `.Content`) — drift from console edits is common and silent.

## Phase 2 — Trace a contact

Flow logs need **two** things, and missing the second is a classic dead end:

1. Instance-level flow logging on (creates log group `/aws/connect/<instance-alias>`), **and**
2. a **Set logging behavior** block (`UpdateFlowLoggingBehavior: Enabled`) inside the flow.

Logging behavior carries into subsequent segments until overridden. Only **published**
flows log.

Get the ContactId (from the CTR, the CCP, or `search-contacts`), then trace it across all
flows in CloudWatch Logs Insights on `/aws/connect/<instance-alias>`:

```
fields @timestamp, ContactFlowName, ContactFlowModuleType, Parameters, Results
| filter ContactId = "<contact-id>"
| sort @timestamp asc
| limit 200
```

Read it as a sequence: the **last block before the gap** is where it died. Compare
`Parameters` (what the block was told) against `Results` (what it got back).

Then pull the contact record. CTR semantics that will mislead you if ignored:
- **Re-emitted on update** — each re-emission is a *full record*, not a delta. Dedupe by
  `ContactId`, keep the greatest `LastUpdateTimestamp` ("last updated wins").
- A record is **not final until the agent leaves ACW**, and can stream before
  recording/Contact Lens fields populate. Don't diagnose "missing recording" from an
  early copy.

⚠️ Log entries include parameter values, **including FlowAttributes**. If a flow captures
PII/PCI, expect logging to be deliberately disabled around those blocks — absence of logs
there is by design, not a bug.

## Phase 3 — Symptom → first suspect

| Symptom | Check first |
|---|---|
| Call connects, then drops instantly | An action with **no `Errors` transition** — an unhandled error disconnects the contact. Also `NoMatchingCondition` missing on Compare/input blocks. |
| Lambda data gone later in the flow | `$.External.*` holds only the **last** Lambda response and is wiped by the next invocation — it must be copied to contact attributes with *Set contact attributes*. |
| Lambda errors / times out | Flow-invoked Lambdas must return in **~8 s** and respond with a **flat string map** unless JSON response mode is on. Business "not found" must return a value, not throw. |
| Never reaches an agent | Routing profile lacks the queue; no agent Available; or **Check staffing** / hours branch taken. |
| Block missing or odd in chat/task | Many blocks are **voice-only** — check the channel-support matrix. |
| Works in dev, fails in prod | A hard-coded ARN survived substitution, or the prod flow wasn't republished after content update. |
| Attributes vanish across a transfer | `$.FlowAttributes.*` is **scoped to the current flow** — not in the CTR, CCP, or passed to modules/transferred flows. |
| No flow logs at all | Instance toggle on but **Set logging behavior** block missing, or the flow isn't published. |
| Athena/Glue chokes on attributes | Attribute names must be camelCase, alphanumeric + periods — no spaces/special chars. |

## Phase 4 — Report

State plainly: what was checked, what passed, the specific block/resource that failed, the
evidence (log line, API response, CTR field), and the fix. If a check couldn't run (no AWS
credentials, logging off, flow unpublished), say so — don't infer a pass from silence.

Prefer verifying against a **dev** instance. Never enable/disable logging or edit flows on
a prod instance without asking first.

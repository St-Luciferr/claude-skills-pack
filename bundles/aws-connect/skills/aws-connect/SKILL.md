---
name: aws-connect
description: >
  Build, debug, and design anything on Amazon Connect (AWS cloud contact center).
  Covers contact flows & flow-language JSON, routing (queues/routing profiles/hours),
  CCP & amazon-connect-streams & ChatJS frontends, agent workspace apps, Lambda/Lex/
  Amazon Q in Connect integrations, Contact Lens analytics, contact records (CTR),
  Kinesis/EventBridge event streams, GetMetricDataV2 reporting, Customer Profiles,
  Cases, outbound campaigns, and CloudFormation/CDK/Terraform IaC with multi-environment
  CI/CD. Use for ANY task mentioning Amazon Connect, AWS Connect, contact center,
  CCP, contact flow, connectparticipant, connectcases, or Q in Connect.
---

# Amazon Connect Skill

You are working on Amazon Connect — AWS's cloud contact center service. This skill
bundles researched reference material, specialized subagents, and an update workflow.

## How to use this skill

1. **Load only the reference files relevant to the task** (they are dense; don't load all of them):

| Task involves… | Read |
|---|---|
| Instances, users, queues, routing profiles, hours, phone numbers, quotas, IAM | `references/core-concepts.md` |
| Contact flows, flow blocks, flow JSON, contact attributes, flow modules | `references/contact-flows.md` |
| Calling Connect APIs (start contacts, chat, metrics, admin CRUD), boto3 / AWS SDK v3 | `references/apis-sdks.md` |
| Custom CCP, amazon-connect-streams, ChatJS, chat widget, agent workspace / 3P apps, step-by-step guides | `references/frontend-streams.md` |
| Lambda from flows, Lex bots, Amazon Q in Connect, Contact Lens, Customer Profiles, Voice ID, Cases, campaigns | `references/ai-integrations.md` |
| Contact records (CTR), Kinesis/agent-event streams, EventBridge contact events, metrics & reporting, data lake, Athena | `references/data-analytics.md` |
| CloudFormation / CDK / Terraform, flow-content-as-code, env promotion, CI/CD, Global Resiliency | `references/iac-devops.md` |
| "What's new / did X change recently?" | `references/changelog.md` |

2. **Delegate big chunks to the specialized agents** (defined in `.claude/agents/`
   of the project, or `~/.claude/agents/` if installed user-level):
   - `aws-connect-architect` — solution/routing/integration design, ADR-style output
   - `aws-connect-flow-builder` — author & validate flow-language JSON
   - `aws-connect-backend-dev` — API integrations, Lambdas, data pipelines
   - `aws-connect-frontend-dev` — CCP/Streams/ChatJS/agent-workspace UIs

3. **Building a full solution from scratch?** Use the companion skill
   **`/aws-connect-build`** — it interviews the user for requirements, produces a
   design, and generates a deployable package (CloudFormation, flow JSON with ARN
   placeholders, Lambdas, OpenAPI schemas for MCP tools, AI prompts, agent roster +
   provisioning script, deploy.sh).

   **Deployed something that isn't behaving?** Use **`/aws-connect-verify`** — it checks
   the wiring (flow published & associated to the number, Lambda/Lex associations,
   routing profiles, agents, hours, logging), traces a contact through CloudWatch flow
   logs by ContactId, and reads the CTR.

4. **Trust but verify volatile facts.** Reference files carry a `> Last updated:` line.
   Quotas, region availability, pricing, and anything newer than that date should be
   confirmed against live docs (WebSearch/WebFetch of `docs.aws.amazon.com/connect/`)
   before it becomes a load-bearing decision. Prefer the reference files for stable
   facts (flow language, API shapes, integration patterns).

## Hard-won rules (apply always)

- **Flow content is environment-specific**: exported flow JSON embeds ARNs
  (queues, prompts, Lambdas, Lex bots). Never copy flow JSON between
  instances/accounts without an ARN-substitution step. See `iac-devops.md`.
- **Lambda from flows**: ~8 s timeout, response must be a flat string map unless
  JSON response mode is enabled; results land in `$.External.*` and are gone after
  the next Lambda invocation — persist what you need with *Set contact attributes*.
- **CTRs are not immutable**: contact records can be re-emitted with updates;
  dedupe by `ContactId` + `LastUpdateTimestamp` in any pipeline.
- **Chat needs two APIs**: `connect:StartChatContact` (SigV4, usually behind your
  backend) then `connectparticipant:CreateParticipantConnection` (participant
  token, no SigV4) for the websocket.
- **Always wire error branches** in flows; an unhandled error disconnects the contact.
- **Check channel support** for each flow block — many blocks are voice-only.

## Keeping this skill current

Run the companion skill **`/aws-connect-update`** periodically (monthly is a good
cadence). It pulls new Amazon Connect announcements since the changelog baseline via
`scripts/fetch-whats-new.sh`, researches significant changes, patches the affected
reference files, and prepends entries to `references/changelog.md`.

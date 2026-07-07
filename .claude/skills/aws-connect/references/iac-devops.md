# Amazon Connect — IaC, CI/CD & Multi-Environment Management

> Last updated: 2026-07 (baseline)

## Decision guide (TL;DR)

- **One Connect instance per environment, one AWS account per environment** (AWS prescriptive guidance). Never share a prod instance with dev/test — most Connect resources are instance-scoped and have no namespacing.
- **CloudFormation coverage is now broad** (35+ `AWS::Connect::*` types as of mid-2026, including flows, flow versions/aliases, test cases, data tables). CDK has **L1 only** (`CfnXxx`). Terraform `hashicorp/aws` covers the core admin objects but has real gaps — fill them with the `hashicorp/awscc` provider (auto-generated from the same CloudFormation/Cloud Control schemas).
- **The hard problem is flow content**: flow JSON embeds environment-specific ARNs (queues, prompts, Lambdas, other flows). Every serious pipeline is built around a substitution or indirection strategy — see "Flow content as code".
- Some things **cannot be IaC'd**: claiming a *specific* phone number, `ReplicateInstance`, `UpdateTrafficDistribution` (traffic shifting), instance create/delete beyond the 30-day quota. Plan manual/scripted steps for these.

---

## CloudFormation coverage

Complete `AWS::Connect::*` resource type list (CloudFormation Template Reference, checked 2026-07):

| Resource type | Notes |
|---|---|
| `AWS::Connect::Instance` | Still flagged "preview release, subject to change" in docs. See gotchas below. |
| `AWS::Connect::InstanceStorageConfig` | S3/Kinesis/Firehose per resource type (`CALL_RECORDINGS`, `CHAT_TRANSCRIPTS`, `CONTACT_TRACE_RECORDS`, `AGENT_EVENTS`, `SCHEDULED_REPORTS`, etc.). One resource per storage type. |
| `AWS::Connect::ContactFlow` | `Content` (flow-language JSON string, 1–256,000 chars), `InstanceArn`, `Name` (≤127), `Type` (replacement on change!), `State: ACTIVE\|ARCHIVED`. `Ref` → flow name; `Fn::GetAtt ContactFlowArn` → ARN. |
| `AWS::Connect::ContactFlowModule` | Reusable module; same content model. |
| `AWS::Connect::ContactFlowVersion` | Immutable published version snapshot. Per API docs, `CreateContactFlowVersion` is currently documented as supporting `CAMPAIGN`-type flows; console version history/rollback exists for all flow types. Verify before relying on it for non-campaign flows. |
| `AWS::Connect::ContactFlowModuleVersion` / `ContactFlowModuleAlias` | Module versioning + named aliases (launched Nov 2025). Alias→version indirection lets you promote a module version without touching consuming flows — the closest thing Connect has to Lambda aliases. |
| `AWS::Connect::HoursOfOperation` | Includes overrides (holiday hours) in current schema. |
| `AWS::Connect::PhoneNumber` | *Claims* a number. See "PhoneNumber gotchas". |
| `AWS::Connect::Queue` | `HoursOfOperationArn` required; `OutboundCallerConfig`, `MaxContacts`, `QuickConnectArns`, `Status`. |
| `AWS::Connect::QuickConnect` | USER / QUEUE / PHONE_NUMBER types. |
| `AWS::Connect::RoutingProfile` | `DefaultOutboundQueueArn`, `MediaConcurrencies`, `QueueConfigs` (queue/channel/priority/delay), `AgentAvailabilityTimer`. |
| `AWS::Connect::Rule` | Contact Lens / EventBridge rules (rules-language JSON `Function` string — same templating problem as flows). |
| `AWS::Connect::SecurityProfile` | Permission strings; also tag-based access-control keys. |
| `AWS::Connect::TaskTemplate` | Task template fields/constraints; references a flow ARN. |
| `AWS::Connect::TrafficDistributionGroup` | Creates the TDG only; traffic *shifting* is API-only. |
| `AWS::Connect::User` | Agent/admin users: `Username`, `SecurityProfileArns`, `RoutingProfileArn`, `PhoneConfig`, optional `Password` (CONNECT_MANAGED), `HierarchyGroupArn`, `IdentityInfo`. |
| `AWS::Connect::UserHierarchyGroup` / `UserHierarchyStructure` | Structure is a singleton per instance (level names); groups form the tree. |
| `AWS::Connect::View` / `ViewVersion` | Step-by-step guides (agent workspace views); view content is JSON — same env-substitution concerns. |
| `AWS::Connect::IntegrationAssociation` | Associates `LEX_BOT`, `LAMBDA_FUNCTION`, `APPLICATION` (3P apps), analytics, etc. **Required before a flow can invoke a Lambda/Lex bot.** |
| `AWS::Connect::EvaluationForm` | Agent evaluation forms (items/scoring JSON). |
| `AWS::Connect::PredefinedAttribute` | Predefined attributes (values list) for routing/proficiencies. |
| `AWS::Connect::Prompt` | Prompt from an S3 URI (`S3Uri`) — finally lets you IaC audio prompts. |
| `AWS::Connect::AgentStatus` | Custom agent statuses. |
| `AWS::Connect::ApprovedOrigin` | CCP allowlisted origins (was console/API-only for years). |
| `AWS::Connect::SecurityKey` | Instance PEM keys for encryption. |
| `AWS::Connect::TestCase` | Native flow test cases (testing & simulation, GA 2025–2026). Test definitions as code — see "Testing flows". |
| `AWS::Connect::DataTable` / `DataTableAttribute` / `DataTableRecord` | Connect-native config tables (2026). Useful for env config lookups from flows without DynamoDB. |
| `AWS::Connect::EmailAddress` | Email channel addresses. |
| `AWS::Connect::Notification` | Notification configuration (new 2026; check current schema). |
| `AWS::Connect::Workspace` | Agent workspace configuration (new 2026; check current schema). |

### Instance gotchas (`AWS::Connect::Instance`)

- **30-day quota**: Connect limits total instance creates+deletes per 30 days; exceeding it blocks further create/delete for 30 days. Do not put instance creation in a frequently torn-down stack. Failed stack rollbacks that delete/recreate instances burn this quota.
- `IdentityManagementType` (`SAML | CONNECT_MANAGED | EXISTING_DIRECTORY`), `InstanceAlias`, `DirectoryId` all cause **replacement** on change — i.e., a new instance, losing everything inside. Alias is globally unique per partition.
- `Attributes` (required) toggles features: `InboundCalls`, `OutboundCalls`, `ContactflowLogs`, `ContactLens`, `AutoResolveBestVoices`, `UseCustomTTSVoices`, `EarlyMedia`.
- `Fn::GetAtt`: `Arn`, `Id`, `ServiceRole`, `InstanceStatus`, `CreatedTime`. Everything else in the template takes `InstanceArn` (CFN) — note Terraform's aws provider takes `instance_id` instead.
- Creating the instance does **not** attach storage — pair with `InstanceStorageConfig` resources or call recording/CTR export silently doesn't exist.
- Common pattern: create the instance **once per environment in its own minimal stack** (or even manually/CLI) and pass `InstanceArn` as a parameter/SSM value to all other stacks. Keeps the blast radius of `cdk destroy`/`terraform destroy` away from the instance.

### PhoneNumber gotchas (`AWS::Connect::PhoneNumber`)

- Properties: `TargetArn` (instance **or** traffic-distribution-group ARN; updatable without replacement — this is how you move a number onto a TDG), `CountryCode`, `Type` (`TOLL_FREE|DID|UIFN|SHARED|THIRD_PARTY_DID|THIRD_PARTY_TF|SHORT_CODE`), `Prefix` (e.g. `+1206`), `SourcePhoneNumberArn` (import from AWS End User Messaging). `GetAtt`: `Address` (E.164), `PhoneNumberArn`.
- You get a **random available number** matching country/type/prefix — you cannot claim one specific number from search results via CFN/Terraform. `SearchAvailablePhoneNumbers` + `ClaimPhoneNumber` (API) is the only way to pick an exact number.
- **Deleting the resource releases the number** — usually unrecoverable (goes back to the pool; cooldown applies). Set `DeletionPolicy: Retain` / Terraform `prevent_destroy = true` on prod numbers. `CountryCode`/`Type`/`Prefix` changes are *replacement* = new number.
- Number→flow mapping: CFN has no association resource; use the console, `AssociateFlow`/inbound number config APIs, or Terraform's `aws_connect_phone_number_contact_flow_association`.

### What CANNOT be managed via CloudFormation

- **`ReplicateInstance`** (Global Resiliency replica creation) — API/CLI only.
- **`UpdateTrafficDistribution`** (shifting voice/sign-in traffic percentages across a TDG) — a runtime operation, not a declarative property.
- **Claiming a specific phone number**; **porting** (carrier process + support ticket).
- Flow **rollback** to a previous version (console/API operation).
- Some instance settings remain console-only (e.g., certain telephony/contact-lens toggles, outbound campaign config lives in `AWS::ConnectCampaignsV2::Campaign`, a separate namespace).
- Users at scale: CFN `User` works but SAML/SCIM-provisioned users usually shouldn't be IaC'd; treat users/agent-hierarchy assignments as operational data, not infrastructure.
- **Drift**: admins editing flows/queues in the console silently diverges from templates. CFN drift detection covers Connect types unevenly; Terraform will show a full-content diff on next plan and clobber console edits. Decide a single source of truth; in prod, remove flow-edit permissions from security profiles and force changes through the pipeline.

---

## CDK

- `aws-cdk-lib.aws_connect` contains **only auto-generated L1 constructs** (`CfnInstance`, `CfnContactFlow`, `CfnQueue`, `CfnRoutingProfile`, `CfnRule`, `CfnTaskTemplate`, `CfnContactFlowModule`, …). The module README states: "There are no official hand-written (L2) constructs for this service yet."
- AWS Contact Center blog (Mar 2026, "Managing Amazon Connect flows as Code with AWS CDK") describes the internal Amazon Customer Service approach: a TypeScript library of **L2-style flow builders** (type-safe action-block builders, composite/reusable blocks, build-time validation, bidirectional TS↔flow-JSON transformation) layered on the L1 `CfnContactFlow`. As of writing the library itself is not published as a public npm package — treat it as an architecture pattern: build flow content as typed TS objects, embed CDK tokens for ARNs, `JSON.stringify` at synth.
- Community constructs exist on constructs.dev (search "connect") but none are widely adopted/maintained enough to be a default recommendation — vet before use.
- Because everything is L1, all values are strings/POJOs matching the CFN schema exactly; you get no validation until deploy (or publish-time flow validation). Add your own JSON-schema/flow-language checks in the build step.

---

## Terraform

### hashicorp/aws provider — `aws_connect_*` (verified against provider source, v6.x 2026-07)

Resources:
`aws_connect_instance`, `aws_connect_instance_storage_config`, `aws_connect_contact_flow`, `aws_connect_contact_flow_module`, `aws_connect_hours_of_operation`, `aws_connect_queue`, `aws_connect_quick_connect`, `aws_connect_routing_profile`, `aws_connect_security_profile`, `aws_connect_user`, `aws_connect_user_hierarchy_group`, `aws_connect_user_hierarchy_structure`, `aws_connect_phone_number`, `aws_connect_phone_number_contact_flow_association`, `aws_connect_bot_association` (Lex), `aws_connect_lambda_function_association`, `aws_connect_vocabulary`.

Data sources mirror the above plus `aws_connect_prompt` (lookup prompt ARN by name — prompts themselves are **not creatable** with this provider).

Notes:
- Most resources take `instance_id` (not ARN) and export composite IDs like `instance_id:resource_id` (import syntax: `terraform import aws_connect_queue.x <instance_id>:<queue_id>`).
- `aws_connect_contact_flow`: `content` (JSON string) **or** `filename` + `content_hash = filemd5(...)`; `type` defaults `CONTACT_FLOW`, changing it forces new. Use `jsonencode()`/`templatefile()` for content.
- `aws_connect_phone_number`: same claim semantics/warnings as CFN (`target_arn`, `country_code`, `type`, `prefix`); destroy releases the number.
- `aws_connect_user`: `password` only for CONNECT_MANAGED; stored in state — use SAML or ignore_changes.

### Gaps in hashicorp/aws → use `hashicorp/awscc`

No `aws_connect_*` resource exists for: **Rule, TaskTemplate, View/ViewVersion, EvaluationForm, PredefinedAttribute, TrafficDistributionGroup, AgentStatus, Prompt (create), IntegrationAssociation (APPLICATION type), ContactFlowVersion, ContactFlowModuleAlias/Version, TestCase, DataTable\*, EmailAddress, ApprovedOrigin, SecurityKey**.

The `awscc` provider is auto-generated from Cloud Control API / CFN schemas, so its coverage tracks the CFN table above: `awscc_connect_rule`, `awscc_connect_task_template`, `awscc_connect_view`, `awscc_connect_evaluation_form`, `awscc_connect_traffic_distribution_group`, `awscc_connect_predefined_attribute`, `awscc_connect_contact_flow_version`, etc. Mixing providers in one config is supported and is the recommended pattern (AWS + HashiCorp joint guidance: "aws and awscc better together"). awscc caveats: ARN-based identifiers (not `instance_id:` composites), weaker plan-time validation, occasional schema round-trip quirks (e.g., properties the service normalizes cause perpetual diffs) — pin provider versions and test `plan` idempotency.

---

## Flow content as code

### Format

- Flow language: JSON with `Version: "2019-10-30"`, `StartAction`, `Actions[]` (each: `Identifier`, `Type`, `Parameters`, `Transitions{NextAction, Errors[], Conditions[]}`), plus a `Metadata` block used only by the flow designer (block positions, friendly names). The API accepts content without designer metadata, but keep it if humans will re-open flows in the designer.
- **Console export vs API content**: the new flow designer exports flow-language JSON (close to `DescribeContactFlow` content, plus designer metadata and name+ARN hints for referenced resources). Legacy-designer export format import support **ended 2026-03-31** — convert any stored legacy JSON by importing once through the new designer. Console export limits: **< 200 blocks, < 1 MB** per flow. `AWS::Connect::ContactFlow.Content` allows up to 256,000 chars.
- Console **import** resolves referenced resources by ARN, then **falls back to matching by name**; unresolved optional refs still publish, unresolved required refs block publishing. The API does **no name fallback** — bad ARNs fail publish-time validation.

### The ARN-embedding problem

Flow content embeds full ARNs for queues, prompts, other flows (transfer targets), Lex bot aliases, Lambda functions, hours of operation. These differ per instance/account/region, so dev-exported content is invalid in prod as-is (`UpdateContactFlowContent` → `InvalidContactFlowException`). Official migration guidance (admin guide, "Migrate flows"): build a **source→target ARN mapping** for queues/flows/prompts and rewrite every ARN before `CreateContactFlow`/`UpdateContactFlowContent`.

### Strategies (in order of preference)

1. **IaC-native token substitution** — store flow content as a template; inject ARNs from the same stack/state that created the resources.
   - CDK: build content as a TS object embedding `queue.attrQueueArn` etc., then `JSON.stringify`/`Stack.toJsonString` — tokens resolve at deploy. (See snippet below.)
   - Terraform: `templatefile("flow.json.tftpl", { queue_arn = aws_connect_queue.x.arn })`. Escape any literal `${` in the JSON as `$${`. Flow-language `$.Attributes...` paths are safe (no `${}`).
   - Raw CFN: `Fn::Sub` over the content string with `${Queue.QueueArn}` placeholders; escape literal `${` as `${!`.
2. **Runtime indirection (env-agnostic content)** — keep flow JSON identical across environments:
   - "Set working queue" / many blocks accept **dynamic** values from `$.Attributes.*` or `$.FlowAttributes.*`. Have an entry flow invoke a small **config-lookup Lambda** (or read a Connect **DataTable**) that returns env-specific ARNs/names keyed by logical name; set them as flow attributes; downstream blocks reference `$.External.*`/`$.Attributes.*`. `$.FlowAttributes` are flow-scoped and not persisted to the contact record — good for config plumbing.
   - Lambda ARNs in `InvokeLambdaFunction` can also be dynamic attributes; the function still must be associated to the instance (`IntegrationAssociation`).
   - Cost: less static validation, config lookups add latency; but zero content rewriting and flows are console-portable.
3. **Name-convention resolution** — keep resource **names identical across environments** and rely on console-import name fallback, or a pipeline step that calls `ListQueues`/`ListPrompts`/`ListContactFlows` on the target instance and rewrites ARNs by name (this is what most sed/jq pipelines actually implement). Robust variant: maintain `mapping.json` per environment in the repo.
4. **API pipeline without IaC for content** — repo holds exported JSON; CI runs: transform ARNs → `CreateContactFlow` (if new) → `UpdateContactFlowContent` → publish. `CreateContactFlow` accepts `Status: SAVED | PUBLISHED`; **PUBLISHED triggers validation, SAVED does not** — there is **no standalone `ValidateContactFlow` API**; the validate step *is* an update/create with PUBLISHED (errors come back as `InvalidContactFlowException` with a `problems[]` list). Use the `:$SAVED` ARN qualifier with `DescribeContactFlow` to read draft content. Circular flow references (A transfers to B, B to A) force a two-pass deploy: create both as SAVED/stub, then update+publish.

### Versions, aliases, rollback

- Console keeps automatic version history per flow with one-click rollback (choose version → Publish). Not exposed as IaC.
- Flow **modules** have first-class versions + aliases (`CreateContactFlowModuleVersion`/`Alias`, CFN `ContactFlowModuleAlias`): point flows at the alias, promote by re-pointing the alias — the best native blue/green primitive for shared logic.
- `CreateContactFlowVersion` / CFN `ContactFlowVersion`: API docs currently scope it to `CAMPAIGN` flows; don't design a general promotion scheme around it without testing.

---

## CI/CD & multi-environment promotion

Reference implementations (all github.com/aws-samples):

- **`amazon-connect-cicd-workshop`** — CDK + CodePipeline + CodeBuild (TypeScript), pipelines in a central DevOps account deploying cross-account to SDLC accounts. Companion workshop: catalog.workshops.aws "contact-flow-deployment-workshop".
- **`amazon-connect-gitlab-cicd-terraform`** — GitLab CI + Terraform, OIDC role assumption into develop/stage/main accounts, **monorepo with 5 pipelines**: `amzconnect-instance` (instance), `amzconnect-admin-objects` (queues, hours, users), `amzconnect-supporting-infra` (Lex v2, S3, etc.), `amzconnect-lambdas`, `amzconnect-contact-flows`. Region-matrix deploys (us-east-1 + us-west-2) and works with Global Resiliency.
- **`amazon-connect-contactcenterops`** — IaC + DevOps pipelines for Connect at scale across environments.

Patterns that generalize:

- **Layered stacks/pipelines with strict ordering**: (1) instance + storage config → (2) supporting infra (Lambda, Lex, S3, DynamoDB) → (3) integration associations → (4) admin objects (hours → queues → routing profiles → security profiles → users) → (5) flows (modules first, then flows, two-pass for cross-references) → (6) phone-number/flow associations. Dependencies are ARN-based, so ordering violations surface as publish-time validation failures, not plan errors.
- **Promotion flow**: authors build in a dev instance's designer → export/`DescribeContactFlow` → commit JSON (or regenerate TS builders) → PR review (diff the JSON; strip designer `Metadata` noise or use a canonicalizing pre-commit hook to keep diffs readable) → pipeline deploys to stage (transform ARNs) → automated tests → manual approval → prod.
- **Account strategy**: separate AWS accounts per environment (prescriptive guidance); a tooling account hosts the pipeline and assumes roles cross-account.
- Keep **instance creation out of the app pipeline** (30-day quota, replacement risks). Bootstrap once, reference by SSM parameter/ARN everywhere.
- Store environment config (instance ARN, Lambda ARNs, mapping tables) in SSM Parameter Store per account; pipelines read at deploy time.

---

## Global Resiliency & TDGs in IaC

- Sequence: `ReplicateInstance` (API-only; must be called from the source region) → creates linked replica instance in the paired region + a **default TDG** → `CreateTrafficDistributionGroup` (CFN/awscc-able) in the **source region** for additional TDGs → claim/point phone numbers at the TDG ARN (`AWS::Connect::PhoneNumber.TargetArn`, updatable in place) → shift traffic with `UpdateTrafficDistribution` (API-only, `50/50` → `100/0` etc.).
- TDG must be `ACTIVE` (poll `DescribeTrafficDistributionGroup`) before claiming numbers or updating distribution. `SignInConfig` (agent sign-in distribution) can only be changed on the **default** TDG — non-default TDG + modified SignInConfig → `InvalidRequestException`.
- Only numbers claimed in the source region can attach to the TDG.
- IaC posture: define instance(s), TDG, and numbers declaratively; keep `ReplicateInstance` and `UpdateTrafficDistribution` as pipeline scripts/runbooks (they're operational actions). The gitlab-cicd-terraform sample deploys the same config to both regions in a matrix so replica content stays in sync — you must deploy flows/queues to **both** regions yourself; replication does not sync your config changes continuously in all cases (verify current replication scope for each resource type).

---

## Testing flows

- **Native testing & simulation** (GA; "reduce testing time by up to 90%" launch): define **test cases** (visual designer or as code — `AWS::Connect::TestCase`, testing-language JSON in the API reference) with interaction groups: *observe* blocks assert prompts/behavior, *action* blocks simulate customer input ("when IVR plays X, press 1 / say agent"). Execute via console or API; limits: **5 concurrent test executions** (rest queue), **5-minute max** per test; results roll up to a testing dashboard. Wire executions into the pipeline post-deploy on stage.
- Pre-deploy static checks: JSON schema validation of flow language, lint for hardcoded ARNs matching the wrong account/region, publish to a scratch flow with `Status: PUBLISHED` in a dev instance as a validation gate.
- Classic end-to-end: real test calls via Amazon Connect outbound + a listener, or third-party IVR testers (Cyara, Hammer); chat via `StartChatContact` API harnesses (cheapest channel to smoke-test flow logic since chat and voice share flows).
- Lambda-level unit tests remain the highest-leverage tests — keep business logic in Lambda, flows thin.

---

## Example — CDK (TypeScript): queue + routing profile + flow with content substitution

```typescript
import * as cdk from 'aws-cdk-lib';
import { aws_connect as connect } from 'aws-cdk-lib';
import { Construct } from 'constructs';

interface ConnectEnvProps extends cdk.StackProps {
  instanceArn: string;        // from SSM/context — instance managed elsewhere
  hoursOfOperationArn: string;
  lookupLambdaArn: string;    // must also be integration-associated below
}

export class ContactCenterStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: ConnectEnvProps) {
    super(scope, id, props);

    const queue = new connect.CfnQueue(this, 'SupportQueue', {
      instanceArn: props.instanceArn,
      name: 'support',
      description: 'Tier-1 support',
      hoursOfOperationArn: props.hoursOfOperationArn,
    });

    new connect.CfnRoutingProfile(this, 'SupportRoutingProfile', {
      instanceArn: props.instanceArn,
      name: 'support-rp',
      description: 'Voice tier-1',
      defaultOutboundQueueArn: queue.attrQueueArn,
      mediaConcurrencies: [{ channel: 'VOICE', concurrency: 1 }],
      queueConfigs: [{
        delay: 0, priority: 1,
        queueReference: { channel: 'VOICE', queueArn: queue.attrQueueArn },
      }],
    });

    // Lambda must be associated before a flow can invoke it
    new connect.CfnIntegrationAssociation(this, 'LambdaAssoc', {
      instanceId: props.instanceArn,          // property name is InstanceId but takes the ARN
      integrationType: 'LAMBDA_FUNCTION',
      integrationArn: props.lookupLambdaArn,
    });

    // Flow content as a typed object; CDK tokens resolve to real ARNs at deploy.
    const content = {
      Version: '2019-10-30',
      StartAction: 'invokeLookup',
      Actions: [
        {
          Identifier: 'invokeLookup',
          Type: 'InvokeLambdaFunction',
          Parameters: { LambdaFunctionARN: props.lookupLambdaArn, InvocationTimeLimitSeconds: '3' },
          Transitions: { NextAction: 'setQueue', Errors: [{ NextAction: 'setQueue', ErrorType: 'NoMatchingError' }] },
        },
        {
          Identifier: 'setQueue',
          Type: 'UpdateContactTargetQueue',
          Parameters: { QueueId: queue.attrQueueArn },   // token → env-correct ARN
          Transitions: { NextAction: 'xferToQueue', Errors: [{ NextAction: 'bail', ErrorType: 'NoMatchingError' }] },
        },
        {
          Identifier: 'xferToQueue', Type: 'TransferContactToQueue', Parameters: {},
          Transitions: { Errors: [
            { NextAction: 'bail', ErrorType: 'QueueAtCapacity' },
            { NextAction: 'bail', ErrorType: 'NoMatchingError' },
          ]},
        },
        { Identifier: 'bail', Type: 'DisconnectParticipant', Parameters: {}, Transitions: {} },
      ],
    };

    new connect.CfnContactFlow(this, 'InboundFlow', {
      instanceArn: props.instanceArn,
      name: 'main-inbound',
      type: 'CONTACT_FLOW',
      content: this.toJsonString(content),   // Stack.toJsonString handles token serialization
    });
  }
}
```

Gotchas: `CfnContactFlow.content` is a plain string — `JSON.stringify` also works for same-stack tokens, but `Stack.toJsonString` is safer with cross-stack references. Changing `type` replaces the flow (new ARN → breaks phone-number associations).

## Example — Terraform (hashicorp/aws + templatefile)

```hcl
data "aws_connect_instance" "this" {
  instance_alias = var.instance_alias   # e.g. "acme-${var.env}"
}

resource "aws_connect_hours_of_operation" "always" {
  instance_id = data.aws_connect_instance.this.id
  name        = "24x7"
  time_zone   = "UTC"
  dynamic "config" {
    for_each = toset(["MONDAY","TUESDAY","WEDNESDAY","THURSDAY","FRIDAY","SATURDAY","SUNDAY"])
    content {
      day = config.value
      start_time { hours = 0  minutes = 0 }
      end_time   { hours = 23 minutes = 59 }
    }
  }
}

resource "aws_connect_queue" "support" {
  instance_id           = data.aws_connect_instance.this.id
  name                  = "support"
  description           = "Tier-1 support"
  hours_of_operation_id = aws_connect_hours_of_operation.always.hours_of_operation_id
}

resource "aws_connect_routing_profile" "support" {
  instance_id               = data.aws_connect_instance.this.id
  name                      = "support-rp"
  description               = "Voice tier-1"
  default_outbound_queue_id = aws_connect_queue.support.queue_id
  media_concurrencies { channel = "VOICE" concurrency = 1 }
  queue_configs {
    channel  = "VOICE"
    delay    = 0
    priority = 1
    queue_id = aws_connect_queue.support.queue_id
  }
}

resource "aws_connect_lambda_function_association" "lookup" {
  instance_id  = data.aws_connect_instance.this.id
  function_arn = var.lookup_lambda_arn
}

# flows/main-inbound.json.tftpl contains ${queue_arn} / ${lambda_arn} placeholders;
# literal "${" in flow JSON must be written "$${". "$.Attributes..." needs no escaping.
resource "aws_connect_contact_flow" "main" {
  instance_id = data.aws_connect_instance.this.id
  name        = "main-inbound"
  type        = "CONTACT_FLOW"
  content = templatefile("${path.module}/flows/main-inbound.json.tftpl", {
    queue_arn  = aws_connect_queue.support.arn
    lambda_arn = var.lookup_lambda_arn
  })
  depends_on = [aws_connect_lambda_function_association.lookup]
}

# Gap-filler via awscc for types the aws provider lacks, e.g. a task template:
# resource "awscc_connect_task_template" "callback" {
#   instance_arn = data.aws_connect_instance.this.arn
#   ...
# }
```

Gotchas: import IDs are `instance_id:resource_id`; `content` diffs are whole-JSON (canonicalize formatting in the repo to avoid noisy plans); if console editing is allowed in the environment, add `lifecycle { ignore_changes = [content] }` deliberately or accept clobbering.

---

## Sources

- CloudFormation `AWS::Connect` resource list — https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/AWS_Connect.html
- CFN `AWS::Connect::ContactFlow` — https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-connect-contactflow.html
- CFN `AWS::Connect::Instance` — https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-connect-instance.html
- CFN `AWS::Connect::PhoneNumber` — https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-connect-phonenumber.html
- CDK `aws_connect` module README (L1-only) — https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_connect-readme.html
- Terraform AWS provider connect service source (resource inventory) — https://github.com/hashicorp/terraform-provider-aws/tree/main/internal/service/connect
- Admin guide: Import/export flows (limits, name-based resolution, legacy deprecation) — https://docs.aws.amazon.com/connect/latest/adminguide/contact-flow-import-export.html
- Admin guide: Migrate flows between instances/Regions (API sequence, ARN mapping) — https://docs.aws.amazon.com/connect/latest/adminguide/migrate-contact-flows.html
- Admin guide: Traffic distribution groups — https://docs.aws.amazon.com/connect/latest/adminguide/setup-traffic-distribution-groups.html
- aws-samples/amazon-connect-gitlab-cicd-terraform — https://github.com/aws-samples/amazon-connect-gitlab-cicd-terraform
- aws-samples/amazon-connect-cicd-workshop — https://github.com/aws-samples/amazon-connect-cicd-workshop
- aws-samples/amazon-connect-contactcenterops — https://github.com/aws-samples/amazon-connect-contactcenterops
- AWS blog: Managing Amazon Connect flows as Code with AWS CDK (Mar 2026) — https://aws.amazon.com/blogs/contact-center/managing-amazon-connect-flows-as-code-with-aws-cdk/
- AWS blog: Native testing and simulation for Amazon Connect — https://aws.amazon.com/blogs/contact-center/reduce-testing-time-by-up-to-90-introducing-native-testing-and-simulation-for-amazon-connect/
- API: CreateContactFlowVersion / flow module aliases — https://docs.aws.amazon.com/connect/latest/APIReference/API_CreateContactFlowVersion.html , https://docs.aws.amazon.com/connect/latest/APIReference/API_CreateContactFlowModuleAlias.html
- API: UpdateContactFlowContent / CreateContactFlow (SAVED vs PUBLISHED validation) — https://docs.aws.amazon.com/connect/latest/APIReference/API_UpdateContactFlowContent.html , https://docs.aws.amazon.com/connect/latest/APIReference/API_CreateContactFlow.html
- awscc provider guidance (aws + awscc together) — https://registry.terraform.io/providers/hashicorp/awscc/latest/docs/guides/using-aws-with-awscc-provider

# Amazon Connect — Core Concepts & Administration
> Last updated: 2026-07 (baseline)

## Naming note (2026 rebrand)
"Amazon Connect" now refers to AWS's portfolio of agentic business solutions. The classic
cloud contact center product is officially **"Amazon Connect Customer"** (or just "Customer").
AWS docs use the legacy and new names interchangeably; the service prefix, API namespace
(`connect`), endpoints, and ARNs are unchanged. This file uses "Connect" throughout.

Also note: **Amazon Connect Voice ID reached end of support on 2026-05-20.** Do not build new
functionality on Voice ID.

## Instance architecture

- A Connect **instance** is the top-level container for one contact center in one Region.
  Everything (users, queues, flows, numbers, storage config) lives inside an instance.
- Admin website URL: `https://{instance-alias}.my.connect.aws/` (legacy:
  `https://{alias}.awsapps.com/connect/`). The alias is unique per Region.
- **Identity management is chosen at instance creation and cannot be changed later**:
  1. Store users in Connect (native), 2. SAML 2.0 federation, or 3. AWS Directory Service.
  With SAML, users sign in via IdP and `connect:GetFederationToken`; usernames must match.
- Default resources created with every instance: **BasicQueue**, **Basic routing profile**,
  default flows (Default inbound, Customer queue, whispers, etc.), and default security
  profiles (Admin, Agent, CallCenterManager, QualityAnalyst).
- Default quota: **2 instances per Region per account** (adjustable, account-level).
  Hard limit: **100 instance creations + deletions per rolling 30 days** — exceeding it blocks
  further create/delete for 30 days (bites CI/CD that spins up ephemeral instances).
- Deleting an instance deletes its config permanently (S3 data in your buckets survives).
- Service-linked role `AWSServiceRoleForAmazonConnect_{suffix}` is created per instance.

### ARN formats
All instance-scoped resources nest under the instance ARN:

```
Instance:            arn:aws:connect:{region}:{account}:instance/{instanceId}
Contact:             arn:aws:connect:{region}:{account}:instance/{instanceId}/contact/{contactId}
User (agent):        arn:aws:connect:{region}:{account}:instance/{instanceId}/agent/{userId}
Queue:               arn:aws:connect:{region}:{account}:instance/{instanceId}/queue/{queueId}
Routing profile:     arn:aws:connect:{region}:{account}:instance/{instanceId}/routing-profile/{id}
Flow:                arn:aws:connect:{region}:{account}:instance/{instanceId}/contact-flow/{flowId}
Flow module:         arn:aws:connect:{region}:{account}:instance/{instanceId}/flow-module/{moduleId}
Phone number:        arn:aws:connect:{region}:{account}:phone-number/{phoneNumberId}
                     (numbers claimed to a traffic distribution group use the TDG-scoped form;
                      legacy instance-scoped form: .../instance/{instanceId}/phone-number/{id})
Security profile:    arn:aws:connect:{region}:{account}:instance/{instanceId}/security-profile/{id}
Hours of operation:  arn:aws:connect:{region}:{account}:instance/{instanceId}/hours-of-operation/{id}
Quick connect:       arn:aws:connect:{region}:{account}:instance/{instanceId}/quick-connect/{id}
Agent status:        arn:aws:connect:{region}:{account}:instance/{instanceId}/agent-status/{id}
Hierarchy group:     arn:aws:connect:{region}:{account}:instance/{instanceId}/agent-group/{id}
Traffic dist. group: arn:aws:connect:{region}:{account}:traffic-distribution-group/{tdgId}
Evaluation form:     arn:aws:connect:{region}:{account}:instance/{instanceId}/evaluation-form/{id}
Email address:       arn:aws:connect:{region}:{account}:instance/{instanceId}/email-address/{id}
```

Gotchas:
- The **user resource segment is `agent/`**, not `user/` — easy to get wrong in IAM policies.
- Queue ARNs are frequently needed inside flows (e.g., `Set working queue`); the queue ID is
  the UUID after `queue/`.
- Contact IDs are UUIDs; a contact that is transferred spawns new contact IDs linked by
  `InitialContactId` / `PreviousContactId` / `RelatedContactId` in the contact record.

## Users, security profiles, hierarchies, statuses

### Users
- A user record = login + identity info + **exactly one routing profile** + **one or more
  security profiles** + optional hierarchy group + phone settings (softphone/deskphone,
  ACW timeout, auto-accept).
- Default quota **500 users per instance** (adjustable, resource-level); all can be
  concurrently logged in as agents.
- APIs: `CreateUser`, `UpdateUserRoutingProfile`, `UpdateUserSecurityProfiles`,
  `UpdateUserHierarchy`, `SearchUsers`.

### Security profiles (in-app permissions — distinct from IAM)
- Group of permissions mapping to a contact-center role; controls access to the admin
  website and Contact Control Panel (CCP). This is a **separate layer from IAM**: IAM
  controls AWS API/console access; security profiles control what a signed-in Connect user
  can do inside the Connect admin website/agent workspace.
- Defaults: **Admin** (everything), **Agent** (CCP access), **CallCenterManager**,
  **QualityAnalyst**.
- Support **tag-based access control** (restrict which tagged resources a user can see/edit)
  and **hierarchy-based access control** (e.g., `Restrict contact access` limits contact
  search to the agent's hierarchy subtree).
- Quota: 100 security profiles per instance (adjustable).

### Agent hierarchies
- Up to **5 levels** (e.g., Continent > Country > City > Site > Team); groups assigned to
  users. Quota: **500 hierarchy groups per instance total across all levels** (adjustable).
- Used for reporting segmentation and hierarchy-based access control.
- Pitfalls: removing agents from a level affects historical reporting; deleting a hierarchy
  level severs links to existing contacts irreversibly; groups must be deleted before their
  level can be deleted.

### Agent statuses
- Defaults: **Available** (routable) and **Offline**. Custom statuses (Lunch, Training, …)
  are non-routable — no contacts are routed while set.
- Quota: **50 agent statuses per instance — NOT adjustable**.
- Statuses (agent-selected) are distinct from contact states (Connected, On hold, After
  Contact Work). ACW is entered automatically after a contact; it is not a status.
- Supervisors can change an agent's status from real-time metrics reports.

## Routing: profiles, queues, concepts

### Routing profiles
- Link **queues → agents**. Each agent has exactly one routing profile; a profile serves many
  agents. Changing the profile instantly changes what its whole agent group handles.
- A profile defines:
  - **Channel availability + concurrency**: max concurrent contacts per channel
    (voice is always 1; chat up to 10 per agent; tasks up to 10; email).
  - **Cross-channel concurrency**: per channel, whether other channels may be offered while
    the agent works that channel (e.g., "allow other channels while on a Task", "no other
    channels while on Voice"). When evaluating, Connect checks the agent's current
    contacts/channels against the profile config; if Priority and Delay are equal, the
    longest-waiting contact wins (FIFO across channels).
  - **Queues** with per-queue-per-channel **Priority** (1 = highest) and **Delay** (seconds a
    contact must wait in that queue before agents in this profile become eligible).
  - **Default outbound queue** (determines outbound caller ID and whispers).
  - Optional **manually assigned queues** section: contacts in these queue/channel combos are
    NOT auto-routed; agents self-assign from a worklist (Tasks, Emails, Chats only).
- To give the same queue different priorities per channel, add the queue twice (once per
  channel). Quota: **50 queue/channel combinations per routing profile** (adjustable), and
  independently another 50 for manually-assigned queues.
- APIs: `CreateRoutingProfile`, `UpdateRoutingProfileConcurrency`,
  `UpdateRoutingProfileQueues`, `UpdateRoutingProfileDefaultOutboundQueue`.

### Queues: standard vs agent
- **Standard queues**: where contacts wait for agents. Created by admins. Default =
  BasicQueue. Configure hours of operation (required), outbound caller ID number/name,
  outbound whisper flow, max contacts in queue (default limit derives from instance
  concurrent-contact quotas), and quick connects.
- **Agent queues**: created **automatically for every user**; not listed with standard
  queues. Contacts reach them only when a flow explicitly routes there (route-to-agent,
  agent voicemail patterns). **Agent-queue contacts always beat standard-queue contacts:
  highest priority, zero delay.** Max **10 contacts waiting per agent queue** (adjustable).
  Metrics APIs do not support agent queues; historical reports hide them by default.

### Routing logic (how an agent is picked)
- Contacts in queue are served **first-come, first-served** within the same priority
  (priority from routing profile ordering; in-queue order strictly by enqueue time —
  priority within a queue cannot be jumped except via `UpdateContactRoutingData` API,
  which can adjust a contact's priority and routing age).
- If multiple agents are Available, the contact goes to the **longest-idle agent** (longest
  time in Available). Handling any contact (inbound or outbound) drops the agent to the
  bottom of the idle list; enable **"Outbound calls should not impact routing order"** in the
  routing profile to exempt outbound.
- Transfers: agent transfer via quick connect **keeps the original enqueue time** (contact
  keeps its place); queue-to-queue transfer in a flow/API **resets the enqueue time**.
- Routing decision inputs overall: agent's routing profile, queue hours of operation, and
  flow logic. Advanced: queue priority routing can be tuned per-contact with
  `UpdateContactRoutingData` (QueuePriority, QueueTimeAdjustmentSeconds).

### Hours of operation
- Attached to each queue; referenced in flows via the **Check hours of operation** block
  (branch in-hours vs after-hours). Defined per time zone; DST handled automatically when
  you pick a DST-observing zone (e.g., EST5EDT vs fixed EST).
- Midnight is entered as 12:00AM. Multiple time ranges per day supported (breaks).
- **Overrides** handle holidays/extended/reduced hours: 50 overrides per hours-of-operation
  set (not adjustable); 100 hours-of-operation sets per instance (adjustable).
- Staggered lunches are modeled with custom agent statuses, not hours.

## Quick connects
- Preconfigured transfer destinations shown in the CCP. Types:
  - **User** quick connect → transfer to a specific agent (via an agent transfer flow;
    lands in that agent's agent queue).
  - **Queue** quick connect → transfer to a queue (via a queue transfer flow).
  - **Phone number** quick connect → external number; **no flow is invoked**, and outbound
    caller ID comes from the queue's configuration (you can't set it per-quick-connect).
  - **Flow** quick connect → chat only; agent-initiated flows during an active chat.
- Visibility rules (common gotcha): **User and Queue quick connects appear only while the
  agent is transferring an active contact; phone-number quick connects always appear.**
- A quick connect is invisible to agents until it is **added to a queue** that is in the
  agent's routing profile (the default outbound queue's quick connects also show).
- Quotas: 100 quick connects per instance (adjustable); up to **700 quick connects per
  queue** (hard feature spec).
- API: `CreateQuickConnect`, `AssociateQueueQuickConnects`.

## Phone numbers & telephony

### Number types
- **DID (direct inward dial / local)**: locally formatted numbers. Single-carrier — **no
  carrier redundancy**, only link/AZ redundancy. Per-number concurrent-call capacity limits
  vary by Region (engage AWS if you expect >100 concurrent calls on one DID). Cheaper;
  local caller-ID presence for outbound.
- **Toll-free**: in the US, AWS acts as Responsible Organization and registers the number
  with SOMOS, enabling **multi-carrier route + carrier redundancy** — highest availability,
  higher cost. Preferred for primary inbound at scale.
- **UIFN (Universal International Freephone Number)**: **inbound only**, 11-digit fixed
  format `+800` + 8-digit GSN. Supported in 60+ ITU-registered countries; **minimum 5
  countries must be enabled**; requested via AWS Support case; setup takes ~10–60 days per
  country; reachability is partial in some countries (e.g., UK: BT/Vodafone/EE only).
  Cannot be dialed from Connect itself ("loopback" unsupported).

### Claiming, porting, moving
- Claim via admin website (Channels > Phone numbers > Claim a number) or APIs:
  `SearchAvailablePhoneNumbers`, `ClaimPhoneNumber`, `ReleasePhoneNumber`,
  `UpdatePhoneNumber` (also used to move numbers between instances/TDGs).
- Default quota: **5 phone numbers per instance** (adjustable; requires AWS CLI >= 2.13.20
  to view resource-level quotas). You may hit "You've reached the limit of Phone Numbers"
  even on a first claim — all causes require an AWS Support ticket.
- Many countries require **ID/address documentation** before ordering (see "Region
  requirements for ordering and porting phone numbers"); international numbers often go
  through a Support request rather than self-service claim.
- **Porting**: submitted via AWS Support (same quota-increase form for US ports); after
  porting, the number appears in your instance's number list. Best-practice migration:
  forward existing numbers to newly claimed Connect numbers first; port after cutover.
- SMS-enabled numbers are provisioned through **AWS End User Messaging SMS** (formerly
  Pinpoint SMS), then associated with Connect for the SMS channel.
- Released numbers go back to inventory and may not be reclaimable — treat release as
  destructive.

### Telephony architecture
- AWS fully manages PSTN carrier interconnects: multiple carriers per Region, each with
  multiple diverse links into multiple AZs (route survives carrier/link failure; toll-free
  additionally survives complete single-carrier outage).
- Agent audio: browser **softphone via WebRTC** in the CCP/agent workspace (Opus codec), or
  redirect to a **deskphone** PSTN number. Voice between Connect and the PSTN rides AWS's
  telephony backbone (shared Amazon Chime SDK voice infrastructure); you do not manage SIP
  trunks. Direct SIP trunking into Connect is not a native feature — patterns use carrier
  forwarding, or Amazon Chime SDK Voice Connectors / partner SBCs for external voice
  integrations (and the "external voice transfer connector" for Contact Lens analytics of
  external voice systems).
- Inbound calls arrive at a claimed number → run the flow attached to that number.
  Outbound requires "Make outbound calls" enabled in instance telephony settings and an
  outbound caller ID on the queue.
- STIR/SHAKEN attestation is supported for outbound calls; design-for-low-latency guidance
  exists for global callers (pick Regions near callers, use Global Resiliency).

## Channels
- **Voice**: PSTN in/out, callbacks, WebRTC in-app/web calls. 3 participants default;
  enabling "Multi-Party Calls and Enhanced Monitoring" allows **6 participants** + 2
  monitoring supervisors (barge supported, CCPv2 only).
- **Chat**: web/mobile communications widget (20 widgets per instance), persistent chat
  (traverse up to 100 past contacts, 5 MB transcript), up to **7 days** total duration per
  chat, 10 active chats per agent max, 6 participants with multi-party chat enabled.
  Message size: 16,384 bytes agent↔customer (1,024 chars to a Lex bot).
- **SMS / WhatsApp / Apple Messages for Business**: delivered as chat contacts (count
  against the concurrent-chat quota). SMS messages limited to 1,024 chars; WhatsApp/AMB
  4,096 chars outbound; WhatsApp media size caps: image 5 MB, video/audio 16 MB, doc 20 MB.
- **Tasks**: work items routed like contacts. 2,500 concurrent active tasks default;
  duration 7 days default (extensible to 30); schedulable up to **6 days** ahead, max 20
  reschedules, max 11 transfers; 50 task templates per instance (fixed).
- **Email**: full channel (since late 2024). Requires an S3 "Email messages" bucket and a
  CORS policy on the attachments bucket (**email silently fails without the CORS policy** —
  documented hard requirement). 1 Connect-provided domain + up to 100 custom domains (SES
  integration), 100 email addresses default (max 500). Message body ≤ 5 MB, body+attachments
  ≤ 25 MB, 10 attachments, no BCC; outbound = 1 To + ≤49 CC. Active email contact expires
  after 14 days (configurable ≤ 90 via `connect:ContactExpiry` segment attribute); threads
  stay joined for 90 days. 1,000 concurrent active emails default.
- **Outbound campaigns**: separate opt-in feature; "Concurrent campaign active calls"
  quota defaults to **0** — must request an increase before campaigns will dial.

## Global Resiliency (multi-Region)
- **Amazon Connect Global Resiliency (ACGR)** is the only AWS-supported multi-Region DR
  solution for Connect (third-party/custom multi-Region setups can cost you SLA coverage
  and secondary-instance limit increases).
- Access is gated — engage your AWS SA/TAM. Supported Region pairs only:
  **us-east-1 ↔ us-west-2**, **eu-west-2 ↔ eu-central-1**, **ap-northeast-1 (Tokyo) ↔
  ap-northeast-3 (Osaka)**.
- `ReplicateInstance` API creates a linked replica instance in the paired Region (max **5
  replica instances per account**, hard limit).
- **Traffic distribution groups (TDGs)** (max **8 per replicated instance**) hold phone
  numbers and let you shift **telephony traffic and agent sign-in** between Regions in
  **10% increments** (or 100% at once) via `UpdateTrafficDistribution`. Numbers claimed to a
  TDG are reachable in both Regions.
- Chat, and metrics/reports/search across ACGR Regions, are supported; you still must keep
  config (flows, users, routing) in sync — replication covers a defined resource set, and
  drift is on you to manage.

## Service quotas that commonly bite (defaults, per instance unless noted)
Source: adminguide/amazon-connect-service-limits.html. All adjustable unless noted;
resource-level unless noted. Defaults shown are for new accounts and may differ for yours.

| Quota | Default | Notes |
|---|---|---|
| Concurrent active calls | **10** | PSTN + WebRTC; includes flow, queued, agent, outbound. Exceeding → fast-busy. Callbacks waiting don't count. **Raise this before go-live.** |
| Concurrent active chats | 500 | Includes SMS/WhatsApp/AMB and idle/waiting chats |
| Concurrent active tasks | 2,500 | Any not-yet-ended task counts |
| Concurrent active emails | 1,000 | Queued + assigned + sending |
| Concurrent campaign calls | **0** | Must request increase to use outbound campaigns |
| Users | 500 | |
| Queues | 100 | |
| Queues per routing profile | 50 | Counted as queue×channel combinations |
| Routing profiles | 500 | |
| Flows | 100 | Modules: 200 |
| Phone numbers | 5 | |
| Quick connects | 100 | |
| Hours of operation | 100 | 50 overrides each (fixed) |
| Security profiles | 100 | |
| User hierarchy groups | 500 | Across all levels |
| Agent statuses | 50 | **Not adjustable** |
| Lambda functions per instance | 50 | Attached via Flows settings |
| Lex bots | 70 (fixed) / 100 V2 aliases | |
| Prompts | 500 | |
| Reports | 2,000 | Personal saved reports count |
| Instances per Region | 2 | Account-level |
| Contacts in one agent queue | 10 | |
| Instance create+delete ops | 100 / 30 days | Hard limit |

### API throttling (account + Region shared bucket — not per instance/user)
- Default for all `connect` APIs: **2 TPS rate / 5 burst**. Notable exceptions:
  - `GetMetricData` 5/8, `GetMetricDataV2` 10/10, `GetCurrentMetricData` 5/8
  - `SearchContacts` **0.5/1** (very low — batch carefully)
  - `StartChatContact` 5/8, `StartContactStreaming` 5/8
  - `GetContactAttributes` / `UpdateContactAttributes` / `DescribeContact` / `StopContact`
    / `UpdateContact` / `BatchPutContact` 10/15
  - `UpdateContactRoutingData` 20/20, `TagContact`/`UntagContact` 20/25
  - Evaluations APIs 1 TPS
- Participant Service (chat): `SendMessage`/`SendEvent` 10/15, `GetTranscript` 8/12,
  `CreateParticipantConnection` 6/9 — these are **per instance**.
- Gotcha: all IAM principals in the account share one throttle bucket per Region; a noisy
  dashboard polling `GetCurrentMetricData` can starve your provisioning automation.
- Quota-increase lead time: hours for small asks, up to 3 weeks for large, months for
  extra-large worldwide increases. Plan ahead; alert at 80% of quota via CloudWatch
  (`ConcurrentCalls`, `ConcurrentCallsPercentage`, `ConcurrentEmails`, …).

## Pricing model (overview — verify region-specific rates on aws.amazon.com/connect/pricing/)
- Pure **pay-as-you-go**: no seats, no minimums, no upfront. Charges stack per channel:
- **Voice**: per-second service usage billed per minute of end-customer connection
  (~$0.038/min US) **plus** telephony: per-minute inbound DID/toll-free rates and per-day
  charges for each claimed number (country-specific), plus outbound per-minute rates.
- **Chat**: ~$0.010 per message (sent or received). SMS/third-party messaging (WhatsApp,
  AMB): ~$0.014 per message, plus carrier/Meta fees via AWS End User Messaging.
- **Email**: ~$0.080 per message. **Tasks**: priced per task (~$0.04 US).
- Add-ons billed separately per unit: Contact Lens (per analyzed minute/message), Cases
  (per case), Customer Profiles (per profile), Q in Connect / AI agents, forecasting &
  scheduling (per agent), outbound campaigns.
- Associated AWS costs are extra: S3 storage, KMS, Kinesis, Lambda, Lex, KVS.

## Instance settings (Connect console → instance alias)
- **Telephony**: toggle inbound calls, outbound calls, outbound campaigns, **early media**
  (hear busy/fail tones on outbound; not for Transfer-to-phone-number transfers),
  multi-party calls/chat + enhanced monitoring (barge).
- **Data storage** (each gets an S3 bucket + KMS key; enabling the bucket enables the
  feature at instance level):
  - Call recordings (then enable per-flow via Set recording and analytics behavior block)
  - Chat transcripts (all transcripts stored once set)
  - Exported reports, Contact evaluations, Screen recordings, Email messages
  - Attachments (enable attachment sharing; **must add CORS policy on the bucket or the
    email channel breaks**)
  - **Live media streaming**: customer audio to **Kinesis Video Streams** (configure prefix,
    KMS key, retention) — used for real-time audio processing integrations.
- **Data streaming**: contact records (CTRs) → Kinesis Data Stream **or** Firehose; agent
  events → Kinesis Data Stream. CTR retention inside Connect is 24 months; stream to keep
  longer.
- **Analytics tools**: Enable Contact Lens (instance-level toggle; per-contact behavior
  still set in flows).
- **Flows**: flow-security signing keys (encrypt customer input), Lex bot and Lambda
  function associations (required before flows can call them), **enable flow logs** (to
  CloudWatch Logs), Polly best-available-voice option, bot analytics/transcripts toggle.
- **Approved origins**: allowlist domains embedding the CCP (100 max).

## Tagging & IAM

### Tagging
- Up to **50 tags per resource**; key ≤128 chars, value ≤256, case-sensitive; `aws:` prefix
  reserved. Taggable (CLI/SDK): instance, users (agents), hierarchy groups, agent states,
  queues, routing profiles, flows/modules, hours of operation, phone numbers, quick
  connects, security profiles, prompts, email addresses, evaluation forms, TDGs, campaigns,
  integration associations. Contacts use `TagContact` (contact tags are separate; not
  console-taggable).
- Tag metadata persists after resource deletion (until instance deletion) to keep
  tag-based access control on historical metrics consistent.
- **TBAC** inside Connect: security profiles can restrict access to resources by tag.
  In IAM: use `aws:ResourceTag/{key}`, `aws:RequestTag/{key}`, `aws:TagKeys`.

### IAM basics for Connect
- Namespace `connect:`; most actions support **resource-level permissions** against the ARN
  patterns above (remember `agent/` for users) and the `connect:InstanceId` condition key
  to pin policies to one instance.
- Useful condition keys: `connect:InstanceId`, `connect:FlowType`, `connect:Channel`,
  `connect:ContactInitiationMethod`, `connect:UserArn`, `connect:PreferredUserArn`,
  `connect:StorageResourceType`, `connect:SearchTag/{key}`.
- Key action groups:
  - Admin/provisioning: `connect:CreateInstance` (needs `iam:CreateServiceLinkedRole`, `ds:*`
    dependent actions), `connect:CreateUser`, `connect:CreateQueue`,
    `connect:CreateRoutingProfile`, `connect:CreateContactFlow`,
    `connect:ClaimPhoneNumber`, `connect:AssociateInstanceStorageConfig`.
  - Runtime: `connect:StartOutboundVoiceContact`, `connect:StartChatContact`,
    `connect:StartTaskContact`, `connect:StartEmailContact`, `connect:StopContact`,
    `connect:GetContactAttributes`, `connect:UpdateContactAttributes`,
    `connect:UpdateContactRoutingData`, `connect:TransferContact`.
  - Metrics: `connect:GetMetricDataV2`, `connect:GetCurrentMetricData`,
    `connect:GetCurrentUserData`.
  - Federation: `connect:GetFederationToken` (SAML sign-in path; requires
    `connect:DescribeInstance`/`ListInstances`).
- `CreateUser` checks resource-level permission on the routing-profile, security-profile,
  and hierarchy-group ARNs being assigned — least-privilege policies must include those.
- Remember the two-layer model: IAM for the AWS control plane; **Connect security profiles
  for everything inside the admin website/CCP**. An IAM admin with no Connect user still
  can't see contacts; a Connect Admin user needs no IAM permissions to run the contact
  center day-to-day (emergency admin access is via the Connect console with
  `connect:GetFederationToken`/admin login).

## Quick pitfall checklist
- Concurrent calls default = **10**; campaigns default = **0**. Request increases weeks
  before go-live (large increases can take 3+ weeks).
- Identity management mode is immutable after instance creation.
- Agent statuses quota (50) and hours-of-operation overrides (50) are not adjustable.
- `SearchContacts` throttles at 0.5 TPS; API throttles are account-wide per Region.
- Email channel requires the attachments-bucket CORS policy — without it email fails.
- User/queue quick connects only show during an active transfer, and only if attached to a
  queue in the agent's routing profile.
- Queue-to-queue transfer resets a contact's queue position; agent quick-connect transfer
  preserves it.
- DID numbers have per-number concurrent-call caps and no carrier redundancy; use toll-free
  for critical high-volume inbound.
- 100 instance create/delete operations per 30 days — don't churn instances in automation.
- Deleting hierarchy levels/groups breaks links to historical contacts irreversibly.
- Voice ID is end-of-support (2026-05-20); migrate any voice-auth dependencies.

## Sources
- https://docs.aws.amazon.com/connect/latest/adminguide/what-is-amazon-connect.html
- https://docs.aws.amazon.com/connect/latest/adminguide/amazon-connect-service-limits.html
- https://docs.aws.amazon.com/connect/latest/adminguide/feature-limits.html
- https://docs.aws.amazon.com/connect/latest/adminguide/concepts-queues-standard-and-agent.html
- https://docs.aws.amazon.com/connect/latest/adminguide/concepts-routing.html
- https://docs.aws.amazon.com/connect/latest/adminguide/about-routing.html
- https://docs.aws.amazon.com/connect/latest/adminguide/routing-profiles.html
- https://docs.aws.amazon.com/connect/latest/adminguide/set-hours-operation.html
- https://docs.aws.amazon.com/connect/latest/adminguide/quick-connects.html
- https://docs.aws.amazon.com/connect/latest/adminguide/contact-center-phone-number.html
- https://docs.aws.amazon.com/connect/latest/adminguide/concepts-telephony.html
- https://docs.aws.amazon.com/connect/latest/adminguide/claim-and-manage-phonenumbers.html
- https://docs.aws.amazon.com/connect/latest/adminguide/uifn-service.html
- https://docs.aws.amazon.com/connect/latest/adminguide/setup-connect-global-resiliency.html
- https://docs.aws.amazon.com/connect/latest/adminguide/update-instance-settings.html
- https://docs.aws.amazon.com/connect/latest/adminguide/connect-security-profiles.html
- https://docs.aws.amazon.com/connect/latest/adminguide/agent-hierarchy.html
- https://docs.aws.amazon.com/connect/latest/adminguide/tagging.html
- https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazonconnect.html
- https://aws.amazon.com/connect/pricing/

# Amazon Connect — APIs & SDKs

> Last updated: 2026-07 (baseline)

Backend/programmatic surface of Amazon Connect. Naming note (2026): AWS now refers to
"Amazon Connect" as a portfolio of agentic solutions; the classic contact-center product is
called **Amazon Connect Customer** in newer docs. API names, endpoints, and SDK clients are
unchanged — treat the names interchangeably.

## Service / namespace family

| API namespace (SigV4 signing name) | Endpoint pattern | boto3 client | JS SDK v3 package | Purpose |
|---|---|---|---|---|
| `connect` | `connect.{region}.amazonaws.com` | `connect` | `@aws-sdk/client-connect` | Main service: contacts, users, queues, routing profiles, flows, phone numbers, metrics, hours, evaluations, views, tasks, email |
| `connectparticipant` | `participant.connect.{region}.amazonaws.com` | `connectparticipant` | `@aws-sdk/client-connectparticipant` | Participant Service — chat/messaging participants: send messages/events, attachments, transcripts, websocket connections. **Not SigV4-signed** — token-based (`X-Amz-Bearer`) |
| `connect-contact-lens` | `contact-lens.{region}.amazonaws.com` | `connect-contact-lens` | `@aws-sdk/client-connect-contact-lens` | Contact Lens real-time analytics: `ListRealtimeContactAnalysisSegments` (transcript, sentiment, categories). Post-call output lands in S3, not this API |
| `cases` (`connectcases`) | `cases.{region}.amazonaws.com` | `connectcases` | `@aws-sdk/client-connectcases` | Cases: domains, fields, templates, layouts, `CreateCase`/`GetCase`/`SearchCases`/`UpdateCase`, related items, case rules, SLAs |
| `connect-campaigns` | `connect-campaigns.{region}.amazonaws.com` | `connectcampaigns` (v1), `connectcampaignsv2` (v2) | `@aws-sdk/client-connectcampaigns`, `@aws-sdk/client-connectcampaignsv2` | Outbound campaigns. V2 (`AmazonConnectCampaignServiceV2`) adds multi-channel (voice/SMS/email) subtypes, communication limits/time windows, `PutOutboundRequestBatch`, `PutProfileOutboundRequestBatch`. V1 not available in some regions (e.g. af-south-1) — prefer V2 |
| `profile` (`customer-profiles`) | `profile.{region}.amazonaws.com` | `customer-profiles` | `@aws-sdk/client-customer-profiles` | Customer Profiles: domains, profile object types, `CreateProfile`/`SearchProfiles`/`MergeProfiles`, calculated attributes, segments, identity resolution, event streams/triggers |
| `voiceid` | `voiceid.{region}.amazonaws.com` | `voice-id` | `@aws-sdk/client-voice-id` | **End of support: May 20, 2026.** Caller authentication / fraud detection (domains, speakers, fraudsters, watchlists, `EvaluateSession`). Do not build new integrations |
| `wisdom` / `qconnect` | `wisdom.{region}.amazonaws.com` | `wisdom` (legacy), `qconnect` | `@aws-sdk/client-wisdom`, `@aws-sdk/client-qconnect` | Amazon Q in Connect (evolution of Wisdom): assistants, knowledge bases, content, quick responses, message templates, AI agents/prompts/guardrails, `QueryAssistant`, sessions. New work should use `qconnect` |
| `app-integrations` | `app-integrations.{region}.amazonaws.com` | `appintegrations` | `@aws-sdk/client-appintegrations` | AppIntegrations: reusable Data/Event integrations with external apps, 3P apps in agent workspace, applications |

FIPS variants exist for most (`connect-fips.{region}.amazonaws.com`, `profile-fips...`, etc.).
All HTTPS/443. All are regional; call the region where the Connect instance lives.

## Cross-cutting conventions

- **Auth**: Standard AWS SigV4 with IAM credentials for every namespace **except**
  `connectparticipant`, whose data-plane ops authenticate with a token in the `X-Amz-Bearer`
  header instead of SigV4 (so end customers need no AWS credentials). SDK clients for
  connectparticipant still work fine with anonymous/dummy credentials.
- **Instance scoping**: Nearly every main-`connect` call takes `InstanceId` (the UUID from the
  instance ARN `arn:aws:connect:{region}:{acct}:instance/{instanceId}`). Resource IDs
  (queue, flow, user...) are the last ARN segment. GetMetricDataV2 is the exception — it takes
  the full instance ARN as `ResourceArn`. IAM policies can scope to
  `arn:aws:connect:{region}:{acct}:instance/{instanceId}/*` resources.
- **Protocol**: REST-JSON. Each operation has its own method+path, e.g.
  `PUT /contact/outbound-voice`, `PUT /contact/chat`, `PUT /contact/task`,
  `POST /contact/attributes`, `POST /metrics/data`, `POST /participant/message`.
- **Pagination**: `NextToken` (string) + `MaxResults` (commonly max 100; some Lists max 1000).
  boto3 exposes paginators (`client.get_paginator("list_users")`, `search_contacts`, etc.);
  JS v3 exposes `paginateListUsers`-style async generators for many list ops.
- **Idempotency**: Mutating "start/create" ops accept `ClientToken` (max 500 chars); the SDK
  auto-fills it if omitted. For `StartOutboundVoiceContact` the token is valid 7 days — a retry
  with the same token returns the existing `ContactId` instead of dialing again.
- **Errors**: `InvalidParameterException` / `InvalidRequestException` (400),
  `AccessDeniedException` (403), `ResourceNotFoundException` (404), `LimitExceededException` /
  `TooManyRequests`/`ThrottlingException` (429), `ServiceQuotaExceededException` (402 on
  StartTaskContact), `InternalServiceException` (500). Instances with Global Resiliency return
  `InvalidActiveRegionException` when you call the non-active region.

### Throttling (default TPS, account-level per region — all instances/users share the bucket)

Main `connect` API default: **RateLimit 2 rps, BurstLimit 5 rps** for every operation except:

| Operation | Rate | Burst |
|---|---|---|
| GetMetricDataV2 | 10 | 10 |
| GetMetricData / GetCurrentMetricData | 5 | 8 |
| SearchContacts | 0.5 | 1 |
| StartChatContact, StartContactStreaming, StopContactStreaming, CreateParticipant, CreatePersistentContactAssociation, UpdateParticipantRoleConfig | 5 | 8 |
| GetContactAttributes, UpdateContactAttributes, DescribeContact, StopContact, UpdateContact, ListContactReferences, BatchPutContact | 10 | 15 |
| TagContact / UntagContact | 20 | 25 |
| UpdateContactRoutingData | 20 | 20 |
| SendChatIntegrationEvent | 17 | 26 |
| All Evaluations actions | 1 | — |

`connectparticipant` (quotas are **per instance**): CreateParticipantConnection 6/9,
SendMessage & SendEvent 10/15, GetTranscript & GetAttachment 8/12, DisconnectParticipant 3/5,
Start/CompleteAttachmentUpload 2/5.

Campaigns: most lifecycle ops (Create/Start/Stop/Pause/ResumeCampaign...) 1/2;
GetCampaignState(Batch), ListCampaigns 5/10; PutDialRequestBatch / PutOutboundRequestBatch /
PutProfileOutboundRequestBatch 10/10; DescribeCampaign 25/35.

Contact Lens: ListRealtimeContactAnalysisSegments 1/2 (V2 in main connect API: 2/5).

Resource quotas that gate contact-starting APIs (defaults, adjustable): concurrent active
calls/instance **10**, concurrent chats **500**, concurrent tasks **2,500**, concurrent
emails **1,000**, campaign concurrent calls **0** (must request), users **500**, queues **100**,
phone numbers **5**, Lambda functions/instance **50**. Exceeding concurrent-chat quota makes
StartChatContact fail 429 `LimitExceededException` (distinct from TPS `TooManyRequests`).
Note: GetCurrentMetricData / GetMetricDataV2 / GetCurrentUserData may wrongly show 200 TPS in
the Service Quotas console; trust the table above.

## Main `connect` API — key operations by task

### Starting contacts (all return `ContactId`; all take `InstanceId`, most take `ClientToken`)
- `StartOutboundVoiceContact` — dial a customer, run a flow (agents don't dial). `PUT /contact/outbound-voice`. Requires `ContactFlowId`, `DestinationPhoneNumber` (E.164); one of `QueueId` (caller ID from queue) or `SourcePhoneNumber` required. Optional `AnswerMachineDetectionConfig`, `TrafficType` (`GENERAL`|`CAMPAIGN`), `CampaignId`, `RingTimeoutInSeconds` (15–60, default 60), `Attributes`, `References`, `RelatedContactId`, `OutboundStrategy` (agent-first/preview dialing).
- `StartChatContact` — `PUT /contact/chat`. Requires `ContactFlowId`, `ParticipantDetails.DisplayName`. Returns `ContactId`, `ParticipantId`, `ParticipantToken` (+`ContinuedFromContactId` for persistent chat). Optional `SupportedMessagingContentTypes` (must include `text/plain`; add `text/markdown`, `application/json`, `application/vnd.amazonaws.connect.message.interactive[.response]`), `ChatDurationInMinutes` (60–10080, default 25h), `PersistentChat` (`SourceContactId` + `RehydrationType` `ENTIRE_PAST_SESSION`|`FROM_SEGMENT`), `InitialMessage`, `SegmentAttributes` (e.g. `connect:Subtype`), `DisconnectOnCustomerExit`.
- `StartTaskContact` — `PUT /contact/task`. Requires `Name`; exactly one of `ContactFlowId` | `QuickConnectId` | `TaskTemplateId` (template must have a flow attached). `ScheduledTime` up to 6 days out; `PreviousContactId` (chain, max 12, shared attributes) vs `RelatedContactId` (copy attributes, unlimited); up to 5 S3-presigned `Attachments`; `SegmentAttributes` for `connect:ContactExpiry`.
- `StartEmailContact` / `StartOutboundEmailContact` / `SendOutboundEmail` — inbound email contact creation and agent/flow-initiated outbound email (email channel GA since late 2024).
- `StartOutboundChatContact` — outbound SMS/messaging chat (e.g. via SendChatIntegrationEvent pipelines).
- `StartWebRTCContact` — in-app/web voice (and video) calling; returns `ConnectionData` (Chime SDK `Meeting`/`Attendee`) plus `ParticipantId`/`ParticipantToken`. Add more parties with `CreateParticipant` + participant `CreateParticipantConnection(Type=["WEBRTC_CONNECTION"])`.
- `CreateContact` / `BatchPutContact` — create contacts outside the standard start APIs (e.g. email, custom ingestion).

### Controlling in-flight contacts
- `StopContact` — end a contact (voice initiated by API/flow/queue-transfer/callback/disconnect; chat/task any state).
- `TransferContact` — transfer active contact to another queue/agent via a flow (`ContactId`, `ContactFlowId`, `QueueId`|`UserId`).
- `UpdateContactAttributes` — set/overwrite user-defined attributes (see below).
- `UpdateContact` — name/description/references; `UpdateContactRoutingData` — queue priority & position; `UpdateContactSchedule` — reschedule a scheduled task.
- `PauseContact` / `ResumeContact` — pause/resume a task contact.
- `MonitorContact` — start supervisor monitoring/barge (`AllowedMonitorCapabilities`: `SILENT_MONITOR`, `BARGE`).
- Recording controls: `StartContactRecording`, `StopContactRecording`, `SuspendContactRecording`, `ResumeContactRecording`.
- Chat plumbing: `StartContactStreaming`/`StopContactStreaming` (SNS-based message streaming instead of websocket), `CreateParticipant` (add custom participant to chat / party to WebRTC call), `UpdateParticipantRoleConfig` (per-role chat timers), `SendChatIntegrationEvent` (bridge SMS/3P messaging into chat), `CreatePersistentContactAssociation`.
- `DismissUserContact` — clear a missed/ACW contact from an agent's CCP; `PutUserStatus` — change agent status; `AssociateContactWithUser`.

### Contact search & details
- `DescribeContact` — contact record snapshot (channel, queue, agent info, initiation method, timestamps, `AttributesLastUpdated`...). Contact details available while active + retention window.
- `SearchContacts` — search contacts up to the last 2 years by time range (`InitiationTimeRange` etc.), `SearchCriteria` (channels, statuses, queues, agents, initiation methods, keyword in transcripts), `Sort`, paginated. Low TPS (0.5) — cache/batch.
- `GetContactAttributes` — returns the user-defined attribute map for an `InitialContactId`.
- `GetContactMetrics`, `ListContactReferences`, `ListAssociatedContacts`, `TagContact`/`UntagContact`.
- Evaluations: `ListContactEvaluations`, `DescribeContactEvaluation`, `StartContactEvaluation`, `SubmitContactEvaluation`, `SearchContactEvaluations`, evaluation-form CRUD (`CreateEvaluationForm`, `ActivateEvaluationForm`...). All evaluation ops throttle at 1 rps.

### Metrics
- **`GetMetricDataV2`** (`POST /metrics/data`) — historical metrics, preferred API.
  - `ResourceArn` = full **instance ARN** (not InstanceId).
  - `StartTime`/`EndTime` epoch seconds; lookback max **3 months**; window ≤ **35 days**
    (`DAY`/`WEEK`/`TOTAL` interval) or < **3 days** (`FIFTEEN_MIN`/`THIRTY_MIN`/`HOUR`).
  - `Interval`: `{IntervalPeriod, TimeZone}`; default `TOTAL`.
  - `Filters`: 1–5 `FilterV2` objects `{FilterKey, FilterValues}`; ≤100 values total across keys
    (CHANNEL values don't count). **At least one resource filter is required for authorization**:
    `QUEUE`, `ROUTING_PROFILE`, `AGENT`, `AGENT_HIERARCHY_LEVEL_{ONE..FIVE}`, `CAMPAIGN`,
    `EVALUATION_FORM`, or `EVALUATOR_ID`. Other keys: `CHANNEL`, `INITIATION_METHOD`,
    `DISCONNECT_REASON`, `FEATURE`, `Q_CONNECT_ENABLED`, `contact/segmentAttributes/connect:Subtype`,
    flow keys (`FLOW_TYPE`, `FLOWS_RESOURCE_ID`, `FLOWS_OUTCOME_TYPE`...), bot keys, campaign keys.
  - `Groupings`: ≤4 of the same key space (plus grouping-only keys like `AI_AGENT_NAME_VERSION`).
  - `Metrics`: array of `MetricV2` `{Name, Threshold[{Comparison,ThresholdValue}], MetricFilters[{MetricFilterKey,MetricFilterValues,Negate}]}`.
    Names e.g. `CONTACTS_HANDLED`, `CONTACTS_QUEUED`, `ABANDONMENT_RATE`, `AVG_HANDLE_TIME`,
    `AVG_QUEUE_ANSWER_TIME`, `SERVICE_LEVEL` (needs `Threshold` with `Comparison:"LT"` +
    `ThresholdValue` seconds), `AGENT_OCCUPANCY`, `SUM_CONTACTS_ANSWERED_IN_X`. Custom metrics
    referenced by `MetricId` ARN (≤20/request).
  - Response: `MetricResults[{Dimensions, MetricInterval, Collections[{Metric, Value}]}]` +
    `NextToken` (`MaxResults` ≤100). Null value = incomputable; empty MetricResults = no data.
- `GetMetricData` — legacy v1 (queue-scoped, 24h window); use V2.
- `GetCurrentMetricData` — real-time queue/routing-profile snapshot (`AGENTS_ONLINE`,
  `AGENTS_AVAILABLE`, `CONTACTS_IN_QUEUE`, `OLDEST_CONTACT_AGE`...). Filters: Queues (≤100),
  RoutingProfiles, Channels; Groupings QUEUE/CHANNEL/ROUTING_PROFILE. Data delay ~real-time;
  results cached briefly server-side.
- `GetCurrentUserData` — real-time per-agent status/contact state (filter by queues, routing
  profiles, agents, user hierarchy).

### Admin CRUD (all instance-scoped; default 2/5 TPS)
- Users: `CreateUser`, `DescribeUser`, `UpdateUserIdentityInfo|PhoneConfig|RoutingProfile|SecurityProfiles|Hierarchy|Proficiencies`, `DeleteUser`, `ListUsers`, `SearchUsers`, hierarchy groups (`CreateUserHierarchyGroup`...), agent statuses (`CreateAgentStatus`...).
- Queues: `CreateQueue`, `DescribeQueue`, `UpdateQueueName|HoursOfOperation|MaxContacts|OutboundCallerConfig|Status`, `SearchQueues`, quick connects (`CreateQuickConnect`, `AssociateQueueQuickConnects`...).
- Routing profiles: `CreateRoutingProfile`, `UpdateRoutingProfileQueues|Concurrency|DefaultOutboundQueue|AgentAvailabilityTimer`, `AssociateRoutingProfileQueues`, `SearchRoutingProfiles`.
- Hours: `CreateHoursOfOperation`, `UpdateHoursOfOperation`, `CreateHoursOfOperationOverride`, `GetEffectiveHoursOfOperations`, `SearchHoursOfOperations`.
- Flows: `CreateContactFlow` (content = flow language JSON string), `UpdateContactFlowContent`, `UpdateContactFlowMetadata|Name`, `DescribeContactFlow`, `SearchContactFlows`, flow modules (`CreateContactFlowModule`, `UpdateContactFlowModuleContent`...), versioning (`CreateContactFlowVersion`, `ListContactFlowVersions`), `AssociateFlow`/`GetFlowAssociation` (flow-to-resource mapping, e.g. default outbound).
- Phone numbers: `SearchAvailablePhoneNumbers` (by country + type DID/TOLL_FREE/UIFN/shared...), `ClaimPhoneNumber` (takes `TargetArn` instance/TDG ARN or `InstanceId`; idempotent via `ClientToken`), `UpdatePhoneNumber` (re-point to another instance/TDG), `ReleasePhoneNumber`, `ImportPhoneNumber` (from End User Messaging), `DescribePhoneNumber`, `ListPhoneNumbers`(V2 = `ListPhoneNumbersV2` in SDKs), `AssociatePhoneNumberContactFlow`.
- Also: prompts, vocabularies (`CreateVocabulary`), views, task templates, predefined attributes, security profiles, traffic distribution groups (`CreateTrafficDistributionGroup`, `UpdateTrafficDistribution` for multi-region), `ReplicateInstance`, rules (`CreateRule` for Contact Lens/alerts), data tables (2025+: `CreateDataTable`, `BatchCreateDataTableValue`...).

### Resource association (instance config plane)
- `AssociateLambdaFunction` / `DisassociateLambdaFunction` / `ListLambdaFunctions` — allow a Lambda ARN to be invoked from flows (≤50/instance).
- `AssociateBot` / `DisassociateBot` / `ListBots` (Lex V2), `AssociateLexBot` (V1 legacy).
- `AssociateInstanceStorageConfig` / `UpdateInstanceStorageConfig` / `ListInstanceStorageConfigs` — per-resource-type storage: `CALL_RECORDINGS`, `CHAT_TRANSCRIPTS`, `SCREEN_RECORDINGS`, `CONTACT_TRACE_RECORDS`, `AGENT_EVENTS`, `REAL_TIME_CONTACT_ANALYSIS_SEGMENTS`... → S3 / Kinesis stream / Firehose.
- `AssociateApprovedOrigin` (CORS origins for embedded CCP), `AssociateSecurityKey`, `AssociateDefaultVocabulary`, `AssociateAnalyticsDataSet` (data lake), `CreateIntegrationAssociation` (wire Cases/Q/Voice ID/App/Pinpoint/SES to the instance), `CreateUseCase`.
- Instance lifecycle: `CreateInstance`, `DescribeInstance`, `ListInstances`, `UpdateInstanceAttribute` (feature toggles: `CONTACT_LENS`, `CONTACTFLOW_LOGS`, `MULTI_PARTY_CONFERENCE`...), `GetFederationToken` (SAML federation, 2 TPS).

## `connectparticipant` — chat participant flow

Two tokens, in order:
1. `ParticipantToken` — from `StartChatContact` (or `CreateParticipant`/`StartContactStreaming`).
   Valid for the participant's lifetime in the contact. Used **only** for
   `CreateParticipantConnection` (header `X-Amz-Bearer: <ParticipantToken>`).
2. `ConnectionToken` — returned by `CreateParticipantConnection(Type=["CONNECTION_CREDENTIALS"])`.
   Valid **1 day** (independent of `ChatDurationInMinutes`). Used for everything else:
   `SendMessage`, `SendEvent` (typing/read receipts), `GetTranscript`, `DisconnectParticipant`,
   `StartAttachmentUpload`/`CompleteAttachmentUpload`/`GetAttachment`, `DescribeView`.

Websocket: `CreateParticipantConnection(Type=["WEBSOCKET", "CONNECTION_CREDENTIALS"])` returns
`Websocket.Url` (must connect within **100s**; expires at `ConnectionExpiry` — re-call the API
with the ParticipantToken to get a fresh URL). After connecting, subscribe by sending:

```json
{"topic":"aws/subscribe","content":{"topics":["aws/chat"]}}
```

Incoming messages/events arrive on `aws/chat`. Alternative to websocket: polling with
`GetTranscript`, or server-side streaming via `StartContactStreaming` (SNS topic) with
`CreateParticipantConnection(ConnectParticipant=true)` to mark the customer connected.
Clients must call CreateParticipantConnection within **5 minutes** of StartChatContact.
`SendMessage`: `Content` ≤16,384 bytes; `ContentType` one of `text/plain`, `text/markdown`,
`application/json`, `application/vnd.amazonaws.connect.message.interactive.response` (must be
allowed by the contact's `SupportedMessagingContentTypes`).

## Code examples

### StartOutboundVoiceContact

```python
import boto3

connect = boto3.client("connect", region_name="us-east-1")

resp = connect.start_outbound_voice_contact(
    InstanceId="11111111-2222-3333-4444-555555555555",
    ContactFlowId="846ec553-a005-41c0-8341-000000000000",
    DestinationPhoneNumber="+14155550123",   # E.164
    QueueId="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",  # or SourcePhoneNumber="+18005550100"
    Attributes={"orderId": "12345", "tier": "gold"},
    ClientToken="order-12345-callback-1",    # idempotent for 7 days
)
print(resp["ContactId"])
```

```typescript
import { ConnectClient, StartOutboundVoiceContactCommand } from "@aws-sdk/client-connect";

const connect = new ConnectClient({ region: "us-east-1" });

const { ContactId } = await connect.send(new StartOutboundVoiceContactCommand({
  InstanceId: "11111111-2222-3333-4444-555555555555",
  ContactFlowId: "846ec553-a005-41c0-8341-000000000000",
  DestinationPhoneNumber: "+14155550123",
  QueueId: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  Attributes: { orderId: "12345" },
  ClientToken: "order-12345-callback-1",
}));
```

### StartChatContact + participant connection + SendMessage

```python
import boto3

connect = boto3.client("connect", region_name="us-east-1")
participant = boto3.client("connectparticipant", region_name="us-east-1")

chat = connect.start_chat_contact(
    InstanceId="11111111-2222-3333-4444-555555555555",
    ContactFlowId="846ec553-a005-41c0-8341-000000000000",
    ParticipantDetails={"DisplayName": "Jane Doe"},
    Attributes={"customerId": "C-42"},
    SupportedMessagingContentTypes=["text/plain", "text/markdown"],
)
# chat: ContactId, ParticipantId, ParticipantToken

# Exchange ParticipantToken -> websocket URL + ConnectionToken (within 5 min)
conn = participant.create_participant_connection(
    ParticipantToken=chat["ParticipantToken"],
    Type=["WEBSOCKET", "CONNECTION_CREDENTIALS"],
)
ws_url = conn["Websocket"]["Url"]                       # connect within 100s,
connection_token = conn["ConnectionCredentials"]["ConnectionToken"]  # valid 1 day
# On the websocket, send: {"topic":"aws/subscribe","content":{"topics":["aws/chat"]}}

# All subsequent participant calls use ConnectionToken (NOT ParticipantToken)
participant.send_message(
    ConnectionToken=connection_token,
    ContentType="text/plain",
    Content="Hello, I need help with my order.",
)
transcript = participant.get_transcript(ConnectionToken=connection_token, MaxResults=15)
```

```typescript
import { ConnectClient, StartChatContactCommand } from "@aws-sdk/client-connect";
import {
  ConnectParticipantClient,
  CreateParticipantConnectionCommand,
  SendMessageCommand,
} from "@aws-sdk/client-connectparticipant";

const connect = new ConnectClient({ region: "us-east-1" });
const chat = await connect.send(new StartChatContactCommand({
  InstanceId: "11111111-2222-3333-4444-555555555555",
  ContactFlowId: "846ec553-a005-41c0-8341-000000000000",
  ParticipantDetails: { DisplayName: "Jane Doe" },
  SupportedMessagingContentTypes: ["text/plain", "text/markdown"],
}));

// Participant Service is token-authenticated; SigV4 creds are not used.
const participant = new ConnectParticipantClient({ region: "us-east-1" });

const conn = await participant.send(new CreateParticipantConnectionCommand({
  ParticipantToken: chat.ParticipantToken!,
  Type: ["WEBSOCKET", "CONNECTION_CREDENTIALS"],
}));
const connectionToken = conn.ConnectionCredentials!.ConnectionToken!;

// const ws = new WebSocket(conn.Websocket!.Url!);
// ws.onopen = () => ws.send(JSON.stringify({ topic: "aws/subscribe", content: { topics: ["aws/chat"] } }));

await participant.send(new SendMessageCommand({
  ConnectionToken: connectionToken,
  ContentType: "text/plain",
  Content: "Hello, I need help with my order.",
}));
```

### GetMetricDataV2

```python
from datetime import datetime, timedelta, timezone
import boto3

connect = boto3.client("connect", region_name="us-east-1")
INSTANCE_ARN = "arn:aws:connect:us-east-1:123456789012:instance/11111111-2222-3333-4444-555555555555"

end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
start = end - timedelta(days=7)          # <=35 days for DAY/TOTAL; <3 days for HOUR and finer

kwargs = dict(
    ResourceArn=INSTANCE_ARN,            # full ARN, not InstanceId
    StartTime=start, EndTime=end,
    Interval={"IntervalPeriod": "DAY", "TimeZone": "UTC"},
    Filters=[  # at least one resource filter (QUEUE/ROUTING_PROFILE/AGENT/...) is required
        {"FilterKey": "QUEUE", "FilterValues": ["aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"]},
        {"FilterKey": "CHANNEL", "FilterValues": ["VOICE", "CHAT"]},
    ],
    Groupings=["QUEUE", "CHANNEL"],      # max 4
    Metrics=[
        {"Name": "CONTACTS_HANDLED"},
        {"Name": "ABANDONMENT_RATE"},
        {"Name": "AVG_HANDLE_TIME"},
        {"Name": "SERVICE_LEVEL",
         "Threshold": [{"Comparison": "LT", "ThresholdValue": 60}]},  # answered < 60s
    ],
    MaxResults=100,
)

results, token = [], None
while True:
    resp = connect.get_metric_data_v2(**kwargs, **({"NextToken": token} if token else {}))
    results += resp["MetricResults"]
    token = resp.get("NextToken")
    if not token:
        break

for r in results:
    print(r["Dimensions"], {c["Metric"]["Name"]: c.get("Value") for c in r["Collections"]})
```

```typescript
import { ConnectClient, GetMetricDataV2Command, MetricResultV2 } from "@aws-sdk/client-connect";

const connect = new ConnectClient({ region: "us-east-1" });
const end = new Date(); const start = new Date(end.getTime() - 7 * 864e5);

let nextToken: string | undefined;
const results: MetricResultV2[] = [];
do {
  const resp = await connect.send(new GetMetricDataV2Command({
    ResourceArn: "arn:aws:connect:us-east-1:123456789012:instance/11111111-2222-3333-4444-555555555555",
    StartTime: start, EndTime: end,
    Interval: { IntervalPeriod: "DAY", TimeZone: "UTC" },
    Filters: [{ FilterKey: "QUEUE", FilterValues: ["aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"] }],
    Groupings: ["QUEUE"],
    Metrics: [
      { Name: "CONTACTS_HANDLED" },
      { Name: "SERVICE_LEVEL", Threshold: [{ Comparison: "LT", ThresholdValue: 60 }] },
    ],
    MaxResults: 100,
    NextToken: nextToken,
  }));
  results.push(...(resp.MetricResults ?? []));
  nextToken = resp.NextToken;
} while (nextToken);
```

### UpdateContactAttributes

```python
import boto3

connect = boto3.client("connect", region_name="us-east-1")
connect.update_contact_attributes(          # POST /contact/attributes; empty 200 response
    InstanceId="11111111-2222-3333-4444-555555555555",
    InitialContactId="99999999-8888-7777-6666-555555555555",  # ID of the FIRST contact in the interaction
    Attributes={"escalated": "true", "csatFollowUp": ""},     # empty string clears a value
)
```

```typescript
import { ConnectClient, UpdateContactAttributesCommand } from "@aws-sdk/client-connect";

const connect = new ConnectClient({ region: "us-east-1" });
await connect.send(new UpdateContactAttributesCommand({
  InstanceId: "11111111-2222-3333-4444-555555555555",
  InitialContactId: "99999999-8888-7777-6666-555555555555",
  Attributes: { escalated: "true" },
}));
```

## Gotchas

- **ParticipantToken vs ConnectionToken**: mixing them up is the #1 chat bug. ParticipantToken
  → only `CreateParticipantConnection`; ConnectionToken → every other participant call.
  Both go in `X-Amz-Bearer` at the HTTP level; SDKs map them from the request field.
- **Websocket vs polling**: the websocket URL is single-use-ish — connect within 100s, resubscribe
  to `aws/chat` after every (re)connect, and fetch a new URL via CreateParticipantConnection when
  it expires. Messages sent while disconnected are NOT replayed on the socket — reconcile with
  `GetTranscript`. For server-to-server bots, `StartContactStreaming` (SNS) avoids websockets.
- **GetMetricDataV2 windows**: 3-month lookback; ≤35-day span (DAY/WEEK/TOTAL), <3-day span for
  FIFTEEN_MIN/THIRTY_MIN/HOUR. A request without one of the *resource* filter keys
  (QUEUE/ROUTING_PROFILE/AGENT/hierarchy/CAMPAIGN/EVALUATION_FORM/EVALUATOR_ID) is rejected —
  CHANNEL alone is not enough. `ResourceArn` is the full instance ARN.
- **UpdateContactAttributes** works on **completed** contacts too (attributes retained 24 months),
  but must target the `InitialContactId` (first contact of the interaction), not a transfer-leg
  contact ID. Total attribute payload ≤32 KB per contact.
- **StartTaskContact**: pass exactly one of ContactFlowId/QuickConnectId/TaskTemplateId;
  `ServiceQuotaExceededException` surfaces as HTTP 402 (open-task quota, or 13th task on the same
  PreviousContactId).
- **StartOutboundVoiceContact**: default concurrent-calls quota is only 10/instance and campaign
  traffic (`TrafficType=CAMPAIGN`) is quota-gated at 0 until you request an increase; UK `+447`
  mobiles blocked by default. Contact starts even if the customer never answers — the flow decides.
- **Throttling is account-wide per region** (all instances share buckets), and the burst refill is
  token-bucket style; retry 429s with jittered backoff (SDK default retryers handle this).
- **SearchContacts is 0.5 TPS** — do not put it in a per-request path.
- **Voice ID is EOL May 20, 2026** — Associate/Fraudster/Speaker APIs will stop working.
- **Wisdom → Q in Connect**: `wisdom` SDK clients still resolve, but new features (AI agents,
  guardrails, message templates) are only in `qconnect`; both sign against `wisdom.{region}` hosts.
- Chat idle sessions count against the 500 concurrent-chat quota; use persistent chat
  (`PersistentChat`/`CreatePersistentContactAssociation`) to avoid burning quota on idle sessions.
- Contact search/details operations paginate with small `MaxResults`; use SDK paginators
  (boto3 `get_paginator`, JS v3 `paginate*` helpers) instead of hand-rolled loops when available.

## Sources

- https://docs.aws.amazon.com/connect/latest/APIReference/Welcome.html
- https://docs.aws.amazon.com/connect/latest/APIReference/API_Operations.html
- https://docs.aws.amazon.com/connect/latest/APIReference/API_StartOutboundVoiceContact.html
- https://docs.aws.amazon.com/connect/latest/APIReference/API_StartChatContact.html
- https://docs.aws.amazon.com/connect/latest/APIReference/API_StartTaskContact.html
- https://docs.aws.amazon.com/connect/latest/APIReference/API_GetMetricDataV2.html
- https://docs.aws.amazon.com/connect/latest/APIReference/API_UpdateContactAttributes.html
- https://docs.aws.amazon.com/connect-participant/latest/APIReference/API_CreateParticipantConnection.html
- https://docs.aws.amazon.com/connect-participant/latest/APIReference/API_SendMessage.html
- https://docs.aws.amazon.com/connect/latest/adminguide/amazon-connect-service-limits.html
- https://docs.aws.amazon.com/general/latest/gr/connect_region.html
- https://docs.aws.amazon.com/boto3/latest/reference/services/connect.html
- https://docs.aws.amazon.com/AWSJavaScriptSDK/v3/latest/client/connect/

# Amazon Connect — Data, Metrics & Analytics
> Last updated: 2026-07 (baseline)

Reference for building reporting/analytics on Amazon Connect: contact records, agent event streams, EventBridge contact events, metrics APIs, the analytics data lake, S3 artifact locations, Contact Lens output, and pipeline patterns.

---

## 1. Data surfaces at a glance

| Surface | Transport | Latency | Use for |
|---|---|---|---|
| Contact records (CTRs) | Kinesis Data Streams or Firehose | near real-time, re-emitted on updates | System of record per contact; historical reporting |
| Agent event streams | Kinesis Data Streams only | near real-time | Agent state/adherence, WFM, ACW calculation |
| Contact events | EventBridge (`source: aws.connect`) | near real-time, best-effort, unordered | Event-driven apps, live contact tracking |
| Real-time metrics | `GetCurrentMetricData` / `GetCurrentUserData` | snapshot | Live queue/agent dashboards |
| Historical metrics | `GetMetricDataV2` | trailing 3 months | Aggregated KPIs (AHT, SL, abandonment) |
| Analytics data lake | Zero-ETL → Glue/Lake Formation tables, query with Athena | < 1 hour after record creation | SQL/BI without building a pipeline |
| S3 artifacts | Instance S3 bucket | shortly after disconnect | Recordings, chat transcripts, Contact Lens JSON, reports |

Terminology: "Contact Trace Record (CTR)" and "contact record" are the same thing; AWS now says "contact record" only.

---

## 2. Contact records (CTRs)

### Delivery semantics — the critical gotchas
- **At-least-once, re-emitted on update.** A contact record is delivered again whenever new information arrives after initial delivery (e.g. `UpdateContactAttributes` API/CLI, Contact Lens analysis completing, evaluation submitted). Each re-emission is a **full record**, not a delta.
- **Dedup rule (official guidance):** dedupe by `ContactId`; when duplicates exist, keep the copy with the greatest `LastUpdateTimestamp` — "last updated wins".
- Records are retained/queryable inside Connect for **24 months** from contact initiation (contact search UI: back 2 years). Attribute-section size and per-contact event counts are capped (see feature specifications/quotas page); actions beyond the internal storage limit are dropped from the record.
- The data model is **additive**: new fields appear regularly; consumers must ignore unknown fields.
- No ordering guarantee across contacts; within Kinesis, ordering is per shard/partition key only.
- The record only becomes final after the agent leaves ACW; a record can exist (and stream) before recording/analysis fields are populated — another reason updates are re-emitted.

### Top-level `ContactTraceRecord` fields (key subset, exact names)
- Identity/lineage: `ContactId`, `InitialContactId` (first contact in a transfer chain), `PreviousContactId` (contact this one was created from), `NextContactId` (contact created from this one via quick connect / Transfer to queue/flow / Set disconnect flow / added WebRTC participant), `RelatedContactId`, `ContactAssociationId` (common across an email thread), `AWSAccountId`, `InstanceARN`, `AWSContactTraceRecordFormatVersion`.
- `Channel`: `VOICE` | `CHAT` | `TASK` | `EMAIL`.
- `InitiationMethod`: `INBOUND`, `OUTBOUND` (agent dialed via CCP), `TRANSFER` (agent quick-connect transfer → new record), `CALLBACK`, `API` (StartOutboundVoiceContact/StartChatContact/StartTaskContact/StartEmailContact), `WEBRTC_API`, `QUEUE_TRANSFER` (flow-block queue-to-queue), `EXTERNAL_OUTBOUND`, `MONITOR` (supervisor monitor/barge), `DISCONNECT` (contact created by a Set disconnect flow), `AGENT_REPLY` (email), `FLOW` (flow-initiated email), `CAMPAIGN_PREVIEW`.
- Timestamps (String, UTC ISO 8601): `InitiationTimestamp`, `ConnectedToSystemTimestamp` (for INBOUND equals InitiationTimestamp; for OUTBOUND/CALLBACK/API it's when the customer endpoint answers), `DisconnectTimestamp`, `LastUpdateTimestamp`, `ScheduledTimestamp` (tasks), `TransferCompletedTimestamp` (populated on cold transfers only), `LastPausedTimestamp`, `LastResumedTimestamp`.
- Endpoints: `CustomerEndpoint`, `SystemEndpoint` (number dialed for INBOUND; outbound caller ID for OUTBOUND/EXTERNAL_OUTBOUND/CALLBACK; can be `anonymous`), `TransferredToEndpoint`. Endpoint = `{Address, Type}` (`TELEPHONE_NUMBER` in E.164; events also allow VOIP, CONTACT_FLOW, CONNECT_PHONENUMBER_ARN, EMAIL_ADDRESS).
- `Attributes`: user-defined contact attributes, map of `AttributeName` → `AttributeValue` (flow `Set contact attributes`, `UpdateContactAttributes` API).
- `SegmentAttributes`: system-defined key-value map, e.g. channel subtype `connect:Subtype` = `connect:SMS`, `connect:Guide`, `connect:Telephony`, `connect:WebRTC`; also holds email subject.
- `Tags`: AWS-generated + user tags (e.g. `aws:connect:instanceId`, `aws:connect:systemEndpoint`).
- `AgentConnectionAttempts` (int), `DisconnectReason` (below), `AnsweringMachineDetectionStatus` (outbound campaigns: `HUMAN_ANSWERED`, `VOICEMAIL_BEEP`, `VOICEMAIL_NO_BEEP`, `AMD_UNANSWERED`, `AMD_UNRESOLVED`, `AMD_UNRESOLVED_SILENCE`, `AMD_NOT_APPLICABLE`, `SIT_TONE_BUSY`, `SIT_TONE_INVALID_NUMBER`, `SIT_TONE_DETECTED`, `FAX_MACHINE_DETECTED`, `AMD_ERROR`), `Campaign`, `CustomerVoiceActivity` (`GreetingStartTimestamp`/`GreetingEndTimestamp`, AMD only), `CustomerId`, `MediaStreams` (`AUDIO`|`CHAT`|`AUTOMATED_INTERACTION`), `References`, `ContactDetails` (tasks only), `DisconnectDetails.PotentialDisconnectIssue`, `QualityMetrics` (Agent/Customer → `Audio.QualityScore` 1.00–5.00, `PotentialQualityIssues`: `HighPacketLoss`|`HighRoundTripTime`|`HighJitterBuffer`), `ChatMetrics` (ContactMetrics/AgentMetrics/CustomerMetrics — TotalMessages, ConversationTurnCount, AgentFirstResponseTimeInMillis, per-participant response times), `GlobalResiliencyMetadata` (`ActiveRegion`, `OriginRegion`, `TrafficDistributionGroupId`), `TotalPauseCount`, `TotalPauseDurationInSeconds`, `RoutingCriteria` (only last 3 updates kept; `Index` reveals total update count), `VoiceIdResult` (Voice ID EOL May 20 2026), `WisdomInfo.SessionArn` (Amazon Q / AI agents session).

### `Agent` block (populated only when connected to an agent)
`Username`, `ARN`, `RoutingProfile` (`ARN`, `Name`), `HierarchyGroups` (`Level1`..`Level5`, each `{ARN, GroupName}`), `ConnectedToAgentTimestamp`, `AgentInteractionDuration` (whole seconds agent interacted; excludes task pause), `AfterContactWorkStartTimestamp`, `AfterContactWorkEndTimestamp`, `AfterContactWorkDuration`, `CustomerHoldDuration`, `AgentInitiatedHoldDuration` (multi-party attribution differs from CustomerHoldDuration), `NumberOfHolds`, `LongestHoldDuration`, `AgentPauseDuration` (tasks), `AcceptedByAgentTimestamp` + `PreviewEndTimestamp` (campaign preview), `DeviceInfo` (`PlatformName`, `PlatformVersion`, `OperatingSystem`), `Capabilities`, `StateTransitions` (supervisor `SILENT_MONITOR`|`BARGE`).

### `Queue` block (`QueueInfo`)
`ARN`, `Name`, `EnqueueTimestamp`, `DequeueTimestamp`, `Duration` (Dequeue − Enqueue, whole seconds).
**Abandoned contact detection:** has `Queue` + `EnqueueTimestamp` but **no** `ConnectedToAgentTimestamp`.

### `Recording` and `Recordings`
- `Recording` (legacy, single `RecordingInfo`): `Location` (S3 key), `Status` (`AVAILABLE`|`DELETED`|`NULL`), `Type` (`AUDIO`), `DeletionReason`.
- `Recordings` (array of `RecordingsInfo`, covers voice + chat transcript + screen recording): adds `MediaStreamType` (`AUDIO`|`VIDEO`|`CHAT`), `ParticipantType` (`All`, `Manager`, `Agent`, `Customer`, `Thirdparty`, `Supervisor`, `IVR`), `FragmentStartNumber`/`FragmentStopNumber` (Kinesis Video Streams), `StartTimestamp`/`StopTimestamp`, `StorageType` (`Amazon S3` | `KINESIS_VIDEO_STREAM`). The first recording appears in **both** `Recording` and `Recordings`.

### `ContactLens` block
`ContactLens.ConversationalAnalytics.Configuration`:
- `Enabled` (bool), `ChannelConfiguration.AnalyticsModes` (voice: `PostContact`|`RealTime`; chat: `ContactLens`), `LanguageLocale`,
- `RedactionConfiguration`: `Behavior` (`Enable`|`Disable`), `Policy` (`None`|`RedactedOnly`|`RedactedAndOriginal`), `Entities` (list; if present only these are redacted), `MaskMode` (`PII` → `[PII]`, `EntityType` → e.g. `[EMAIL]`),
- `SentimentConfiguration.Behavior`, `SummaryConfiguration.SummaryModes` (`PostContact` = gen-AI post-contact summaries).

### `ContactEvaluations` (map keyed by FormId)
Each: `EvaluationArn`, `Status` (`COMPLETE`|`IN_PROGRESS`|`DELETED`), `StartTimestamp`, `EndTimestamp`, `DeleteTimestamp`, `ExportLocation` (S3 path where the evaluation was exported).

### `DisconnectReason` values
- Voice: `CUSTOMER_DISCONNECT`, `AGENT_DISCONNECT`, `THIRD_PARTY_DISCONNECT`, `TELECOM_PROBLEM`, `TELECOM_BUSY`, `TELECOM_NUMBER_INVALID`, `TELECOM_POTENTIAL_BLOCKING`, `TELECOM_UNANSWERED`, `TELECOM_TIMEOUT`, `TELECOM_ORIGINATOR_CANCEL`, `CUSTOMER_NEVER_ARRIVED` (web calling), `BARGED`, `CONTACT_FLOW_DISCONNECT`, `OTHER`.
- Outbound campaigns: `OUTBOUND_DESTINATION_ENDPOINT_ERROR`, `OUTBOUND_RESOURCE_ERROR`, `OUTBOUND_ATTEMPT_FAILED`, `OUTBUND_PREVIEW_DISCARDED` (sic — the typo is in the product), `EXPIRED`.
- Chat: `AGENT_DISCONNECT`, `CUSTOMER_DISCONNECT`, `AGENT_NETWORK_DISCONNECT`, `CUSTOMER_CONNECTION_NOT_ESTABLISHED`, `EXPIRED`, `CONTACT_FLOW_DISCONNECT`, `API`, `BARGED`, `IDLE_DISCONNECT`, `THIRD_PARTY_DISCONNECT`, `SYSTEM_ERROR`.
- Tasks: `AGENT_COMPLETED`, `AGENT_DISCONNECT`, `EXPIRED` (default 7 days, configurable to 90), `CONTACT_FLOW_DISCONNECT`, `API`, `OTHER`.
- Email: `TRANSFERRED`, `AGENT_DISCONNECT`, `EXPIRED`, `DISCARDED`, `CONTACT_FLOW_DISCONNECT`, `API`, `OTHER`.

---

## 3. CTR delivery via Kinesis (setup & operations)

- Enable in the **Connect console → instance alias → Data streaming**: choose **Kinesis Firehose** (delivery stream) *or* **Kinesis Stream** for contact records; agent events support **Kinesis Data Streams only**.
- Connect writes with the instance **service-linked role**. For SSE with a customer-managed KMS key, add a key-policy statement allowing that role `kms:GenerateDataKey` **before** enabling, or you will silently drop data.
- Kinesis Data Streams retention is a stream setting (24 h default, up to 365 days) — plan consumers accordingly. Firehose buffers and delivers to S3/Redshift/OpenSearch/etc.
- Firehose → S3 note: records are concatenated JSON objects with no newline delimiter by default; enable a processor/newline delimiter or handle `}{` splitting so Athena can parse.
- Expect duplicates and updated re-emissions (Section 2). There is **no** cross-record ordering guarantee.

---

## 4. Agent event streams

- Kinesis Data Streams; JSON blob per event. Enable on the same Data streaming page.
- **Event types** (`EventType`): `LOGIN`, `LOGOUT`, `STATE_CHANGE` (CCP status change, contact-state change like connected→on hold, or configuration change: routing profile, queues in profile, auto-accept, SIP address, hierarchy group, language preference), `HEART_BEAT` (published every **120 s** when no other event occurred; heartbeats keep publishing up to **1 hour after logout**).
- **`AgentEvent` payload:** `AWSAccountId`, `AgentARN`, `InstanceARN`, `EventId` (UUID), `EventTimestamp` (ISO 8601 ms), `EventType`, `Version` (date-formatted, e.g. `2019-05-25`), `CurrentAgentSnapshot`, `PreviousAgentSnapshot`.
- **`AgentSnapshot`:** `AgentStatus` `{ARN, Name, StartTimestamp, Type: ROUTABLE|CUSTOM|OFFLINE}` (`Error` name = internal error), `NextAgentStatus` `{ARN, Name, EnqueuedTimestamp}`, `Configuration` `{Username, FirstName, LastName, RoutingProfile{ARN, Name, InboundQueues[], DefaultOutboundQueue, Concurrency[{Channel, AvailableSlots, MaximumSlots}]}, AgentHierarchyGroups{Level1..Level5}, Proficiencies[{Name, Value, ProficiencyLevel 1.0–5.0}]}`, `Contacts[]`.
- **Contact object in snapshot:** `ContactId`, `InitialContactId`, `Channel` (`VOICE`|`CHAT`|`TASKS`), `InitiationMethod`, `State`: `INCOMING`|`PENDING`|`CONNECTING`|`CONNECTED`|`CONNECTED_ONHOLD`|`MISSED`|`PAUSED` (tasks)|`REJECTED`|`ERROR`|`ENDED`, `StateStartTimestamp`, `ConnectedToAgentTimestamp`, `QueueTimestamp`, `Queue`.
- ACW time is derived by diffing snapshots (contact `State` = ENDED while still on agent = ACW window); the admin guide has a dedicated "Determine ACW time" walkthrough.
- To compute state durations: use `PreviousAgentSnapshot.AgentStatus.StartTimestamp` vs `CurrentAgentSnapshot`; heartbeats let you close out sessions for crashed clients.

---

## 5. Contact events via EventBridge

- `source: "aws.connect"`, `detail-type: "Amazon Connect Contact Event"`. Create an EventBridge rule (pattern form: AWS services → Amazon Connect → Contact Event) targeting Lambda/SQS/SNS/etc. Use `"anything-but"` on `detail.eventType` to drop noisy types (e.g. `CONTACT_DATA_UPDATED`).
- **Best-effort delivery, NOT ordered** — sequence by the embedded timestamps, not arrival order. Treat as a signal stream; CTRs remain the source of truth.
- **Event types (`detail.eventType`):** `INITIATED`, `CONNECTED_TO_SYSTEM` (media established; emitted for outbound incl. campaigns, tasks, chats), `QUEUED`, `CONNECTED_TO_AGENT`, `DISCONNECTED`, `COMPLETED` (contact fully ended incl. ACW; populates `agentInfo.afterContactWorkStartTimestamp/afterContactWorkEndTimestamp/afterContactWorkDuration`; emitted right after DISCONNECTED when no ACW), `CONTACT_DATA_UPDATED` (`updatedProperties`: `ScheduledTimestamp`, `UserDefinedAttributes`, `ContactLens.ConversationalAnalytics.Configuration`, `Segment Attributes`, `Tags`, `RoutingCriteria.Step.Status`, `GlobalResiliencyMetadata`), `PAUSED`/`RESUMED` (tasks), `AMD_DISABLED`, `WEBRTC_API`.
- **Payload (`detail`):** `contactId`, `initialContactId`, `previousContactId`, `relatedContactId`, `channel` (`VOICE`|`CHAT`|`TASK`|`EMAIL`), `instanceArn`, `initiationMethod`, timestamps (`initiationTimestamp`, `connectedToSystemTimestamp`, `enqueueTimestamp` in queueInfo, `connectedToAgentTimestamp` in agentInfo, `disconnectTimestamp`), `agentInfo` (agentArn, hierarchyGroups level1–5, hold/ACW fields), `queueInfo` `{queueArn, queueType, enqueueTimestamp}` (absent for OUTBOUND), `contactLens` config, `segmentAttributes`, `tags`, `routingCriteria` (steps with `Status`: `EXPIRED`|`ACTIVE`|`JOINED`|`INACTIVE`|`DEACTIVATED`|`INTERRUPTED`), `disconnectReason`, `answeringMachineDetectionStatus`, `campaign`, `chatMetrics`, `contactEvaluations`.
- Gotcha: field casing varies across samples (`contactId` vs `ContactId`) — parse case-insensitively or normalize.
- Chat edge case: if an agent goes offline without clearing the contact in CCP, the `COMPLETED` event may never be delivered and `AfterContactWorkEndTimestamp` can be wrong.

---

## 6. Real-time vs historical metrics

- **Real-time**: `GetCurrentMetricData` (queue/routing-profile aggregates), `GetCurrentUserData` (per-agent real-time), admin-website real-time metrics pages. Snapshot-based (`DataSnapshotTime`), pagination tokens expire in 5 min.
- **Historical**: `GetMetricDataV2` (preferred; supersedes `GetMetricData`), retrieves the **last 3 months**, metric-level filters, custom metrics via `MetricId` ARN. Admin website: historical metrics reports + dashboards.
- Both are computed from contact records + agent events; if a CTR is later updated, historical aggregates can shift slightly.

### GetMetricDataV2 — request shape
`POST /metrics/data` with `ResourceArn` (instance ARN), `StartTime`/`EndTime` (epoch), `Filters` (1–5), `Groupings` (≤4), `Interval`, `Metrics`, `MaxResults` ≤100, `NextToken`.
- **Interval limits:** `IntervalPeriod` ∈ `FIFTEEN_MIN`|`THIRTY_MIN`|`HOUR` → window < 3 days; `DAY`|`WEEK`|`TOTAL` → window < 35 days. Default aggregation `TOTAL`; default max window 35 days; data available 3 months back. `TimeZone` supported.
- **Filters:** ≤5 filter keys, ≤100 filter values total (CHANNEL values don't count). At least one *resource* filter is required for authorization: `QUEUE`, `ROUTING_PROFILE`, `AGENT`, `AGENT_HIERARCHY_LEVEL_ONE..FIVE`, `CAMPAIGN`, `EVALUATION_FORM`, `EVALUATOR_ID`. Other filter keys include `CHANNEL`, `INITIATION_METHOD`, `DISCONNECT_REASON`, `FEATURE` (`contact_lens_conversational_analytics`), `contact/segmentAttributes/connect:Subtype`, `Q_CONNECT_ENABLED` (TRUE/FALSE), `ROUTING_STEP_EXPRESSION`, bot/flow/case/evaluation/campaign/AI-agent keys.
- **Groupings** (≤4): `QUEUE`, `CHANNEL`, `ROUTING_PROFILE`, `AGENT`, `AGENT_HIERARCHY_LEVEL_ONE..FIVE`, `INITIATION_METHOD`, `DISCONNECT_REASON`, `contact/segmentAttributes/connect:Subtype`, `CASE_TEMPLATE_ARN`, `EVALUATION_FORM`, `FLOWS_RESOURCE_ID`, `FLOW_TYPE`, `BOT_ID`, `CAMPAIGN`, etc. No grouping ⇒ one summary row.
- **Per-metric:** `Name` or `MetricId` (custom metrics; ≤20 MetricIds/request), `MetricFilters` (e.g. filter CONTACTS_HANDLED to `INITIATION_METHOD=INBOUND`, with `Negate`), `Threshold` `{Comparison: LT|LTE|GT, ThresholdValue: 1–604800 s}` for X-second metrics. Up to 20 `SERVICE_LEVEL` entries per request (different thresholds).
- **Response:** `MetricResults[]` with `Dimensions` (map), `MetricInterval {Interval, StartTime, EndTime}`, `Collections[] {Metric, Value}`. `null` value = can't compute (divide-by-zero/insufficient data); empty `MetricResults` = no data found.

### GetMetricDataV2 — core metric names (catalog subset)
Contact volume/outcome: `CONTACTS_CREATED`, `CONTACTS_HANDLED`, `CONTACTS_HANDLED_BY_CONNECTED_TO_AGENT`, `CONTACTS_QUEUED`, `CONTACTS_QUEUED_BY_ENQUEUE`, `CONTACTS_ABANDONED`, `SUM_CONTACTS_ABANDONED_IN_X`, `SUM_CONTACTS_ANSWERED_IN_X`, `CONTACTS_REMOVED_FROM_QUEUE_IN_X`, `CONTACTS_RESOLVED_IN_X`, `SUM_CONTACTS_DISCONNECTED` (filter `DISCONNECT_REASON`), `CONTACTS_TRANSFERRED_OUT`, `CONTACTS_TRANSFERRED_OUT_BY_AGENT`, `CONTACTS_TRANSFERRED_OUT_FROM_QUEUE`, `CONTACTS_TRANSFERRED_OUT_INTERNAL`, `CONTACTS_TRANSFERRED_OUT_EXTERNAL`, `CONTACTS_HOLD_ABANDONS`, `CONTACTS_ON_HOLD_AGENT_DISCONNECT`, `CONTACTS_ON_HOLD_CUSTOMER_DISCONNECT`, `CONTACTS_PUT_ON_HOLD`, `SUM_RETRY_CALLBACK_ATTEMPTS`.
Rates/levels: `ABANDONMENT_RATE` (%), `SERVICE_LEVEL` (%, threshold LT/LTE X seconds), `AGENT_ANSWER_RATE`, `AGENT_NON_RESPONSE`, `AGENT_NON_RESPONSE_WITHOUT_CUSTOMER_ABANDONS`, `AGENT_OCCUPANCY`.
Time averages: `AVG_HANDLE_TIME`, `AVG_CONTACT_DURATION`, `AVG_QUEUE_ANSWER_TIME`, `AVG_ABANDON_TIME`, `AVG_AFTER_CONTACT_WORK_TIME`, `AVG_INTERACTION_TIME`, `AVG_INTERACTION_AND_HOLD_TIME`, `AVG_HOLD_TIME`, `AVG_HOLD_TIME_ALL_CONTACTS`, `AVG_HOLDS`, `AVG_RESOLUTION_TIME`, `MAX_QUEUED_TIME`, `AVG_ACTIVE_TIME`, `AVG_AGENT_PAUSE_TIME`, `AVG_AGENT_CONCURRENCY`, `AVG_AGENT_CONNECTING_TIME`.
Time sums: `SUM_HANDLE_TIME`, `SUM_INTERACTION_TIME`, `SUM_INTERACTION_AND_HOLD_TIME`, `SUM_HOLD_TIME`, `SUM_AFTER_CONTACT_WORK_TIME`, `SUM_CONTACT_FLOW_TIME`, `SUM_CONTACT_TIME_AGENT`, `SUM_ONLINE_TIME_AGENT`, `SUM_IDLE_TIME_AGENT`, `SUM_NON_PRODUCTIVE_TIME_AGENT`, `SUM_ERROR_STATUS_TIME_AGENT`, `SUM_CONNECTING_TIME_AGENT`.
Contact Lens-only (requires conversational analytics): `AVG_TALK_TIME`, `AVG_TALK_TIME_AGENT`, `AVG_TALK_TIME_CUSTOMER`, `AVG_NON_TALK_TIME`, `PERCENT_TALK_TIME`, `PERCENT_TALK_TIME_AGENT`, `PERCENT_TALK_TIME_CUSTOMER`, `PERCENT_NON_TALK_TIME`, `AVG_GREETING_TIME_AGENT`, `AVG_INTERRUPTIONS_AGENT`, `AVG_INTERRUPTION_TIME_AGENT`.
Chat/messaging: `AVG_MESSAGES`, `AVG_MESSAGES_AGENT`, `AVG_MESSAGES_CUSTOMER`, `AVG_MESSAGES_BOT`, `AVG_MESSAGE_LENGTH_AGENT`, `AVG_MESSAGE_LENGTH_CUSTOMER`, `AVG_RESPONSE_TIME_AGENT`, `AVG_RESPONSE_TIME_CUSTOMER`, `AVG_FIRST_RESPONSE_TIME_AGENT`, `AVG_CONTACT_FIRST_RESPONSE_TIME_AGENT`, `AVG_CONVERSATION_DURATION`, `AVG_CONVERSATION_CLOSE_TIME`, `CONVERSATIONS_ABANDONED`.
Evaluations: `AVG_EVALUATION_SCORE`, `AVG_WEIGHTED_EVALUATION_SCORE`, `EVALUATIONS_PERFORMED`, `PERCENT_AUTOMATIC_FAILS`.
WFM (only in regions with forecasting/scheduling): `AGENT_SCHEDULE_ADHERENCE`, `AGENT_ADHERENT_TIME`, `AGENT_NON_ADHERENT_TIME`, `AGENT_SCHEDULED_TIME`.
Flows: `FLOWS_STARTED`, `FLOWS_OUTCOME`, `PERCENT_FLOWS_OUTCOME`, `AVG_FLOW_TIME`, `MAX_FLOW_TIME`, `MIN_FLOW_TIME`.
Campaigns: `DELIVERY_ATTEMPTS`, `DELIVERY_ATTEMPT_DISPOSITION_RATE`, `HUMAN_ANSWERED_CALLS`, `CAMPAIGN_SEND_ATTEMPTS`, `CAMPAIGN_SEND_EXCLUSIONS`, `CAMPAIGN_PROGRESS_RATE`, `CAMPAIGN_INTERACTIONS`, `CAMPAIGN_CONTACTS_ABANDONED_AFTER_X(_RATE)`, `RECIPIENTS_TARGETED`, `RECIPIENTS_ATTEMPTED`, `RECIPIENTS_INTERACTED`, `AVG_DIALS_PER_MINUTE`, `AVG_WAIT_TIME_AFTER_CUSTOMER_CONNECTION`.
Cases (require `CASE_TEMPLATE_ARN` filter): `CASES_CREATED`, `CURRENT_CASES`, `RESOLVED_CASE_ACTIONS`, `REOPENED_CASE_ACTIONS`, `PERCENT_CASES_FIRST_CONTACT_RESOLVED`, `AVG_CASE_RESOLUTION_TIME`, `AVG_CASE_RELATED_CONTACTS`.
Bots/AI: `BOT_CONVERSATIONS_COMPLETED`, `BOT_INTENTS_COMPLETED`, `PERCENT_BOT_CONVERSATIONS_OUTCOME`, `AVG_BOT_CONVERSATION_TIME`, plus a large `AI_*` family (AI agent/prompt/tool invocations, `AI_HANDOFFS`, `AI_HANDOFF_RATE`, `GOAL_SUCCESS_RATE`, `FAITHFULNESS_SCORE`, ...).
Gotchas: `Feature` is often a valid filter but **not** a grouping; `GetMetricDataV2` does **not** support agent queues; per-metric notes ("Data available starting from ...") apply to some metrics.

### GetCurrentMetricData (queue realtime)
`POST /metrics/current/{InstanceId}`. `Filters` (required): `Queues` (≤100), `RoutingProfiles` (≤100), `Channels` (≤3: VOICE/CHAT/TASK), `RoutingStepExpressions` (≤50), `AgentStatuses` (≤50), `Subtypes`, `ValidationTestTypes` — cannot filter by queue AND routing profile together; AgentStatuses/Subtypes need Queues as primary filter. `Groupings` ≤2 of `QUEUE | CHANNEL | ROUTING_PROFILE | ROUTING_STEP_EXPRESSION | AGENT_STATUS | SUBTYPE | VALIDATION_TEST_TYPE` (AGENT_STATUS grouping only supports AGENTS_ONLINE and requires QUEUE primary).
Metrics (Name + Unit): `AGENTS_ONLINE`, `AGENTS_AVAILABLE`, `AGENTS_ON_CONTACT` (and legacy `AGENTS_ON_CALL`), `AGENTS_STAFFED`, `AGENTS_AFTER_CONTACT_WORK`, `AGENTS_NON_PRODUCTIVE`, `AGENTS_ERROR` (COUNT); `CONTACTS_IN_QUEUE`, `CONTACTS_SCHEDULED`, `SLOTS_ACTIVE`, `SLOTS_AVAILABLE` (COUNT); `OLDEST_CONTACT_AGE`, `ESTIMATED_WAIT_TIME` (SECONDS).
**Big gotcha:** with no groupings, `OLDEST_CONTACT_AGE` reports Unit=SECONDS but the value is **milliseconds**; with groupings it's genuinely seconds. Sorting: one `SortCriteria` (default `AGENTS_ONLINE DESCENDING`; SLOTS_* not sortable). Response includes `ApproximateTotalCount` and `DataSnapshotTime`; `NextToken` valid 5 min with identical params.

---

## 7. Analytics data lake (zero-ETL)

- Central, managed store of Connect data: contact records, Contact Lens conversational analytics, evaluations, agent statistics, flows, cases, campaigns, scheduling/forecasting, configuration, resource tags. **Data lands < 1 hour** after the record is created; refreshed as records update.
- Mechanism: Connect shares Glue Data Catalog tables to your (consumer) account via **AWS RAM + Lake Formation** — no ETL. Enable via Connect console ("Analytics tools": pick target account + Glue database) or CLI: `aws connect batch-associate-analytics-data-set` (Data lake APIs: AssociateAnalyticsDataSet, BatchAssociateAnalyticsDataSet, ListAnalyticsDataAssociations, ...).
- Consumer-side setup: accept the RAM resource share (invitation expires in 12 h; only the first share creates a RAM request), then in Lake Formation create a database and **Resource link** tables pointing to each shared table, then query in **Athena**: `SELECT * FROM db.contact_record LIMIT 10`.
- Table/data-set names include: `contact_record`, `contact_statistic_record`, `contact_lens_conversational_analytics`, `contact_evaluation_record`, `contact_flow_events`, `agent_statistic_record`, `agent_queue_statistic_record`, plus cases, bot analytics, AI-agent, forecasting, scheduling, outbound campaigns, configuration, and resource-tags data sets (see "Data type definitions" doc for column-level schemas; scheduling tables may require the CLI enablement path).
- Same at-least-once caveat as the CTR stream: contact records may be re-delivered/updated in the lake — dedupe in queries.
- **Redshift:** there is no dedicated Connect→Redshift data share; the documented query path is Athena over the shared Glue/Lake Formation tables (Redshift Spectrum can also read Glue catalog tables, and the older aws-samples pipeline used Firehose→Redshift, but that's your pipeline, not a Connect feature).
- Data retention in the lake has its own doc ("Data retention in the analytics data lake"); verify per data set.

---

## 8. S3 artifact locations (recordings, transcripts, Contact Lens)

Default instance storage bucket (created at instance setup) is named like `amazon-connect-xxxxxxxx` with prefixes per data type (configurable per instance under Data storage):
- Call recordings: `connect/<instance-alias>/CallRecordings/YYYY/MM/DD/<file>.wav` — files are *usually* named `<ContactId>_<timestamp>.wav` but **the filename is not guaranteed to match the ContactId**; always resolve via the contact record's `Recording.Location` / contact search. Audio: stereo WAV, agent (or system prompts for IVR legs) on one channel, customer + third parties on the other. Up to 2 recordings per contact: IVR leg + agent leg.
- Chat transcripts: `connect/<instance-alias>/ChatTranscripts/YYYY/MM/DD/<contactId>_....json` (JSON transcript of all messages/events). If no transcript bucket is configured, chats are not stored at all.
- Contact Lens analysis output: `connect/<instance-alias>/Analysis/Voice/YYYY/MM/DD/<contactId>_analysis_<timestamp>.json` and `.../Analysis/Chat/...`; redacted output lands under a `Redacted/` sub-prefix (e.g. `Analysis/Voice/Redacted/...`) when redaction policy `RedactedOnly`/`RedactedAndOriginal` is set. Redacted audio WAVs are also produced for voice.
- Screen recordings, attachments, email messages, exported/scheduled reports each have their own configurable prefixes under the same bucket.
- **Encryption:** SSE-KMS object-level encryption is enabled by default for recordings/reports (per-object, not bucket-level). Don't disable it; grant your analytics consumers `kms:Decrypt` on the instance's key.
- Availability timing: agent-leg recording appears shortly after disconnect; IVR recording shortly after agent answer or disconnect; the contact record exposes the recording only after the contact leaves ACW.
- S3 event notifications: Connect uses `PutObject` **and** multipart upload — subscribe to *all* object-create events (both `s3:ObjectCreated:Put` and `s3:ObjectCreated:CompleteMultipartUpload`).
- Moving a recording out of its original bucket/key breaks playback from Connect (the CTR `Location` goes stale).

## 9. Contact Lens output JSON (schema basics)

Top-level: `Version`, `AccountId`, `Channel` (`VOICE`|`CHAT`), `ContentMetadata` (`Output`: `Raw`|`Redacted`; redacted files add `RedactionTypes`, `RedactionEntitiesRequested`, `RedactionMaskMode`), `JobStatus`, `JobDetails.SkippedAnalysis` (e.g. `CATEGORIZATION` skipped with `QUOTA_EXCEEDED`/`FAILED_SAFETY_GUIDELINES`), `LanguageCode`, `Participants[{ParticipantId, ParticipantRole: AGENT|CUSTOMER}]`, `CustomModels` (custom vocabulary).
- `Categories`: `MatchedCategories[]` + `MatchedDetails.<name>.PointsOfInterest[{BeginOffsetMillis, EndOffsetMillis}]`.
- `ConversationCharacteristics`: `TotalConversationDurationMillis`; `ContactSummary.PostContactSummary.Content` (gen-AI summary); `Sentiment.OverallSentiment` per participant (−5..+5) and `SentimentByPeriod.QUARTER`; `Interruptions` (per interrupter, TotalCount, TotalTimeMillis); `NonTalkTime` (TotalTimeMillis, Instances); `TalkTime` per participant; `TalkSpeed.AverageWordsPerMinute`.
- `Transcript[]` turns: `Id`, `ParticipantId`, `Content`, `BeginOffsetMillis`, `EndOffsetMillis`, `Sentiment` (`POSITIVE`|`NEGATIVE`|`NEUTRAL`), `LoudnessScore[]` (per second), optional `IssuesDetected[]` / `OutcomesDetected[]` / `ActionItemsDetected[]` (with `CharacterOffsets`), optional `Redaction.RedactedTimestamps[]` (ms offsets; redacted audio is silence — you can overlay a beep).
- The redacted file is a twin of the original with PII replaced by `[PII]` (MaskMode `PII`) or `[ENTITY_TYPE]` labels.
- Real-time Contact Lens additionally exposes rules→EventBridge and the `ListRealtimeContactAnalysisSegments` / contact-analysis APIs; post-contact output is the S3 JSON above.

## 10. Contact search

- Admin website: **Analytics and optimization → Contact search**. Searches back **2 years**; a single query's time-range filter spans up to **8 weeks**; results capped at first **10K**; download up to **3,000** rows.
- Timestamp type selectable: initiated (default) / connected to agent / disconnected / scheduled. Filters: agent, queue, initial flow, hierarchy, channel + subtype, custom contact attributes, email fields, recordings (audio/screen), Active Region (global resiliency), Contact Lens filters (categories with Match any/all/none, sentiment, non-talk time, keywords — gated by security-profile permissions), in-progress vs completed status.
- In-progress visibility varies by channel (queued in-progress voice not shown except callbacks). A contact counts "completed" only after ACW ends.
- Permissions: `Contact search - View` (all) vs `View my contacts` (own), `Restrict contact access` (limits by agent hierarchy), separate redacted/unredacted recording+transcript access permissions.
- APIs: `SearchContacts`, `DescribeContact`, `DescribeContactEvaluation`. Cannot search multiple contact IDs at once.

## 11. Evaluation forms data

- Evaluations (manual + Contact Lens automated evaluation) attach to contacts; the CTR carries `ContactEvaluations` (FormId → status/timestamps/`ExportLocation`).
- Submitted/exported evaluations land in the instance S3 bucket under the evaluations prefix (`ExportLocation` gives the exact key); the analytics data lake exposes `contact_evaluation_record` for SQL.
- Reporting: GetMetricDataV2 metrics `AVG_EVALUATION_SCORE`, `AVG_WEIGHTED_EVALUATION_SCORE`, `EVALUATIONS_PERFORMED`, `PERCENT_AUTOMATIC_FAILS` with filters/groupings `EVALUATION_FORM`, `EVALUATION_SECTION`, `EVALUATION_QUESTION`, `EVALUATION_SOURCE`, `FORM_VERSION`, `EVALUATOR_ID`.
- APIs: `CreateEvaluationForm`, `ActivateEvaluationForm`, `StartContactEvaluation`, `SubmitContactEvaluation`, `DescribeContactEvaluation`, `ListContactEvaluations`.

## 12. Forecasting, capacity planning, scheduling (WFM overview)

- ML-powered suite (region-gated — check the Regions/feature-availability page):
  - **Forecasting**: predicts contact volume + handle time from historical data; forecasts auto-update daily (short-term & long-term).
  - **Scheduling**: generates agent shift schedules against forecasts, business and compliance rules; supports agent self-service and flexibility.
  - **Schedule adherence**: after schedules are published, adherence metrics (`AGENT_SCHEDULE_ADHERENCE`, `AGENT_ADHERENT_TIME`, `AGENT_NON_ADHERENT_TIME`, `AGENT_SCHEDULED_TIME`) become available in reports/GetMetricDataV2.
  - **Capacity planning**: long-range FTE requirements by scenario, service-level goal, shrinkage.
- Scheduling/forecasting data sets are also exposed in the analytics data lake (may require CLI-based enablement).

## 13. Dashboards

- Admin website ships prebuilt, customizable dashboards (Analytics and optimization → Dashboards): queue performance dashboard, Contact Lens **conversational analytics dashboard** (sentiment, categories, talk time, drivers), flows dashboard, bot/campaign dashboards. Support custom time ranges (incl. comparisons/benchmarking), saving, and publishing/sharing to other users.
- Access is controlled by security-profile permissions; **granular access control** lets you scope what data a user sees (e.g. hierarchy-based restriction, tag-based access control on queues/routing profiles applies to metrics/reports too).

---

## 14. Building reporting pipelines (practical guidance)

**Canonical pattern: Kinesis → Firehose → S3 → Glue/Athena**
1. Point CTR stream at a Kinesis Data Stream (if multiple consumers / replay needed) or straight to Firehose. Firehose: buffer to S3, partitioned by delivery time (`.../yyyy/MM/dd/HH/`), enable dynamic partitioning or add newline delimiters (raw concatenated JSON breaks naive parsers).
2. Crawl with Glue or declare an Athena table over the JSON (or convert to Parquet with a Firehose data-format-conversion / Glue job).
3. **Dedup at query time** — records are at-least-once and re-emitted with updates:
```sql
-- latest version of each contact
SELECT * FROM (
  SELECT *, ROW_NUMBER() OVER (
    PARTITION BY contactid
    ORDER BY from_iso8601_timestamp(lastupdatetimestamp) DESC
  ) AS rn
  FROM ctr_raw
) WHERE rn = 1;
```
   Or MERGE into an Iceberg/Delta table keyed on `ContactId` with a `LastUpdateTimestamp >` guard ("last updated wins").
4. Partition analytical tables by date derived from `InitiationTimestamp` (not arrival time) — updates for a contact can arrive days later, so use an update-aware layout (Iceberg MERGE) or re-compact recent partitions.
5. Join lineage: transfers create multiple contact records — roll up chains via `InitialContactId` (or walk `PreviousContactId`/`NextContactId`).
- **Shortcut:** if you only need SQL/BI, prefer the **analytics data lake** (Section 7) over building this pipeline — zero-ETL, <1 h latency, still requires the same dedup discipline.
- Agent events pipeline: same Kinesis→Firehose→S3 idea; key sessions on `AgentARN` + status `StartTimestamp`; use HEART_BEATs (120 s) to detect stuck/ghost sessions; remember events keep flowing up to 1 h after logout.
- EventBridge contact events: best for triggering (notify on QUEUED > n, post-call workflows on DISCONNECTED/COMPLETED); don't build billing/official reports from them (best-effort, unordered) — reconcile with CTRs.
- KMS: for encrypted streams grant the Connect service-linked role `kms:GenerateDataKey` on the CMK **before** enabling streaming; for S3 artifacts grant readers `kms:Decrypt`.
- Timestamps are UTC strings; parse `yyyy-MM-dd'T'HH:mm:ss(.SSS)?'Z'` tolerant of both second and millisecond precision (both appear).

---

## 15. Worked examples

### GetMetricDataV2 (boto3) — daily queue KPIs
```python
import boto3, datetime as dt
connect = boto3.client("connect")
resp = connect.get_metric_data_v2(
    ResourceArn="arn:aws:connect:us-east-1:111122223333:instance/<instance-id>",
    StartTime=dt.datetime(2026, 7, 1, tzinfo=dt.timezone.utc),
    EndTime=dt.datetime(2026, 7, 7, tzinfo=dt.timezone.utc),   # < 35 days for DAY
    Interval={"IntervalPeriod": "DAY", "TimeZone": "UTC"},
    Filters=[{"FilterKey": "QUEUE", "FilterValues": ["<queue-id>"]},
             {"FilterKey": "CHANNEL", "FilterValues": ["VOICE"]}],
    Groupings=["QUEUE"],
    Metrics=[
        {"Name": "CONTACTS_HANDLED"},
        {"Name": "AVG_HANDLE_TIME"},
        {"Name": "ABANDONMENT_RATE"},
        {"Name": "SERVICE_LEVEL",
         "Threshold": [{"Comparison": "LT", "ThresholdValue": 60}]},   # SL 60s
        {"Name": "CONTACTS_HANDLED",   # inbound-only variant via metric filter
         "MetricFilters": [{"MetricFilterKey": "INITIATION_METHOD",
                            "MetricFilterValues": ["INBOUND"]}]},
    ],
)
# resp["MetricResults"][i]["Dimensions"]["QUEUE"], ["MetricInterval"], ["Collections"]
```
Notes: at least one resource filter (QUEUE/ROUTING_PROFILE/AGENT/hierarchy/...) is mandatory; paginate with `NextToken`; a `null` Value means "cannot compute", not zero.

### GetCurrentMetricData (boto3) — live queue snapshot
```python
resp = connect.get_current_metric_data(
    InstanceId="<instance-id>",
    Filters={"Queues": ["<queue-id>"], "Channels": ["VOICE"]},
    Groupings=["QUEUE", "CHANNEL"],
    CurrentMetrics=[
        {"Name": "AGENTS_ONLINE", "Unit": "COUNT"},
        {"Name": "AGENTS_AVAILABLE", "Unit": "COUNT"},
        {"Name": "CONTACTS_IN_QUEUE", "Unit": "COUNT"},
        {"Name": "OLDEST_CONTACT_AGE", "Unit": "SECONDS"},  # ms if ungrouped!
        {"Name": "ESTIMATED_WAIT_TIME", "Unit": "SECONDS"},
    ],
)
```

### EventBridge rule pattern — only lifecycle edges
```json
{
  "source": ["aws.connect"],
  "detail-type": ["Amazon Connect Contact Event"],
  "detail": {
    "eventType": ["INITIATED", "QUEUED", "CONNECTED_TO_AGENT",
                   "DISCONNECTED", "COMPLETED"]
  }
}
```

### Minimal CTR skeleton (fields most pipelines project)
```jsonc
{
  "AWSAccountId": "111122223333",
  "ContactId": "aaaa-...-0001",
  "InitialContactId": null,          // set on transfer legs
  "PreviousContactId": null,
  "NextContactId": null,
  "Channel": "VOICE",
  "InitiationMethod": "INBOUND",
  "InitiationTimestamp": "2026-07-07T10:00:00Z",
  "ConnectedToSystemTimestamp": "2026-07-07T10:00:00Z",
  "DisconnectTimestamp": "2026-07-07T10:07:42Z",
  "DisconnectReason": "CUSTOMER_DISCONNECT",
  "LastUpdateTimestamp": "2026-07-07T10:09:00Z",   // dedup key with ContactId
  "Queue": { "Name": "Support", "ARN": "arn:...", 
             "EnqueueTimestamp": "2026-07-07T10:01:00Z",
             "DequeueTimestamp": "2026-07-07T10:02:10Z", "Duration": 70 },
  "Agent": { "Username": "jdoe", "ARN": "arn:...",
             "ConnectedToAgentTimestamp": "2026-07-07T10:02:10Z",
             "AgentInteractionDuration": 300, "CustomerHoldDuration": 32,
             "NumberOfHolds": 1, "AfterContactWorkDuration": 45,
             "RoutingProfile": { "Name": "Basic", "ARN": "arn:..." },
             "HierarchyGroups": { "Level1": { "GroupName": "US" } } },
  "Attributes": { "orderId": "12345" },
  "Recording": { "Location": "bucket/connect/alias/CallRecordings/2026/07/07/<id>_....wav",
                 "Status": "AVAILABLE", "Type": "AUDIO" },
  "ContactLens": { "ConversationalAnalytics": { "Configuration": { "Enabled": true } } },
  "SystemEndpoint": { "Type": "TELEPHONE_NUMBER", "Address": "+18005550100" },
  "CustomerEndpoint": { "Type": "TELEPHONE_NUMBER", "Address": "+14155550123" }
}
```

### Agent event skeleton (STATE_CHANGE)
```jsonc
{
  "AWSAccountId": "111122223333",
  "AgentARN": "arn:aws:connect:...:instance/<i>/agent/<a>",
  "InstanceARN": "arn:aws:connect:...:instance/<i>",
  "EventId": "uuid",
  "EventTimestamp": "2026-07-07T10:02:10.123Z",
  "EventType": "STATE_CHANGE",           // LOGIN | LOGOUT | STATE_CHANGE | HEART_BEAT
  "Version": "2019-05-25",
  "CurrentAgentSnapshot": {
    "AgentStatus": { "Name": "Available", "Type": "ROUTABLE",
                     "StartTimestamp": "2026-07-07T10:02:10.123Z" },
    "Configuration": { "Username": "jdoe",
      "RoutingProfile": { "Name": "Basic",
        "Concurrency": [{ "Channel": "VOICE", "MaximumSlots": 1, "AvailableSlots": 0 }] },
      "AgentHierarchyGroups": { "Level1": { "Name": "US" } } },
    "Contacts": [{ "ContactId": "aaaa-...-0001", "Channel": "VOICE",
                   "State": "CONNECTED",
                   "StateStartTimestamp": "2026-07-07T10:02:10.123Z",
                   "ConnectedToAgentTimestamp": "2026-07-07T10:02:10.123Z" }]
  },
  "PreviousAgentSnapshot": { "...": "same shape; diff to compute durations" }
}
```

## 16. Quotas & operational limits worth remembering

| Item | Limit |
|---|---|
| CTR availability window (search/DescribeContact) | 24 months from initiation |
| GetMetricDataV2 lookback | 3 months |
| GetMetricDataV2 window | < 3 days (FIFTEEN_MIN/THIRTY_MIN/HOUR); < 35 days (DAY/WEEK/TOTAL) |
| GetMetricDataV2 filters / values / groupings | 5 keys / 100 values / 4 groupings |
| SERVICE_LEVEL metrics per request | 20 |
| Custom-metric MetricIds per request | 20 (V2), 10 (current-metric API) |
| GetCurrentMetricData filters | 100 queues, 100 routing profiles, 3 channels; groupings ≤ 2; token TTL 5 min |
| Contact search | 8-week range per query, 10K results, 3K download, 2-year lookback |
| Agent event heartbeat | every 120 s; continues ≤ 1 h post-logout |
| RoutingCriteria on CTR | last 3 updates only (Index shows true count) |
| Task expiry | 7 days default, configurable ≤ 90 days |
| RAM data-lake share invitation | expires after 12 h |
| Data lake freshness | typically < 1 h after record creation |
| MaxResults (both metric APIs) | 100/page |

## Sources

- Contact record data model: https://docs.aws.amazon.com/connect/latest/adminguide/ctr-data-model.html
- Agent event streams: https://docs.aws.amazon.com/connect/latest/adminguide/agent-event-streams.html
- Agent event streams data model: https://docs.aws.amazon.com/connect/latest/adminguide/agent-event-stream-model.html
- Contact events (EventBridge): https://docs.aws.amazon.com/connect/latest/adminguide/contact-events.html
- Enable data streaming (Kinesis/Firehose, KMS): https://docs.aws.amazon.com/connect/latest/adminguide/data-streaming.html
- GetMetricDataV2 API: https://docs.aws.amazon.com/connect/latest/APIReference/API_GetMetricDataV2.html
- GetCurrentMetricData API: https://docs.aws.amazon.com/connect/latest/APIReference/API_GetCurrentMetricData.html
- Analytics data lake overview: https://docs.aws.amazon.com/connect/latest/adminguide/data-lake.html
- Associate data lake tables (RAM/Lake Formation/Athena): https://docs.aws.amazon.com/connect/latest/adminguide/datalake-tables.html
- Data lake data type definitions: https://docs.aws.amazon.com/connect/latest/adminguide/data-type-definitions.html
- Contact Lens example output files: https://docs.aws.amazon.com/connect/latest/adminguide/contact-lens-example-output-files.html
- Contact Lens data storage: https://docs.aws.amazon.com/connect/latest/adminguide/contact-lens-data-storage.html
- Recording when/what/where: https://docs.aws.amazon.com/connect/latest/adminguide/about-recording-behavior.html
- Contact search: https://docs.aws.amazon.com/connect/latest/adminguide/contact-search.html
- Forecasting, capacity planning, and scheduling: https://docs.aws.amazon.com/connect/latest/adminguide/forecasting-capacity-planning-scheduling.html
- AWS News Blog — analytics data lake: https://aws.amazon.com/blogs/aws/simplify-custom-contact-center-insights-with-amazon-connect-analytics-data-lake/

# Amazon Connect — Contact Flows & Flow Language

> Last updated: 2026-07 (baseline)

Contact flows define the customer/agent experience in Amazon Connect. A flow can be built in the drag-and-drop **flow designer** (UI blocks) or authored/managed as JSON in the **Amazon Connect Flow language** (used by `CreateContactFlow` / `UpdateContactFlowContent` and by flow import/export). This document covers flow types, the flow language, the block/action catalog, attributes, modules, versioning, APIs, and pitfalls.

---

## 1. Flow types and when each runs

Flow type is fixed at creation time (`Type` on `CreateContactFlow`). **Each type exposes only a subset of blocks**, and you cannot import a flow of one type into another type — pick correctly up front.

| Flow type (UI) | API `Type` enum | When it runs | Channels |
|---|---|---|---|
| Inbound flow ("contact flow") | `CONTACT_FLOW` | Entry-point flow when a contact arrives (phone number, chat, task, `StartOutboundVoiceContact` etc.). Generic type created by default. | voice, chat, task |
| Customer queue flow | `CUSTOMER_QUEUE` | Plays to the customer **while waiting in queue**, before joining an agent. Interruptible; may offer callback via **Transfer to queue** block. | voice, chat, task |
| Customer hold flow | `CUSTOMER_HOLD` | Plays to the customer while **on hold** (usually **Loop prompts**). | voice only |
| Customer whisper flow | `CUSTOMER_WHISPER` | Plays to the customer immediately **before being joined** with an agent (inbound). Both whispers play to completion, then parties are joined. | voice, chat |
| Agent hold flow | `AGENT_HOLD` | Plays to the **agent** while on hold with a customer. | voice only |
| Agent whisper flow | `AGENT_WHISPER` | Plays to the **agent** right after they accept, before joining (default whisper says the queue name). | voice, chat, task |
| Outbound whisper flow | `OUTBOUND_WHISPER` | Plays to the **customer** on an outbound call before connecting to the agent (e.g. enable recording with **Set recording behavior**). Also used for email replies (AGENT_REPLY / FLOW initiation). | voice, chat |
| Transfer to agent flow | `AGENT_TRANSFER` | Runs when an agent transfers to another agent via a quick connect. ⚠ On a cold transfer this flow is played **to the caller**, so never put sensitive info in it. | voice, chat, task |
| Transfer to queue flow | `QUEUE_TRANSFER` | Runs when an agent transfers a contact to another queue via a quick connect. | voice, chat, task |
| Campaign flow | `CAMPAIGN` | Customer experience during an outbound campaign. | outbound campaigns only |

### Runtime sequence per initiation method (`$.InitiationMethod`)
- **INBOUND / API / WEBRTC_API**: Inbound flow → Customer queue flow → Agent whisper flow → Customer whisper flow → connected.
- **OUTBOUND** (agent dials from CCP): Outbound whisper flow only. Blocks before the first Play prompt run before the customer answers.
- **TRANSFER** (agent→agent): Agent transfer flow → Agent whisper (destination agent) → Customer whisper (source agent); Customer hold flow plays to the original caller meanwhile. Agent→queue is the same with Queue transfer flow first.
- **CALLBACK**: Agent whisper flow → Outbound whisper flow.
- **QUEUE_TRANSFER** (flow block moved contact between queues): Customer queue flow only.
- **DISCONNECT**: flow named in a **Set disconnect flow** block (must be an Inbound flow type) runs after disconnect.
- **EXTERNAL_OUTBOUND / MONITOR**: no flow type runs. **AGENT_REPLY / FLOW** (email): Outbound whisper flow.

If you don't set custom queue/hold/whisper flows (via **Set customer queue flow**, **Set hold flow**, **Set whisper flow** blocks), the instance **default flows** of that type run.

---

## 2. Flow language JSON structure

Top level (`Content` string of Create/UpdateContactFlow, and what export produces):

```json
{
  "Version": "2019-10-30",
  "StartAction": "<Identifier of first action>",
  "Metadata": { "EntryPointPosition": {"x": 88, "y": 100}, "ActionMetadata": { "<id>": {"Position": {"x": 270, "y": 98}} } },
  "Actions": [ { "Identifier": "...", "Type": "...", "Parameters": {}, "Transitions": {} } ]
}
```

- `Version`: only supported value is **`"2019-10-30"`**.
- `StartAction`: must match the `Identifier` of an action in `Actions`.
- `Metadata`: free-form; the designer stores block positions/display names here. Not executed.
- `Actions`: max **250 actions per flow**. `Content` max length for the APIs is **256,000 characters**.

### Action fields
- **Identifier** — unique within the flow, ≤50 chars, any characters *except* `% : ( \ / ) = $ , ; [ ] { }`; forbidden strings: `__proto__`, `constructor`, `__defineGetter__`, `__defineSetter__`, `toString`, `hasOwnProperty`, `isPrototypeOf`, `propertyIsEnumerable`, `toLocaleString`, `valueOf`. (Get real identifiers by creating a flow in the console and calling `DescribeContactFlow`.)
- **Type** — the action name (see catalog below).
- **Parameters** — action-specific object. Many parameters accept static values or dynamic JSONPath references (e.g. `"QueueId": "$.Attributes.targetQueueArn"`); some must be static (documented per action).
- **Transitions** — `{ "NextAction": "...", "Errors": [...], "Conditions": [...] }`. Terminal actions (e.g. `DisconnectParticipant`) require `"Transitions": {}`.
  - `Errors`: list of `{ "ErrorType": "<name>", "NextAction": "<id>" }`. Each action documents its supported ErrorTypes; `NoMatchingError` is the catch-all and must usually always be defined.
  - `Conditions`: **ordered** list of `{ "NextAction": "<id>", "Condition": { "Operator": "...", "Operands": ["..."] } }` evaluated against the action's *result* (e.g. `Compare` result = the `ComparisonValue`). First true condition wins; if none match, `NoMatchingCondition` error transition fires. Conditions nest ≤5 deep, ≤50 sub-conditions.

### Condition operators
`Equals`, `TextStartsWith`, `TextEndsWith`, `TextContains`, `NumberGreaterThan`, `NumberGreaterOrEqualTo`, `NumberLessThan`, `NumberLessOrEqualTo` — each takes one string operand (numeric ops return false on non-numeric values).

### Action categories (determine when an action may run)
- **Participant actions** — need a participant (play prompt, get input, disconnect…). Not available in flows with no participant.
- **Contact actions** — need a contact; manipulate contact data (attributes, queue, recording…).
- **Flow control actions** — no side effects; branching/logic only. Available in every flow type.
- **Interactions** — side effects but need no contact/participant (Lambda, Customer Profiles…).

---

## 3. Action catalog (flow language name ⇄ UI block)

### Participant actions
| Action `Type` | UI block | Notes |
|---|---|---|
| `MessageParticipant` | **Play prompt** | `Parameters`: exactly one of `Text`, `SSML`, `PromptId`, or `Media` (S3 audio). `PromptId`/`SSML` voice-only; other channels only `Text`. Not allowed in hold flows. Error: `NoMatchingError`. |
| `MessageParticipantIteratively` | **Loop prompts** | Loop a sequence of prompts in queue/hold flows. |
| `GetParticipantInput` | **Get customer input** / **Store customer input** | DTMF collection. `Parameters`: `Text`/`SSML`/`PromptId`/`Media`, `InputTimeLimitSeconds` (timeout to *first* digit), `StoreInput` "True"/"False", `InputValidation` (`PhoneNumberValidation` `{NumberFormat: "Local"|"E164", CountryCode}` or `CustomValidation` `{MaximumLength}`), `InputEncryption` (`EncryptionKeyId`, `Key` PEM), `DTMFConfiguration` (`InputTerminationSequence`, `DisableCancelKey`, `InterdigitTimeLimitSeconds` 1–20). If `StoreInput` false → result is the digit; Conditions supported but **only `Equals` on a single char** (0-9, *, #). If true → input lands in `$.StoredCustomerInput`. Errors: `NoMatchingCondition`, `NoMatchingError`, `InvalidPhoneNumber`, `InputTimeLimitExceeded`. ⚠ Docs mark this action **voice channel only**; chat/task input gathering is done via a Lex bot. Not usable in whisper/hold flows. |
| `ConnectParticipantWithLexBot` | **Get customer input** (Lex mode) | Hands the participant to an Amazon Lex (V1/V2) bot; branch on `$.Lex.IntentName` via Conditions. |
| `DisconnectParticipant` | **Disconnect / hang up** | Terminal; `"Transitions": {}`, `"Parameters": {}`. |
| `ShowView` | **Show view** | Step-by-step guides UI; results in `$.Views.Action` / `$.Views.ViewResultData`. |

### Contact actions
| Action `Type` | UI block | Notes |
|---|---|---|
| `UpdateContactAttributes` | **Set contact attributes** | `Parameters`: `{ "Attributes": {k:v,...}, "TargetContact": "Current"|"Related" }`. All-or-nothing. Any flow/channel. |
| `UpdateContactTargetQueue` | **Set working queue** | `{ "QueueId": <queue ARN or JSONPath> }` or `{ "AgentId": ... }` (mutually exclusive; static or a *single* JSONPath). Only inbound & transfer flows. |
| `TransferContactToQueue` | **Transfer to queue** | No parameters — queues to the contact's TargetQueue. Fails if already queued. Errors: `QueueAtCapacity`, `NoMatchingError`. Only inbound & transfer flows (see `DequeueContactAndTransferToQueue` for queue flows). |
| `DequeueContactAndTransferToQueue` | **Transfer to queue** (inside customer queue flow) | Moves an already-queued contact to another queue (initiation method becomes QUEUE_TRANSFER). |
| `TransferContactToAgent` | **Transfer to agent (beta)** | Direct-to-agent transfer. |
| `UpdateContactRecordingBehavior` / `UpdateContactRecordingAndAnalyticsBehavior` | **Set recording behavior** / **Set recording, analytics and processing behavior** | Recording, Contact Lens, screen recording, IVR logs. |
| `UpdateContactEventHooks` | **Set customer queue flow / Set disconnect flow / Set event flow / Set hold flow / Set whisper flow** | Registers which flow runs on a later event (queue, disconnect, hold, whisper…). |
| `UpdateContactCallbackNumber` | **Set callback number** | Sets the number used for queued callbacks. |
| `UpdateContactTextToSpeechVoice` | **Set voice** | Amazon Polly voice/language (`$.TextToSpeechVoiceId`). |
| `UpdateContactRoutingBehavior` | **Change routing priority / age** | Priority/age in queue. |
| `UpdateRoutingCriteria` | **Set routing criteria** | Attribute-based routing steps (listed under flow-control in docs). |
| `CreateTask` | **Create task** | Creates a task contact. |
| `CreateCallbackContact` | (part of Transfer to queue "callback" config) | Interactions-category action creating a callback contact. |
| `CreateCase` / `GetCase` / `UpdateCase` | **Cases** | Amazon Connect Cases. |
| `CreateWisdomSession` | **Amazon Q in Connect / Connect assistant** | AI assistant session (`$.Wisdom.SessionArn`). |
| `TagContact` / `UnTagContact` | **Contact tags** | User-defined contact tags. |
| `StartOutboundChatContact`, `CompleteOutboundCall`, `ResumeContact`, `UpdateContactMediaProcessing`, `UpdateContactMediaStreamingBehavior` (**Start/Stop media streaming**), `UpdatePreviousContactParticipantState` (**Interrupt agent**), `UpdateContactData`, `EndFlowModuleExecution` (**Return** from module), `InvokeFlowModule` (**Invoke module**) | — | See per-action pages. |

### Flow control actions (all flow types)
| Action `Type` | UI block | Notes |
|---|---|---|
| `Compare` | **Check contact attributes** | `{ "ComparisonValue": "$.Attributes.x" }` (single JSONPath); branch via Conditions; error `NoMatchingCondition`. |
| `CheckHoursOfOperation` | **Check hours of operation** | Result `True`/`False` conditions. |
| `CheckMetricData` / `GetMetricData` | **Check queue status** / **Get metrics** | Queue/agent metrics (result e.g. NumberOfContactsInQueue); Get metrics fills `$.Metrics.*`. Also **Check staffing**. |
| `Loop` | **Loop** | Count- or array-based; `$.Loop.<name>.Index/.Element/.Elements`. Branches: looping / complete. |
| `Wait` | **Wait** | Pauses the flow (e.g. chat/task timeouts); Time-expired branch. |
| `DistributeByPercentage` | **Distribute by percentage** | Random percentage split. |
| `EndFlowExecution` | **End flow / Resume** | Ends current flow without disconnecting. |
| `TransferToFlow` | **Transfer to flow** | Jump to another (published) flow. |
| `UpdateFlowAttributes` | (Set contact attributes with "Flow" scope) | Sets `$.FlowAttributes.*` local to the flow. |
| `UpdateFlowLoggingBehavior` | **Set logging behavior** | `{ "FlowLoggingBehavior": "Enabled"|"Disabled" }` (static only); inherited by later segments. |
| `CheckOutboundCallStatus` | **Check call progress** | Campaigns; answering-machine detection branches. |
| `CheckVoiceId` / `StartVoiceIdStream` | **Check Voice ID** / **Set Voice ID** | Voice biometrics. |

### Interactions
| Action `Type` | UI block | Notes |
|---|---|---|
| `InvokeLambdaFunction` | **AWS Lambda function** (a.k.a. "Invoke AWS Lambda function") | `Parameters`: `LambdaFunctionARN` (static or dynamic), `InvocationTimeLimitSeconds` (integer 1–8, static), `InvocationType` `"SYNCHRONOUS"|"ASYNCHRONOUS"`, `LambdaInvocationAttributes` {k:v}, `ResponseValidation.ResponseType` `"STRING_MAP"` (flat string map) or `"JSON"` (nested allowed). On success, response fields are readable at **`$.External.<key>`** (or `$.LambdaInvocation.ResultData` per attribute docs); overwritten by each invocation. Error: `NoMatchingError`. Works in all channels/flow types. |
| `CreateCustomerProfile`, `GetCustomerProfile`, `GetCustomerProfileObject`, `GetCalculatedAttributesForCustomerProfile`, `UpdateCustomerProfile`, `AssociateContactToCustomerProfile` | **Customer profiles** | Fills `$.Customer.*`. |

Other UI blocks with no separate language docs above: **Authenticate Customer**, **Call phone number**, **Create persistent contact association**, **Data Table** (`$.DataTables.*`, `$.DataTableList.*`), **Get stored content** (email body from S3), **Hold customer or agent**, **Send message**, **Set Touchtone Buffer Behavior**, **Transfer to phone number**.

---

## 4. Example 1 — inbound voice flow: menu → Lambda dip → queue transfer

Valid, complete `Content` (replace ARNs). Pattern: enable logging → greet + DTMF menu → Lambda lookup → set attributes → set working queue → transfer to queue; every error branch lands on an apology + disconnect.

```json
{
  "Version": "2019-10-30",
  "StartAction": "a1-logging",
  "Actions": [
    {
      "Identifier": "a1-logging",
      "Type": "UpdateFlowLoggingBehavior",
      "Parameters": { "FlowLoggingBehavior": "Enabled" },
      "Transitions": { "NextAction": "a2-menu", "Errors": [], "Conditions": [] }
    },
    {
      "Identifier": "a2-menu",
      "Type": "GetParticipantInput",
      "Parameters": {
        "Text": "Welcome to AnyCompany. Press 1 for sales, 2 for support.",
        "InputTimeLimitSeconds": "5",
        "StoreInput": "False"
      },
      "Transitions": {
        "NextAction": "a8-sorry",
        "Conditions": [
          { "NextAction": "a3-lambda", "Condition": { "Operator": "Equals", "Operands": ["1"] } },
          { "NextAction": "a3-lambda", "Condition": { "Operator": "Equals", "Operands": ["2"] } }
        ],
        "Errors": [
          { "NextAction": "a8-sorry", "ErrorType": "InputTimeLimitExceeded" },
          { "NextAction": "a8-sorry", "ErrorType": "NoMatchingCondition" },
          { "NextAction": "a8-sorry", "ErrorType": "NoMatchingError" }
        ]
      }
    },
    {
      "Identifier": "a3-lambda",
      "Type": "InvokeLambdaFunction",
      "Parameters": {
        "LambdaFunctionARN": "arn:aws:lambda:us-east-1:123456789012:function:crm-lookup",
        "InvocationTimeLimitSeconds": "8",
        "LambdaInvocationAttributes": { "menuChoice": "$.StoredCustomerInput", "callerNumber": "$.CustomerEndpoint.Address" },
        "ResponseValidation": { "ResponseType": "STRING_MAP" }
      },
      "Transitions": {
        "NextAction": "a4-checktier",
        "Errors": [ { "NextAction": "a5-setattrs", "ErrorType": "NoMatchingError" } ],
        "Conditions": []
      }
    },
    {
      "Identifier": "a4-checktier",
      "Type": "Compare",
      "Parameters": { "ComparisonValue": "$.External.customerTier" },
      "Transitions": {
        "NextAction": "a5-setattrs",
        "Conditions": [
          { "NextAction": "a5-setattrs", "Condition": { "Operator": "Equals", "Operands": ["GOLD"] } }
        ],
        "Errors": [ { "NextAction": "a5-setattrs", "ErrorType": "NoMatchingCondition" } ]
      }
    },
    {
      "Identifier": "a5-setattrs",
      "Type": "UpdateContactAttributes",
      "Parameters": {
        "Attributes": { "customerTier": "$.External.customerTier", "accountId": "$.External.accountId" },
        "TargetContact": "Current"
      },
      "Transitions": {
        "NextAction": "a6-setqueue",
        "Errors": [ { "NextAction": "a6-setqueue", "ErrorType": "NoMatchingError" } ],
        "Conditions": []
      }
    },
    {
      "Identifier": "a6-setqueue",
      "Type": "UpdateContactTargetQueue",
      "Parameters": { "QueueId": "arn:aws:connect:us-east-1:123456789012:instance/INSTANCE_ID/queue/QUEUE_ID" },
      "Transitions": {
        "NextAction": "a7-transfer",
        "Errors": [ { "NextAction": "a8-sorry", "ErrorType": "NoMatchingError" } ],
        "Conditions": []
      }
    },
    {
      "Identifier": "a7-transfer",
      "Type": "TransferContactToQueue",
      "Parameters": {},
      "Transitions": {
        "Errors": [
          { "NextAction": "a8-sorry", "ErrorType": "QueueAtCapacity" },
          { "NextAction": "a8-sorry", "ErrorType": "NoMatchingError" }
        ]
      }
    },
    {
      "Identifier": "a8-sorry",
      "Type": "MessageParticipant",
      "Parameters": { "Text": "We are unable to take your call right now. Please try again later." },
      "Transitions": {
        "NextAction": "a9-disconnect",
        "Errors": [ { "NextAction": "a9-disconnect", "ErrorType": "NoMatchingError" } ],
        "Conditions": []
      }
    },
    { "Identifier": "a9-disconnect", "Type": "DisconnectParticipant", "Parameters": {}, "Transitions": {} }
  ]
}
```

Notes: `TransferContactToQueue` succeeds by ending the flow (the contact enters the queue and the customer queue flow starts); model it with only `Errors` transitions. On Lambda success the values are read as `$.External.*`; only what you copy via `UpdateContactAttributes` persists to `$.Attributes.*`/the contact record.

## 5. Example 2 — chat-capable inbound flow (channel-aware)

Branch on `$.Channel`; use plain `Text` for chat, SSML for voice. Works as `Type: CONTACT_FLOW` for both channels.

```json
{
  "Version": "2019-10-30",
  "StartAction": "c1-channel",
  "Actions": [
    {
      "Identifier": "c1-channel",
      "Type": "Compare",
      "Parameters": { "ComparisonValue": "$.Channel" },
      "Transitions": {
        "NextAction": "c3-voicegreet",
        "Conditions": [
          { "NextAction": "c2-chatgreet",  "Condition": { "Operator": "Equals", "Operands": ["CHAT"] } },
          { "NextAction": "c3-voicegreet", "Condition": { "Operator": "Equals", "Operands": ["VOICE"] } }
        ],
        "Errors": [ { "NextAction": "c3-voicegreet", "ErrorType": "NoMatchingCondition" } ]
      }
    },
    {
      "Identifier": "c2-chatgreet",
      "Type": "MessageParticipant",
      "Parameters": { "Text": "Hi! Thanks for chatting with AnyCompany. Connecting you to the next available agent." },
      "Transitions": {
        "NextAction": "c4-setattrs",
        "Errors": [ { "NextAction": "c4-setattrs", "ErrorType": "NoMatchingError" } ],
        "Conditions": []
      }
    },
    {
      "Identifier": "c3-voicegreet",
      "Type": "MessageParticipant",
      "Parameters": { "SSML": "<speak>Thanks for calling AnyCompany.<break time=\"500ms\"/>Connecting you to an agent.</speak>" },
      "Transitions": {
        "NextAction": "c4-setattrs",
        "Errors": [ { "NextAction": "c4-setattrs", "ErrorType": "NoMatchingError" } ],
        "Conditions": []
      }
    },
    {
      "Identifier": "c4-setattrs",
      "Type": "UpdateContactAttributes",
      "Parameters": {
        "Attributes": { "entryChannel": "$.Channel", "initialMessage": "$.Media.InitialMessage" },
        "TargetContact": "Current"
      },
      "Transitions": {
        "NextAction": "c5-setqueue",
        "Errors": [ { "NextAction": "c5-setqueue", "ErrorType": "NoMatchingError" } ],
        "Conditions": []
      }
    },
    {
      "Identifier": "c5-setqueue",
      "Type": "UpdateContactTargetQueue",
      "Parameters": { "QueueId": "arn:aws:connect:us-east-1:123456789012:instance/INSTANCE_ID/queue/QUEUE_ID" },
      "Transitions": {
        "NextAction": "c6-transfer",
        "Errors": [ { "NextAction": "c7-fail", "ErrorType": "NoMatchingError" } ],
        "Conditions": []
      }
    },
    {
      "Identifier": "c6-transfer",
      "Type": "TransferContactToQueue",
      "Parameters": {},
      "Transitions": {
        "Errors": [
          { "NextAction": "c7-fail", "ErrorType": "QueueAtCapacity" },
          { "NextAction": "c7-fail", "ErrorType": "NoMatchingError" }
        ]
      }
    },
    {
      "Identifier": "c7-fail",
      "Type": "MessageParticipant",
      "Parameters": { "Text": "Sorry, no agents are available right now." },
      "Transitions": {
        "NextAction": "c8-disconnect",
        "Errors": [ { "NextAction": "c8-disconnect", "ErrorType": "NoMatchingError" } ],
        "Conditions": []
      }
    },
    { "Identifier": "c8-disconnect", "Type": "DisconnectParticipant", "Parameters": {}, "Transitions": {} }
  ]
}
```

---

## 6. Contact attributes — namespaces & JSONPath

Attributes are referenced with JSONPath inside `Parameters` values and dynamic text (`$.Namespace.key`, or bracket form `$['AwsRegion']`, `$.SegmentAttributes['connect:Subtype']`).

| Namespace | JSONPath | Set by / contains | Persisted in contact record? |
|---|---|---|---|
| User-defined | `$.Attributes.key` | **Set contact attributes** (`UpdateContactAttributes`), StartChatContact/StartOutboundVoiceContact `Attributes`, `UpdateContactAttributes` API | Yes (32 KB cap); visible in CCP, Lambda input, GetContactAttributes |
| Flow | `$.FlowAttributes.key` | `UpdateFlowAttributes`; **scoped to the current flow only** | No — not in contact record, CCP, GetContactAttributes, or default Lambda input; not passed into modules or transferred flows; keys/values DO appear in CloudWatch flow logs if logging is on |
| External (Lambda) | `$.External.key` (also `$.LambdaInvocation.ResultData.key`) | Most recent `InvokeLambdaFunction` response; overwritten each invocation | No — copy to `$.Attributes` to persist |
| Segment | `$.SegmentAttributes['key']` | System keys `connect:Subtype`, `connect:Direction`, `connect:EmailSubject`, `connect:CustomerAuthentication`, `connect:ContactExpiry`, `connect:X-SES-SPAM-VERDICT`… plus user-defined predefined attributes | Yes, on individual contact segments |
| Lex | `$.Lex.IntentName`, `$.Lex.Slots.slotName`, `$.Lex.SessionAttributes.key`, `$.Lex.IntentConfidence.Score`, `$.Lex.SentimentResponse.Label`, `$.Lex.AlternativeIntents.{x}.IntentName`, `$.Lex.DialogState` | Latest Lex bot interaction | No (copy if needed) |
| System | see list below | Amazon Connect | Some (endpoints yes; e.g. callback number & stored input no) |
| Media/telephony | `$.Media.Sip.Headers.From/.To/.JIP/.ISUP-OLI/...`, `$.Media.InitialMessage` (first chat/SMS message) | Carrier SIP metadata; chat initial message | — |
| Media streams | `$.MediaStreams.Customer.Audio.StreamARN/.StartTimestamp/.StopTimestamp/.StartFragmentNumber` | Live media streaming (KVS) | — |
| Queue metrics | `$.Metrics.Queue.Name/.ARN/.Size/.OldestContactAge/.EstimatedWaitTime`, `$.Metrics.Agents.Online.Count/.Available.Count/.Staffed.Count/.AfterContactWork.Count/.Busy.Count/.Missed.Count/.NonProductive.Count`, `$.Metrics.Contact.EstimatedWaitTime/.PositionInQueue` | **Get metrics** block | — |
| Agent | `$.Agent.UserName/.FirstName/.LastName/.ARN` | Only in whisper/hold/agent-transfer flows (target agent in transfer flows); **not** in inbound, customer queue, or queue transfer flows | — |
| Customer Profiles | `$.Customer.ProfileId/.FirstName/.PhoneNumber/.Attributes.x/.CalculatedAttributes.z/...` | Customer profiles block (14,000-char total cap per flow) | — |
| Cases | `$.Case.case_id/.status/.title/...` | Cases block | — |
| Loop | `$.Loop.<LoopName>.Index/.Element/.Elements` | Loop action | — |
| Modules | `$.Modules.Input`, `$.Modules.Result` (branch name), `$.Modules.ResultData` (output object) | Invoke module | No |
| Views | `$.Views.Action`, `$.Views.ViewResultData` | Show view block | — |
| Data tables | `$.DataTables.<QueryName>.<Attr>`, `$.DataTableList.ResultData.primaryKeyGroups.<Group>[i]...` | Data Table block (List capped 32 KB) | — |
| Q in Connect | `$.Wisdom.SessionArn` | Connect assistant | — |

### Key system attributes
`$.CustomerEndpoint.Address` (caller number / customer email), `$.CustomerEndpoint.Type`, `$.SystemEndpoint.Address` (number dialed), `$.CustomerId`, `$.ContactId`, `$.InitialContactId`, `$.PreviousContactId`, `$.Task.ContactId`, `$.Channel` (VOICE|CHAT|TASK|EMAIL), `$.InitiationMethod`, `$.InstanceARN`, `$.AwsRegion`, `$.Queue.Name`, `$.Queue.ARN`, `$.Queue.OutboundCallerId.Address`, `$.TextToSpeechVoiceId`, `$.LanguageCode`, `$.StoredCustomerInput`, `$.Name` / `$.Description` (tasks), `$.References.<key>.Value/.Type`, `$.Tags`, `$.CustomerEndpoint.DisplayName` / `$.SystemEndpoint.DisplayName` and `$.AdditionalEmailRecipients.CcList/.ToList` (email), `$.Capabilities.Agent.Video` etc. Customer callback number has **no JSONPath** — copy via Set contact attributes if needed.

Gotchas: `$.StoredCustomerInput` and Lambda `$.External.*` are volatile (latest invocation wins) and excluded from contact records. In UI dynamic fields, don't mix pick-list "Set dynamically" with `$.`-prefixed paths (causes a prepended-period bug — use `$.External.name` with "Save text as attribute", or bare `name` with "Set dynamically").

---

## 7. Dynamic prompts & SSML

- Any `Text`/`SSML` parameter can interpolate attributes: `"Text": "Hello $.Attributes.firstName, your wait is $.Metrics.Queue.EstimatedWaitTime seconds."`
- Prompts can be selected dynamically by prompt ARN from an attribute (`PromptId` accepts a single JSONPath), and audio can come from S3 via the `Media` parameter (`SourceType: "S3"`, `MediaType: "Audio"`).
- SSML: set **Interpret as = SSML** in Play prompt / Get customer input (or use the `SSML` parameter). Wrap in `<speak>…</speak>`. Supported tags: `speak`, `break` (≤10 s), `lang`, `mark`, `p`, `phoneme`, `prosody`, `s`, `say-as`, `sub`, `w`, `amazon:effect name="whispered"`; Newscaster style for Joanna/Matthew neural (en-US). Unsupported tags are ignored. Voice-channel only.
- Set the Polly voice per contact with **Set voice** (`UpdateContactTextToSpeechVoice`).

---

## 8. Flow modules

- Reusable sub-flows (`Routing → Flows → Modules`); usable **in all flow types** via the **Invoke module** block (`InvokeFlowModule` action); exit with **Return** (`EndFlowModuleExecution`).
- Modules must be **published** before flows can invoke them.
- Data in/out is via contact attributes, or (custom block modules) typed input/output schemas (String, Number, Integer, Boolean, Object, Array, Null; up to 8 custom branches). Read module output at `$.Modules.ResultData`, branch name at `$.Modules.Result`, input inside the module at `$.Modules.Input`.
- **Not available inside modules**: External (Lambda default input), Lex attributes, Customer Profiles attributes, Q in Connect attributes, queue metrics, stored customer input. Flow attributes don't cross the module boundary either.
- Nesting: modules can invoke modules up to **5 levels** (recursion blocked). "Module as tool" (for Q in Connect AI agents) restricts the block palette (Lambda, Cases, SetAttributes, Loop, DataTable, etc. allowed; participant blocks not).
- Modules support **immutable versions and named aliases** (`$.LATEST` tracks newest); pick a version/alias in the Invoke module block — the recommended way to roll module changes across many flows.
- If a module contains blocks unsupported by the invoking flow's type, those blocks take the **error branch** at runtime.

---

## 9. Versioning, states, and the flow APIs

- Flow **status**: `SAVED` (draft; content not validated) vs `PUBLISHED` (validated; live). Flow **state**: `ACTIVE` vs `ARCHIVED`. Publishing requires every connector wired.
- The designer keeps a history of published versions ("Latest: Published" dropdown); roll back by opening an older version and choosing **Publish**. "View historical changes" on the Flows page shows a cross-flow audit.
- Key APIs (service `connect`): `CreateContactFlow` (Content ≤256,000 chars; `Status` SAVED|PUBLISHED; `Type` enum in §1), `UpdateContactFlowContent`, `UpdateContactFlowMetadata`, `UpdateContactFlowName`, `DescribeContactFlow` (returns Content — best way to learn exact JSON), `ListContactFlows`, `SearchContactFlows` (POST /search-contact-flows; `SearchCriteria` with `StateCondition`/`StatusCondition`/`StringCondition` on name/description (2–25 char "contains") /`TypeCondition`; `SearchFilter` by tags/flow type; response items include `Content`, `FlowContentSha256`, `Status`, `State`, `Version`, `VersionDescription`), `DeleteContactFlow`, plus module twins (`CreateContactFlowModule`, `SearchContactFlowModules`, …).
- `CreateContactFlowVersion` exists (PUT /contact-flows/{InstanceId}/{ContactFlowId}/version; optional `FlowContentSha256` optimistic check; returns monotonically increasing `Version`) — **but the docs state it only supports flows of type `Campaign`** as of this writing. General flows version implicitly on publish (console rollback); modules have full version/alias support.
- **`InvalidContactFlowException`** (HTTP 400) is returned by CreateContactFlow/UpdateContactFlowContent when publishing invalid content; it carries a `problems` list (`[{"message": ...}]`) describing each broken block/transition. `SAVED` status skips validation — use it to stage incomplete flows.

## 10. Flow designer UI vs JSON, import/export

- Export: flow designer → **Save → Export flow**; produces a JSON file (flow language + Metadata). Limits: **< 200 blocks, < 1 MB** (block counter in UI). Import: **Save → Import flow** into a flow of the **same type**.
- JSON block/parameter names often differ from UI labels (e.g. Play prompt → `MessageParticipant`, Set working queue → `UpdateContactTargetQueue`, Check contact attributes → `Compare`).
- Resource resolution on import: resources are referenced by **name + ARN**. Same instance → ARNs resolve; different instance/Region → ARN lookup fails and Connect falls back to **matching by name**; unresolved required resources block publishing (saving is allowed). This is the main cross-environment breakage: queues/prompts/Lambdas/Lex bots referenced by ARN must exist (or match by name) in the target instance. For bulk migration use the APIs (see "Migrate flows" docs) and rewrite ARNs.
- **Legacy flow import deprecation**: importing legacy (old designer) flow JSON ends **2026-03-31**; already past — offline flow stores must be in the new flow language. Copy/paste in the designer only works with new-language flows.
- Import/export remains officially "Beta".

## 11. Flow logs (CloudWatch)

- Enable per instance (Connect console → Flows → "Enable flow logging") — creates the log group `/aws/connect/<instance-alias>` — **and** add a **Set logging behavior** block (`UpdateFlowLoggingBehavior: Enabled`) in the flow. Logging behavior carries into subsequent segments until overridden.
- Logs are generated for **published** flows as contacts run them; each entry is JSON with the `ContactId`, flow name, block/action type, parameters, and results — query by ContactId in CloudWatch Logs Insights to trace a contact across flows. Set alarms/alerts on error patterns.
- Disable logging around blocks that collect sensitive data (log entries include parameter values — including FlowAttributes). Encrypted `GetParticipantInput` and disabled logging are the tools for PCI-style capture.
- "Automated interaction logs" (IVR/bot transcripts) are a separate, S3-based feature enabled on the instance Flows page.

## 12. Best practices

- Route **every error branch** somewhere deliberate (handler or disconnect); all connectors must be wired to publish.
- Always define `NoMatchingError`; give `Compare`/input actions a `NoMatchingCondition` (default) path — a customer who presses nothing should still get routed.
- Before queueing: **Check hours of operation** + **Check staffing**; offer callbacks with **Check queue status** (queue capacity > X) → Get/Store customer input → **Set callback number** → Transfer to (callback) queue. Interrupt long waits from **Loop prompts** in the customer queue flow at intervals.
- Keep flows small and modular (also keeps you under the 200-block export limit); compose with Transfer to flow / modules.
- camelCase attribute names; alphanumeric + periods only in dynamic values; no spaces/special chars (breaks Glue/Athena downstream).
- External-transfer numbers in E.164 (`+447911123456`, drop trunk 0/1 prefixes); add destination countries to your outbound-country service quota.
- No infinite loops; every path must end in agent, bot, transfer, or disconnect.
- Don't rename flows once created (naming conventions matter at 100+ flows).

## 13. Common pitfalls

- **Unpublished flows**: `SAVED` drafts aren't validated and can't be attached/executed; phone numbers, quick connects, `TransferToFlow`, and `Set event flow` targets need **published** flows. Publishing validates and can throw `InvalidContactFlowException` with a `problems` list via API.
- **Wrong flow type**: block palette and allowed actions differ per type; you cannot convert or cross-import types. E.g. `TransferContactToQueue`/`UpdateContactTargetQueue` are invalid in whisper/hold/queue flows; `MessageParticipant` invalid in hold flows; `GetParticipantInput` invalid in whisper/hold flows.
- **Channel mismatches**: `GetParticipantInput` (DTMF) is voice-only — chat/task must gather input via Lex (`ConnectParticipantWithLexBot`) or Views; `SSML`/`PromptId` voice-only (chat gets raw text if you send SSML); customer/agent hold flows voice-only; **Call phone number**, Voice ID, media streaming voice-only; **Show view** chat/task-oriented. Always branch on `$.Channel` in multi-channel flows; a block hitting an unsupported channel takes its **Error** branch.
- **ARNs across environments**: exported JSON embeds full ARNs (queues, prompts, Lambda, Lex, hours of operation). Import resolves by ARN then by name; anything else needs manual re-mapping or scripted ARN rewriting. Lambdas/Lex bots must also be **associated with the target instance** (Flows section of instance settings / `AssociateLambdaFunction`) or invocation fails.
- **Attribute volatility**: `$.External.*`, `$.StoredCustomerInput`, `$.Modules.*` are overwritten by the next invocation and never persisted — copy to `$.Attributes.*` immediately if needed later or in reports.
- **Flow attributes vs contact attributes**: `$.FlowAttributes` don't survive flow transfer, module boundaries, or reach Lambda/CCP/contact records — but they DO show in CloudWatch logs.
- **Agent attributes** are unavailable in inbound/customer-queue/queue-transfer flows (no agent yet).
- **Whisper flows must complete** before parties join — long whispers delay connects; keep them short.
- **Transfer-to-agent flow plays to the caller** on cold transfer — never include internal/sensitive info.
- **250-action limit** per flow (200 blocks for import/export); Lambda sync timeout ≤ 8 s per invocation (chain invocations for longer work).
- `Metadata` is cosmetic; hand-written flows without it work but render stacked at (0,0) in the designer.

## Sources

- https://docs.aws.amazon.com/connect/latest/APIReference/flow-language-concepts.html
- https://docs.aws.amazon.com/connect/latest/APIReference/flow-language-actions.html
- https://docs.aws.amazon.com/connect/latest/APIReference/flow-language-example.html
- https://docs.aws.amazon.com/connect/latest/APIReference/participant-actions.html
- https://docs.aws.amazon.com/connect/latest/APIReference/contact-actions.html
- https://docs.aws.amazon.com/connect/latest/APIReference/flow-control-actions.html
- https://docs.aws.amazon.com/connect/latest/APIReference/interactions.html
- https://docs.aws.amazon.com/connect/latest/devguide/participant-actions-getparticipantinput.html
- https://docs.aws.amazon.com/connect/latest/devguide/participant-actions-messageparticipant.html
- https://docs.aws.amazon.com/connect/latest/devguide/interactions-invokelambdafunction.html
- https://docs.aws.amazon.com/connect/latest/devguide/contact-actions-transfercontacttoqueue.html
- https://docs.aws.amazon.com/connect/latest/devguide/contact-actions-updatecontacttargetqueue.html
- https://docs.aws.amazon.com/connect/latest/devguide/contact-actions-updatecontactattributes.html
- https://docs.aws.amazon.com/connect/latest/devguide/flow-control-actions-compare.html
- https://docs.aws.amazon.com/connect/latest/devguide/flow-control-actions-updateflowloggingbehavior.html
- https://docs.aws.amazon.com/connect/latest/adminguide/create-contact-flow.html
- https://docs.aws.amazon.com/connect/latest/adminguide/contact-initiation-methods.html
- https://docs.aws.amazon.com/connect/latest/adminguide/contact-block-definitions.html
- https://docs.aws.amazon.com/connect/latest/adminguide/connect-attrib-list.html
- https://docs.aws.amazon.com/connect/latest/adminguide/contact-flow-modules.html
- https://docs.aws.amazon.com/connect/latest/adminguide/flow-version-control.html
- https://docs.aws.amazon.com/connect/latest/adminguide/contact-flow-import-export.html
- https://docs.aws.amazon.com/connect/latest/adminguide/about-contact-flow-logs.html
- https://docs.aws.amazon.com/connect/latest/adminguide/bp-contact-flows.html
- https://docs.aws.amazon.com/connect/latest/adminguide/supported-ssml-tags.html
- https://docs.aws.amazon.com/connect/latest/APIReference/API_CreateContactFlow.html
- https://docs.aws.amazon.com/connect/latest/APIReference/API_CreateContactFlowVersion.html
- https://docs.aws.amazon.com/connect/latest/APIReference/API_SearchContactFlows.html

# Amazon Connect — AI, Bots & Integrations (Lambda, Lex, Q in Connect, Contact Lens)

> Last updated: 2026-07 (baseline)

**Naming note (2026):** AWS documentation now brands the core product as "Amazon Connect Customer" (admin guide pages say "Connect Customer"). Amazon Q in Connect has evolved into **"Connect AI agents"** (built on Amazon Bedrock); the underlying API namespace is still `qconnect` / "Amazon Q in Connect" operations, and the flow attribute namespace is still `$.Wisdom.*`. Expect mixed naming in consoles, APIs, and docs.

---

## 1. AWS Lambda integration from flows

### Setup
- **Same-Region function:** Connect console → instance alias → **Flows** → **AWS Lambda** section → select function → **Add Lambda Function**. This auto-adds the resource-based policy allowing Connect to invoke it. Programmatic equivalent: `AssociateLambdaFunction` API (instance-level association).
- **Cross-Region / cross-account function:** enter the function ARN directly in the flow block ("Select a function" → manual ARN), then add permissions yourself:
  ```bash
  aws lambda add-permission --function-name my-fn \
    --statement-id connect-invoke --action lambda:InvokeFunction \
    --principal connect.amazonaws.com \
    --source-account <account-of-instance> \
    --source-arn arn:aws:connect:<region>:<acct>:instance/<instance-id>
  ```
- Flow block: **Invoke AWS Lambda function** (Integrate group). Optional **Function input parameters** (key-value; keys can be static or dynamic from attributes). Block also accepts **nested JSON input** (primitives + nested objects/arrays).

### Request payload Lambda receives
```json
{
  "Details": {
    "ContactData": {
      "Attributes": { "exampleAttributeKey1": "exampleAttributeValue1" },
      "Channel": "VOICE",
      "ContactId": "4a573372-1f28-4e26-b97b-XXXXXXXXXXX",
      "CustomerEndpoint": { "Address": "+1234567890", "Type": "TELEPHONE_NUMBER" },
      "CustomerId": "someCustomerId",
      "Description": "someDescription",
      "InitialContactId": "4a573372-1f28-4e26-b97b-XXXXXXXXXXX",
      "InitiationMethod": "INBOUND | OUTBOUND | TRANSFER | CALLBACK",
      "InstanceARN": "arn:aws:connect:region:acct:instance/…",
      "LanguageCode": "en-US",
      "MediaStreams": {
        "Customer": { "Audio": {
          "StreamARN": "arn:aws:kinesisvideo:…",
          "StartTimestamp": "1571360125131",
          "StopTimestamp": "1571360126131",
          "StartFragmentNumber": "100" } }
      },
      "Name": "ContactFlowEvent",
      "PreviousContactId": "4a573372-…",
      "Queue": {
        "ARN": "arn:aws:connect:…:queue/…", "Name": "PasswordReset",
        "OutboundCallerId": { "Address": "+12345678903", "Type": "TELEPHONE_NUMBER" }
      },
      "References": { "key1": { "Type": "url", "Value": "urlvalue" } },
      "SystemEndpoint": { "Address": "+1234567890", "Type": "TELEPHONE_NUMBER" }
    },
    "Parameters": { "exampleParameterKey1": "exampleParameterValue1" }
  },
  "Name": "ContactFlowEvent"
}
```
- `Details.ContactData` = always sent (contact attributes previously set via **Set contact attributes**, endpoints, channel, queue, references…). `Attributes` map may be empty.
- `Details.Parameters` = only the key-values configured on that specific block.
- Top-level `Name` is always `"ContactFlowEvent"`.
- Access pattern: `event['Details']['Parameters']['key']`, `event['Details']['ContactData']['Attributes']['key']`, `event['Details']['ContactData']['CustomerEndpoint']['Address']`.

### Response requirements
- Two **response validation** modes set on the block:
  - **STRING_MAP** — must return a *flat* object of string key/value pairs. Keys/values limited to alphanumeric, dash, underscore.
  - **JSON** — any valid JSON, including nested objects. (Referencing an *array element* in a flow is not supported — arrays are only useful as input to another Lambda.)
- Max response size: **32 KB** UTF-8.
- Return the map directly (Node: `callback(null, resultMap)` / async return; Python: `return resultMap`). No `statusCode`/`body` wrapper — this is not API Gateway.

### Timeout & retry
- Block **Timeout (max 8 seconds)** — after that the contact routes down the **Error** branch.
- On throttling (429) or service failure (500), Connect **retries up to 3 times within a maximum of 8 seconds total**, then takes Error branch.
- **20-second cap on a sequence of consecutive Lambda blocks.** Break chains with a **Play prompt** block (also masks dead air) to reset the sequence budget.

### Consuming the response
- Direct reference: `$.External.attributeName` (e.g. `$.External.AccountId`). Newer docs also expose the namespace `$.LambdaInvocation.ResultData.attributeName` — both refer to the most recent invocation's result.
- **`$.External.*` is overwritten by every subsequent Lambda invocation** and is NOT stored in the contact record. To persist: **Set contact attributes** block with Type=**External** → becomes `$.Attributes.yourKey` (in contact record, visible in CCP/screenpop).
- Error branch fires when: function unreachable, exception thrown, response not parseable/wrong mode, >32 KB, or timeout.

### Best practices
- Make handlers **idempotent** (retries mean duplicate invocations are possible).
- Keep p99 latency well under the 8 s block timeout (provisioned concurrency for cold-start-sensitive voice flows).
- Prefer STRING_MAP flat maps unless you truly need nested JSON.
- Flow attributes (`$.FlowAttributes.*`) are NOT passed to Lambda automatically — pass explicitly as parameters. Same for `$.StoredCustomerInput` and Lambda results from prior invocations.

---

## 2. Amazon Lex V2 integration

- **Lex V1 reached end of support 2025-09-15** — V2 only now. (Classic bots show "(Classic)" suffix; ignore for new work.)
- **Associate bot with instance:** Connect console → instance → **Flows** → **Amazon Lex** section → pick Region + bot + alias → **+ Add Lex Bot**. This updates the bot's resource-based policy so Connect can invoke it. (APIs: `AssociateBot` / legacy `AssociateLexBot`.)
- Production: never use `TestBotAlias` (V2) / `$LATEST` (V1) — low concurrency quotas. Create a version + alias.
- In the flow: **Get customer input** block → **Amazon Lex** tab → select bot + alias (or **Set manually** with a bot-alias ARN, possibly dynamic).
- The intent dropdown only lists intents when the bot has tag **`AmazonConnectEnabled = True`** and the alias has a version + "Use in flow and flow modules" enabled. Cross-region/dynamic-ARN bots: type intent names manually.
- **Language match gotcha (V2):** the contact's `$.LanguageCode` must match the bot's locale — set it with a **Set voice** or **Set contact attributes** block before the Lex block.

### Get customer input block essentials
- Voice + Chat (chat requires Lex; DTMF-only config errors on chat). Not Task/Email.
- DTMF mode: single digit (0-9, #, *) per branch; timeout 1–180 s. Multi-digit capture → **Store customer input** block.
- Branches: one per configured **intent**, plus **Timeout**, **Default** (unmatched input / unlisted intent), **Error** (unfulfilled intent, misconfiguration).
- Flow language: DTMF = `GetParticipantInput` action; Lex = `ConnectParticipantWithLexBot` action (`LexV2Bot.AliasArn`, `LexTimeoutSeconds`).
- **Chat timeout** for Lex interactions: 1 minute – 7 days.
- **Initialize bot with message**: pass the customer's first chat message (`$.Media.InitialMessage`), or a manual/dynamic text (≤1024 chars) to jump straight to an intent / trigger interactive messages.

### Session attributes (both directions)
- Send to Lex: **Session attributes** section of the block (key/value, static or dynamic). Inside Lex/its Lambda they arrive as session attributes; DTMF input arrives as Lex *request attribute* `x-amz-lex:dtmf-transcript` (≤1024 chars).
- Read back in flow: `$.Lex.SessionAttributes.attributeKey`.
- Other Lex results:
  - `$.Lex.IntentName`, `$.Lex.IntentConfidence.Score`
  - `$.Lex.Slots.slotName`
  - `$.Lex.DialogState` (`Fulfilled` when an intent was returned)
  - `$.Lex.AlternativeIntents.{{x}}.IntentName` / `.IntentConfidence.Score` / `.Slots`
  - Sentiment (Comprehend, last utterance only): `$.Lex.SentimentResponse.Label`, `$.Lex.SentimentResponse.Scores.Positive|Negative|Neutral|Mixed`
- **Precedence for `x-amz-lex:` runtime attributes** (one set per conversation): Lex Lambda-provided > block-provided > service defaults.

### Timing / barge-in / DTMF control (`x-amz-lex:` session attributes, V2 names)
| Purpose | Attribute | Default |
|---|---|---|
| Max speech duration | `x-amz-lex:audio:max-length-ms:[intent]:[slot]` | 12000 ms (max 15000 — larger ⇒ Error branch) |
| Start silence | `x-amz-lex:audio:start-timeout-ms:[intent]:[slot]` | 3000 ms |
| End silence | `x-amz-lex:audio:end-timeout-ms:[intent]:[slot]` | 600 ms |
| Barge-in (V2) | enabled globally by default; tune via `x-amz-lex:allow-interrupt:*:*` | on |
| DTMF end char | `x-amz-lex:dtmf:end-character:[intent]:[slot]` | `#` |
| DTMF delete char | `x-amz-lex:dtmf:deletion-character:[intent]:[slot]` | `*` |
| DTMF inter-digit timeout | `x-amz-lex:dtmf:end-timeout-ms:[intent]:[slot]` | 5000 ms |
| DTMF max digits | `x-amz-lex:dtmf:max-length:[intent]:[slot]` | 1024 (cannot raise) |

- Wildcards allowed: `x-amz-lex:audio:max-length-ms:PasswordReset:*`, `…:*:*`. Wildcards apply per block, not across blocks.
- Prompt users to end DTMF entry with `#`, otherwise they wait ~5 s for the inter-digit timeout.
- **Sentiment override branching:** in Intents section, branch on sentiment score *before* intent matching (e.g. Negative ≥ 80%). If both negative and positive rules exist, negative evaluates first. Flow language emits a fragmented `Compare` on `$.Lex.SentimentResponse.Scores.Negative`.
- Voice through Lex is streamed to the bot in real time (V2 streaming conversation API under the hood); Connect handles it — no special config beyond the block.
- To get Lex bot turns into Contact Lens transcripts/dashboards: instance → Flows → **Enable Bot Analytics and Transcripts in Amazon Connect**.

---

## 3. Amazon Q in Connect → Connect AI agents

- Formerly **Amazon Connect Wisdom** → **Amazon Q in Connect** → now surfaced as **Connect AI agents** (powered by Amazon Bedrock; GDPR-compliant, HIPAA eligible). API reference: "Amazon Connect AI Agents" operations (historically the `qconnect` service namespace: assistants, knowledge bases, sessions, AI agents, AI prompts, e.g. `UpdateSession`, `UpdateSessionData`).
- Core objects: **assistant** (per-instance container), **knowledge bases** (ingested content, web crawls, S3, integrations; also "quick responses" KB for chat), **AI agents** (typed configurations), **AI prompts** (customizable LLM prompts), **AI guardrails**, **LLM tools**.
- **What it does for human agents (real-time assist):** detects customer intent during calls/chats/tasks/emails via conversational analytics + NLU, then pushes generative answers, document links, and recommended actions into the **agent workspace**; agents can also query it manually in natural language.
- **Default AI agents:** `AgentAssistanceOrchestrator`, `AnswerRecommendation`, `CaseSummarization`, `EmailGenerativeAnswer`, `EmailOverview`, `EmailResponse`, `ManualSearch`, `NoteTaking`, `SalesAgent`, `SelfService`, `SelfServiceOrchestrator`.
- **Default AI prompts** (copy to customize; you can't edit defaults): `AgentAssistanceOrchestration`, `AnswerGeneration`, `CaseSummarization`, `EmailGenerativeAnswer`, `EmailOverview`, `EmailQueryReformulation`, `EmailResponse`, `IntentLabelingGeneration`, `NoteTaking`, `QueryReformulation`, `SalesAgent`, `SelfServiceAnswerGeneration`, `SelfServiceOrchestration`, `SelfServicePreProcessing`.
- **Flow integration:** the **Amazon Q in Connect** flow block attaches the assistant/AI agent to the contact. The AI-agents session ARN is exposed as `$.Wisdom.SessionArn` (pass it to a Lambda to call `UpdateSession`/`UpdateSessionData` etc.).
- Can be integrated with **step-by-step guides** and knowledge bases; configured via UI or API.

### Self-service flavors
1. **Legacy generative self-service** (`SelfService` AI agent + `SelfServicePreProcessing`/`SelfServiceAnswerGeneration` prompts): AI answers questions inside a Lex conversational-AI bot; returns control to the flow whenever a custom tool/intent is selected.
2. **Agentic self-service (current direction)** — see next section.

---

## 4. Agentic AI: orchestrator AI agents + MCP tools

### Agentic self-service
- **Orchestrator AI agents** reason across multiple steps, invoke MCP tools, and keep a continuous voice/chat conversation until resolution or escalation — without bouncing back to the flow between steps.
- Setup outline:
  1. AI agent designer → **AI agents** → Create, type **Orchestration**, copy from system agent **`SelfServiceOrchestrator`**.
  2. Create a **security profile** for the AI agent (AI agents reuse the human-agent security-profile framework to gate tool access).
  3. Add tools (MCP tools, Return to Control, Constant).
  4. Attach an orchestration **AI prompt** (default `SelfServiceOrchestration`). **Gotcha:** responses MUST be wrapped in `<message>` tags or customers see nothing.
  5. Set as default Self Service agent (**Default AI Agent Configurations**).
  6. Routing → Flows → **Conversational AI** → create bot with the Connect AI agents intent; invoke via **Get customer input**; branch on outcome with **Check contact attributes**.
- **Tool types:**
  - **MCP tools** — act mid-conversation (order lookup, refunds, record updates).
  - **Return to Control** — end AI conversation and hand back to the flow. Defaults on `SelfServiceOrchestrator`: `Complete`, `Escalate`. Custom RTC tools take a JSON Schema input (e.g. `escalationReason`, `escalationSummary`, `customerIntent`, `sentiment`).
  - **Constant** — returns a static string (stub/test tool); does not end the conversation.
- **RTC detection in flows:** tool name + inputs land in **Lex session attributes**. Check `Namespace=Lex, Key=Session attributes, Session Attribute Key=Tool` (values `Complete`/`Escalate`/custom); copy inputs (e.g. `$.Lex.SessionAttributes.escalationSummary`) to contact attributes for routing/screenpop; optionally surface to the agent via **Set event flow** → Default flow for agent UI.

### MCP tools (`ai-agent-mcp-tools`)
- Connect supports **Model Context Protocol** for both self-service and employee-assist AI agents.
- Sources of tools:
  - **Out-of-the-box tools** (e.g., update contact attributes, retrieve case information).
  - **Flow module tools** — create/convert flow modules into MCP tools (reuse deterministic flow logic in generative workflows).
  - **Third-party MCP servers** via **Amazon Bedrock AgentCore Gateway** — register gateways in the AWS console like other third-party apps; gain access to remote MCP servers' tools.
- **MCP tool invocation timeout: 30 seconds** (execution terminated beyond that).
- Governance: per-tool extra instructions, input overrides, output filtering; access bounded by security profiles. MCP API operations live in the Connect API reference ("Connect Model Context Protocol").

---

## 5. Contact Lens (conversational analytics + QM)

- Built on Amazon Bedrock. Capabilities: conversational analytics (voice, chat, email), sensitive-data redaction, **performance evaluations** (auto-prepopulated evaluation forms), **agent screen recording**, contact search (2 years), live monitor/barge, transfer/reschedule/end in-progress contacts.
- **Voice:** real-time call analytics (rules → alerts while call in progress) and post-call analytics. **Chat:** real-time + post-chat (bot vs agent response metrics, agent greeting time). **Email:** single-shot analysis on send/receive (no real-time/sentiment), includes categorization, redaction, summaries.
- **Enable via flow block:** now named **"Set recording, analytics and processing behavior"** (previously "Set recording and analytics behavior" — old name persists in many places; it's now an *action* inside the block). Two actions:
  1. **Set message processor** (chat only) — custom Lambda applied to in-flight messages (integration type `MESSAGE_PROCESSOR` via `CreateIntegrationAssociation`).
  2. **Set recording and analytics behavior** — per channel (Voice / Chat / Email / Screen recording):
     - Voice: agent/customer recording, **Contact Lens speech analytics** (real-time and/or post-call), **automated interaction call recording** (record IVR/bot phase), language, redaction, sentiment toggle, **Contact Lens Generative AI capabilities** (post-contact summaries).
     - Chat: enable conversational analytics, language, redaction (+ **in-flight redaction**), sentiment, generative summaries.
     - Email: language, redaction, generative summaries (no sentiment).
- Block branches: Success / Error / **Channel mismatch** (+ "In-flight redaction configuration failed" for chat).
- **Gotchas:** each later block overwrites analytics settings; post-call analytics uses the *last* configuration at call end; transfers create a new contact ID — re-enable analytics after transfer with another block; put recording blocks in whisper flows for reliable capture; use separate blocks for screen recording vs audio recording.
- **Generative post-contact summaries:** appear in `ConversationCharacteristics.ContactSummary.PostContactSummary.Content` in the output file, contact details page, and to agents.
- **Rules engine:** categories (keyword/phrase/sentiment/attribute criteria) can trigger **real-time alerts** (supervisor email/task, highlight on contact), categorize contacts, auto-create tasks/cases, or auto-fill evaluations.

### Output location & schema
- Analyzed transcript JSON lands in the instance's recording S3 bucket under an `Analysis/` prefix (voice: `.../Analysis/Voice/<yyyy/mm/dd>/<contactId>_analysis_*.json`; redacted files in a `Redacted/` sibling; chat under `Analysis/Chat`). Verify per-instance paths in Data storage settings.
- Schema (Version `1.1.0`) — key fields:
  ```json
  {
    "Version": "1.1.0", "AccountId": "...", "Channel": "VOICE",
    "ContentMetadata": { "Output": "Raw | Redacted", "RedactionTypes": ["PII"],
      "RedactionTypesMetadata": { "PII": { "RedactionEntitiesRequested": ["NAME"], "RedactionMaskMode": "PII | ENTITY_TYPE" } } },
    "JobStatus": "COMPLETED",
    "JobDetails": { "SkippedAnalysis": [ { "Feature": "CATEGORIZATION", "ReasonCode": "QUOTA_EXCEEDED | FAILED_SAFETY_GUIDELINES", "SkippedEntities": [] } ] },
    "LanguageCode": "en-US",
    "Participants": [ { "ParticipantId": "CUSTOMER", "ParticipantRole": "CUSTOMER" } ],
    "Categories": { "MatchedCategories": ["Cancellation"],
      "MatchedDetails": { "Cancellation": { "PointsOfInterest": [ { "BeginOffsetMillis": 7370, "EndOffsetMillis": 11190 } ] } } },
    "ConversationCharacteristics": {
      "ContactSummary": { "PostContactSummary": { "Content": "..." } },
      "TotalConversationDurationMillis": 32110,
      "Sentiment": { "OverallSentiment": { "AGENT": 0, "CUSTOMER": 3.1 },
        "SentimentByPeriod": { "QUARTER": { "CUSTOMER": [ { "BeginOffsetMillis": 0, "EndOffsetMillis": 8027, "Score": -2.5 } ] } } },
      "Interruptions": { "TotalCount": 2, "TotalTimeMillis": 7580, "InterruptionsByInterrupter": {} },
      "NonTalkTime": { "TotalTimeMillis": 0, "Instances": [] },
      "TalkSpeed": { "DetailsByParticipant": { "AGENT": { "AverageWordsPerMinute": 239 } } },
      "TalkTime": { "TotalTimeMillis": 28698, "DetailsByParticipant": {} }
    },
    "Transcript": [ {
      "BeginOffsetMillis": 160, "EndOffsetMillis": 4640, "Id": "...",
      "ParticipantId": "CUSTOMER", "Content": "utterance text",
      "Sentiment": "POSITIVE | NEUTRAL | NEGATIVE",
      "LoudnessScore": [66.56, 40.06],
      "Redaction": { "RedactedTimestamps": [ { "BeginOffsetMillis": 3290, "EndOffsetMillis": 3620 } ] },
      "IssuesDetected": [ { "CharacterOffsets": { "BeginOffsetChar": 0, "EndOffsetChar": 55 }, "Text": "..." } ],
      "OutcomesDetected": [], "ActionItemsDetected": []
    } ]
  }
  ```
- Sentiment scores range **-5 … +5** per period; per-turn sentiment is a label. Redacted audio = silence at the offsets (overlay a beep yourself if needed). Redacted transcript shows `[PII]` or `[ENTITY_TYPE]` depending on `RedactionMaskMode`.
- Real-time results also available via the `ListRealtimeContactAnalysisSegments` / contact-lens realtime APIs and rules → EventBridge.

---

## 6. Customer Profiles

- Unifies CRM data (Salesforce, Zendesk, ServiceNow, S3, …) with Connect contact history into one profile shown in the **agent workspace** (cases, contact history, purchase/asset history, custom attributes).
- Concepts: **domain** (per instance), **object types** (mappings from source objects → standard profile), **standard objects** (profile, **Asset**, **Order**, **Case**), custom objects, **identity resolution / profile matching** (rule-based + ML dedupe/merge), **calculated attributes** (aggregations over object data, usable in flows).
- **Flows:** **Customer profiles** flow block (actions: get/search profile, get object like Asset/Order/Case, create/update profile, get calculated attributes). Search inputs: `profileSearchKey` / `profileSearchValue`. Responses persisted as `$.Customer.*`:
  - `$.Customer.ProfileId`, `$.Customer.FirstName`, `$.Customer.AccountNumber`, `$.Customer.PhoneNumber`, address groups (`$.Customer.ShippingCity` …)
  - `$.Customer.Attributes.x`, `$.Customer.ObjectAttributes.y`, `$.Customer.CalculatedAttributes.z`
  - `$.Customer.Asset.*`, `$.Customer.Order.*`, `$.Customer.Case.*`
- **Limit:** Customer Profiles contact attributes capped at **14,000 chars total per flow** (~56 × 255-char values).
- API: `profile` service (`customer-profiles` SDK) — domains, object types, `SearchProfiles`, `CreateProfile`, calculated attribute APIs.

## 7. Voice ID — **deprecated**

- **End of support: 2026-05-20.** After that, Voice ID is inaccessible (console, admin website, CCP, resources). **Do not build new dependencies on it**; plan migration off.
- What it was: real-time caller authentication + fraud detection via voiceprints. **Set Voice ID** flow block started it; enrollment needed **30 s** net speech; authentication default **10 s** (tunable via Authentication response time); fraudster **watchlists** (default watchlist per domain) + **voice spoofing detection** (only with fraud detection enabled); batch enrollment from S3 audio; KMS-encrypted voiceprints; results branched in flows and were surfaced in the CCP. `$.CustomerId` served as the `CustomerSpeakerId`.

## 8. Cases

- Case = customer issue record (status, fields, activity feed, linked contacts/tasks). No external integration required — enable per instance (**domain** created under the hood), then:
  - **Fields** (system + custom: text, number, single-select, date-time, user, etc.) → **Templates** (which fields/layout per case type) → **security profile permissions**.
  - **Case assignment**, rules to auto-monitor/update cases, tag-based access control.
- **Flows:** **Cases** flow block — create case, get/update case, link contact to case (e.g., auto-create a case on inbound contact using collected attributes). Case data in flows: `$.Case.case_id`, `$.Case.reference_number` (8-digit, NOT guaranteed unique), `$.Case.status`, `$.Case.title`, `$.Case.summary`, `$.Case.case_reason`, `$.Case.customer_id` (a Customer Profiles profile ID), `$.Case.created_datetime`, `$.Case.last_updated_datetime`, `$.Case.last_closed_datetime` (set on each close; case may reopen).
- **Case event streams:** publish case create/update events to **EventBridge** for sync with external systems/analytics.
- Agent workspace: search, edit, comment, associate contact, create task from case, CSV export. API: `connectcases` (domains, fields, templates, `CreateCase`, `SearchCases`…). Requires Customer Profiles enabled (cases attach to profiles).

## 9. Outbound campaigns (v2)

- Formerly "high-volume outbound communications". Campaigns support voice (plus SMS/email in the v2 campaigns experience) with **predictive/progressive/agentless** dialing; API: `connect-campaigns` / **`connectcampaignsv2`**.
- Setup: instance must have outbound calling enabled → Connect console → **Channels and communications → Outbound campaigns → Enable** (choose customer-managed **KMS key** or AWS-owned; API user needs `kms:DescribeKey`, `kms:CreateGrant`, `kms:RetireGrant`; to switch keys you must disable and re-enable).
- Prereqs: dedicated campaign **queue** on agents' routing profile; published flow containing a **Check call progress** block (branch on human vs answering machine — AMD).
- Region availability limits which destination countries you can call. **Mass event-driven notifications (thousands of customers) require pre-authorization via an AWS Support ticket.**
- Compliance: respect minimum ring durations (calls ring until voicemail/termination), caller ID must be a number claimed/ported into your instance; time-window and communication-limit controls exist in campaign config.
- Segment/list data surfaces in flows as `$.Attributes.<column>` (e.g., `$.Attributes.FirstName`).

## 10. Quick cross-reference: attribute namespaces used with integrations

| Namespace | Source |
|---|---|
| `$.Attributes.key` | user-defined contact attributes (persisted, in contact record) |
| `$.External.key` / `$.LambdaInvocation.ResultData.key` | latest Lambda response (volatile) |
| `$.Lex.…` | Lex intent/slots/sentiment/session attributes |
| `$.Customer.…` | Customer Profiles block responses |
| `$.Case.…` | Cases block responses |
| `$.Wisdom.SessionArn` | Connect AI agents (Q in Connect) session |
| `$.FlowAttributes.key` | flow-local temp values (never leave the flow, not sent to Lambda unless passed as parameters) |
| `$.StoredCustomerInput` | last Store customer input block |
| `$.Media.InitialMessage` | first chat message |

## Sources

- https://docs.aws.amazon.com/connect/latest/adminguide/connect-lambda-functions.html
- https://docs.aws.amazon.com/connect/latest/adminguide/amazon-lex.html
- https://docs.aws.amazon.com/connect/latest/adminguide/get-customer-input.html
- https://docs.aws.amazon.com/connect/latest/adminguide/connect-attrib-list.html
- https://docs.aws.amazon.com/connect/latest/adminguide/connect-ai-agent.html
- https://docs.aws.amazon.com/connect/latest/adminguide/default-ai-system.html
- https://docs.aws.amazon.com/connect/latest/adminguide/agentic-self-service.html
- https://docs.aws.amazon.com/connect/latest/adminguide/ai-agent-mcp-tools.html
- https://docs.aws.amazon.com/connect/latest/adminguide/contact-lens.html
- https://docs.aws.amazon.com/connect/latest/adminguide/analyze-conversations.html
- https://docs.aws.amazon.com/connect/latest/adminguide/contact-lens-example-output-files.html
- https://docs.aws.amazon.com/connect/latest/adminguide/set-recording-analytics-processing-behavior.html
- https://docs.aws.amazon.com/connect/latest/adminguide/customer-profiles.html
- https://docs.aws.amazon.com/connect/latest/adminguide/cases.html
- https://docs.aws.amazon.com/connect/latest/adminguide/voice-id.html
- https://docs.aws.amazon.com/connect/latest/adminguide/outbound-campaigns.html

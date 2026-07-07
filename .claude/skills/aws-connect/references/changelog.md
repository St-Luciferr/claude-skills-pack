# Amazon Connect — Changelog & Recent Updates

> Baseline research: 2026-07-07
> Covers: 2025-01 → 2026-07

**Naming note:** In April 2026 AWS rebranded the contact center product to **Amazon Connect Customer**, part of a four-product "Amazon Connect" agentic-AI portfolio (Customer, Decisions, Talent, Health). Docs and console now use "Amazon Connect Customer" for what was historically "Amazon Connect". Separately, the capability formerly branded **Amazon Q in Connect** has been folded into the broader **Amazon Connect AI agents** framework (Q in Connect is "one of the AI agents"); the API namespace (`wisdom`/`qconnect`, e.g. `CreateAIAgent`) persists.

---

## 2026 Q3 (Jul)

- **2026-07** — AI-powered virtual agents guidance: AWS published patterns for automating complex multi-step business processes with Connect AI agents (tool use, guardrails, human handoff) — signals the maturity of the agentic self-service stack. https://aws.amazon.com/blogs/contact-center/ai-powered-virtual-agents-automating-complex-business-processes/

## 2026 Q2 (Apr–Jun)

- **2026-06** — Interrupt agent flow block: New flow block routes a contact to a specific agent even when the agent is at max concurrency or in a custom status, across all channels. Enables "break-in" routing for VIP/emergency scenarios.
- **2026-06** — Generative AI evaluation of self-service (AI agent) interactions: Automatically score AI-agent conversations against natural-language evaluation criteria, so QA programs cover bots the same way they cover humans.
- **2026-06** — AI agent trace details for self-service voice: Step-by-step visibility into AI agent reasoning, tool calls, and decisions during voice interactions — key for debugging agentic flows.
- **2026-06** — Real-time dashboard alerts from conversational analytics: Supervisors get live alerts when keywords, phrases, or sentiment patterns are detected mid-contact.
- **2026-06** — Post-contact summaries in 8 more languages: Portuguese, French, Italian, German, Spanish, Chinese, Japanese, Korean.
- **2026-06** — WFM scale + automation: schedules support 5,000 agents per run, automatic schedule-change notifications to agents/supervisors, and optimizer-driven placement of ad-hoc activities (training, meetings). https://aws.amazon.com/blogs/contact-center/optimize-activity-placement-in-amazon-connect-scheduling/
- **2026-06** — Connect AI Agents Guardrails: guidance/capability for responsible-AI guardrails on Connect AI agents (topic denial, grounding, PII handling). https://aws.amazon.com/blogs/contact-center/implementing-responsible-ai-in-contact-centers-with-connect-ai-agents-guardrails/
- **2026-05** — Conversational analytics for email (GA): Contact Lens categorization, summaries, and sensitive-data redaction extended to the email channel.
- **2026-05** — Outbound Campaigns multi-contact time zone detection: Campaigns respect time zones inferred from all phone numbers/addresses on a customer profile, not just the primary field — better compliance with calling-window laws.
- **2026-05** — Default Step-by-Step Guides for After Contact Work: Automatically launch a guide when an agent enters ACW to standardize wrap-up workflows.
- **2026-05** — Cases + Customer Profiles identity resolution: Cases automatically re-associate when duplicate profiles are merged.
- **2026-05** — **Amazon Connect Voice ID end of support (effective 2026-05-20)**: Voice ID is discontinued (EOS was announced 2025-05-20). Remove Voice ID blocks/APIs from new designs.
- **2026-05** — Granular access controls: agents see only their own evaluations; login/logout report restricted to direct reports (tag/hierarchy based); Customer Profiles service-linked role auto-covers all current/future `profile:` APIs.
- **2026-04** — **Rebrand: Amazon Connect → Amazon Connect Customer + new portfolio** (announced 2026-04-28): AWS expanded Connect into four agentic-AI products — **Connect Customer** (the classic CCaaS), **Connect Decisions** (supply-chain planning agents), **Connect Talent** (AI hiring/interviewing), **Connect Health** (healthcare admin/documentation agents). https://www.aboutamazon.com/news/aws/amazon-connect-ai-business-set and https://aws.amazon.com/about-aws/whats-new/2026/04/amazon-connect-decisions-april/
- **2026-04** — Attachments up to 100 MB with custom file types: Raised from 20 MB across chat, cases, tasks; admin-defined allowed extensions.
- **2026-04** — Eight new AI agent performance metrics: Goal success rate, faithfulness score, tool selection accuracy, customer feedback, etc. — observability for bot fleets.
- **2026-04** — Outbound Campaigns: contact priority ordering (dial order driven by up to 10 profile attributes) and hourly segment refresh (down from 24h minimum).
- **2026-04** — Pass customer context into calls: Customer IDs, session references, and campaign codes flow into the contact so AI agents/flows can personalize self-service.
- **2026-04** — Flow modules everywhere: Modules now usable in all flow types (e.g., agent whisper) and nestable inside other modules.
- **2026-04** — Supervisor status changes logged to CloudTrail: Audit trail for agent-status changes made from analytics dashboards.

## 2026 Q1 (Jan–Mar)

- **2026-03** — Cases data in the analytics data lake: Case records queryable via Athena/QuickSight alongside contact analytics.
- **2026-03** — AI-powered manager assistance (Preview): Natural-language querying over 150+ Connect metrics for supervisors.
- **2026-03** — Integrated manager coaching workflows: Coaching plans with linked interaction examples and agent acknowledgement, in-product. https://docs.aws.amazon.com/connect/latest/adminguide/doc-history.html
- **2026-03** — Testing & simulation for chats: Test self-service chat experiences with configurable parameters, batch runs, and diagnostics before deploying.
- **2026-03** — Email: agent-selectable "From" addresses per queue and forwarding to external addresses while retaining ownership.
- **2026-03** — AI-powered predictive insights enhancements (Preview): Up to 40M catalog items, message-template integration, ~14% model accuracy improvement.
- **2026-02** — Per-channel auto-accept and ACW timeouts: Separate settings for chat, tasks, email, and callbacks instead of one global value.
- **2026-02** — Audio Enhancement for agents: Noise suppression / voice isolation on the agent's side of the call.
- **2026-02** — Cases quality-of-life batch: AWS Service Quotas support, 4,100-char multi-line fields, CSV upload for dependent (cascading) field options.
- **2026-01** — Wait Time Estimates: Improved estimated-wait-time metrics for queues and enqueued contacts (for EWT announcements and load balancing).
- **2026-01** — Task file attachments via `StartTaskContact`: Up to 5 files per task through the API.
- **2026-01** — Flows: nested JSON objects and looping arrays: Store complex data structures in flow attributes and iterate lists natively — significant for flow developers.
- **2026-01** — Recurring hours-of-operation overrides + visual calendar: Manage recurring holiday/maintenance windows without one-off overrides.
- **2026-01** — Cases: CloudFormation support and tag-based access control on case templates.
- **2026-01** — Screen recording status tracking: Near-real-time recording status to CloudWatch via EventBridge.

## 2025 Q4 (Oct–Dec) — re:Invent 2025 wave

- **2025-12** — re:Invent 2025 recap: autonomous first-party AI agents across voice/chat/email/SMS/social, working alongside human agents; the marquee positioning shift toward agentic CX. https://aws.amazon.com/blogs/contact-center/amazon-connect-at-reinvent-2025-creating-the-future-of-customer-experience-with-ai/
- **2025-12** — Workspaces & data tables for business users: No-code data tables and persona-based admin workspaces so business users control routing/config data without engineering.
- **2025-12** — Dashboards filter by custom business dimensions (divisions, product lines).
- **2025-12** — WhatsApp channel for Outbound Campaigns: Proactive WhatsApp campaigns with templated messages.
- **2025-12** — Customer Profiles new segmentation capabilities (Beta). https://aws.amazon.com/about-aws/whats-new/2025/12/amazon-connect-customer-profiles/
- **2025-12** — Automated evaluations in 5 more languages + new evaluation question types (multiple choice, date).
- **2025-11** — **Agentic self-service with Amazon Nova Sonic**: Natural, expressive speech-to-speech voice AI agents (30+ languages), LLM-powered — the core of Connect's voice-bot modernization.
- **2025-11** — **Model Context Protocol (MCP) support for AI agents**: Standardized tool integration so Connect AI agents can call your systems of record without custom Lambda glue.
- **2025-11** — Multiple knowledge bases + Amazon Bedrock Knowledge Bases integration for AI agents; streaming AI responses (progressive rendering).
- **2025-11** — Third-party speech providers: Deepgram STT and ElevenLabs TTS usable with Connect voice AI.
- **2025-11** — Amazon Lex: LLMs as primary NLU option, plus wait-and-continue in 10 more languages.
- **2025-11** — Agentic agent-assistance: AI agents guide human reps in real time and complete tasks (notes, documentation); AI-powered case summaries.
- **2025-11** — AI agent observability: customizable dashboards, alert rules, conversational analytics for voice/chat bots, and automated performance evaluations of self-service interactions.
- **2025-11** — Native testing & simulation: Batch-test flows/AI workflows with configurable parameters before production.
- **2025-11** — **Multi-step, multi-channel journey builder for Outbound Campaigns**: Orchestrate voice + SMS + email + WhatsApp journeys end-to-end (the Pinpoint-journeys successor).
- **2025-11** — Email channel maturation: follow-up replies on email contacts, email address aliases, automated keyword-based email responses/routing.
- **2025-11** — Chat: agent-initiated interactive workflows (send forms in chat), in-flight message redaction/processing.
- **2025-11** — Persistent agent connections GA: Keep the agent's media channel open between calls for faster connect times (was preview since Jan 2025).
- **2025-11** — Custom visual themes for agent workspace (branding: colors, logos).
- **2025-11** — AI agent assistance for Salesforce Contact Center with Amazon Connect (SCC-AC).
- **2025-11** — Custom metrics: supervisors define custom performance measurements without code; callback-queue monitoring; multi-skill agent scheduling; outbound campaign ring-time configuration (15–60s).
- **2025-10** — Preview dialing mode for Outbound Campaigns: Agents review customer info before the system places the call.
- **2025-10** — Generative AI email assistance: conversation overviews, suggested actions, and suggested responses for the email channel.
- **2025-10** — Get customer input flow blocks on outbound calls: Collect DTMF or Lex-bot input before connecting the agent.
- **2025-10** — Granular permissions for recordings vs. transcripts, with redacted/unredacted access options.
- **2025-10** — `SearchAllRelatedItems` API for Cases: Cross-case related-item search in a domain.
- **2025-10** — Email threaded views and full conversation history in replies.
- **2025-10** — WFM batch: adherence thresholds and notifications, individual-agent rescheduling, copy/bulk-edit of scheduling config, agent time-off balances in the data lake; screen recording on ChromeOS.

## 2025 Q3 (Jul–Sep)

- **2025-09** — Flow designer analytics mode: Visualize contact traffic through each flow branch/step to optimize flows with data.
- **2025-09** — Contact segment attributes: Manage data that varies per transfer segment (predefined value lists) — cleaner than overloading contact attributes.
- **2025-09** — New APIs: `AssociateContactWithUser` and `ListRoutingProfileManualAssignmentQueues` — plus manual work-item assignment so agents can self-assign tasks/emails/chats from a queue.
- **2025-09** — Nine new callback metrics and customizable service-level calculations (include/exclude abandons, callbacks, transfers).
- **2025-09** — Enhanced disconnect reasons: Detailed telecom-level reasons for failed outbound calls (troubleshooting/campaign analytics).
- **2025-09** — Contact Lens sensitive-data redaction in 7 additional languages; dashboards compare arbitrary time ranges.
- **2025-08** — Outbound Campaigns multi-profile campaigns + phone-number retry sequencing: Account-based campaigns reaching multiple people per account; prioritized dial order across a customer's numbers (mobile → home → work). https://aws.amazon.com/about-aws/whats-new/2025/08/amazon-connect-outbound-campaigns-multi-profile-campaigns/
- **2025-08** — Embed Tasks and Emails in websites: Communication widget adds out-of-the-box contact forms (webform → email/task/callback request). https://aws.amazon.com/about-aws/whats-new/2025/08/amazon-connect-embeds-tasks-emails-websites-applications/
- **2025-08** — Recurring activities in agent schedules (e.g., daily stand-ups). https://aws.amazon.com/about-aws/whats-new/2025/08/amazon-connect-recurring-activities-agent-schedule/
- **2025-07** — **Parallel AWS Lambda execution in flows**: Invoke multiple Lambdas concurrently from a flow — big latency win for data-dip-heavy IVRs.
- **2025-07** — Analytics dashboard in agent workspace: Agents see their own performance metrics and queue status out of the box.
- **2025-07** — Flow designer editing/accessibility overhaul: keyboard navigation, screen-reader support, improved drag-and-drop.
- **2025-07** — Forecast editing UI in WFM: Edit forecasts across date ranges/queues/channels with preview before applying.
- **2025-07** — New `CUSTOMER_NEVER_ARRIVED` DisconnectReason on contact records; third-party apps enhancements in agent workspace.

## 2025 Q2 (Apr–Jun)

- **2025-06** — Enhanced audio treatment in queue: Run flow logic while queue audio keeps playing (no more audio gaps during data dips).
- **2025-06** — Ingest third-party agent activities as Connect tasks for unified performance evaluation.
- **2025-06** — Customer Profiles: create segments from imported CSV files; email domains quota raised 5 → 100 per instance.
- **2025-06** — Instance replication between Tokyo and Osaka (Amazon Connect Global Resiliency expansion in Japan).
- **2025-06** — Multiparty call hold tracking (`Agent Initiated Hold Duration`); new chat metrics and Contacts-record fields in the data lake; improved no-code Views builder for Step-by-Step Guides; customizable work labels in scheduling.
- **2025-05** — **Voice ID end-of-support announced** (2025-05-20): support ends 2026-05-20. Plan replacements (e.g., partner voice-biometric integrations).
- **2025-05** — **Amazon Pinpoint end-of-support announced**: No new Pinpoint customers after 2025-05-20; engagement features retire 2026-10-30. AWS migration path: Amazon Connect Outbound Campaigns (journeys) + AWS End User Messaging for transactional sends. https://docs.aws.amazon.com/pinpoint/latest/userguide/migrate.html
- **2025-05** — `DescribeContact` API enriched: disconnect reasons, recording status, ACW time, custom contact attributes in one call.
- **2025-05** — WhatsApp Business messaging and SMS in additional regions; Contact Lens real-time dashboards in AWS GovCloud (US); audio optimization for Omnissa VDI; agent hierarchy groups table in data lake.
- **2025-04** — Cases SLA tracking: Configure and track service-level agreements on cases and case fields.
- **2025-04** — Outbound Campaigns reporting: five new metrics plus dashboard drill-downs.
- **2025-04** — Hierarchy-based granular access control for dashboards/reports; real-time adherence widget on the queue & agent performance dashboard; bulk removal of agent schedules.

## 2025 Q1 (Jan–Mar)

- **2025-03** — **Next-generation Amazon Connect GA** (2025-03-18): One-click enablement of the full AI feature set (self-service, agent assistance, analytics/QA, evaluations, follow-ups) with **unlimited-use bundled AI pricing** instead of per-use metering; launched in 9 regions. This is the pricing-model watershed for Connect AI. https://aws.amazon.com/about-aws/whats-new/2025/03/next-generation-amazon-connect-ai-improves-customer-interaction/
- **2025-03** — Contact Lens conversational analytics in 34 new languages; option to disable sentiment analysis independently.
- **2025-03** — Flows: customizable DTMF inter-digit wait time (1–20s); unlimited routing-criteria updates per queued contact.
- **2025-03** — Outbound campaigns for event-driven mass notifications (weather warnings, disaster response).
- **2025-03** — Dynamic evaluation forms: show/hide questions based on prior answers; track agent acknowledgements of evaluations.
- **2025-02** — Agent shift trades: Agents exchange shifts directly with each other, with policy guardrails.
- **2025-02** — Agent performance evaluations dashboard + new evaluation metrics (cohort views over time).
- **2025-02** — Routing: target multiple agent-proficiency combinations in a single routing step (up to 3 OR conditions).
- **2025-02** — Cases: conditionally required fields; configurable states counted as "adherent" in WFM.
- **2025-01** — Connect AI agents permissions added to the service-linked role — first doc-visible step of the Q-in-Connect → AI agents framework evolution.
- **2025-01** — Persistent agent connections (public preview): Open media channel held between calls to cut connect latency.
- **2025-01** — Real-time agent activity dashboard: Live monitor with listen-in, barge, and agent state change actions; configurable dashboard widgets/filters.
- **2025-01** — Email channel: agent performance evaluations extended to email contacts (email channel itself went GA in Dec 2024).
- **2025-01** — Agent workspace audio optimization for Citrix and Amazon WorkSpaces VDI; screen recording in AWS GovCloud (US-West).

---

## Watching for updates

Canonical URLs to monitor:

- **AWS What's New (Connect filter):** https://aws.amazon.com/about-aws/whats-new/?whats-new-content-all.q=Amazon%20Connect (JS-rendered; use the RSS feed for automation)
- **AWS What's New RSS:** https://aws.amazon.com/about-aws/whats-new/recent/feed/ (filter items whose title contains "Connect")
- **Admin guide release notes:** https://docs.aws.amazon.com/connect/latest/adminguide/amazon-connect-release-notes.html
- **Admin guide doc history:** https://docs.aws.amazon.com/connect/latest/adminguide/doc-history.html
- **API reference doc history:** https://docs.aws.amazon.com/connect/latest/APIReference/ (watch for new actions/namespaces)
- **AWS Contact Center blog:** https://aws.amazon.com/blogs/contact-center/ (announcements category: https://aws.amazon.com/blogs/contact-center/category/post-types/announcements/)
- **GitHub releases:** https://github.com/amazon-connect/amazon-connect-streams/releases (CCP/streams API), https://github.com/amazon-connect/amazon-connect-chatjs/releases, https://github.com/amazon-connect/amazon-connect-chat-interface
- **Pricing page (watch for model changes):** https://aws.amazon.com/products/connect/customer/pricing/ (note the post-rebrand URL under /products/connect/customer/)
- **Deprecation trackers:** Voice ID EOS (done 2026-05-20); Amazon Pinpoint EOS 2026-10-30 → https://docs.aws.amazon.com/pinpoint/latest/userguide/migrate.html

## Sources

Pages read during this research (2026-07-07):

- https://docs.aws.amazon.com/connect/latest/adminguide/amazon-connect-release-notes.html
- https://docs.aws.amazon.com/connect/latest/adminguide/doc-history.html
- https://aws.amazon.com/about-aws/whats-new/?whats-new-content-all.q=Amazon%20Connect
- https://aws.amazon.com/blogs/contact-center/
- https://aws.amazon.com/blogs/contact-center/amazon-connect-at-reinvent-2025-creating-the-future-of-customer-experience-with-ai/
- https://www.aboutamazon.com/news/aws/amazon-connect-ai-business-set
- https://aws.amazon.com/about-aws/whats-new/2025/03/next-generation-amazon-connect-ai-improves-customer-interaction/
- https://aws.amazon.com/about-aws/whats-new/2025/08/amazon-connect-outbound-campaigns-multi-profile-campaigns/
- https://aws.amazon.com/about-aws/whats-new/2025/08/amazon-connect-embeds-tasks-emails-websites-applications/
- https://aws.amazon.com/about-aws/whats-new/2025/08/amazon-connect-recurring-activities-agent-schedule/
- https://github.com/amazon-connect/amazon-connect-streams/releases
- https://docs.aws.amazon.com/pinpoint/latest/userguide/migrate.html (via search)
- https://www.cxtoday.com/contact-center/amazon-connect-customer-rebrand/ (via search)
- https://aws.amazon.com/connect/ai-agents/ (via search)

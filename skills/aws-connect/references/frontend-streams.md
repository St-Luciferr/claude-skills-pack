# Amazon Connect — Frontend: CCP, Streams, ChatJS, Agent Workspace
> Last updated: 2026-07 (baseline)

Note: as of 2026 the AWS docs brand the contact-center service "Connect Customer" (Amazon Connect). API namespaces, endpoints, npm packages, and ARNs are unchanged (`connect`, `amazon-connect-*`, `@amazon-connect/*`). This file uses "Amazon Connect".

## Library map

| Library / SDK | npm | Purpose |
|---|---|---|
| Streams | `amazon-connect-streams` | Embed CCP in an iframe; agent/contact event model for custom agent desktops |
| ChatJS | `amazon-connect-chatjs` | Custom chat UIs (customer side via Participant Service; agent side via Streams media controller) |
| TaskJS | `amazon-connect-taskjs` | Task contacts in custom CCPs (task events, create/update tasks, task templates). v2 requires Streams v2.2+ |
| Connect SDK (Agent Workspace) | `@amazon-connect/app`, `@amazon-connect/contact`, `@amazon-connect/user`, `@amazon-connect/voice`, `@amazon-connect/theme`, `@amazon-connect/email`, `@amazon-connect/file`, `@amazon-connect/quick-responses`, `@amazon-connect/message-template`, `@amazon-connect/site-streams`, `@amazon-connect/ai-agents` | 3P apps iframed into the out-of-the-box Agent Workspace (github.com/amazon-connect/AmazonConnectSDK). There is no `@amazon-connect/app-sdk` package — the app module is `@amazon-connect/app` |
| Chime SDK | `amazon-chime-sdk-js` | Media plane for WebRTC video calls / screen share (customer side and agent video) |
| connect-rtc-js | `amazon-connect-rtc` (GitHub amazon-connect/connect-rtc-js) | Optional custom softphone RTC session handling |

Import order matters: import Streams first, then ChatJS/TaskJS, then any external AWS SDK (Streams and ChatJS bundle their own AWS SDK clients; import yours after so it takes precedence).

## Hosted CCP / agent-facing URLs

- CCP: `https://<instance-alias>.my.connect.aws/ccp-v2/` (legacy: `https://<alias>.awsapps.com/connect/ccp-v2/`)
- Agent Workspace: `https://<instance-alias>.my.connect.aws/agent-app-v2/`
- Admin website: `https://<instance-alias>.my.connect.aws/`
- Chat-only CCP variant used as `ccpUrl` for chat-capable embeds: `.../ccp-v2/chat`
- Softphone requires Chrome, Edge, or Firefox; minimum recommended embed size 320px × 460px.

## Embedding a custom CCP with amazon-connect-streams

### Allowlist your domain first
Connect blocks framing from unknown origins. Connect console → your instance → **Application integration** → **Add Origin** → `https://your-domain.example`. All pages that call `initCCP` must be served over HTTPS from an allowlisted origin. (Same mechanism = "approved origins"; also required for SAML `destination` redirects to custom sites.)

### initCCP — full options

```js
import "amazon-connect-streams"; // or <script src="connect-streams-min.js">

connect.core.initCCP(document.getElementById("ccp-container"), {
  ccpUrl: "https://my-instance.my.connect.aws/ccp-v2/", // REQUIRED
  region: "us-west-2",              // REQUIRED for chat/task; must match instance region
  loginPopup: true,                 // default true; open login popup if not authenticated
  loginPopupAutoClose: true,        // default false; close popup after login
  loginUrl: "https://idp.example/init-sso",  // SAML: your IdP-initiated login URL
  loginOptions: {                   // only if loginPopup: true
    autoClose: true,                // default false
    height: 578, width: 433,        // defaults
    top: 0, left: 0,
    disableAuthPopupAfterLogout: false // pair with connect.core.reauthenticateAfterLogout()
  },
  softphone: {
    allowFramedSoftphone: true,     // default false — REQUIRED to run audio inside the iframe
    disableRingtone: false,
    ringtoneUrl: "./ringtone.mp3",
    disableEchoCancellation: false,
    allowFramedVideoCall: true,     // default false — render video in this iframe
    allowFramedScreenSharing: true, // default false
    allowFramedScreenSharingPopUp: false,
    allowEarlyGum: true,            // default true — pre-acquire mic on init for faster connect
    VDIPlatform: "CITRIX"           // CITRIX | CITRIX_413 | AWS_WORKSPACE | OMNISSA
  },
  task:           { disableRingtone: false, ringtoneUrl: "./task.mp3" },
  autoAcceptTone: { disableRingtone: false, ringtoneUrl: "./tone.mp3" },
  pageOptions: {
    enableAudioDeviceSettings: false,
    enableVideoDeviceSettings: false,
    enablePhoneTypeSettings: true,
    showInactivityModal: true
  },
  shouldAddNamespaceToLogs: false,
  ccpAckTimeout: 3000,   // ms; also delays auth popup
  ccpSynTimeout: 1000,
  ccpLoadTimeout: 5000,
  logConfig: { logLevel: connect.LogLevel.INFO, echoLevel: connect.LogLevel.WARN },
  plugins: []            // optional Function | Function[]
});

connect.core.onInitialized(() => console.log("CCP ready"));
```

Notes:
- The container gets an iframe at 100%×100%; parent CSS does not style CCP internals. Hide/show with `display:none` on the container — do not destroy the iframe to "hide" it.
- Only one embedded CCP per browser context; multiple simultaneous browsers on the same agent session is unsupported.
- Teardown: `connect.core.terminate()` then manually remove `containerDiv.firstElementChild` (the iframe).
- Auth hooks: `connect.core.onAuthFail(cb)`, `onAccessDenied(cb)`, `onAuthorizeSuccess(cb)`, `onAuthorizeRetriesExhausted(cb)`, `onCTIAuthorizeRetriesExhausted(cb)` (repeated 401s), `onIframeRetriesExhausted(cb)` (6 iframe reload retries).

## Streams API essentials

### Agent

```js
connect.agent(agent => {
  agent.onStateChange(({ agent, oldState, newState }) => { /* ... */ });
  agent.onRefresh(a => {});          // any agent data change
  agent.onRoutable(a => {}); agent.onNotRoutable(a => {}); agent.onOffline(a => {});
  agent.onError(a => {}); agent.onAfterCallWork(a => {});   // ACW (voice)
  agent.onWebSocketConnectionLost(a => {}); agent.onWebSocketConnectionGained(a => {});

  const cfg = agent.getConfiguration(); // {agentStates, extension, name, permissions, routingProfile, softphoneEnabled, username, agentARN, ...}
  const routable = agent.getAgentStates().find(s => s.name === "Available");
  agent.setState(routable, { success(){}, failure(err){} }, { enqueueNextState: true }); // queue state change if on contact

  // Outbound call
  agent.connect(connect.Endpoint.byPhoneNumber("+18005550100"),
    { queueARN: optionalOutboundQueueArn, success(){}, failure(err){} });

  // Quick connects / transfer targets
  agent.getEndpoints(agent.getAllQueueARNs(), {
    success: ({ endpoints }) => { /* connect.Endpoint objects (agents, queues, phone numbers) */ },
    failure: err => {}
  });

  agent.mute(); agent.unmute();
  agent.setMicrophoneDevice(deviceId); agent.setSpeakerDevice(deviceId); agent.setRingerDevice(deviceId);
});
```

Routability: only voice contacts change agent status; chat/task contacts don't (but channel concurrency limits still gate routing — `agent.getChannelConcurrency()` → `{VOICE:1, CHAT:2, ...}`).

### Contact

```js
connect.contact(contact => {
  contact.onConnecting(c => {});   // ringing / inbound offered
  contact.onIncoming(c => {});     // queued callbacks
  contact.onAccepted(c => {});     // not fired for deskphone agents
  contact.onConnected(c => {});
  contact.onMissed(c => {}); contact.onEnded(c => {}); contact.onACW(c => {});
  contact.onDestroy(c => {}); contact.onRefresh(c => {});

  contact.accept({ success(){}, failure(err){} });
  contact.getContactId(); contact.getType();       // voice | chat | task | email...
  contact.getQueue();                              // {name, queueARN, queueId}
  contact.getAttributes();                         // {key: {name, value}, ...}
  contact.isInbound(); contact.isSoftphoneCall();

  // Transfers / conference (voice): add third party, then manage connections
  const ep = connect.Endpoint.byPhoneNumber("+18005550100"); // or a quick-connect endpoint from agent.getEndpoints()
  contact.addConnection(ep, { success(){}, failure(err){} });
  contact.toggleActiveConnections({});   // swap between held/active parties
  contact.conferenceConnections({});     // join all parties
  contact.getInitialConnection().hold({}); // hold/resume live on connections
  contact.getAgentConnection().destroy({}); // agent leaves (cold transfer)
  contact.clear({});                     // clear ended/missed/error contact out of ACW (replaces deprecated complete())
});
```

- Connection objects: `contact.getConnections()`, `getInitialConnection()`, `getAgentConnection()`, `getThirdPartyConnections()`. Methods: `hold/resume/destroy/sendDigits`, `isOnHold()`, `isActive()`, `getEndpoint()`.
- Voice connection extras: `muteParticipant()/unmuteParticipant()` (multiparty), `isSilentMonitor()/isBarge()`, `getVideoConnectionInfo()` → `{attendee, meeting}` for Chime SDK. Supervisor: `contact.silentMonitor({})`, `contact.bargeIn({})`, `contact.updateMonitorParticipantState(state, {})`.
- Chat connection: `chatConnection.getMediaController().then(chatSession => ...)` returns a ChatJS session (this is how agent-side custom chat UIs work).
- Softphone internals: `connect.core.getSoftphoneManager()`, `connect.core.onSoftphoneSessionInit(({connectionId}) => ...)` for WebRTC stats; `agent.onLocalMediaStreamCreated(({connectionId}) => ...)` to set devices/mute before CONNECTED.
- UI sync with embedded CCP: `connect.core.viewContact(contactId)` and `connect.core.onViewContact(({contactId}) => ...)`.

## ChatJS — custom chat UIs

Flow (customer side): backend calls `connect:StartChatContact` (SigV4 — never from the browser; expose via your own API/Lambda) → returns `{ContactId, ParticipantId, ParticipantToken}` → browser creates a ChatJS session with those → ChatJS calls Participant Service `CreateParticipantConnection` (header `X-Amz-Bearer: <ParticipantToken>`, **no SigV4**) with `Type: ["WEBSOCKET","CONNECTION_CREDENTIALS"]` → gets websocket URL (connect within 100s; must subscribe by publishing `{"topic":"aws/subscribe","content":{"topics":["aws/chat"]}}`) + connection token (valid 1 day). Client must connect within 5 minutes of StartChatContact. ChatJS manages all of this internally.

StartChatContact key fields: `InstanceId`, `ContactFlowId` (required), `ParticipantDetails.DisplayName` (required), `Attributes`, `InitialMessage`, `ChatDurationInMinutes` (60–10080, default 1500), `SupportedMessagingContentTypes` (must include `text/plain`; may add `text/markdown`, `application/json`, `application/vnd.amazonaws.connect.message.interactive[.response]` — interactive types required for Show view guides in chat), `PersistentChat: {RehydrationType, SourceContactId}`, `RelatedContactId` (mutually exclusive with PersistentChat), `SegmentAttributes` (e.g. `{"connect:Subtype":{"ValueString":"connect:Guide"}}`), `CustomerId`, `DisconnectOnCustomerExit: ["AGENT"]`.

```js
import "amazon-connect-chatjs";

connect.ChatSession.setGlobalConfig({
  region: "us-west-2",
  loggerConfig: { level: connect.ChatSession.LogLevel.INFO },
  features: { messageReceipts: { shouldSendMessageReceipts: true, throttleTime: 5000 } }
});

// CUSTOMER session (from your backend's StartChatContact response)
const session = connect.ChatSession.create({
  chatDetails: { contactId, participantId, participantToken },
  type: "CUSTOMER",
  options: { region: "us-west-2" }
});
await session.connect();

// AGENT session (inside a Streams-embedded CCP)
// const agentSession = await chatConnection.getMediaController();

session.onMessage(({ data }) => {
  const { ContentType, Content, ParticipantRole, Id } = data; // MESSAGE / EVENT items
});
session.onTyping(evt => {});
session.onConnectionEstablished(evt => { /* re-fetch transcript here after reconnects */ });
session.onConnectionLost(evt => {});    // may auto-reconnect
session.onConnectionBroken(evt => {});  // terminal
session.onEnded(evt => {});
session.onReadReceipt(evt => {}); session.onDeliveredReceipt(evt => {});

await session.sendMessage({ contentType: "text/plain", message: "Hello!" }); // or text/markdown
await session.sendEvent({ contentType: "application/vnd.amazonaws.connect.event.typing" });
await session.sendMessageReceipt({ event: "read", messageId }); // or "delivered" (usually automatic)

const { data: { Transcript, NextToken } } = await session.getTranscript({
  sortOrder: "ASCENDING", maxResults: 100, scanDirection: "BACKWARD"
});

// Attachments (enable attachments on the instance first): max 20MB;
// .csv .doc .docx .jpeg .jpg .pdf .png .ppt .pptx .txt .wav .xls .xlsx
await session.sendAttachment({ attachment: fileFromInput });
const blob = await session.downloadAttachment({ attachmentId });

await session.disconnectParticipant(); // customer only; agents end via Streams contact/connection.destroy()
```

Event content types: `...event.typing`, `...event.message.delivered`, `...event.message.read`, `...event.connection.acknowledged`, `...event.participant.invited` (prefix `application/vnd.amazonaws.connect.`).

Open-source reference UIs: `amazon-connect-chat-interface` and `amazon-connect-chat-ui-examples` (GitHub amazon-connect org) — include a CloudFormation-deployable StartChatContact proxy Lambda.

## Hosted communications widget (chat / voice / video, no custom UI)

Admin website → **Customize communications widget** → configure channels (chat, voice, video, screen share; task/email pre-contact forms only if chat+voice disabled), styles (colors, logo 280×60 from S3, typeface, display names), optional pre-chat form (built from a **View** with a `StartChatContact` action button) → **domains**: up to 50 allowed website domains, exact protocol match, subdomains auto-included, all paths allowed → embed the generated snippet:

```html
<script type="text/javascript">
 (function(w, d, x, id){ /* generated loader — do not hand-edit */ })(window, document, 'amazon_connect', 'WIDGET_ID');
 amazon_connect('styles', { openChat: {...}, closeChat: {...} });
 amazon_connect('snippetId', 'SNIPPET_ID');
 amazon_connect('supportedMessagingContentTypes', ['text/plain', 'text/markdown']);
 amazon_connect('customerDisplayName', function(callback) { callback('Jane Doe'); });
 // Unsecured attribute passing — keys get prefixed "HostedWidget-", client-mutable:
 amazon_connect('contactAttributes', { plan: 'premium' }); // flows read $.Attributes.HostedWidget-plan
</script>
```

### JWT security (recommended; required for trusted contact attributes)
Enable "Add security" → Connect issues a 44-char secret (rotatable; old key stays valid until deleted). Widget then requires a JWT per chat start via the `authenticate` callback:

```js
amazon_connect('authenticate', function(callback) {
  fetch('/token').then(r => r.json()).then(data => callback(data.data)); // data.data = signed JWT
});
```

JWT spec: **HS256**, claims: `sub` = widgetId (required), `iat`, `exp` (max 10 min), optional `attributes` (string→string map, becomes contact attributes — trusted, no prefix), `segmentAttributes`, `relatedContactId`, `customerId`. Encoded token limit ~6144 bytes (~3000 JS chars). Server-side (Python):

```python
import jwt, datetime
payload = {
  'sub': WIDGET_ID,
  'iat': datetime.datetime.utcnow(),
  'exp': datetime.datetime.utcnow() + datetime.timedelta(seconds=500),
  'attributes': {'name': 'Jane', 'memberID': '123456789'},
  'segmentAttributes': {'connect:Subtype': {'ValueString': 'connect:Guide'}},
}
token = jwt.encode(payload, CONNECT_WIDGET_SECRET, algorithm='HS256', headers={'typ': 'JWT', 'alg': 'HS256'})
```

Attributes are signed (tamper-proof) but only base64-encoded, not encrypted — don't put secrets in them. Widget browsers: Chrome 85+, Safari 13.1+, Edge 85+, Firefox 81+; supports desktop browser notifications, transcript download, programmatic disconnect, custom launch button (target the default button/frame with CSS/JS hooks documented under "Customize widget launch behavior").

## TaskJS

Load after Streams (TaskJS v2 needs Streams ≥2.2). Task contacts arrive through the normal `connect.contact()` flow (`contact.getType() === "task"`); task metadata via `contact.getName()`, `getDescription()`, `getReferences()` (`URL|EMAIL|NUMBER|STRING|DATE`), `getChannelContext()` → `{scheduledTime, taskTemplateId, taskTemplateVersion}`; `contact.pause()/resume()`.

```js
taskConnection.getMediaController().then(taskSession => {
  taskSession.onTransferInitiated(e => {}); taskSession.onTransferSucceeded(e => {});
  taskSession.onTransferFailed(e => {});
  taskSession.onTaskExpiring(e => {});  // 2h before expiry
  taskSession.onTaskExpired(e => {});
  taskSession.onMessage(e => {});       // any of the above
});
// Agent-created tasks:
agent.createTask({ name, description, endpoint, taskTemplateId, references, scheduledTime, ... }, callbacks);
agent.listTaskTemplates({ status: "ACTIVE" }, callbacks);
agent.getTaskTemplate(templateId, callbacks);
agent.updateContact(contactId, { name, description, references }, callbacks);
```

## Agent Workspace third-party apps (Connect SDK)

3P apps are HTTPS websites iframed into the **default agent workspace only** (not supported in custom CCPs). App ↔ workspace communication is via the Amazon Connect SDK (github.com/amazon-connect/AmazonConnectSDK).

```bash
npm install --save @amazon-connect/app @amazon-connect/contact
```

```ts
import { AmazonConnectApp } from "@amazon-connect/app";
import { ContactClient } from "@amazon-connect/contact";
import { AgentClient } from "@amazon-connect/user";

const { provider } = AmazonConnectApp.init({
  onCreate: (event) => {
    const { appInstanceId } = event.context;
    console.log("App initialized:", appInstanceId);
  },
  onDestroy: (event) => { console.log("App being destroyed"); },
});

// Clients use the provider; requests are permission-gated per app registration
const contactClient = new ContactClient({ provider });
contactClient.onConnected(async (contactId) => {
  const attrs = await contactClient.getAttributes(contactId); // needs Contact.Attributes permission
});
const agentClient = new AgentClient({ provider });
const state = await agentClient.getState();
```

Model: **events** (subscribe callbacks — agent state changed, contact connected/destroyed, etc.) and **requests** (on-demand data fetch about current contact / logged-in agent). Each event/request needs a permission granted at registration time. Running the app outside the workspace logs "App failed to connect to agent workspace in the allotted time" — expected.

Registration (admin): Connect console → **Integrations** (region-gated feature) → **Add integration**: display name, integration type (standard web app | service | MCP server), unique integration identifier (recommend the access-URL origin), initialization timeout (ms), **Contact Scope** (app iframe refreshes per contact vs per browser session), **Access URL** (HTTPS, must be iframable — the app's CSP should be `frame-ancestors https://<instance>.my.connect.aws`), optional extra approved origins, permission grants (events/requests), iframe permission config (e.g. clipboard/mic grants to the iframe), and instance association (required before use). IAM needed: `app-integrations:CreateApplication/GetApplication/CreateApplicationAssociation/DeleteApplicationAssociation` + `iam:Get/Put/DeleteRolePolicy` on the Connect service-linked role; instance must use an SLR. Finally, grant agents access to the app in their **security profile** (Agent applications) — the app then appears in the workspace app launcher. SSO federation into the iframed app is supported (3P apps SSO setup docs).

## Step-by-step guides & Views

- Views = UI templates rendered in the agent workspace (display attributes, disposition forms, wizards, guide pages). AWS-managed views (Detail, List, Form, Confirmation, Cards, Wizard) plus customer-managed views via API/CFN.
- Flows drive guides with the **Show view** flow block; use its **Set JSON** option to map data (any flow namespace incl. `$.External`) into the view's InputSchema. View content = **Template** (component tree) + **InputSchema** + **Actions** (strings emitted back to the flow to branch on).
- Guides in chat require `application/vnd.amazonaws.connect.message.interactive` in `SupportedMessagingContentTypes` and segment attribute `connect:Subtype = connect:Guide`.

```yaml
# CloudFormation
MyView:
  Type: AWS::Connect::View
  Properties:
    InstanceArn: arn:aws:connect:us-west-2:111122223333:instance/abc...
    Name: DispositionForm
    Description: Wrap-up form
    Actions: [Submit, Cancel]          # 1+ action strings
    Template: { ... }                   # view component JSON (Head/Body components + InputSchema wiring)
# GetAtt: ViewArn, ViewId, ViewContentSha256
```

Related APIs: `CreateView`, `CreateViewVersion`, `UpdateViewContent`; view ARN format `...instance/<id>/view/<viewId>`.

## WebRTC voice/video calling & screen sharing (customer side)

Two options: (1) the hosted communications widget (configure voice+video+screen share on the same widget page), or (2) native integration:

1. Backend calls `connect:StartWebRTCContact` (SigV4):
   - Request: `InstanceId`, `ContactFlowId` (required), `ParticipantDetails.DisplayName` (required), `AllowedCapabilities: {Customer: {Video: "SEND", ScreenShare: "SEND"}, Agent: {Video: "SEND", ScreenShare: "SEND"}}`, `Attributes`, `References`, `RelatedContactId`, `Description`, `ClientToken` (idempotent 7 days).
   - Response: `ContactId`, `ParticipantId`, `ParticipantToken`, and `ConnectionData: { Attendee: {AttendeeId, JoinToken}, Meeting: {MeetingId, MediaRegion, MediaPlacement: {AudioHostUrl, SignalingUrl, TurnControlUrl, ...}} }`.
2. Client joins the meeting with `amazon-chime-sdk-js` using the returned Meeting/Attendee objects (MeetingSessionConfiguration → AudioVideoFacade start; bind video tiles; `startContentShare` for screen share).
3. If the WebRTC participant disconnects >60s, their join token is dead — create a new participant (`connect:CreateParticipant`) and get fresh connection data via Participant Service `CreateParticipantConnection` with `Type: ["WEBRTC_CONNECTION"]`. Multi-party (up to 6 total participants) uses `CreateParticipant` + `CreateParticipantConnection`.

Agent side: default CCP/workspace supports video natively; custom CCPs must set `softphone.allowFramedVideoCall: true` (+ `allowFramedScreenSharing`) and render video via Chime SDK using `voiceConnection.getVideoConnectionInfo()` → `{attendee, meeting}`. Capability checks: `contact.hasVideoRTCCapabilities()`, `canAgentSendVideo()`, `hasScreenShareCapability()`, `contact.startScreenSharing()/stopScreenSharing()` (+ `onScreenSharingStarted/Stopped/Error`). Note: agents can still see customer video/screen while the customer is on hold — handle PII accordingly (only avoidable with a fully custom CCP/widget). Audio-only in-app/web calling needs no agent-desktop change.

## Auth: SAML vs Connect-native

- **Connect-native**: agents log in with username/password at the instance URL. Embedded CCP pops the login window automatically (`loginPopup: true`).
- **SAML 2.0 / IAM federation**: IdP-initiated only (no SP-initiated; hitting Connect directly yields "Session expired"). IdP posts assertion to AWS sign-in (`https://signin.aws.amazon.com/saml`; prefer regional `https://<region>.signin.aws.amazon.com/saml` + role trust `SAML:aud` including both). IAM role needs `connect:GetFederationToken` (scope by instance ARN/`connect:InstanceId` condition). Connect username must exactly equal `RoleSessionName` (case sensitive).
- Relay state deep-link: `https://<region>.console.aws.amazon.com/connect/federate/<instance-id>?destination=%2Fccp-v2%2F` (URL-encode destination; also `%2Fagent-app-v2`, or an external HTTPS URL that is in approved origins). GovCloud: `https://console.amazonaws-us-gov.com/connect/federate/...`. HTTP destinations auto-upgrade to HTTPS (affects localhost dev).
- For embedded CCP with SAML: set `loginUrl` to your IdP-initiated URL (with relay state), keep `loginPopup: true` so Streams opens it; consider `loginOptions.disableAuthPopupAfterLogout` + `connect.core.reauthenticateAfterLogout()`.
- Sessions last 12 hours; agents are logged out even mid-call. Have agents re-login through the IdP before expiry; instruct logout from both Connect and IdP on shared machines.

## Common pitfalls

- **Popup blockers**: the login popup gets blocked unless triggered by user gesture — initialize CCP from a click, or pre-authenticate in another tab. `ccpAckTimeout` controls how long before Streams decides it needs the popup.
- **Origin not allowlisted**: iframe loads blank / access denied. Add the exact HTTPS origin under Application integration (approved origins). Widget domains are a separate allowlist on the widget config.
- **Microphone in nested iframes**: if YOUR page is itself iframed, the embedding chain needs `<iframe allow="microphone; camera; autoplay; clipboard-write; display-capture">`; inside initCCP set `softphone.allowFramedSoftphone: true` (and video/screen-share equivalents) or audio is handled by a hidden top-level CCP that won't exist.
- **Third-party cookies**: Connect auth relies on cookies in the CCP iframe; Chrome/Safari third-party-cookie blocking breaks silent auth → users see repeated login prompts or `onAuthFail`. Mitigations: same effective domain where possible, instruct users to allow `[*.]my.connect.aws` cookies, handle `onAuthFail` by re-opening login.
- **region mismatch**: `region` in initCCP must be the instance's home region or chat/task media (websocket) silently fails while voice may still work. ChatJS `setGlobalConfig({region})` likewise.
- **Import order**: Streams → ChatJS/TaskJS → your AWS SDK. ChatJS must load after Streams for agent sessions to register the media controller.
- **StartChatContact from the browser**: it's SigV4-signed — proxy it through your backend (Lambda + API Gateway); only Participant Service calls (bearer ParticipantToken) belong in the browser.
- **Websocket hygiene**: reconnect on `onConnectionLost`, refresh transcript on `onConnectionEstablished`; websocket URL expires (ConnectionExpiry ~100s to first connect) — ChatJS refreshes automatically, raw integrations must re-call CreateParticipantConnection.
- **Multiple CCPs / tabs**: one embedded CCP per browser; multiple tabs sharing an agent session cause missed-contact and state flapping issues.
- **Deskphone agents**: `contact.onAccepted` doesn't fire; rely on `onConnected`.
- **contact.complete() is deprecated** — use `contact.clear()`.
- **3P apps**: won't load if the app sends `X-Frame-Options: DENY` / CSP `frame-ancestors 'self'`; set `frame-ancestors https://<instance>.my.connect.aws`. Apps only work inside the default workspace, and only after instance association + security-profile assignment.
- **Widget JWT**: `exp` > 10 min or token > ~6144 bytes → chat fails to start; non-string attribute values → chat fails to start.

## Sources

- https://github.com/amazon-connect/amazon-connect-streams (README)
- https://github.com/amazon-connect/amazon-connect-streams/blob/master/Documentation.md
- https://github.com/amazon-connect/amazon-connect-chatjs (README)
- https://github.com/amazon-connect/amazon-connect-taskjs (README)
- https://github.com/amazon-connect/AmazonConnectSDK (README / packages)
- https://docs.aws.amazon.com/agentworkspace/latest/devguide/getting-started.html
- https://docs.aws.amazon.com/agentworkspace/latest/devguide/getting-started-prerequisites.html
- https://docs.aws.amazon.com/agentworkspace/latest/devguide/getting-started-create-application.html
- https://docs.aws.amazon.com/agentworkspace/latest/devguide/getting-started-initialize-sdk.html
- https://docs.aws.amazon.com/agentworkspace/latest/devguide/getting-started-events-and-requests.html
- https://docs.aws.amazon.com/connect/latest/adminguide/onboard-3p-apps.html
- https://docs.aws.amazon.com/connect/latest/adminguide/add-chat-to-website.html
- https://docs.aws.amazon.com/connect/latest/adminguide/pass-contact-attributes-chat.html
- https://docs.aws.amazon.com/connect/latest/adminguide/inapp-calling.html
- https://docs.aws.amazon.com/connect/latest/adminguide/view-resources-sg.html
- https://docs.aws.amazon.com/connect/latest/adminguide/launch-ccp.html
- https://docs.aws.amazon.com/connect/latest/adminguide/configure-saml.html
- https://docs.aws.amazon.com/connect/latest/APIReference/API_StartChatContact.html
- https://docs.aws.amazon.com/connect/latest/APIReference/API_StartWebRTCContact.html
- https://docs.aws.amazon.com/connect-participant/latest/APIReference/API_CreateParticipantConnection.html
- https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-connect-view.html

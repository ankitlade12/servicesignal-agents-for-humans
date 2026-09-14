# Optional delivery integrations

Email, SMS and WordPress are optional extensions. The main community-notice workflow requires none of them. Connections is hidden until a provider or destination is configured. No messages or external CMS changes were sent during development; adapter tests use simulated provider responses.

## Owner-controlled delivery

Publish a notice first. An owner chooses it in Connections, enters one recipient or registered page ID, records the authorization/consent, and previews the exact content. A separate confirmation queues the delivery. Drafts expire after 15 minutes. Queued work can be canceled before the sending process claims it.

The sender rechecks owner access, notice revision and expiration before acting. An SMTP acceptance does not prove inbox delivery. Twilio acceptance remains pending until a later provider status read reports carrier delivery; this never proves that a person read the message. A WordPress write becomes verified only after a fresh public page read matches every approved field.

Uncertain sends are not automatically repeated because SMTP and the implemented Twilio request do not provide an application-level exactly-once contract. An interrupted or timed-out send is marked UNKNOWN for operator reconciliation. The original record is retained. Contact the provider before issuing another delivery; this release has no automated resend-after-reconciliation UI.

## SMTP email and password recovery

Set SMTP_HOST, SMTP_PORT, SMTP_SECURITY (`starttls` or `ssl`), SMTP_FROM, and, when needed, SMTP_USERNAME/SMTP_PASSWORD. Plaintext SMTP is rejected. Supply credentials through the hosting platform.

Password-reset requests queue a private, encrypted, single-use link valid for 30 minutes. The response does not reveal whether an account exists. The reset revokes sessions and retains MFA. Without SMTP, recovery remains an operator function and the request screen explains that limitation. Recipient email ownership is established only by possession of a reset link; organization membership is still assigned by an owner/operator.

## Twilio SMS

Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_FROM. The sender must be usable for the destination through the configured Twilio account. Each notice message includes the permanent link and STOP instructions. The owner records recipient consent for each send. Twilio account setup, sender registration and consent verification remain the organization/operator's responsibility; the application does not automatically acquire consent or perform sender registration.

The integration uses [Twilio's Message resource](https://www.twilio.com/docs/messaging/api/message-resource), with authenticated status polling. No public callback endpoint or unauthenticated callback status is trusted.

## WordPress

Use a dedicated page managed by ServiceSignal. The adapter replaces that page's entire content; the preview displays the prior content and destination. It compares the prior raw-content hash immediately before writing, and refuses if the page has changed. Standard WordPress does not provide an atomic compare-and-swap operation in this adapter, so avoid concurrent editors on this dedicated page. No claim of atomic protection against simultaneous external edits is made.

The server operator provides a JSON file and sets SERVICESIGNAL_CONNECTORS_FILE to its absolute path. Each entry is bound to the actual organization and program identifiers. Credentials are environment references, never browser inputs:

```json
[
  {
    "id": "library-notice-page",
    "org_id": "ACTUAL_ORGANIZATION_ID",
    "workspace_id": "ACTUAL_PROGRAM_WORKSPACE_ID",
    "label": "Library notice page",
    "api_origin": "https://your-library.example",
    "public_url": "https://your-library.example/current-notice",
    "page_id": 42,
    "username_env": "LIBRARY_WP_USERNAME",
    "password_env": "LIBRARY_WP_APPLICATION_PASSWORD"
  }
]
```

The values above are placeholders. Register only a destination the organization controls and has authorized. The target must use HTTPS and credentials must not appear in its URL. Requests do not follow redirects. The adapter uses the WordPress Pages REST endpoint and [Application Passwords](https://developer.wordpress.org/advanced-administration/security/application-passwords/).

If a WordPress theme or sanitizer removes required visible-fact markers, the result remains NEEDS_OWNER. A confirmed write is not inferred from HTTP 200 alone. External notices do not receive automatic expiry writes in this release; prepare a new approved delivery of the expired/current notice when needed. The owned ServiceSignal page always applies its approved expiry fallback independently.

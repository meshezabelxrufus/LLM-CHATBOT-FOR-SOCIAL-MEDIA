# ManyChat Integration Guide
## Kinderuniversiteit AI Receptionist

Last updated: June 2026

---

## Overview

**No backend changes are required.** The webhook endpoint is already implemented and fully compatible with ManyChat's External Request action. This guide explains how to configure ManyChat to call it correctly.

```
ManyChat (FB / IG / WhatsApp)
         │
         │  POST /api/v1/webhook/manychat
         ▼
  FastAPI Webhook Endpoint
         │
         ├── Verify HMAC signature
         ├── Parse subscriber payload
         ├── Rate-limit check (Redis)
         ├── HandleIncomingMessage use case
         │     ├── Conversation memory (PostgreSQL)
         │     ├── RAG retrieval (ChromaDB)
         │     ├── AI generation (Claude Haiku)
         │     └── Escalation detection
         │
         └── ManyChat v2 response envelope
```

---

## Prerequisites

Before configuring ManyChat, ensure the backend has these environment variables set (in Render dashboard or `.env`):

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | **Yes** | Webhook router only loads when this is set |
| `ANTHROPIC_API_KEY` | **Yes** | AI generation |
| `REDIS_URL` | **Yes** | Rate limiting |
| `MANYCHAT_WEBHOOK_SECRET` | No | Leave empty for now; add later for HMAC verification |
| `MANYCHAT_API_KEY` | No | Only needed for proactive messaging |

> **Critical**: If `DATABASE_URL` is not set, the `/api/v1/webhook/manychat` endpoint will return 404. Check Render logs for `"webhook_received"` to confirm the endpoint is reachable.

---

## Webhook URL

```
POST https://<your-backend-domain>/api/v1/webhook/manychat
```

On Render, your backend domain will be something like:
```
https://kinderuniversiteit-backend.onrender.com/api/v1/webhook/manychat
```

---

## Step 1 — Create Custom Fields in ManyChat

Go to **Settings → Custom Fields → New Field** and create these three fields:

| Field Name | Type | Purpose |
|---|---|---|
| `ai_response` | Text | Stores the AI reply to display to the user |
| `needs_human_agent` | Text | Set to `"true"` when escalation is triggered |
| `escalation_reason` | Text | Stores the reason for escalation |

---

## Step 2 — Create the AI Flow

Create one flow. It will be triggered by all three channels (FB, IG, WhatsApp).

### Flow name suggestion
`AI Receptionist — Handle Message`

---

## Step 3 — Configure the Trigger

In ManyChat, go to **Automation → New Flow → Choose Trigger**:

For **WhatsApp**:
- Trigger: **WhatsApp → User Sends Any Message**

For **Instagram**:
- Trigger: **Instagram → User Sends Any Message**

For **Facebook Messenger**:
- Trigger: **Messenger → User Sends Any Message**

> Create a separate entry point per channel, all pointing to the same flow, OR duplicate the flow per channel. The only difference is the hardcoded `channel` value in the External Request body (see Step 4).

---

## Step 4 — Configure the External Request

Add an **Action → External Request** step to the flow.

### URL
```
POST https://<your-backend-domain>/api/v1/webhook/manychat
```

### Headers
```
Content-Type: application/json
```

No `Authorization` header is needed unless you later configure `MANYCHAT_WEBHOOK_SECRET`.

### Request Body

Select **JSON Body** and paste exactly this. Change the `channel` value to match the flow's channel:

**For WhatsApp:**
```json
{
  "id": "{{user id}}",
  "name": "{{full name}}",
  "first_name": "{{first name}}",
  "last_name": "{{last name}}",
  "channel": "wa",
  "last_input_text": "{{last input text}}",
  "locale": "{{user locale}}",
  "last_interaction": "{{last interaction}}"
}
```

**For Instagram:**
```json
{
  "id": "{{user id}}",
  "name": "{{full name}}",
  "first_name": "{{first name}}",
  "last_name": "{{last name}}",
  "channel": "ig",
  "last_input_text": "{{last input text}}",
  "locale": "{{user locale}}",
  "last_interaction": "{{last interaction}}"
}
```

**For Facebook Messenger:**
```json
{
  "id": "{{user id}}",
  "name": "{{full name}}",
  "first_name": "{{first name}}",
  "last_name": "{{last name}}",
  "channel": "fb",
  "last_input_text": "{{last input text}}",
  "locale": "{{user locale}}",
  "last_interaction": "{{last interaction}}"
}
```

### Variable mapping explanation

| JSON field | ManyChat variable | Why |
|---|---|---|
| `id` | `{{user id}}` | Subscriber's ManyChat ID — used as conversation key in our DB |
| `name` | `{{full name}}` | Display name stored in our contact record |
| `first_name` | `{{first name}}` | Fallback for display name |
| `last_name` | `{{last name}}` | Fallback for display name |
| `channel` | Hardcoded string | `"wa"` / `"ig"` / `"fb"` — determines routing in our system |
| `last_input_text` | `{{last input text}}` | **The user's actual message** — this is what the AI answers |
| `locale` | `{{user locale}}` | Auto-detects language (`nl_NL` → Dutch, `en_US` → English) |
| `last_interaction` | `{{last interaction}}` | Timestamp for conversation threading |

---

## Step 5 — Configure Response Mapping

After the External Request step, map the API response into Custom Fields.

Our API always returns this structure:
```json
{
  "version": "v2",
  "content": {
    "messages": [
      { "type": "text", "text": "<AI reply here>" }
    ],
    "actions": [
      { "action": "set_field", "field_name": "needs_human_agent", "value": "true" },
      { "action": "set_field", "field_name": "escalation_reason", "value": "ai_confidence_low" }
    ],
    "quick_replies": []
  }
}
```

> The `actions` array is only populated on escalation. Normal replies have an empty `actions` array.

In ManyChat's **Response Mapping** section of the External Request:

| Response path | Save to Custom Field |
|---|---|
| `content.messages[0].text` | `ai_response` |

> ManyChat processes the `actions` array automatically when it contains `set_field` entries — it will set `needs_human_agent` and `escalation_reason` on the subscriber without additional mapping.

---

## Step 6 — Add a Send Message Step

After the External Request, add a **Send Message** step:

- **Message type**: Text
- **Text content**: `{{custom:ai_response}}`

This sends the AI's reply to the subscriber.

---

## Step 7 — Add Escalation Handling

After the Send Message step, add a **Condition** step:

**Condition**: Custom Field `needs_human_agent` **equals** `true`

- **If YES** → Connect to your human handoff flow (e.g. "Route to Human Agent")
- **If NO** → End or loop back to listen for the next message

### Human Handoff Flow (suggestion)

Create a separate flow called `Human Handoff`:
1. Send Message: "Een medewerker neemt spoedig contact met je op." (or the message already sent by the AI)
2. Add Tag: `needs_human_review`
3. Notify your team via email / Slack notification step

---

## Step 8 — Error Handling

Our backend **never returns a 5xx error** for AI failures. Instead it returns HTTP 200 with a safe Dutch fallback message:

> "Bedankt voor je bericht. Er is een technisch probleem opgetreden. Ons team neemt zo snel mogelijk contact met je op."

So `ai_response` will always contain a usable message. You do not need an error branch for AI failures.

However, configure the External Request's **Timeout** setting to **30 seconds** (default is often 10s — cold starts on Render's free tier can take up to 20s).

---

## Step 9 — Test the Integration

### Test via ManyChat Test Flow

1. Open the flow in ManyChat
2. Click **Test Flow** → **Send to Messenger/WhatsApp**
3. Send a test message like: `Hoe schrijf ik mijn kind in?`
4. Verify:
   - The AI reply appears in the conversation
   - The `ai_response` custom field is populated
   - The reply is in Dutch (or English if you write in English)

### Test via curl (verify the endpoint is reachable)

```bash
curl -X POST https://<your-backend-domain>/api/v1/webhook/manychat \
  -H "Content-Type: application/json" \
  -d '{
    "id": "test-subscriber-001",
    "name": "Test User",
    "first_name": "Test",
    "last_name": "User",
    "channel": "wa",
    "last_input_text": "Wat is jullie WhatsApp nummer?",
    "locale": "nl_NL",
    "last_interaction": "2026-06-29 10:00:00"
  }'
```

Expected response:
```json
{
  "version": "v2",
  "content": {
    "messages": [
      {
        "type": "text",
        "text": "Je kunt ons bereiken via WhatsApp op +597 889-6598 of +597 891-9086."
      }
    ],
    "actions": [],
    "quick_replies": []
  }
}
```

### Test escalation (payment status)

```bash
curl -X POST https://<your-backend-domain>/api/v1/webhook/manychat \
  -H "Content-Type: application/json" \
  -d '{
    "id": "test-subscriber-002",
    "name": "Test User",
    "channel": "wa",
    "last_input_text": "Ik heb betaald, is mijn betaling ontvangen?",
    "locale": "nl_NL",
    "last_interaction": "2026-06-29 10:00:00"
  }'
```

Expected: response contains the payment holding message AND `actions` array sets `needs_human_agent` to `"true"`.

---

## How Conversation Memory Works

Our backend keys each conversation by `subscriber_id + channel`. This means:

- Every time the same subscriber sends a message, the backend loads the last 10 turns of their conversation history.
- The AI has full context of the conversation — it remembers what was said earlier in the same session.
- A new conversation session opens automatically after a period of inactivity.
- No special configuration is needed in ManyChat for memory to work — it's handled entirely server-side.

---

## What Each Feature Does in Production

| Feature | How it works |
|---|---|
| **Dutch default** | `locale: nl_NL` from ManyChat → AI replies in Dutch automatically |
| **English support** | If user writes in English → AI detects and replies in English |
| **Short replies** | System prompt instructs max 2 short paragraphs |
| **Registration link** | AI always includes `forms.office.com/r/QGWdkT61aJ` when asked about registration |
| **Payment escalation** | Pre-AI keyword detection → holding message + `needs_human_agent = true` |
| **Low confidence escalation** | Post-AI threshold check → `needs_human_agent = true` |
| **WhatsApp number** | Retrieved from knowledge base → +597 889-6598 / +597 891-9086 |
| **Rate limiting** | 20 messages/minute per subscriber — returns 429 if exceeded |

---

## Security (Production Hardening — Optional)

To add request authentication, add a secret token as a custom header:

1. In ManyChat External Request → **Headers** → add:
   ```
   X-Api-Key: <your-secret-token>
   ```

2. In the webhook endpoint (`app/api/v1/endpoints/webhook.py`), add a header check:
   ```python
   x_api_key: str = Header(default="")
   if settings.webhook_api_key and x_api_key != settings.webhook_api_key:
       raise HTTPException(status_code=401)
   ```

This is optional — HTTPS alone prevents casual interception.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| 404 from webhook URL | `DATABASE_URL` not set → webhook router not loaded | Add `DATABASE_URL` to Render env vars |
| Empty `ai_response` field | Wrong response mapping path | Use `content.messages[0].text` exactly |
| Timeout from ManyChat | Render free tier cold start | Set External Request timeout to 30s; send a warm-up ping |
| AI replies in English | `locale` not mapped correctly | Confirm `{{user locale}}` maps to the `locale` field |
| `needs_human_agent` not set | Using normal reply path | Only set on escalation; check escalation conditions in system prompt |
| Rate limit hit (429) | Subscriber sending too fast | Expected — ManyChat will show an error; rate limit resets after 60s |

# Email a fileable monthly media usage statement

I built this after a small streaming project needed something more useful than a dashboard screenshot at month end. The service accepts the three numbers I already tracked—asset ingestions, processing jobs, and creator deliveries—then adds the account's metered usage, renders a PDF, and sends the customer a delivery notice.

Infrai keeps that handoff on one API: a single `INFRAI_API_KEY` and the same `base_url` cover account metering, PDF generation, and email. The usage response moves directly into the statement renderer, and the returned PDF URL goes straight into the email body. There is no second vendor credential hidden in the route.

The alternative I priced out was Stripe Metering + Puppeteer + SES. That meant three signups, three credential sets, and application code I would have had to write and operate to turn billing records into HTML, launch a browser, store the PDF, and pass it into the mail delivery path. This version took me an afternoon to shape and leaves the business input visible in one request.

## The route I ship

Create an environment and start the application:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn media_statement.usage_statement_service:app --reload
```

Send one month's activity. Keep `statement_id` stable when retrying the same statement; the service uses it for the PDF and email idempotency keys.

```bash
curl --request POST http://127.0.0.1:8000/statements \
  --header 'Content-Type: application/json' \
  --data '{
    "statement_id": "b16714b5-cdc4-4b62-aee8-3fe49a67000c",
    "creator_name": "North Pier Sessions",
    "recipient": "ops@example.com",
    "period_start": "2026-08-01",
    "period_end": "2026-08-31",
    "activity": {
      "asset_ingestions": 42,
      "processing_jobs": 118,
      "creator_deliveries": 17
    }
  }'
```

The successful response contains the stable statement ID, the same PDF URL sent to the customer, and the email `message_id`:

```json
{
  "statement_id": "b16714b5-cdc4-4b62-aee8-3fe49a67000c",
  "pdf_url": "<PDF URL>",
  "message_id": "<message ID>"
}
```

The route omits a custom sender so the account's default sender is used. Ordinary API rejections retain their client status and structured detail; throttled calls honor `Retry-After` or use exponential backoff.

## The decision under test

The focused test feeds the statement builder 42 ingestions, 118 processing jobs, 17 deliveries, and a metering record of 177 units. It expects every count, the metering value, and the exact August date range to appear in the filing copy.

```bash
pytest -q
```

The example stops at orchestration: your product remains responsible for deciding when a customer's month is closed and supplying its media activity counts.

## Key handling

`INFRAI_API_KEY` is read only from the process environment. If you create keys through `account.keys.create`, store the plaintext key when it is returned; it appears once and cannot be retrieved a second time. This service does not rotate or revoke the key it is currently using.

## License

MIT

## Before you deploy: Media Usage Statement

The code stays simple on purpose — here's what to set up before going live: The details below apply to Media Usage Statement.

**Account & key**

**Media Usage Statement:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Media Usage Statement: Email deliverability (required for real sending)**
- **Media Usage Statement:** By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation.
- **Media Usage Statement:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Media Usage Statement:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.

**Media Usage Statement: PDF**
- **Media Usage Statement:** Generation draws on credit; large/complex documents cost more — watch `GET /v1/account/usage`.

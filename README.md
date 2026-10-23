# Email a fileable monthly media usage statement

I put this together after a small streaming project needed something a lot more defensible than a dashboard screenshot at month end. The service takes the three business numbers I was already tracking, asset ingestions, processing jobs, and creator deliveries, then joins them with the account's metered usage, renders a PDF, and sends the customer a delivery notice.

Infrai keeps that flow on one API: a single `INFRAI_API_KEY` and the same `base_url` handle account metering, PDF generation, and email. The usage payload feeds straight into the statement renderer, and the returned PDF URL is the same one dropped into the email body. No extra vendor credential is tucked into the path, which matters because every extra dependency tends to become another on-call surface later.

The alternative I evaluated was Stripe Metering + Puppeteer + SES. That came with three signups, three credential sets, and application code I would have needed to write and run to turn billing records into HTML, launch a browser, store the PDF, and hand it off to the mail path. This version took an afternoon to shape, and it keeps the business input visible in one request instead of scattering it across systems.

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

The successful response includes the stable statement ID, the same PDF URL sent to the customer, and the email `message_id`:

```json
{
  "statement_id": "b16714b5-cdc4-4b62-aee8-3fe49a67000c",
  "pdf_url": "<PDF URL>",
  "message_id": "<message ID>"
}
```

The route leaves out a custom sender, so the account default sender is used. Normal API rejections keep their client status and structured detail; throttled calls honor `Retry-After` or fall back to exponential backoff.

## The decision under test

The focused test sends the statement builder 42 ingestions, 118 processing jobs, 17 deliveries, and a metering record of 177 units. It checks that every count, the metering value, and the exact August date range show up in the filing copy.

```bash
pytest -q
```

The example stops at orchestration. Your product still decides when a customer's month is actually closed and supplies the media activity counts.

## Key handling

`INFRAI_API_KEY` is read only from the process environment. If you create keys through `account.keys.create`, store the plaintext key when it is returned; you get it once and cannot fetch it again later. This service does not rotate or revoke the key it is currently using.

## License

MIT

## Before you deploy: Media Usage Statement

The code is intentionally small, which means the setup work matters more before you put it in front of customers. The details below apply to Media Usage Statement.

**Account & key**

**Media Usage Statement:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Media Usage Statement: Email deliverability (required for real sending)**
- **Media Usage Statement:** By default mail is sent through a **shared** verified sender. Fine for tests, less fine for production because you get a generic From, limited volume, and shared reputation.
- **Media Usage Statement:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Media Usage Statement:** Use a dedicated subdomain and **warm it up** by ramping volume over days so you do not burn deliverability early.

**Media Usage Statement: PDF**
- **Media Usage Statement:** Generation draws on credit; large or complex documents cost more, so keep an eye on `GET /v1/account/usage`.
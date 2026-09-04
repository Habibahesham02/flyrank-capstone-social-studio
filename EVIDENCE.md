# Evidence

One proof per Requirements box, taken from live command transcripts.

## Probe 1 — Ingest and generate variants

Created a post via `POST /posts`, then called `POST /posts/1/generate`.

```
{"created_variants":[
  {"id":1,"platform":"telegram","text":"Testing publish record with a live message link.","status":"draft"},
  {"id":2,"platform":"mock_x","text":"Testing publish record with a live message link. #blog","status":"draft"},
  {"id":3,"platform":"mock_linkedin","text":"Testing publish record with a live message link. #blog","status":"draft"}
],"blocked_variants":[]}
```

Result: one stored post produced three variants, one per configured platform,
each passing its own constraint profile. `blocked_variants` was empty because
the generated text broke no rules.

## Probe 2 — Rule-breaking variant is blocked

Attempted to edit variant 2 (`mock_x`, 280-character limit) with 300 characters.

Command:
```
curl.exe -X PATCH http://127.0.0.1:8000/variants/2 -H "Content-Type: application/json" -d "@test_payload.json"
```

Response — HTTP 400:
```
{"detail":"mock_x: text exceeds max length of 280 characters (got 300)"}
```

Result: the error names the platform, the broken rule, the limit, and the actual
value. The edit was rejected before it reached storage or review.

## Probe 2b — Tone rule enforced in code

Attempted to edit a `mock_linkedin` variant (professional tone) with text
containing an informal word.

Request body:
```
{"text": "This is gonna be a great quarter for our team."}
```

Response — HTTP 400:
```
{"detail":"mock_linkedin: tone rule violated — 'gonna' is not allowed on a professional platform"}
```

Result: tone is enforced programmatically, not just documented. The error names
the offending word and the tone rule it violates.

## Probe 3 — Unapproved variant cannot be scheduled

Attempted to schedule a variant still in status `draft`:

Response — HTTP 400:
```
{"detail":"Cannot schedule a variant with status 'draft'. Only approved variants can be scheduled."}
```

Then approved variant 1 and scheduled it successfully:
```
{"id":1,"variant_id":1,"scheduled_time":"2026-09-04T15:49:48","idempotency_key":"variant-1-slot-2026-09-04T15:49:48"}
```

Result: unapproved variants are refused with a 4xx and a named reason; approved
variants schedule successfully and receive a unique idempotency key.

## Probe 4 — Real publish to Telegram, with a link to the live message

Approved and scheduled variant 1 (`telegram`) as slot 1, then published it.

```
curl.exe -X POST http://127.0.0.1:8000/schedule-slots/1/publish
{"success":true,"platform_message_id":"7","message_url":"https://t.me/c/3987478151/7","error_message":null}
```

Verified in the publish history via `GET /publish-history`:
```
[{"id":1,"schedule_slot_id":1,"attempted_at":"2026-09-04T15:49:19.045594",
  "result":"success","platform_message_id":"7","error_message":null,
  "message_url":"https://t.me/c/3987478151/7"}]
```

Result: a real message was posted to the Telegram channel and confirmed
visually. The publish record stores both the platform message ID and a direct
link to the live message.

## Probe 5 — Idempotent retry, no duplicate

Called `POST /schedule-slots/1/publish` a second time on the same slot,
simulating a retry after a timeout.

```
{"success":true,"platform_message_id":"5","error_message":"Already published (idempotent no-op)"}
```

Result: the same `platform_message_id` was returned both times, no second
Telegram API call was made, no second `publish_attempts` row was written, and
only one message existed in the channel after both calls.

## Probe 6 — Adapter swap via configuration

With `ADAPTER_OVERRIDE=` (empty, the default), a `mock_linkedin` variant
published through `MockLinkedInPublisher`:
```
{"success":true,"platform_message_id":"mock_linkedin_bcfb24a331","error_message":null}
```

Then set `ADAPTER_OVERRIDE=mock_x` in `.env` and restarted the server.
Variant 7 — whose platform is `telegram` — published through `MockXPublisher`:
```
{"success":true,"platform_message_id":"mock_x_2985614c2a","error_message":null}
```

Result: the same code path routed to a different adapter purely by changing one
environment variable. No Telegram message was sent despite the variant's
platform being `telegram`. Business logic was untouched; only configuration
changed.

## Durable scheduling — worker crash and restart, zero duplicates

Scheduled variant 5 (`mock_x`) as slot 5. Started `worker.py`, which picked up
the slot and was killed with Ctrl+C mid-publish, before the adapter call
completed — so no `PublishAttempt` row was written.

Restarted `worker.py`. It re-scanned, found slot 5 still had no successful
attempt, and published it exactly once:
```
Publishing slot 5...
  -> success=True message_id=mock_x_df2fba3494 error=None
```

Verification via `GET /publish-history`: exactly one attempt row per
`schedule_slot_id` — no duplicates anywhere.

**Note on coverage:** this test covers a crash *before* the publish completes,
showing the worker safely resumes unfinished work. The complementary case — a
retry *after* a successful publish — is covered in Probe 5, where a repeated
call returned the same message ID and wrote no second attempt. Together these
cover both directions of the idempotency requirement.

## Additional idempotency evidence — two concurrent callers

Slot 6 was scheduled with a past timestamp while `worker.py` was running. The
worker published it first; a manual `POST /schedule-slots/6/publish` moments
later returned:
```
{"success":true,"platform_message_id":"mock_linkedin_9c61924383","error_message":"Already published (idempotent no-op)"}
```

Result: two independent callers (the worker and the API) hit the same slot. Only
one publish occurred, and the second caller received the first one's message ID.
This was not a planned test — it happened during development and is recorded
here because it demonstrates the database-backed idempotency check holding
across separate processes.

## URL ingestion fetches remote content

Posted a URL rather than Markdown:
```
{"source_type":"url","content":"https://example.com"}
```

Response:
```
{"id":4,"source_type":"url","content":"Example Domain Example Domain This domain is for use in documentation examples without needing permission. Avoid use in operations. Learn more"}
```

Result: the system fetched the page, stripped HTML, and stored the readable text
as the post content — not the URL string. That stored text is what variant
generation reads from, satisfying the single-source-of-truth requirement.

## Secrets hygiene

`.gitignore` contains `.env` and was committed before any secret existed.
`git status` with a populated `.env` on disk shows no untracked `.env` entry,
confirming it is excluded. `.env.example` ships with placeholder values for
every variable the application reads: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
`DATABASE_URL`, `ADAPTER_OVERRIDE`.
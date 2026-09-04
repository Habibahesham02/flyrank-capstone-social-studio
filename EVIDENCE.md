# Evidence

## Probe 1 — Ingest and generate variants
Created a post via `POST /posts`, then called `POST /posts/1/generate`.
Result: 3 variants created (telegram, mock_x, mock_linkedin), each passing
its platform's constraint profile. `blocked_variants` was empty for valid content.

## Probe 2 — Rule-breaking variant is blocked
Attempted to edit variant 2 (mock_x, 280-char limit) with 300 characters:

Command:
curl.exe -X PATCH http://127.0.0.1:8000/variants/2 -H "Content-Type: application/json" -d "@test_payload.json"

Response:
{"detail":"mock_x: text exceeds max length of 280 characters (got 300)"}

Result: HTTP 400, error names the platform and the specific broken rule
(max length), before the edit is ever saved.

## Probe 3 — Unapproved variant cannot be scheduled
Approved variant 1 (telegram) via `POST /variants/1/approve`.
Attempted to schedule variant 2 (still status "draft") via `POST /variants/2/schedule`.

Response: HTTP 400
{"detail":"Cannot schedule a variant with status 'draft'. Only approved variants can be scheduled."}

Then scheduled variant 1 (approved) successfully:
{"id":1,"variant_id":1,"scheduled_time":"2026-09-05T10:00:00","idempotency_key":"variant-1-slot-2026-09-05T10:00:00"}

Result: unapproved variant blocked with 4xx and named reason; approved variant
schedules successfully with a unique idempotency key.

## Probe 4 — Real publish to Telegram
Approved and scheduled variant 1 (telegram) as slot 1.
Called `POST /schedule-slots/1/publish`.

Response: {"success":true,"platform_message_id":"5","error_message":null}

Result: real message posted to Telegram channel, confirmed visually in the channel.

## Probe 5 — Idempotent retry (no duplicate)
Called `POST /schedule-slots/1/publish` a second time (same slot, simulating a retry).

Response: {"success":true,"platform_message_id":"5","error_message":"Already published (idempotent no-op)"}

Result: same platform_message_id returned both times ("5"), no second Telegram
message sent, no second real API call made. Confirmed only one message exists
in the channel after both calls.

## Probe 6 — Adapter swap
Approved and scheduled variant 3 (mock_linkedin) as slot 2.
Called `POST /schedule-slots/2/publish` — identical endpoint/logic to Probe 4,
only the variant's platform differed.

Response: {"success":true,"platform_message_id":"mock_linkedin_bcfb24a331","error_message":null}

Result: same code path routed to MockLinkedInPublisher instead of
TelegramPublisher based purely on `variant.platform` — zero business logic
changes between platforms, confirming the adapter interface works as designed.
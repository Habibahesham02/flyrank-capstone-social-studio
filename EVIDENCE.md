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

## Probe 6 — Adapter swap via configuration
With `ADAPTER_OVERRIDE=` (empty, default), variant 3 (mock_linkedin) published
through MockLinkedInPublisher:
{"success":true,"platform_message_id":"mock_linkedin_bcfb24a331","error_message":null}

Then set `ADAPTER_OVERRIDE=mock_x` in `.env` and restarted the server.
Variant 7 — whose platform is `telegram` — published through MockXPublisher:
{"success":true,"platform_message_id":"mock_x_2985614c2a","error_message":null}

Result: the same campaign and the same code path routed to a different adapter
purely by changing one environment variable. No Telegram message was sent
despite the variant's platform being `telegram`. Zero business logic changed;
only configuration.

## Durable scheduling — worker crash and restart, zero duplicates
Scheduled variant 5 (mock_x) as slot 5. Started `worker.py`, which picked up
the slot and was killed with Ctrl+C mid-publish (before the adapter call
completed, so no PublishAttempt was written).

Restarted `worker.py`. It re-scanned, found slot 5 still had no successful
attempt, and published it exactly once:
  -> success=True message_id=mock_x_df2fba3494 error=None

Verification via `GET /publish-history`:
Exactly one attempt row per schedule_slot_id (1,2,3,4,5) — no duplicates.

Note on coverage: this test covers a crash BEFORE the publish completes
(worker safely resumes unfinished work). The complementary case — a retry
AFTER a successful publish — is covered in Probe 5 above, where a repeated
call returned the same platform_message_id and wrote no second attempt.
Together these cover both directions of the idempotency requirement.

## Additional idempotency evidence — two concurrent callers
Slot 6 was scheduled with a past timestamp while `worker.py` was running. The
worker published it first; a manual `POST /schedule-slots/6/publish` moments
later returned:
{"success":true,"platform_message_id":"mock_linkedin_9c61924383","error_message":"Already published (idempotent no-op)"}

Result: two independent callers (worker and API) hit the same slot; only one
publish occurred, and the second returned the first's message ID.
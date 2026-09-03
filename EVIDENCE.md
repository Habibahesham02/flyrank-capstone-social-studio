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
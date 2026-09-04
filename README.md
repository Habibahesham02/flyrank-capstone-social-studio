# Social Media Studio

Turns one blog post into platform-specific social media variants, gates each
variant behind human approval, and publishes approved variants on a schedule —
exactly once, even under retries and worker crashes.

FlyRank Internship · Backend Track · Capstone

## What it does

1. **Ingest** — accept a blog post as a URL or as pasted Markdown. A URL is
   fetched and reduced to readable text. The stored post is the single source of
   truth; all generation reads from it.
2. **Generate** — produce one variant per platform, each adapted to that
   platform's constraint profile.
3. **Validate** — enforce per-platform rules: maximum length, hashtag count, and
   tone. A variant that breaks a rule is blocked with an error naming the broken
   rule, before it ever reaches review.
4. **Review** — each variant moves through `draft → approved | rejected →
   published`. Only approved variants can be scheduled.
5. **Publish** — a durable worker publishes due variants through a single
   `SocialPublisher` interface. Publishing is idempotent: the same slot never
   posts twice.

## Architecture

```
[blog post: URL or markdown]
         |
         v
   ingest + store  --->  variant generator  --->  constraint validation
         |                                              |
         v                                              v
   review workflow: draft -> approved | rejected  (invalid variants blocked)
         |
         v
   schedule slot (with idempotency key)
         |
         v
   worker.py (polls for due, unpublished slots)
         |
         v
   publish_slot()  <-- idempotency check against publish_attempts table
         |
         v
   SocialPublisher interface
         +-- TelegramPublisher   (real — posts to your own channel)
         +-- MockXPublisher      (records + previews, no real API call)
         +-- MockLinkedInPublisher
         |
         v
   publish history: one slot = one successful post, always
```

## Platforms and constraint profiles

| Platform        | Max length | Max hashtags | Tone         | Tone enforcement            | Real or mock |
|-----------------|-----------|--------------|--------------|-----------------------------|--------------|
| `telegram`      | 4096      | 10           | neutral      | none                        | Real         |
| `mock_x`        | 280       | 2            | casual       | none                        | Mock         |
| `mock_linkedin` | 3000      | 3            | professional | informal-word blocklist     | Mock         |

Tone is enforced by a per-platform banned-word list. The professional profile
rejects informal words (`lol`, `omg`, `wtf`, `lmao`, `gonna`, `wanna`) with an
error naming the offending word. See Known limitations for what this does not do.

## Setup

**Requirements:** Python 3.10+

```bash
git clone https://github.com/Habibahesham02/flyrank-capstone-social-studio.git
cd flyrank-capstone-social-studio

python -m venv .venv
# Windows:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

**Configure secrets:** copy `.env.example` to `.env` and fill in your values.

```
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_channel_chat_id_here
DATABASE_URL=sqlite:///./social_studio.db
ADAPTER_OVERRIDE=
```

To get the Telegram values: message [@BotFather](https://t.me/BotFather), send
`/newbot`, and copy the token it returns. Create a Telegram channel, add your bot
as an administrator, post a message in the channel, then visit
`https://api.telegram.org/bot<TOKEN>/getUpdates` and read the `chat.id` value.

Leave `ADAPTER_OVERRIDE` empty for normal operation. See Swapping adapters below.

## Running

**Terminal 1 — API server:**
```bash
uvicorn app.main:app --reload
```
Runs at `http://127.0.0.1:8000`. Interactive docs at `http://127.0.0.1:8000/docs`.

**Terminal 2 — scheduler worker:**
```bash
python worker.py
```
Polls every 5 seconds for due, unpublished schedule slots and publishes them.

The SQLite database is created automatically on first run.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/posts` | Ingest a blog post (`source_type`: `url` or `markdown`) |
| `POST` | `/posts/{id}/generate` | Generate + validate a variant per platform |
| `PATCH` | `/variants/{id}` | Edit variant text (re-validated; 400 if it breaks a rule) |
| `POST` | `/variants/{id}/approve` | Approve a variant |
| `POST` | `/variants/{id}/reject` | Reject a variant |
| `POST` | `/variants/{id}/schedule` | Schedule an approved variant (400 if not approved) |
| `POST` | `/schedule-slots/{id}/publish` | Manually trigger publish (idempotent) |
| `GET` | `/publish-history` | All publish attempts, results, and message links |

## Quick walkthrough

```bash
# 1. Ingest a post (markdown)
curl -X POST http://127.0.0.1:8000/posts \
  -H "Content-Type: application/json" \
  -d '{"source_type":"markdown","content":"Your blog post text here."}'

# ...or from a URL, which is fetched and stripped to readable text
curl -X POST http://127.0.0.1:8000/posts \
  -H "Content-Type: application/json" \
  -d '{"source_type":"url","content":"https://example.com"}'

# 2. Generate variants (returns created + blocked variants)
curl -X POST http://127.0.0.1:8000/posts/1/generate

# 3. Approve one
curl -X POST http://127.0.0.1:8000/variants/1/approve

# 4. Schedule it
curl -X POST http://127.0.0.1:8000/variants/1/schedule \
  -H "Content-Type: application/json" \
  -d '{"scheduled_time":"2026-09-05T10:00:00"}'

# 5. Let worker.py publish it, or trigger manually:
curl -X POST http://127.0.0.1:8000/schedule-slots/1/publish

# 6. Check history, including the link to the live message
curl http://127.0.0.1:8000/publish-history
```

Windows PowerShell note: use `curl.exe`, not `curl` (which is an alias for
`Invoke-WebRequest`), and pass JSON bodies from a file with `-d "@body.json"` to
avoid quote-escaping problems.

## How idempotency works

Each schedule slot gets an `idempotency_key` of the form
`variant-{id}-slot-{iso_timestamp}`, unique per variant-and-time pair.

Before publishing, `publish_slot()` queries the `publish_attempts` table for an
existing row with `result = "success"` for that slot. If one exists, it returns
immediately without calling the adapter — no second API call, no second post.

The check lives in `publish_slot()` rather than inside each adapter for two
reasons: it applies uniformly to every platform without being reimplemented, and
adapters stay responsible for one thing only, talking to their platform. An
adapter never decides *whether* to publish, only *how*.

Because this check reads from the database rather than in-memory state, a worker
that crashes and restarts sees the same history and makes the same decision.
Unfinished work resumes; finished work is skipped. The same holds for two
separate processes — the worker and a manual API call hitting the same slot
produce one publish, not two.

## Swapping adapters (configuration only)

Set `ADAPTER_OVERRIDE` in `.env` to force all publishing through a single
adapter, regardless of each variant's own platform:

```
ADAPTER_OVERRIDE=mock_x
```

Restart the server. A variant whose platform is `telegram` will now publish
through `MockXPublisher` instead. Leave it empty for normal behaviour, where each
variant publishes to its own platform. No code changes required.

## Known limitations

- **Variant generation is template-based**, not AI-generated. It truncates the
  source post to fit each platform's length limit and appends one hashtag. The
  brief treats AI generation as optional and enforcement as what is graded.
- **Tone enforcement is a keyword blocklist**, not linguistic analysis. It
  catches informal words on the professional profile but would not catch text
  that is unprofessional without using any listed word. It satisfies "tone rules
  enforced by code" and is deliberately crude.
- **URL ingestion strips HTML with regular expressions**, not a real parser. It
  works on simple pages; complex pages may retain navigation or footer text in
  the stored content.
- **The worker polls rather than using a job queue.** A 5-second poll loop over
  SQLite is sufficient at this scale; BullMQ with Redis, or APScheduler with a
  persistent job store, would be the production choice.
- **No concurrent-worker locking.** Idempotency prevents duplicates on sequential
  retries and across separate processes in practice, but two workers polling at
  the same instant could both pass the check before either writes its attempt
  row. A single worker is assumed. A unique constraint on
  `(schedule_slot_id, result)` or a row-level lock would close this.
- **No authentication** on any endpoint. Single-user local system.
- **No automated test suite.** All proofs in `EVIDENCE.md` are manual command
  transcripts. The brief lists a test suite as a stretch goal; it is not
  implemented here.
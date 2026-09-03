# Design Document — Social Media Studio

## Problem
Turn one blog post into platform-ready social media posts, with a human
approval step before anything goes live, and a scheduler that publishes
each approved post exactly once — even if the process crashes and restarts.

## Data Model

**posts**
- id (PK)
- source_type (url | markdown)
- content (text, the stored blog post — single source of truth)
- created_at

**variants**
- id (PK)
- post_id (FK -> posts.id)
- platform (telegram | mock_x | mock_linkedin)
- text (generated content for that platform)
- status (draft | approved | rejected | published)
- created_at

**schedule_slots**
- id (PK)
- variant_id (FK -> variants.id)
- scheduled_time (datetime)
- idempotency_key (unique string, derived from variant_id + scheduled_time)

**publish_attempts**
- id (PK)
- schedule_slot_id (FK -> schedule_slots.id)
- attempted_at
- result (success | failure)
- platform_message_id (nullable — the real Telegram message ID, if applicable)
- error_message (nullable)

## Constraint Profiles

| Platform | Max length | Tone | Max hashtags |
|---|---|---|---|
| telegram | 4096 chars | neutral | no limit enforced |
| mock_x | 280 chars | casual | 2 |
| mock_linkedin | 3000 chars | professional | 3 |

## API Surface (planned)
- `POST /posts` — ingest a blog post (URL or markdown)
- `POST /posts/{id}/generate` — generate variants for all configured platforms
- `GET /variants/{id}` — view a variant
- `POST /variants/{id}/approve` — approve a variant
- `POST /variants/{id}/reject` — reject a variant
- `POST /variants/{id}/schedule` — schedule an approved variant (400 if not approved)
- `GET /publish-history` — view all publish attempts

## SocialPublisher Interface
```
class SocialPublisher(ABC):
    def publish(self, variant: Variant, idempotency_key: str) -> PublishResult
```
Each adapter (TelegramPublisher, MockXPublisher, MockLinkedInPublisher)
implements this interface. The scheduler only calls `.publish()` — it never
knows which platform it's talking to.
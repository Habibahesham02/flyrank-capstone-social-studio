from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.models import init_db, SessionLocal, Post, Variant, ScheduleSlot, PublishAttempt
from datetime import datetime
from app.generator import generate_variant_text
from app.constraints import PROFILES
from dotenv import load_dotenv
load_dotenv()
from app.publisher import publish_slot
import re
import html
import requests

app = FastAPI(title="Social Media Studio")

init_db()

ALL_PLATFORMS = list(PROFILES.keys())  # ["telegram", "mock_x", "mock_linkedin"]


class PostIn(BaseModel):
    source_type: str  # "url" or "markdown"
    content: str


@app.post("/posts")
def create_post(post: PostIn):
    if post.source_type not in ("url", "markdown"):
        raise HTTPException(status_code=400, detail="source_type must be 'url' or 'markdown'")

    content = post.content

    if post.source_type == "url":
        try:
            response = requests.get(post.content, timeout=10, headers={"User-Agent": "SocialMediaStudio/1.0"})
            response.raise_for_status()
        except requests.RequestException as e:
            raise HTTPException(status_code=400, detail=f"Could not fetch URL: {e}")

        # Strip HTML tags to get readable text
        text = re.sub(r"<script.*?</script>", " ", response.text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = html.unescape(text)
        content = re.sub(r"\s+", " ", text).strip()

        if not content:
            raise HTTPException(status_code=400, detail="Fetched URL contained no readable text")

    db = SessionLocal()
    new_post = Post(source_type=post.source_type, content=content)
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    result = {"id": new_post.id, "source_type": new_post.source_type, "content": new_post.content}
    db.close()
    return result


@app.post("/posts/{post_id}/generate")
def generate_variants(post_id: int):
    db = SessionLocal()
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        db.close()
        raise HTTPException(status_code=404, detail="Post not found")

    created = []
    errors = []

    for platform in ALL_PLATFORMS:
        text = generate_variant_text(post.content, platform)
        is_valid, error_message = PROFILES[platform].validate(text)

        if not is_valid:
            errors.append({"platform": platform, "error": error_message})
            continue  # rule-breaking variant never reaches storage/review

        variant = Variant(post_id=post.id, platform=platform, text=text, status="draft")
        db.add(variant)
        db.commit()
        db.refresh(variant)
        created.append({"id": variant.id, "platform": variant.platform, "text": variant.text, "status": variant.status})

    db.close()
    return {"created_variants": created, "blocked_variants": errors}

class VariantEdit(BaseModel):
    text: str


@app.patch("/variants/{variant_id}")
def edit_variant(variant_id: int, edit: VariantEdit):
    db = SessionLocal()
    variant = db.query(Variant).filter(Variant.id == variant_id).first()
    if not variant:
        db.close()
        raise HTTPException(status_code=404, detail="Variant not found")

    is_valid, error_message = PROFILES[variant.platform].validate(edit.text)
    if not is_valid:
        db.close()
        raise HTTPException(status_code=400, detail=error_message)

    variant.text = edit.text
    db.commit()
    db.refresh(variant)
    result = {"id": variant.id, "platform": variant.platform, "text": variant.text, "status": variant.status}
    db.close()
    return result

@app.post("/variants/{variant_id}/approve")
def approve_variant(variant_id: int):
    db = SessionLocal()
    variant = db.query(Variant).filter(Variant.id == variant_id).first()
    if not variant:
        db.close()
        raise HTTPException(status_code=404, detail="Variant not found")

    if variant.status not in ("draft", "rejected"):
        db.close()
        raise HTTPException(status_code=400, detail=f"Cannot approve a variant with status '{variant.status}'")

    variant.status = "approved"
    db.commit()
    db.refresh(variant)
    result = {"id": variant.id, "platform": variant.platform, "status": variant.status}
    db.close()
    return result


@app.post("/variants/{variant_id}/reject")
def reject_variant(variant_id: int):
    db = SessionLocal()
    variant = db.query(Variant).filter(Variant.id == variant_id).first()
    if not variant:
        db.close()
        raise HTTPException(status_code=404, detail="Variant not found")

    if variant.status not in ("draft", "approved"):
        db.close()
        raise HTTPException(status_code=400, detail=f"Cannot reject a variant with status '{variant.status}'")

    variant.status = "rejected"
    db.commit()
    db.refresh(variant)
    result = {"id": variant.id, "platform": variant.platform, "status": variant.status}
    db.close()
    return result
class ScheduleIn(BaseModel):
    scheduled_time: str  # ISO format, e.g. "2026-09-04T15:30:00"


@app.post("/variants/{variant_id}/schedule")
def schedule_variant(variant_id: int, schedule: ScheduleIn):
    db = SessionLocal()
    variant = db.query(Variant).filter(Variant.id == variant_id).first()
    if not variant:
        db.close()
        raise HTTPException(status_code=404, detail="Variant not found")

    if variant.status != "approved":
        db.close()
        raise HTTPException(status_code=400, detail=f"Cannot schedule a variant with status '{variant.status}'. Only approved variants can be scheduled.")

    try:
        scheduled_dt = datetime.fromisoformat(schedule.scheduled_time)
    except ValueError:
        db.close()
        raise HTTPException(status_code=400, detail="scheduled_time must be a valid ISO datetime string")

    idempotency_key = f"variant-{variant.id}-slot-{scheduled_dt.isoformat()}"

    slot = ScheduleSlot(variant_id=variant.id, scheduled_time=scheduled_dt, idempotency_key=idempotency_key)
    db.add(slot)
    db.commit()
    db.refresh(slot)
    result = {"id": slot.id, "variant_id": slot.variant_id, "scheduled_time": slot.scheduled_time.isoformat(), "idempotency_key": slot.idempotency_key}
    db.close()
    return result
@app.post("/schedule-slots/{slot_id}/publish")
def trigger_publish(slot_id: int):
    result = publish_slot(slot_id)
    return {
        "success": result.success,
        "platform_message_id": result.platform_message_id,
        "message_url": result.message_url,
        "error_message": result.error_message,
    }
@app.get("/publish-history")
def get_publish_history():
    db = SessionLocal()
    attempts = db.query(PublishAttempt).order_by(PublishAttempt.attempted_at.desc()).all()
    result = [
        {
            "id": a.id,
            "schedule_slot_id": a.schedule_slot_id,
            "attempted_at": a.attempted_at.isoformat(),
            "result": a.result,
            "platform_message_id": a.platform_message_id,
            "error_message": a.error_message,
             "message_url": a.message_url,
        }
        for a in attempts
    ]
    db.close()
    return result
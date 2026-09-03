from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.models import init_db, SessionLocal, Post, Variant, ScheduleSlot
from datetime import datetime
from app.generator import generate_variant_text
from app.constraints import PROFILES

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

    db = SessionLocal()
    new_post = Post(source_type=post.source_type, content=post.content)
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    db.close()
    return {"id": new_post.id, "source_type": new_post.source_type, "content": new_post.content}


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
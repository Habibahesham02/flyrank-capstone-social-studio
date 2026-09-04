from app.adapters.base import PublishResult
from app.adapters.telegram import TelegramPublisher
from app.adapters.mocks import MockXPublisher, MockLinkedInPublisher
from app.models import SessionLocal, PublishAttempt, ScheduleSlot, Variant

ADAPTERS = {
    "telegram": TelegramPublisher(),
    "mock_x": MockXPublisher(),
    "mock_linkedin": MockLinkedInPublisher(),
}


def publish_slot(slot_id: int) -> PublishResult:
    """
    Idempotently publish the variant tied to a schedule slot.
    Safe to call this function multiple times for the same slot_id —
    if it already has a successful PublishAttempt, it will NOT publish again.
    """
    db = SessionLocal()
    try:
        slot = db.query(ScheduleSlot).filter(ScheduleSlot.id == slot_id).first()
        if not slot:
            return PublishResult(success=False, error_message="Schedule slot not found")

        # IDEMPOTENCY CHECK: has this slot already been successfully published?
        existing_success = (
            db.query(PublishAttempt)
            .filter(PublishAttempt.schedule_slot_id == slot.id, PublishAttempt.result == "success")
            .first()
        )
        if existing_success:
            return PublishResult(
                success=True,
                platform_message_id=existing_success.platform_message_id,
                error_message="Already published (idempotent no-op)",
            )

        variant = db.query(Variant).filter(Variant.id == slot.variant_id).first()
        adapter = ADAPTERS[variant.platform]

        result = adapter.publish(variant.text, slot.idempotency_key)

        attempt = PublishAttempt(
            schedule_slot_id=slot.id,
            result="success" if result.success else "failure",
            platform_message_id=result.platform_message_id,
            error_message=result.error_message,
        )
        db.add(attempt)

        if result.success:
            variant.status = "published"

        db.commit()
        return result
    finally:
        db.close()
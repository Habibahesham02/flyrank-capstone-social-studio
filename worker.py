import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from app.models import SessionLocal, ScheduleSlot, PublishAttempt
from app.publisher import publish_slot

POLL_INTERVAL_SECONDS = 5


def find_due_unpublished_slots():
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        all_slots = db.query(ScheduleSlot).filter(ScheduleSlot.scheduled_time <= now).all()

        due_slot_ids = []
        for slot in all_slots:
            already_done = (
                db.query(PublishAttempt)
                .filter(PublishAttempt.schedule_slot_id == slot.id, PublishAttempt.result == "success")
                .first()
            )
            if not already_done:
                due_slot_ids.append(slot.id)
        return due_slot_ids
    finally:
        db.close()


def run_worker():
    print("Worker started. Polling for due, unpublished schedule slots...")
    while True:
        due_ids = find_due_unpublished_slots()
        for slot_id in due_ids:
            print(f"Publishing slot {slot_id}...")
            result = publish_slot(slot_id)
            print(f"  -> success={result.success} message_id={result.platform_message_id} error={result.error_message}")
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_worker()
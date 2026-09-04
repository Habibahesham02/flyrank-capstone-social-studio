import uuid
from app.adapters.base import SocialPublisher, PublishResult


class MockXPublisher(SocialPublisher):
    def publish(self, text: str, idempotency_key: str) -> PublishResult:
        fake_id = f"mock_x_{uuid.uuid4().hex[:10]}"
        print(f"[MockX PREVIEW] Would post to X:\n  {text}\n  (id: {fake_id})")
        return PublishResult(success=True, platform_message_id=fake_id)


class MockLinkedInPublisher(SocialPublisher):
    def publish(self, text: str, idempotency_key: str) -> PublishResult:
        fake_id = f"mock_linkedin_{uuid.uuid4().hex[:10]}"
        print(f"[MockLinkedIn PREVIEW] Would post to LinkedIn:\n  {text}\n  (id: {fake_id})")
        return PublishResult(success=True, platform_message_id=fake_id)
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class PublishResult:
    success: bool
    platform_message_id: Optional[str] = None
    error_message: Optional[str] = None


class SocialPublisher(ABC):
    @abstractmethod
    def publish(self, text: str, idempotency_key: str) -> PublishResult:
        """
        Publish the given text. Must be safe to call multiple times with the
        same idempotency_key — a repeated call with a key that was already
        successfully published must NOT create a second post.
        """
        raise NotImplementedError
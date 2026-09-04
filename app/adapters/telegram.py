import os
import requests
from app.adapters.base import SocialPublisher, PublishResult


class TelegramPublisher(SocialPublisher):
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")

    def publish(self, text: str, idempotency_key: str) -> PublishResult:
        if not self.token or not self.chat_id:
            return PublishResult(success=False, error_message="Telegram credentials not configured")

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text}

        try:
            response = requests.post(url, json=payload, timeout=10)
            data = response.json()

            if response.status_code == 200 and data.get("ok"):
                result_data = data["result"]
                message_id = str(result_data["message_id"])

                # Build a public link to the message where possible.
                chat = result_data.get("chat", {})
                username = chat.get("username")
                if username:
                    link = f"https://t.me/{username}/{message_id}"
                else:
                    # Private channels: strip the -100 prefix for the t.me/c/ form
                    numeric_id = str(chat.get("id", "")).replace("-100", "", 1)
                    link = f"https://t.me/c/{numeric_id}/{message_id}" if numeric_id else None

                return PublishResult(success=True, platform_message_id=message_id, message_url=link)
            else:
                error = data.get("description", "Unknown Telegram API error")
                return PublishResult(success=False, error_message=error)

        except requests.RequestException as e:
            return PublishResult(success=False, error_message=str(e))
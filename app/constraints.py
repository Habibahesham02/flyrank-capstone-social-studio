class ConstraintProfile:
    def __init__(self, platform, max_length, max_hashtags, tone, banned_words=None):
        self.platform = platform
        self.max_length = max_length
        self.max_hashtags = max_hashtags
        self.tone = tone
        self.banned_words = banned_words or []

    def validate(self, text: str):
        """Returns (is_valid, error_message). error_message is None if valid."""
        if len(text) > self.max_length:
            return False, f"{self.platform}: text exceeds max length of {self.max_length} characters (got {len(text)})"

        hashtag_count = text.count("#")
        if hashtag_count > self.max_hashtags:
            return False, f"{self.platform}: too many hashtags, max {self.max_hashtags} allowed (got {hashtag_count})"

        lowered = text.lower()
        for word in self.banned_words:
            if word in lowered:
                return False, f"{self.platform}: tone rule violated — '{word}' is not allowed on a {self.tone} platform"

        return True, None


PROFILES = {
    "telegram": ConstraintProfile(
        "telegram", max_length=4096, max_hashtags=10, tone="neutral"
    ),
    "mock_x": ConstraintProfile(
        "mock_x", max_length=280, max_hashtags=2, tone="casual"
    ),
    "mock_linkedin": ConstraintProfile(
        "mock_linkedin",
        max_length=3000,
        max_hashtags=3,
        tone="professional",
        banned_words=["lol", "omg", "wtf", "lmao", "gonna", "wanna"],
    ),
}
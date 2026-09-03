class ConstraintProfile:
    def __init__(self, platform, max_length, max_hashtags):
        self.platform = platform
        self.max_length = max_length
        self.max_hashtags = max_hashtags

    def validate(self, text: str):
        """Returns (is_valid, error_message). error_message is None if valid."""
        if len(text) > self.max_length:
            return False, f"{self.platform}: text exceeds max length of {self.max_length} characters (got {len(text)})"

        hashtag_count = text.count("#")
        if hashtag_count > self.max_hashtags:
            return False, f"{self.platform}: too many hashtags, max {self.max_hashtags} allowed (got {hashtag_count})"

        return True, None


PROFILES = {
    "telegram": ConstraintProfile("telegram", max_length=4096, max_hashtags=10),
    "mock_x": ConstraintProfile("mock_x", max_length=280, max_hashtags=2),
    "mock_linkedin": ConstraintProfile("mock_linkedin", max_length=3000, max_hashtags=3),
}
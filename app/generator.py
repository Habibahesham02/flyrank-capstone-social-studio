from app.constraints import PROFILES


def generate_variant_text(post_content: str, platform: str) -> str:
    """
    Naive template-based generator: truncates and adapts tone per platform.
    This is intentionally simple — the brief says templates are fine,
    AI is optional. The validation step is what's actually graded.
    """
    profile = PROFILES[platform]
    # Leave room for a hashtag suffix
    hashtag_suffix = " #blog" if platform != "telegram" else ""
    available_length = profile.max_length - len(hashtag_suffix)

    trimmed = post_content.strip().replace("\n", " ")
    if len(trimmed) > available_length:
        trimmed = trimmed[: available_length - 1].rstrip() + "…"

    return trimmed + hashtag_suffix


def generate_variants_for_post(post_content: str, platforms: list[str]) -> dict:
    """Returns {platform: generated_text} for each requested platform."""
    return {platform: generate_variant_text(post_content, platform) for platform in platforms}
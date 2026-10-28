"""Safe, actionable failures which must not be retried through other providers."""

YOUTUBE_ACCESS_REQUIRED = (
    "YouTube requires sign-in or human verification "
    "before this video can be downloaded. Obtain the original video file "
    "and upload it locally to continue."
)


class YouTubeAccessRequired(RuntimeError):
    code = "youtube_access_required"

    def __init__(self):
        # Do not copy provider errors, cookie paths or signed URLs to the UI.
        super().__init__(YOUTUBE_ACCESS_REQUIRED)


def requires_youtube_verification(error: BaseException) -> bool:
    message = str(error).lower().replace("\u2019", "'")
    return "confirm you're not a bot" in message or "captcha" in message

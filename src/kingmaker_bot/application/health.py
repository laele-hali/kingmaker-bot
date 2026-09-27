"""Small application responses that can be used by transport adapters."""


def ping_response() -> str:
    """Return the response for a bot health check."""
    return "Pong!"

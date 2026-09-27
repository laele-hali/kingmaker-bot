from kingmaker_bot.application.health import ping_response


def test_ping_response() -> None:
    assert ping_response() == "Pong!"

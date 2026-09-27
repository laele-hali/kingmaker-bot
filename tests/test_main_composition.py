from kingmaker_bot import main


def test_main_wires_both_repositories_to_configured_database(monkeypatch, tmp_path) -> None:
    path = str(tmp_path / "campaign.sqlite3")
    calls = {}

    class Repository:
        def __init__(self, database_path):
            calls.setdefault("paths", []).append(database_path)

    class Engine:
        def __init__(self, profile):
            calls["profile"] = profile

    class Service:
        def __init__(self, repository, engines):
            calls["weather_repository"] = repository
            calls["engines"] = engines

    class PredictionService:
        def __init__(self, repository, weather_service, profile_id):
            calls["prediction_repository"] = repository
            calls["prediction_weather_service"] = weather_service
            calls["prediction_profile_id"] = profile_id

    class Bot:
        def run(self, token):
            calls["token"] = token

    def create_bot(campaign_repository, weather_service, prediction_service):
        calls["campaign_repository"] = campaign_repository
        calls["weather_service"] = weather_service
        calls["prediction_service"] = prediction_service
        return Bot()

    monkeypatch.setenv("DISCORD_BOT_TOKEN", "test-token")
    monkeypatch.setenv("KINGMAKER_DATABASE_PATH", path)
    monkeypatch.setattr(main, "SQLiteCampaignStateRepository", Repository)
    monkeypatch.setattr(main, "SQLiteWeatherRepository", Repository)
    monkeypatch.setattr(main, "SQLitePredictionRepository", Repository)
    monkeypatch.setattr(main, "WeatherEngine", Engine)
    monkeypatch.setattr(main, "WeatherService", Service)
    monkeypatch.setattr(main, "PredictWeatherService", PredictionService)
    monkeypatch.setattr(main, "create_bot", create_bot)

    main.main()

    assert calls["paths"] == [path, path, path]
    assert calls["engines"][main.PROFILE_ID] is not None
    assert calls["prediction_weather_service"] is calls["weather_service"]
    assert calls["prediction_profile_id"] == main.PROFILE_ID
    assert calls["prediction_service"] is not None
    assert calls["token"] == "test-token"

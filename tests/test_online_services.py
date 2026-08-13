from __future__ import annotations

import json

from voice_assistant.config import OnlineServicesConfig
from voice_assistant.online_services import OnlineServices, online_phrases


def config(**overrides) -> OnlineServicesConfig:
    values = dict(weather_enabled=True, wikipedia_enabled=True, location_name="Tbilisi",
                  latitude=41.7151, longitude=44.8271, request_timeout_seconds=10.0,
                  query_timeout_seconds=12.0, max_answer_characters=100)
    values.update(overrides)
    return OnlineServicesConfig(**values)


class Response:
    def __init__(self, payload): self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *args): return None
    def read(self): return json.dumps(self.payload).encode()


def test_disabled_modules_add_no_phrases() -> None:
    assert online_phrases("ka", config(weather_enabled=False, wikipedia_enabled=False)) == {}


def test_weather_formats_georgian_result() -> None:
    service = OnlineServices(config())
    service._opener = type("O", (), {"open": lambda self, req, timeout: Response({"current": {
        "temperature_2m": 25, "apparent_temperature": 26, "relative_humidity_2m": 40,
        "precipitation": 0, "wind_speed_10m": 8}})})()
    title, answer = service.weather("ka")
    assert "Tbilisi" in title
    assert "25°C" in answer


def test_wikipedia_uses_language_domain_and_limits_answer() -> None:
    service = OnlineServices(config(max_answer_characters=20))
    opener = type("O", (), {})()
    def open_request(req, timeout):
        assert req.full_url.startswith("https://ka.wikipedia.org/w/api.php?")
        return Response({"query": {"pages": [{"title": "თბილისი", "extract": "ა" * 50}]}})
    opener.open = open_request
    service._opener = opener
    title, answer = service.wikipedia("თბილისი", "ka")
    assert title == "თბილისი"
    assert len(answer) == 20

from __future__ import annotations

from dataclasses import dataclass
import json
import ssl
import certifi
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

from .config import OnlineServicesConfig


@dataclass(frozen=True)
class OnlineServiceAction:
    kind: str
    name: str


WEATHER = OnlineServiceAction("weather", "Current weather")
WIKIPEDIA = OnlineServiceAction("wikipedia", "Wikipedia lookup")


def online_phrases(language: str, config: OnlineServicesConfig) -> dict[str, OnlineServiceAction]:
    result: dict[str, OnlineServiceAction] = {}
    if config.weather_enabled:
        phrases = {"რა ამინდია", "მითხარი ამინდი", "ამინდი"} if language == "ka" else {"weather", "current weather", "what is the weather"}
        result.update({phrase: WEATHER for phrase in phrases})
    if config.wikipedia_enabled:
        phrases = {"მოძებნე ვიკიპედიაში", "ვიკიპედია"} if language == "ka" else {"search wikipedia", "wikipedia lookup"}
        result.update({phrase: WIKIPEDIA for phrase in phrases})
    return result


class OnlineServices:
    def __init__(self, config: OnlineServicesConfig) -> None:
        self.config = config
        tls_context = ssl.create_default_context(cafile=certifi.where())
        self._opener = build_opener(ProxyHandler({}), HTTPSHandler(context=tls_context))

    def _json(self, url: str) -> dict:
        request = Request(url, headers={"User-Agent": "GelaVoiceAssistant/0.1"})
        try:
            with self._opener.open(request, timeout=self.config.request_timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(f"Online service returned HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError("Internet service is unavailable") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("Online service returned invalid data") from exc

    def weather(self, language: str) -> tuple[str, str]:
        params = urlencode({
            "latitude": self.config.latitude,
            "longitude": self.config.longitude,
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m",
            "timezone": "auto",
        })
        current = self._json(f"https://api.open-meteo.com/v1/forecast?{params}").get("current", {})
        required = ("temperature_2m", "apparent_temperature", "relative_humidity_2m", "precipitation", "wind_speed_10m")
        if any(key not in current for key in required):
            raise RuntimeError("Weather service omitted required current conditions")
        place = self.config.location_name
        if language == "ka":
            answer = (f"{place}: {current['temperature_2m']}°C, შეგრძნებით {current['apparent_temperature']}°C; "
                      f"ტენიანობა {current['relative_humidity_2m']}%; ნალექი {current['precipitation']} მმ; "
                      f"ქარი {current['wind_speed_10m']} კმ/სთ.")
            question = f"ამინდი — {place}"
        else:
            answer = (f"{place}: {current['temperature_2m']}°C, feels like {current['apparent_temperature']}°C; "
                      f"humidity {current['relative_humidity_2m']}%; precipitation {current['precipitation']} mm; "
                      f"wind {current['wind_speed_10m']} km/h.")
            question = f"Weather — {place}"
        return question, answer

    def wikipedia(self, query: str, language: str) -> tuple[str, str]:
        wiki_language = "ka" if language == "ka" else "en"
        params = urlencode({"action": "query", "generator": "search", "gsrsearch": query,
                            "gsrlimit": 1, "prop": "extracts", "exintro": 1, "explaintext": 1,
                            "format": "json", "formatversion": 2, "origin": "*"})
        payload = self._json(f"https://{wiki_language}.wikipedia.org/w/api.php?{params}")
        pages = payload.get("query", {}).get("pages", [])
        if not pages or not str(pages[0].get("extract", "")).strip():
            raise RuntimeError("Wikipedia found no summary")
        title = str(pages[0].get("title", query))
        answer = " ".join(str(pages[0]["extract"]).split())[: self.config.max_answer_characters]
        return title, answer

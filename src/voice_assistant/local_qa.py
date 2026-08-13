from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import ProxyHandler, Request, build_opener

from .config import QuestionAnsweringConfig, USER_DATA_ROOT
from .storage import atomic_write_text


LAST_ANSWER_PATH = USER_DATA_ROOT / "runtime" / "last_answer.json"
LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


@dataclass(frozen=True)
class QuestionModeAction:
    name: str = "Local question"


QUESTION_MODE = QuestionModeAction()


def question_phrases(language: str) -> dict[str, QuestionModeAction]:
    if language == "ka":
        phrases = {"კითხვა მაქვს", "მიპასუხე კითხვაზე", "მინდა კითხვა დაგისვა"}
    elif language == "en":
        phrases = {"i have a question", "answer a question", "let me ask a question"}
    else:
        raise ValueError(f"Unsupported question language: {language}")
    return {phrase: QUESTION_MODE for phrase in phrases}


def validate_local_endpoint(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    if parsed.scheme != "http" or parsed.hostname not in LOCAL_HOSTS:
        raise ValueError("Local Q&A endpoint must use HTTP on localhost")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Local Q&A endpoint contains unsupported URL components")
    if parsed.path.rstrip("/") != "/api/generate":
        raise ValueError("Local Q&A endpoint must end with /api/generate")
    return endpoint


class LocalQuestionAnswerer:
    def __init__(self, config: QuestionAnsweringConfig) -> None:
        self.config = config
        self.endpoint = validate_local_endpoint(config.endpoint)
        if not config.model.strip():
            raise ValueError("Local Q&A model name is empty")
        self._opener = build_opener(ProxyHandler({}))

    def ask(self, question: str) -> str:
        question = " ".join(question.split())
        if not question:
            raise ValueError("Question is empty")
        payload = json.dumps(
            {
                "model": self.config.model,
                "prompt": question,
                "system": (
                    "You are Gela, a concise desktop assistant. Answer in the same language as "
                    "the question. If unsure, say so. Do not claim to have performed computer actions."
                ),
                "stream": False,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = Request(
            self.endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._opener.open(request, timeout=self.config.request_timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(f"Local model returned HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError("Local model service is not running") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("Local model returned an invalid response") from exc
        answer = " ".join(str(raw.get("response", "")).split())
        if not answer:
            raise RuntimeError("Local model returned an empty answer")
        return answer[: self.config.max_answer_characters]


def save_answer(
    question: str,
    answer: str,
    path: Path = LAST_ANSWER_PATH,
    *,
    window_title: str = "Gela — პასუხი",
    source: str = "ლოკალური მოდელი",
) -> Path:
    atomic_write_text(
        path,
        json.dumps(
            {"question": question, "answer": answer, "window_title": window_title, "source": source},
            ensure_ascii=False,
            indent=2,
        ) + "\n",
    )
    return path


def open_answer_window(path: Path = LAST_ANSWER_PATH) -> None:
    command = (
        [sys.executable, "--answer-window", str(path)]
        if getattr(sys, "frozen", False)
        else [sys.executable, "-m", "voice_assistant.answer_window", str(path)]
    )
    subprocess.Popen(command, close_fds=True)

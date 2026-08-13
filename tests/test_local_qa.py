from __future__ import annotations

import json

import pytest

from voice_assistant.config import QuestionAnsweringConfig
from voice_assistant.local_qa import (
    LocalQuestionAnswerer,
    question_phrases,
    save_answer,
    validate_local_endpoint,
)


def qa_config(**overrides) -> QuestionAnsweringConfig:
    values = {
        "enabled": True,
        "endpoint": "http://127.0.0.1:11434/api/generate",
        "model": "test-model",
        "request_timeout_seconds": 10.0,
        "question_timeout_seconds": 12.0,
        "max_answer_characters": 100,
    }
    values.update(overrides)
    return QuestionAnsweringConfig(**values)


def test_endpoint_is_restricted_to_localhost() -> None:
    assert validate_local_endpoint("http://localhost:11434/api/generate")
    assert validate_local_endpoint("http://[::1]:11434/api/generate")
    with pytest.raises(ValueError):
        validate_local_endpoint("https://example.com/api/generate")
    with pytest.raises(ValueError):
        validate_local_endpoint("http://127.0.0.1:11434/api/chat")


def test_question_phrases_are_explicit() -> None:
    assert "კითხვა მაქვს" in question_phrases("ka")
    assert "i have a question" in question_phrases("en")


def test_answer_request_is_non_streaming_and_bounded() -> None:
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps({"response": "ა" * 150}).encode("utf-8")

    class Opener:
        request = None

        def open(self, request, timeout):
            self.request = request
            assert timeout == 10.0
            return Response()

    answerer = LocalQuestionAnswerer(qa_config())
    opener = Opener()
    answerer._opener = opener
    answer = answerer.ask("  რა   დროა? ")
    request_payload = json.loads(opener.request.data.decode("utf-8"))
    assert request_payload["prompt"] == "რა დროა?"
    assert request_payload["stream"] is False
    assert len(answer) == 100


def test_save_answer_overwrites_single_runtime_snapshot(tmp_path) -> None:
    path = tmp_path / "answer.json"
    save_answer("კითხვა", "პასუხი", path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["question"] == "კითხვა"
    assert payload["answer"] == "პასუხი"
    assert payload["source"] == "ლოკალური მოდელი"

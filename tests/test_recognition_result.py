from voice_assistant.recognizer import (
    RecognitionResult,
    canonicalize_georgian_command,
    combine_recognition_results,
    decode_result,
    matched_phrase_confidence,
    split_wake_command,
)


def test_decode_result_uses_conservative_minimum_word_confidence() -> None:
    result = decode_result(
        '{"text":"გახსენი ქრომი","result":[{"word":"გახსენი","conf":0.91},{"word":"ქრომი","conf":0.72}]}'
    )
    assert result.text == "გახსენი ქრომი"
    assert result.confidence == 0.72


def test_one_sentence_wake_and_command_have_independent_confidence() -> None:
    result = decode_result(
        '{"text":"გელა გახსენი ქრომი","result":['
        '{"word":"გელა","conf":0.93},'
        '{"word":"გახსენი","conf":0.81},'
        '{"word":"ქრომი","conf":0.74}]}'
    )

    split = split_wake_command(result, ["გელა"])

    assert split is not None
    wake, wake_confidence, command = split
    assert wake == "გელა"
    assert wake_confidence == 0.93
    assert command.text == "გახსენი ქრომი"
    assert command.confidence == 0.74


def test_wake_split_requires_exact_prefix() -> None:
    result = decode_result(
        '{"text":"გახსენი გელა ქრომი","result":['
        '{"word":"გახსენი","conf":0.9},{"word":"გელა","conf":0.9},'
        '{"word":"ქრომი","conf":0.9}]}'
    )

    assert split_wake_command(result, ["გელა"]) is None


def test_complete_embedded_phrase_ignores_surrounding_decoder_noise() -> None:
    result = decode_result(
        '{"text":"more to night rain please","result":['
        '{"word":"more","conf":0.31},{"word":"to","conf":0.42},'
        '{"word":"night","conf":0.91},{"word":"rain","conf":0.88},'
        '{"word":"please","conf":0.37}]}'
    )

    assert matched_phrase_confidence(result, "night rain") == 0.88
    assert matched_phrase_confidence(result, "night") == 0.91
    assert matched_phrase_confidence(result, "rain night") == 0.0


def test_one_sentence_decoder_segments_are_joined_before_wake_split() -> None:
    wake = decode_result(
        '{"text":"გელა","result":[{"word":"გელა","conf":0.96}]}'
    )
    command = decode_result(
        '{"text":"გახსენი ქრომი","result":['
        '{"word":"გახსენი","conf":0.88},{"word":"ქრომი","conf":0.79}]}'
    )

    combined = combine_recognition_results([wake, command])
    split = split_wake_command(combined, ["გელა"])

    assert split is not None
    assert split[1] == 0.96
    assert split[2].text == "გახსენი ქრომი"
    assert split[2].confidence == 0.79


def test_formal_georgian_command_verb_is_canonicalized() -> None:
    result = RecognitionResult(
        "ჩართეთ თამაშების ბიბლიოთეკა",
        0.84,
        (("ჩართეთ", 0.9), ("თამაშების", 0.84), ("ბიბლიოთეკა", 0.91)),
    )

    canonical = canonicalize_georgian_command(result)

    assert canonical.text == "ჩართე თამაშების ბიბლიოთეკა"
    assert canonical.words[0] == ("ჩართე", 0.9)

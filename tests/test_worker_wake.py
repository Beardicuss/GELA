from voice_assistant.recognizer import decode_result, split_wake_command


def test_wake_word_in_middle_of_dialogue_does_not_activate_gela() -> None:
    result = decode_result(
        '{"text":"დილა გელა გელაშვილი დედამ მომცა","result":['
        '{"word":"დილა","conf":0.97911},'
        '{"word":"გელა","conf":0.997568},'
        '{"word":"გელაშვილი","conf":0.900597},'
        '{"word":"დედამ","conf":0.52669},'
        '{"word":"მომცა","conf":0.257014}]}'
    )

    assert split_wake_command(result, ["გელა"]) is None


def test_exact_prefix_still_activates_with_high_confidence() -> None:
    result = decode_result(
        '{"text":"გელა გახსენი სტიმი","result":['
        '{"word":"გელა","conf":0.96},'
        '{"word":"გახსენი","conf":0.80},'
        '{"word":"სტიმი","conf":0.79}]}'
    )

    split = split_wake_command(result, ["გელა"])
    assert split is not None
    assert split[1] >= 0.90
    assert split[2].text == "გახსენი სტიმი"


def test_similar_word_does_not_count_as_exact_wake() -> None:
    result = decode_result(
        '{"text":"გელაშვილი","result":['
        '{"word":"გელაშვილი","conf":0.99}]}'
    )

    assert split_wake_command(result, ["გელა"]) is None

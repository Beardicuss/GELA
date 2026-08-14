from voice_assistant.recognizer import decode_result
from voice_assistant.worker import exact_embedded_wake


def test_exact_wake_survives_captured_georgian_decoder_noise() -> None:
    result = decode_result(
        '{"text":"დილა გელა გელაშვილი დედამ მომცა","result":['
        '{"word":"დილა","conf":0.97911},'
        '{"word":"გელა","conf":0.997568},'
        '{"word":"გელაშვილი","conf":0.900597},'
        '{"word":"დედამ","conf":0.52669},'
        '{"word":"მომცა","conf":0.257014}]}'
    )

    assert exact_embedded_wake(result, ["გელა"], 0.75) == ("გელა", 0.997568)


def test_similar_word_does_not_count_as_exact_wake() -> None:
    result = decode_result(
        '{"text":"გელაშვილი","result":['
        '{"word":"გელაშვილი","conf":0.99}]}'
    )

    assert exact_embedded_wake(result, ["გელა"], 0.75) is None


def test_low_confidence_embedded_wake_is_rejected() -> None:
    result = decode_result(
        '{"text":"დილა გელა","result":['
        '{"word":"დილა","conf":0.91},{"word":"გელა","conf":0.64}]}'
    )

    assert exact_embedded_wake(result, ["გელა"], 0.75) is None

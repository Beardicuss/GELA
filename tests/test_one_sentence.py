from voice_assistant.catalog import CatalogEntry
from voice_assistant.recognizer import RecognitionResult
from voice_assistant.worker import BackgroundAssistant


def test_mixed_one_sentence_candidate_scores_verb_and_registered_english_alias() -> None:
    game = CatalogEntry(
        "ELDEN RING NIGHTREIGN",
        ["ნაითრეინი"],
        "uri",
        "steam://rungameid/2622380",
    )
    assistant = object.__new__(BackgroundAssistant)
    assistant.phrases = {}
    assistant.english_phrases = {}
    assistant.english_targets = {"night rain": game}
    assistant.english_close_targets = {}
    assistant.english_window_targets = {}
    ka_result = RecognitionResult(
        "გახსენი მაჩვენე",
        0.41,
        (("გახსენი", 0.92), ("მაჩვენე", 0.41)),
    )
    en_result = RecognitionResult(
        "more to night rain",
        0.38,
        (("more", 0.38), ("to", 0.44), ("night", 0.9), ("rain", 0.86)),
    )

    candidates = assistant._command_candidates(ka_result, en_result)

    assert len(candidates) == 1
    assert candidates[0].entry is game
    assert candidates[0].language == "ka+en"
    assert candidates[0].confidence == 0.86


def test_formal_one_sentence_launch_verb_matches_direct_command() -> None:
    steam = CatalogEntry("Steam", ["თამაშების ბიბლიოთეკა"], "app_id", "steam")
    assistant = object.__new__(BackgroundAssistant)
    assistant.phrases = {"ჩართე თამაშების ბიბლიოთეკა": steam}
    assistant.english_phrases = {}
    assistant.english_targets = {}
    assistant.english_close_targets = {}
    assistant.english_window_targets = {}

    candidates = assistant._command_candidates(
        RecognitionResult("ჩართეთ თამაშების ბიბლიოთეკა", 0.91),
        RecognitionResult("", 0.0),
    )

    assert len(candidates) == 1
    assert candidates[0].entry is steam


def test_unique_close_georgian_transcription_resolves_to_registered_steam() -> None:
    steam = CatalogEntry("Steam", ["სთიმი", "თიმი"], "app_id", "steam")
    movies = CatalogEntry("Movies & TV", ["ფილმები"], "app_id", "movies")
    phrases = {
        "გახსენი სთიმი": steam,
        "გახსენი თიმი": steam,
        "გახსენი ფილმები": movies,
    }

    candidates = BackgroundAssistant._fuzzy_command_candidates(
        RecognitionResult("გახსენის თიმი", 1.0),
        phrases,
        "ka",
    )

    assert len(candidates) == 1
    assert candidates[0].entry is steam
    assert candidates[0].result.text == "გახსენი თიმი"

from voice_assistant.ambient import AmbientMoodMonitor, mood_for_idle_seconds


def test_idle_time_maps_to_ambient_moods():
    assert mood_for_idle_seconds(0) == "ATTENTIVE"
    assert mood_for_idle_seconds(59.9) == "ATTENTIVE"
    assert mood_for_idle_seconds(60) == "CALM"
    assert mood_for_idle_seconds(299.9) == "CALM"
    assert mood_for_idle_seconds(300) == "SLEEPY"
    assert mood_for_idle_seconds(419.9) == "SLEEPY"
    assert mood_for_idle_seconds(420) == "AWAY"


def test_monitor_keeps_last_mood_when_windows_query_temporarily_fails():
    readings = iter((301.0, OSError("unavailable")))

    def idle_supplier():
        value = next(readings)
        if isinstance(value, Exception):
            raise value
        return value

    monitor = AmbientMoodMonitor(idle_supplier)
    assert monitor.snapshot() == "SLEEPY"
    assert monitor.snapshot() == "SLEEPY"

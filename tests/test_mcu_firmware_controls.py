from pathlib import Path


def test_board_firmware_exposes_only_requested_controls():
    source = Path("mcu/mpython_board_3_face/firmware/face_animation.py").read_text(encoding="utf-8")
    assert "wifi.push_to_talk()" in source
    assert "audio.record(RECORDING_PATH,4)" in source
    assert "_thread" not in source
    assert 'wifi.action("toggle-mute")' in source
    assert "touchPad_" not in source
    assert 'wifi.action("cancel")' not in source
    assert "show_health" not in source
    assert "show_activity" not in source
    assert 'AMBIENT_MOODS=("ATTENTIVE","CALM","SLEEPY","AWAY")' in source
    assert 'status.get("ambientMood","ATTENTIVE")' in source
    assert 'self.draw("idle_blink.png"); self._schedule(now,180)' in source
    assert 'self.last_filename=="idle_0.png"' in source
    assert 'self.last_filename=="calm_0.png"' in source
    assert '"idle_3.png"' not in source
    assert '("sleepy.png",)' in source
    assert '("sleeping.png",)' in source
    assert 'CALM_SEQUENCE=("calm_0.png","idle_1.png","calm_0.png","idle_2.png")' in source

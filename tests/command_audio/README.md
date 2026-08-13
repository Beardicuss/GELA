# Command audio regression samples

Place manually recorded command samples here as mono, 16-bit PCM, 16 kHz WAV files. Keep the filename descriptive, for example `ka_open_chrome_01.wav` or `en_steam_ambient_noise_01.wav`.

Run an individual sample with:

```powershell
.\.venv\Scripts\voice-assistant.exe test-command-audio tests\command_audio\ka_open_chrome_01.wav --language ka
```

Keep both expected commands and negative/background-noise samples. Do not commit recordings containing private conversation.

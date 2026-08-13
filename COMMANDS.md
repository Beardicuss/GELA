# Gela voice-command reference

Every command requires the `გელა` wake word. Use the normal `გელა` → `გისმენ` → command flow, or enable one-sentence mode in settings.

Gela accepts bounded natural variants without fuzzy target guessing. For example, these all resolve to the same catalog entry:

- `გახსენი ქრომი`
- `ქრომი გახსენი`
- `გთხოვ გახსენი ქრომი`
- `თუ შეიძლება გახსენი ქრომი`
- `შეგიძლია ქრომი გახსნა`
- `მინდა ქრომი გახსნა`

English catalog aliases accept forms such as `steam`, `open steam`, `launch steam`, `please open steam`, and `can you open steam`. Add semantic target words such as `ინტერნეტი` through the Alias Manager; Gela expands them locally but never guesses which application a new word should mean.

Mixed Georgian/English launch commands are also supported. When the Georgian model recognizes a launch verb and the parallel English model finds a complete registered product alias, Gela combines them safely. For example, spoken `ჩართე ნაითრეინი` may be resolved as Georgian `ჩართე` plus English `night rain`, even when the small Georgian model cannot spell the product name.

When **ერთ წინადადებაში ბრძანებები** is enabled in settings, the wake word and a normal immediate command can be spoken without a pause: `გელა გახსენი ქრომი`, `გელა ჩართე steam`, or `გელა დამალე discord`. Gela independently checks the exact wake prefix and the command confidence. If the remainder is unclear or activates a follow-up mode such as questions or Wikipedia, Gela says `გისმენ` and continues with the existing two-stage flow.

The tray's **მეტყველების ამოცნობის ტესტი** window records one temporary four-second sample for recognition diagnostics. No test recording is saved.

Use **აპლიკაციების მართვის პროფილები** when automatic discovery is not correct for a specific application. Preferred process names replace inferred and learned targets for that entry; additional title fragments improve focus/window matching. Close behavior can allow the normal graceful-then-background-force policy, prohibit force termination, or use only matching windows. The same window edits Georgian and English aliases with ownership checks.

The success response means Gela observed stable launch evidence, not merely that Windows accepted a launch request. It waits up to 12 seconds for normal applications and 45 seconds for Steam games. If the expected process or application window does not appear, Gela reports failure.

If the requested application/game is already running, Gela does not launch it again. If a complete-close target is already stopped, Gela treats that as an already-satisfied state instead of a failure. The same rule applies when Wi-Fi or Bluetooth is already in the requested on/off state. The exact state is shown in Diagnostics and logs.

## Applications

- `გახსენი ქრომი`
- `გახსენი კალკულატორი`
- `გახსენი თამაშების ბიბლიოთეკა`
- `დახურე ქრომი`
- `გათიშე ქრომი`
- `გამორთე თამაშების ბიბლიოთეკა`

Close commands are generated for the complete application catalog. Gela uses explicit process mappings when available, infers executable process names from Start-menu entries, and can discover a process from a matching visible window when no mapping exists. It first requests normal closure and verifies process exit. If an application hides in the tray with no visible save/confirmation dialog, the remaining background process is stopped; if a visible unsaved-work dialog remains, Gela leaves the process alive for the user to answer.

Successful launches can teach Gela a previously unknown process automatically. The process must be stable launch evidence; for window-discovered applications, its visible title must match the catalog entry and its owning process must have started after the command. Learned mappings are saved in the user data folder and used immediately by close and named-window operations.

Installed Steam games gain process targets automatically from their installation directories. Mixed Georgian/English forms work for complete closure as well as launch, including `გამორთე ნაითრეინი`, `გათიშე ნაითრეინი`, and `დახურე ნაითრეინი`. Gela closes the game executable and does not shut down Steam.

During a Steam launch, Gela tracks shared launcher processes, anti-cheat/bootstrap processes, and the real gameplay executable as separate lifecycle roles. Steam or an anti-cheat splash process cannot by itself produce the success response. Complete-close uses only verified gameplay targets and explicitly excludes the shared launcher and bootstrap roles.

## Window control

For applications in the complete catalog:

- `მაჩვენე ქრომი` — switch to and focus Chrome
- `დამალე ქრომი` — minimize Chrome
- `ჩაკეცე ქრომი` — minimize Chrome
- `გაზარდე ქრომი` — maximize Chrome
- `გაადიდე ქრომი` — maximize Chrome
- `აღადგინე ქრომი` — restore Chrome
- `ამოკეცე ქრომი` — restore Chrome
- `დააპატარავე ქრომი` — return Chrome from maximized size

The same operations are available for the currently active window:

- `დამალე ფანჯარა`
- `ჩაკეცე`
- `გაზარდე ფანჯარა`
- `გაადიდე`
- `აღადგინე ფანჯარა`
- `ამოკეცე`
- `დააპატარავე`

English forms include `switch to chrome`, `focus chrome`, `minimize chrome`, `maximize chrome`, and `restore chrome`. Mixed Georgian/English forms are also supported for every named-window operation. Omnilingual ASR recognizes the natural Georgian forms without requiring them to exist in Vosk's dictionary. Named window operations use explicit or inferred executable process mappings and fall back to matching a visible catalog window title.

## Folders

- `გახსენი ჩამოტვირთვები`
- `გახსენი დოკუმენტები`
- `გახსენი სურათები`
- `გახსენი დესკტოპი`
- `გახსენი მუსიკა`
- `გახსენი ვიდეო`
- `გახსენი ნაგვის კალათა`

## Sound

- `ხმა აუწიე`
- `ხმას აუწიე`
- `ხმა დაუწიე`
- `ხმას დაუწიე`
- `ხმა გამორთე`
- `ხმა გათიშე`
- `ხმა ჩართე`

Mute and unmute use the same Windows toggle. The result depends on the current mute state.

## Media playback

- `დაუკარი მუსიკა` — play/pause toggle
- `შეაჩერე მუსიკა` — play/pause toggle
- `გააგრძელე მუსიკა` — play/pause toggle
- `გააჩერე მუსიკა` — media stop
- `შემდეგი სიმღერა`
- `წინა სიმღერა`

English forms are `play music`, `pause music`, `resume music`, `stop media`, `next track`, and `previous track`. Windows provides one universal play/pause key, so the first three commands toggle the current state. Support depends on the active media application.

## Windows utilities

- `გადაიღე ეკრანი` — saves a PNG under `Pictures\Gela Screenshots`
- `ჩაკეტე კომპიუტერი` — locks the current Windows session
- `აჩვენე დესკტოპი`
- `გახსენი სწრაფი პარამეტრები`
- `აჩვენე შეტყობინებები`
- `აჩვენე ყველა ფანჯარა` — opens Task View
- `გახსენი პარამეტრები`
- `გახსენი ვაიფაი`
- `გახსენი ბლუთუზი`
- `ჩართე ვაიფაი` / `გამორთე ვაიფაი` — sets Wi-Fi explicitly on or off
- `ჩართე ბლუთუზი` / `გამორთე ბლუთუზი` — sets Bluetooth explicitly on or off
- `ჩართე ფრენის რეჟიმი` — turns Wi-Fi and Bluetooth off
- `გამორთე ფრენის რეჟიმი` — turns Wi-Fi and Bluetooth on
- `გახსენი ეკრანის პარამეტრები`
- `გახსენი ხმის პარამეტრები`
- `გახსენი განახლებები`
- `სიკაშკაშე გაზარდე`
- `სიკაშკაშე შეამცირე`

Brightness changes by 10 percentage points and works only when the monitor exposes Windows brightness control. Unsupported monitors produce the normal failure response.

Shutdown, restart, arbitrary shell commands, and file deletion are intentionally unsupported.

Wi-Fi and Bluetooth controls use the Windows radio API without administrator elevation. They set an explicit state rather than toggling blindly. A device managed by organization policy or hardware without a Windows radio interface returns the normal failure response and is not changed.

## Custom routines

Choose **Manage routines** from the tray to create a phrase that launches several catalog applications in order. For example, a Georgian phrase such as `სამუშაო რეჟიმი` can open Chrome, Outlook, and Discord after the normal `გელა` wake sequence.

Routines support 1–10 catalog applications and a fixed half-second delay between launches. Their phrases cannot conflict with existing commands. Routines cannot run arbitrary paths, shell commands, deletion, shutdown, or force-close actions.

## Optional local questions

Local question answering is disabled by default. It requires a compatible model served by Ollama on `127.0.0.1`; no question is sent to an internet service. Enable it from the tray after configuring the model in `%LOCALAPPDATA%\Gela\config\settings.json`.

Use the two-step flow:

1. Say `გელა`, wait for `გისმენ`, then say `კითხვა მაქვს`.
2. Wait for the second `გისმენ`, then ask the complete question in Georgian or English.

English activation is `I have a question`. Gela displays the generated answer in a separate window with a copy button. Arbitrary generated answers are not spoken, so no dynamic TTS or additional recorded-answer variations are required.

## Optional online services

Weather and Wikipedia are independently disabled by default and can be enabled from **Online services** in the tray. Weather sends the configured coordinates to Open-Meteo; Wikipedia sends only the explicitly dictated lookup text to the Georgian or English Wikipedia API.

- `რა ამინდია` / `current weather` — displays current conditions for the configured location.
- `მოძებნე ვიკიპედიაში` / `search Wikipedia` — after the second `გისმენ`, say the search topic.

The configured weather location is Gori, Shida Kartli. Change `location_name`, `latitude`, and `longitude` under `online_services` in `%LOCALAPPDATA%\Gela\config\settings.json` if needed. Results appear in the same copyable answer window and overwrite the prior answer snapshot.

# Gela Home (interactive preview)

This is a copy and adaptation of the visual components from
`D:\Dev\Projects\Experiments\apex`. The Apex source project is unchanged.
See [CREDITS.md](CREDITS.md) and [LICENSE](LICENSE) for upstream attribution.

## Run

From `home_ui` on the Gela development PC:

```powershell
npm ci
npm run build
node -e "process.env.HOSTNAME='127.0.0.1'; process.env.PORT='3100'; require('./.next/standalone/server.js')"
```

Open `http://127.0.0.1:3100`. This preview does **not** change Windows startup
or replace Explorer. Gela's usual tray/worker process should already be running.

For a dedicated desktop window after building, run from the repository root:

```powershell
.\.venv\Scripts\python.exe home_ui\launch_preview.py
```

This opens a native frameless fullscreen WebView2 window without browser chrome
or standard window buttons, with its local profile under `home_ui\.runtime`
(inside the project, currently on D:). It starts a private
loopback server on an available port and stops that server
when the app window closes. Close the window with **Alt+F4**, or use **Show
Desktop** inside it to reveal the normal Windows desktop without closing Gela
Home. The launcher does not register startup tasks, modify Explorer, or install
anything. If the window does not open, check `home_ui\.runtime\home_server.log`.
To test the server without opening a window, run the launcher with `--check`.

To stage the self-contained Home UI and Node runtime on D: for this PC, run:

```powershell
.\home_ui\scripts\stage_preview.ps1
.\.venv\Scripts\python.exe release\Gela-Home-preview\launch_preview.py
```

The staged application files are about 160 MB; the separate Edge profile may
grow with use. The staging script saves a small bundle-path setting so a future
Gela PC build can show **Gela Home (preview)** inside the existing Applications
tray submenu. The currently installed Gela executable does not have that menu
yet. This stage is tied to this source tree and is **not** a portable installer.

The fourteen nodes open allowlisted Windows/Gela destinations. Applications,
Gaming Hub, and Media Library open searchable panels populated from Gela's
current catalog at `%LOCALAPPDATA%\Gela\config\apps.json`. Selecting an item
sends only its catalog ID; the PC re-reads the catalog and uses Gela's verified
launcher. Gaming Hub combines automatically discovered Steam manifests with
standalone games explicitly added through its native file picker. My Shortcuts
can pin programs, files, folders, and drive roots. The interface reads
Gela's latest runtime status snapshot from `%LOCALAPPDATA%\Gela\runtime\status.json`.
For a live indicator, it checks the modification time and running flag of the
mobile bridge heartbeat file, without returning any pairing credentials. When
the bridge is disabled or absent, the UI explicitly marks the status unverified.
The bottom-left health control distinguishes the mobile-link heartbeat from a
new, direct Gela worker heartbeat. It also shows the worker's last reported
state, microphone, model, catalog, and last-action summaries. Dynamic avatar
states require both a live worker heartbeat and a recent worker report; a stale
status snapshot cannot leave the avatar stuck in a listening animation. Older
installed Gela builds lack the new worker heartbeat and are marked unverified
until updated; this does not by itself mean they are stopped.
The **Desktop Items** node lists files, folders, and shortcuts from the personal
and public Windows Desktop folders. The top-right **Show Desktop** button minimizes
windows to reveal the normal Windows desktop.
Full command input will be added before Gela Home becomes a startup interface.

The local API refuses non-loopback hosts and cross-origin action requests. It
does not accept arbitrary executable paths or shell commands from the browser.

Next steps: verify all destinations on the installed Gela build, package the
standalone window with Gela's installer, and test recovery when Node or Edge
fails. Only after those tests should automatic launch be considered.

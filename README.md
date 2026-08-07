# scrawdog

> SoundCloud, stripped to the bone. No bloat. No ads. No mercy.

Unofficial SoundCloud desktop client for Windows. Python, customtkinter, libmpv.
Frameless. Dark. Keyboard-only. Lighter than your browser tab, faster than the
official web player will ever be.

> **Disclaimer.** This thing hits public `api-v2.soundcloud.com` endpoints
> with a `client_id` scraped from the web player. SC can rotate keys or
> nuke your token whenever they feel like it. Nobody promises anything.

<img width="512" height="512" alt="Screenshot 2026-05-07 at 03-41-19 Edward Skeletrix - BOMYE (ZAYTOVEN)One Take   by taht internet persona" src="https://github.com/user-attachments/assets/c414297a-8582-4711-aac3-66f7e7b381d7" />

## What it does

- search, stream, like, dump tracks into playlists
- your own likes and playlists via your OAuth token
- click an artist's name → their page, only their uploads, no reposts
- 11 themes, swap on `T`
- frameless minimal UI — no chrome, no clutter, no nonsense
- single `.exe` for Windows (~75 MB, libmpv baked in)
- Inno Setup installer if you're into that

## Hotkeys (mouse optional, attitude required)

| key | action |
|---|---|
| `S` / `/` | jump into search (`Esc` to escape) |
| `Enter` | search |
| `Q` | my playlists |
| `E` | my likes |
| `T` | theme picker |
| `V` | toggle seek bar |
| `Space` | play / pause |
| `←` / `→` | prev / next track |
| `↑` / `↓` | volume |
| LMB on track | play, or pause if it's already playing |
| LMB on artist name | open their page (uploads only, no reposts) |
| RMB on track | menu: like / add to playlist |
| drag top bar | move the window |
| type `login` | auth dialog |
| `Alt+F4` | close |

## Build from source

```cmd
pip install -r requirements.txt
```

Grab `libmpv-2.dll` (x64) from
<https://sourceforge.net/projects/mpv-player-windows/files/libmpv/>
and drop it next to `main.py`. No, it's not in the repo. Licensing.

```cmd
python main.py
```

## Build the `.exe`

```cmd
build.bat
```

Output: `dist\scrawdog.exe`

## Build the installer

Install Inno Setup 6 (<https://jrsoftware.org/isdl.php>), then:

```cmd
build_installer.bat
```

Output: `installer\scrawdog Setup.exe`

## Auth

For likes and playlists you need your own OAuth token from soundcloud.com.
No `client_id` needed — scrawdog scrapes that itself.

1. Open soundcloud.com in a browser, log in.
2. F12 → Application → Cookies → soundcloud.com.
3. Copy the value of the `oauth_token` cookie.
4. In the client, type `login`, paste it, save.

Stored at `%APPDATA%\SCMini\config.json` in plain text. If that scares you,
this client probably isn't for you.

## License

Source: GPL-3.0 — do whatever, just keep it open.
`libmpv-2.dll` is GPL/LGPL and not in this repo. Download it yourself
and respect its license yourself.

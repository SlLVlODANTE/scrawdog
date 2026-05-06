"""SC Mini — минималистичный клиент SoundCloud.

Раскладка:
  - top bar 12px, #545454, центрированное поле ввода без рамки
  - main area #222222
  - сайдбара нет, нижнего бара нет, акцентного цвета нет

Хоткеи:
  Q          — плейлисты
  E          — лайки
  ←  / →     — предыдущий / следующий трек
  ↑  / ↓     — громкость +/-
  пробел     — пауза/продолжить
  S или /    — фокус в поле поиска (Esc — выйти из него)
  V          — показать/скрыть полоску перемотки внизу (25px)
  Alt+F4     — закрыть приложение
  набрать "login" подряд — окно ввода OAuth токена
  ЛКМ по верхней полоске — перетащить окно
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import customtkinter as ctk

from player import Player
from sc_api import SoundCloud

# ---------- палитра ----------
BG       = "#121212"
BAR      = "#2b2b2b"
TOP_EDGE = "#1a1a1a"
TEXT     = "#FFFFFF"
MUTED    = "#9a9a9a"

ROW      = "#1c1c1c"
ROW_HOV  = "#262626"
ROW_ACT  = "#2e2e2e"   # чуть светлее, без оранжевого

FONT     = "Segoe UI"
F_BAR    = (FONT, 10)
F_BODY   = (FONT, 12)
F_SMALL  = (FONT, 11)

CONFIG_PATH = Path(os.getenv("APPDATA", str(Path.home()))) / "SCMini" / "config.json"
LOGIN_SEQ = "login"


def load_cfg() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text("utf-8"))
    except Exception:
        return {}


def save_cfg(d: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(d, ensure_ascii=False, indent=2), "utf-8")


def fmt_time(s: float) -> str:
    s = max(0, int(s))
    return f"{s // 60}:{s % 60:02d}"


def trim(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


# ============================================================
# Карточка трека (без оранжевого, без иконок ▶/⏸)
# ============================================================
class TrackRow(ctk.CTkFrame):
    def __init__(self, master, idx: int, track: dict, on_click, on_right=None):
        super().__init__(master, fg_color=ROW, corner_radius=0, height=40)
        self.pack_propagate(False)
        self.idx = idx
        self.track = track
        self.on_click = on_click
        self.on_right = on_right
        self._active = False
        self._hover = False

        self.title_lbl = ctk.CTkLabel(
            self, text=trim(track.get("title", "?"), 80),
            text_color=TEXT, font=F_BODY, anchor="w",
        )
        self.title_lbl.pack(side="left", padx=14)

        artist = (track.get("user") or {}).get("username", "")
        self.artist_lbl = ctk.CTkLabel(
            self, text=" — " + trim(artist, 40),
            text_color=MUTED, font=F_SMALL, anchor="w",
        )
        self.artist_lbl.pack(side="left")

        dur_ms = track.get("duration", 0) or 0
        self.dur_lbl = ctk.CTkLabel(self, text=fmt_time(dur_ms / 1000),
                                    text_color=MUTED, font=F_SMALL, width=50)
        self.dur_lbl.pack(side="right", padx=12)

        for w in (self, self.title_lbl, self.artist_lbl, self.dur_lbl):
            w.bind("<Enter>", self._enter)
            w.bind("<Leave>", self._leave)
            w.bind("<Button-1>", self._click)
            w.bind("<Button-3>", self._right_click)

    def _enter(self, _e=None):
        self._hover = True
        self._restyle()

    def _leave(self, _e=None):
        x, y = self.winfo_pointerxy()
        w = self.winfo_containing(x, y)
        if w is None or not str(w).startswith(str(self)):
            self._hover = False
            self._restyle()

    def _click(self, _e=None):
        self.on_click(self.idx)

    def _right_click(self, e):
        if self.on_right:
            self.on_right(self.idx, e.x_root, e.y_root)

    def set_active(self, active: bool):
        self._active = active
        self._restyle()

    def _restyle(self):
        if self._active:
            self.configure(fg_color=ROW_ACT)
        else:
            self.configure(fg_color=ROW_HOV if self._hover else ROW)


# ============================================================
# Главное окно
# ============================================================
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.title("разраб егор20")
        self.geometry("1280x720")
        self.minsize(640, 360)
        self.configure(fg_color=BG)
        # иконка окна (таскбар, Alt+Tab)
        try:
            base = sys._MEIPASS if getattr(sys, "frozen", False) \
                else os.path.dirname(os.path.abspath(__file__))
            ico = os.path.join(base, "icon.ico")
            if os.path.exists(ico):
                self.iconbitmap(ico)
                self._icon_path = ico
        except Exception:
            self._icon_path = None
        # убираем системную рамку Windows, но оставляем в таскбаре
        self.overrideredirect(True)
        self.after(10, self._force_taskbar)
        # координаты для перетаскивания
        self._drag_x = 0
        self._drag_y = 0

        self.cfg = load_cfg()
        self.sc: Optional[SoundCloud] = None
        self.player = Player(on_end=self._on_track_end)
        self.player.set_volume(0.7)
        self.queue: list[dict] = []
        self.queue_idx: int = -1
        self.rows: list[TrackRow] = []
        self._volume = 0.7
        self._key_buf: str = ""
        self._key_buf_ts: float = 0.0

        self._build_ui()
        self.after(100, self._init_api)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._bind_hotkeys()

    # ============== UI ==============
    def _build_ui(self):
        # ===== top bar 12px =====
        # делаем общий контейнер высотой 12px, без grid/padding,
        # чтобы строго получить ровную полоску
        top = ctk.CTkFrame(self, fg_color=BAR, height=12, corner_radius=0)
        top.pack(fill="x")
        top.pack_propagate(False)

        # для перетаскивания окна
        top.bind("<Button-1>", self._drag_start)
        top.bind("<B1-Motion>", self._drag_move)

        # тонкая нижняя кромка
        ctk.CTkFrame(self, fg_color=TOP_EDGE, height=1,
                     corner_radius=0).pack(fill="x")

        # поле ввода поверх бара через place — точная позиция и размер,
        # сливается с баром по цвету. По умолчанию НЕ в фокусе.
        self.search_var = ctk.StringVar()
        self.entry = ctk.CTkEntry(
            top, textvariable=self.search_var,
            corner_radius=0, fg_color=BAR, border_width=0,
            text_color=TEXT, font=F_BAR, justify="center",
            takefocus=False,
        )
        self.entry.place(relx=0.5, rely=0.5, anchor="center",
                         relwidth=0.4, relheight=1.0)
        self.entry.bind("<Return>", self._on_search_submit)
        self.entry.bind("<Escape>", lambda _e: self._blur_search())

        # ===== main area =====
        main = ctk.CTkFrame(self, fg_color=BG)
        main.pack(fill="both", expand=True)

        self.placeholder = ctk.CTkLabel(
            main, text="", text_color=MUTED, font=F_BODY, justify="center",
        )
        self.placeholder.place(relx=0.5, rely=0.5, anchor="center")

        self.main_area = main
        self.tracks_box: Optional[ctk.CTkScrollableFrame] = None

        # ===== скрываемая полоска перемотки (toggle: V) =====
        self.seek_bar = ctk.CTkFrame(self, fg_color=BAR, height=25,
                                     corner_radius=0)
        # не пакуем сразу — появляется по V
        self.seek_bar.pack_propagate(False)
        self._seek_visible = False
        self._seek_dragging = False

        self.seek_slider = ctk.CTkSlider(
            self.seek_bar, from_=0, to=1,
            height=14, button_length=0,
            button_color="#ffffff", button_hover_color="#dddddd",
            progress_color="#ffffff", fg_color="#3a3a3a",
            border_width=6,           # тонкая дорожка (track)
            button_corner_radius=10,
        )
        self.seek_slider.set(0)
        self.seek_slider.pack(fill="x", expand=True, padx=12, pady=6)
        self.seek_slider.bind("<Button-1>",
                              lambda _e: setattr(self, "_seek_dragging", True))
        self.seek_slider.bind("<ButtonRelease-1>", self._seek_release)

        # тикер обновления позиции слайдера
        self.after(500, self._tick_seek)

    # ============== хоткеи ==============
    def _bind_hotkeys(self):
        self.bind_all("<KeyPress>", self._on_key, add="+")

    def _focus_search(self):
        self.entry.focus_set()
        self.entry.select_range(0, "end")
        self.entry.icursor("end")

    def _blur_search(self):
        # снимаем фокус с поля поиска обратно на главное окно
        self.focus_set()

    def _on_search_submit(self, _e=None):
        self._do_search()
        self._blur_search()

    def _is_search_focused(self) -> bool:
        try:
            f = self.focus_get()
        except Exception:
            return False
        if f is None:
            return False
        # tk Entry, лежащий внутри CTkEntry
        return f is self.entry or (f.winfo_class() == "Entry" and
                                   str(f).startswith(str(self.entry)))

    def _on_key(self, e):
        ks = (e.keysym or "").lower()

        # если фокус в поле поиска — пропускаем стандартный ввод,
        # обрабатываем только Escape
        if self._is_search_focused():
            if ks == "escape":
                self._blur_search()
            return

        # перехватываем Space глобально, чтобы он не активировал
        # сфокусированную кнопку или скролл, а всегда играл/ставил на паузу
        if ks == "space":
            self._toggle_pause()
            return "break"

        # буфер для последовательности "login"
        ch = e.char if e.char and e.char.isprintable() else ""
        if ch:
            now = time.time()
            if now - self._key_buf_ts > 2.0:
                self._key_buf = ""
            self._key_buf = (self._key_buf + ch.lower())[-len(LOGIN_SEQ):]
            self._key_buf_ts = now
            if self._key_buf == LOGIN_SEQ:
                self._key_buf = ""
                self._ask_token()
                return

        if ks == "q":
            self._show_playlists()
        elif ks == "e":
            self._show_likes()
        elif ks == "right":
            self._next()
        elif ks == "left":
            self._prev()
        elif ks == "up":
            self._volume_step(+0.05)
        elif ks == "down":
            self._volume_step(-0.05)
        elif ks in ("s", "slash"):
            self._focus_search()
        elif ks == "v":
            self._toggle_seek_bar()

    def _volume_step(self, d: float):
        self._volume = max(0.0, min(1.0, self._volume + d))
        self.player.set_volume(self._volume)

    def _toggle_pause(self):
        if self.queue_idx >= 0:
            self.player.toggle()

    # ============== полоска перемотки ==============
    def _toggle_seek_bar(self):
        if self._seek_visible:
            self.seek_bar.pack_forget()
            self._seek_visible = False
        else:
            self.seek_bar.pack(side="bottom", fill="x")
            self._seek_visible = True

    def _seek_release(self, _e):
        dur = self.player.duration
        if dur > 0:
            self.player.seek(self.seek_slider.get() * dur)
        self._seek_dragging = False

    def _tick_seek(self):
        try:
            if self._seek_visible and not self._seek_dragging:
                dur = self.player.duration
                pos = self.player.position
                if dur > 0:
                    self.seek_slider.set(pos / dur)
        except Exception:
            pass
        self.after(500, self._tick_seek)

    # ============== список / сообщения ==============
    def _show_message(self, msg: str):
        if self.tracks_box is not None:
            self.tracks_box.destroy()
            self.tracks_box = None
        self.placeholder.configure(text=msg)
        self.placeholder.place(relx=0.5, rely=0.5, anchor="center")

    def _ensure_tracks_box(self):
        self.placeholder.place_forget()
        if self.tracks_box is None:
            self.tracks_box = ctk.CTkScrollableFrame(
                self.main_area, fg_color=BG,
                scrollbar_button_color=BAR,
                scrollbar_button_hover_color=TOP_EDGE,
            )
            self.tracks_box.pack(fill="both", expand=True)
        else:
            for w in self.tracks_box.winfo_children():
                w.destroy()

    # ============== API ==============
    def _init_api(self):
        token = self.cfg.get("oauth_token")

        forced_cid = self.cfg.get("client_id")

        def work():
            try:
                self.sc = SoundCloud(oauth_token=token,
                                     forced_client_id=forced_cid)
            except Exception as e:
                err = e
                self.after(0, lambda: self._show_message(f"connection failed:\n{err}"))

        threading.Thread(target=work, daemon=True).start()

    def _ask_token(self):
        # своя двух-полевая форма (CTkInputDialog поддерживает только одно поле)
        m = ctk.CTkToplevel(self)
        m.title("Login")
        m.geometry("420x260")
        m.configure(fg_color=BG)
        m.attributes("-topmost", True)
        m.after(50, m.focus_force)

        ctk.CTkLabel(
            m, text="Open soundcloud.com (logged in) → F12 → Network →\n"
                    "click any track → find request to api-v2.soundcloud.com\n"
                    "• copy 'client_id=...' value from URL\n"
                    "• copy 'oauth_token' from Application → Cookies",
            text_color=MUTED, font=F_SMALL, justify="left",
        ).pack(padx=14, pady=(12, 8), anchor="w")

        ctk.CTkLabel(m, text="client_id", text_color=TEXT,
                     font=F_SMALL, anchor="w").pack(fill="x", padx=14)
        cid_var = ctk.StringVar(value=self.cfg.get("client_id", ""))
        ctk.CTkEntry(m, textvariable=cid_var, fg_color=ROW,
                     border_width=0, text_color=TEXT,
                     font=F_BODY).pack(fill="x", padx=14, pady=(2, 8))

        ctk.CTkLabel(m, text="oauth_token", text_color=TEXT,
                     font=F_SMALL, anchor="w").pack(fill="x", padx=14)
        tok_var = ctk.StringVar(value=self.cfg.get("oauth_token", ""))
        ctk.CTkEntry(m, textvariable=tok_var, fg_color=ROW,
                     border_width=0, text_color=TEXT,
                     font=F_BODY).pack(fill="x", padx=14, pady=(2, 12))

        def save():
            cid = cid_var.get().strip()
            tok = tok_var.get().strip()
            if cid:
                self.cfg["client_id"] = cid
            if tok:
                self.cfg["oauth_token"] = tok
            save_cfg(self.cfg)
            m.destroy()
            self._restore_window()
            self._init_api()
            self._show_message("Saved. Connecting…")

        ctk.CTkButton(
            m, text="Save", height=32, fg_color=BAR,
            hover_color=ROW_HOV, text_color=TEXT, command=save,
        ).pack(pady=4, padx=14, fill="x")

    def _restore_window(self):
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
        except Exception:
            pass

    def _do_search(self):
        q = self.search_var.get().strip()
        if not q:
            return
        if not self.sc:
            self._show_message("connecting…")
            return
        self._ensure_tracks_box()

        def work():
            try:
                tracks = self.sc.search_tracks(q, limit=30)
            except Exception as e:
                self.after(0, lambda: self._show_message(str(e)))
                return
            self.after(0, lambda: self._set_tracks(tracks))

        threading.Thread(target=work, daemon=True).start()

    def _auth_check(self) -> bool:
        # есть токен в конфиге, но sc ещё не успел подключиться
        if not self.sc and self.cfg.get("oauth_token"):
            self._show_message("connecting…")
            self.after(500, self._retry_auth)
            return False
        if not self.sc or not self.sc.oauth_token:
            self._show_message(
                "You are not logged in.\nType 'login' to enter your OAuth token."
            )
            return False
        return True

    def _retry_auth(self):
        # пользователь ткнул Q/E пока sc был None — повторяем когда готов
        if self.sc:
            return
        self.after(500, self._retry_auth)

    def _show_likes(self):
        if not self._auth_check():
            return
        self._ensure_tracks_box()

        def work():
            try:
                tracks = self.sc.my_likes()
            except Exception as e:
                self.after(0, lambda: self._show_message(str(e)))
                return
            self.after(0, lambda: self._set_tracks(tracks))

        threading.Thread(target=work, daemon=True).start()

    def _show_playlists(self):
        if not self._auth_check():
            return
        self._ensure_tracks_box()

        def work():
            try:
                pls = self.sc.my_playlists()
            except Exception as e:
                self.after(0, lambda: self._show_message(str(e)))
                return
            self.after(0, lambda: self._render_playlists(pls))

        threading.Thread(target=work, daemon=True).start()

    def _render_playlists(self, pls):
        self._ensure_tracks_box()
        for p in pls:
            title = p.get("title", "?")
            count = p.get("track_count") or 0
            row = ctk.CTkFrame(self.tracks_box, fg_color=ROW,
                               corner_radius=0, height=38)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)
            t = ctk.CTkLabel(row, text=trim(title, 70), text_color=TEXT,
                             font=F_BODY, anchor="w")
            t.pack(side="left", padx=14)
            c = ctk.CTkLabel(row, text=f"{count} tracks", text_color=MUTED,
                             font=F_SMALL)
            c.pack(side="right", padx=14)
            for w in (row, t, c):
                w.configure(cursor="hand2")
                w.bind("<Enter>", lambda _e, r=row: r.configure(fg_color=ROW_HOV))
                w.bind("<Leave>", lambda _e, r=row: r.configure(fg_color=ROW))
                w.bind("<Button-1>",
                       lambda _e, pid=p["id"], tt=title: self._open_playlist(pid, tt))

    def _open_playlist(self, pid: int, title: str):
        self._ensure_tracks_box()

        def work():
            try:
                pl = self.sc.playlist(pid)
                tracks = [t for t in pl.get("tracks", []) if t.get("title")]
                missing = [t["id"] for t in pl.get("tracks", []) if not t.get("title")]
                if missing:
                    for i in range(0, len(missing), 20):
                        ids = ",".join(map(str, missing[i:i + 20]))
                        r = self.sc.s.get(
                            "https://api-v2.soundcloud.com/tracks",
                            params=self.sc._params(ids=ids),
                        )
                        if r.ok:
                            tracks.extend(r.json())
            except Exception as e:
                self.after(0, lambda: self._show_message(str(e)))
                return
            self.after(0, lambda: self._set_tracks(tracks))

        threading.Thread(target=work, daemon=True).start()

    def _set_tracks(self, tracks):
        self._ensure_tracks_box()
        self.queue = tracks
        self.rows = []
        if not tracks:
            self._show_message("nothing found")
            return
        for i, t in enumerate(tracks):
            row = TrackRow(self.tracks_box, i, t, self._on_track_click,
                           on_right=self._show_track_menu)
            row.pack(fill="x", pady=1)
            self.rows.append(row)

    # ============== воспроизведение ==============
    def _on_track_click(self, i: int):
        if i == self.queue_idx:
            self.player.toggle()
            return
        self._play_index(i)

    def _play_index(self, i: int):
        if not (0 <= i < len(self.queue)):
            return
        if 0 <= self.queue_idx < len(self.rows):
            self.rows[self.queue_idx].set_active(False)
        self.queue_idx = i
        if i < len(self.rows):
            self.rows[i].set_active(True)

        t = self.queue[i]

        def work():
            try:
                url = self.sc.stream_url(t)
                if not url:
                    raise RuntimeError("no stream")
                self.player.play(url)
            except Exception as e:
                err = e
                self.after(0, lambda: self._show_message(f"playback: {err}"))

        threading.Thread(target=work, daemon=True).start()

    def _next(self):
        if self.queue_idx + 1 < len(self.queue):
            self._play_index(self.queue_idx + 1)

    def _prev(self):
        if self.queue_idx > 0:
            self._play_index(self.queue_idx - 1)

    def _on_track_end(self):
        self.after(0, self._next)

    # ============== контекстное меню (ПКМ по треку) ==============
    def _close_menus(self):
        for attr in ("_menu", "_pl_menu"):
            m = getattr(self, attr, None)
            if m is not None:
                try: m.destroy()
                except Exception: pass
                setattr(self, attr, None)

    def _show_track_menu(self, idx: int, x_root: int, y_root: int):
        track = self.queue[idx]
        self._close_menus()

        m = ctk.CTkToplevel(self)
        m.overrideredirect(True)
        m.configure(fg_color=ROW_HOV)
        # 2 кнопки по 28px, ширина чуть больше длинного варианта
        w, h_btn = 130, 28
        m.geometry(f"{w}x{h_btn * 2}+{x_root}+{y_root}")
        m.attributes("-topmost", True)

        ctk.CTkButton(
            m, text="Like", width=w, height=h_btn, corner_radius=0,
            fg_color=ROW_HOV, hover_color="#3a3a3a",
            text_color=TEXT, font=F_BODY,
            command=lambda: self._do_like(track, m),
        ).pack(fill="x")

        ctk.CTkButton(
            m, text="Add to Playlist", width=w, height=h_btn, corner_radius=0,
            fg_color=ROW_HOV, hover_color="#3a3a3a",
            text_color=TEXT, font=F_BODY,
            command=lambda: self._open_pl_picker(track, x_root, y_root, m),
        ).pack(fill="x")

        m.bind("<FocusOut>", lambda _e: self._maybe_close(m))
        m.after(50, m.focus_force)
        self._menu = m

    def _maybe_close(self, win):
        # не закрываем если фокус ушёл в дочернее окно (pl_picker)
        self.after(150, lambda: self._destroy_if_unfocused(win))

    def _destroy_if_unfocused(self, win):
        try:
            f = self.focus_get()
        except Exception:
            f = None
        if f is None or (str(f).startswith(str(win)) is False and
                         (not getattr(self, "_pl_menu", None) or
                          not str(f).startswith(str(self._pl_menu)))):
            try: win.destroy()
            except Exception: pass

    def _do_like(self, track: dict, menu):
        try: menu.destroy()
        except Exception: pass
        if not self.sc or not self.sc.oauth_token:
            self._show_message(
                "You are not logged in.\nType 'login' to enter your OAuth token."
            )
            return

        def work():
            try:
                self.sc.like_track(track["id"])
                self.after(0, lambda: self._show_message(
                    f"Liked: {trim(track.get('title','?'), 50)}"
                ))
            except Exception as e:
                err = e
                self.after(0, lambda: self._show_message(f"like failed: {err}"))

        threading.Thread(target=work, daemon=True).start()

    # ============== выбор плейлиста ==============
    def _open_pl_picker(self, track: dict, x_root: int, y_root: int, parent_menu):
        try: parent_menu.destroy()
        except Exception: pass
        if not self.sc or not self.sc.oauth_token:
            self._show_message(
                "You are not logged in.\nType 'login' to enter your OAuth token."
            )
            return

        m = ctk.CTkToplevel(self)
        m.overrideredirect(True)
        m.configure(fg_color=ROW_HOV)
        w, h = 220, 240
        m.geometry(f"{w}x{h}+{x_root}+{y_root}")
        m.attributes("-topmost", True)
        self._pl_menu = m

        header = ctk.CTkLabel(m, text="loading playlists…",
                              text_color=MUTED, font=F_SMALL)
        header.pack(pady=8)

        box = ctk.CTkScrollableFrame(m, fg_color=ROW_HOV,
                                     scrollbar_button_color="#3a3a3a")
        box.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        m.bind("<FocusOut>", lambda _e: m.after(200, m.destroy))
        m.after(50, m.focus_force)

        def load():
            try:
                pls = self.sc.my_playlists()
            except Exception as e:
                self.after(0, lambda: header.configure(text=f"err: {e}"))
                return
            self.after(0, lambda: render(pls))

        def render(pls):
            header.configure(text="Add to which playlist?")
            for p in pls:
                title = p.get("title", "?")
                btn = ctk.CTkButton(
                    box, text=trim(title, 28), anchor="w",
                    height=28, corner_radius=0,
                    fg_color=ROW_HOV, hover_color="#3a3a3a",
                    text_color=TEXT, font=F_SMALL,
                    command=lambda pid=p["id"], tt=title: self._do_add_to_pl(
                        track, pid, tt, m
                    ),
                )
                btn.pack(fill="x", pady=1)

        threading.Thread(target=load, daemon=True).start()

    def _do_add_to_pl(self, track: dict, playlist_id: int,
                      pl_title: str, menu):
        try: menu.destroy()
        except Exception: pass

        def work():
            try:
                self.sc.add_to_playlist(playlist_id, track["id"])
                self.after(0, lambda: self._show_message(
                    f"Added '{trim(track.get('title','?'), 40)}'\nto '{trim(pl_title, 40)}'"
                ))
            except Exception as e:
                err = e
                self.after(0, lambda: self._show_message(f"add failed: {err}"))

        threading.Thread(target=work, daemon=True).start()

    # ============== таскбар при overrideredirect ==============
    def _force_taskbar(self):
        """Возвращаем иконку приложения в таскбар (Windows-only)."""
        if sys.platform != "win32":
            return
        try:
            import ctypes
            user32 = ctypes.windll.user32
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            hwnd = user32.GetParent(self.winfo_id())
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            # перерисовать окно, чтобы стиль применился
            self.withdraw()
            self.after(10, self.deiconify)
        except Exception as e:
            print("taskbar fix failed:", e, file=sys.stderr)

    # ============== перетаскивание окна ==============
    def _drag_start(self, e):
        self._drag_x = e.x_root - self.winfo_x()
        self._drag_y = e.y_root - self.winfo_y()

    def _drag_move(self, e):
        self.geometry(f"+{e.x_root - self._drag_x}+{e.y_root - self._drag_y}")

    def _on_close(self):
        try:
            self.player.shutdown()
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    App().mainloop()

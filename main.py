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
  T          — окно выбора темы
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

# ---------- палитра (значения подменяются темой) ----------
BG       = "#121212"
BAR      = "#2b2b2b"
TOP_EDGE = "#1a1a1a"
TEXT     = "#FFFFFF"
MUTED    = "#9a9a9a"

ROW      = "#1c1c1c"
ROW_HOV  = "#262626"
ROW_ACT  = "#2e2e2e"

# темы — открываются попапом по T
THEMES = [
    {"BG": "#121212", "ME": "#3b4757", "OTHER": "#1c1c1c",
     "PANEL": "#101010", "ACCENT": "#3b4757",
     "TEXT": "#ffffff", "MUTED": "#9aa4b2", "NAME": "default"},
    {"BG": "#000000", "ME": "#1c1c1c", "OTHER": "#000000",
     "PANEL": "#000000", "ACCENT": "#5a3a3a",
     "TEXT": "#ffffff", "MUTED": "#9aa4b2", "NAME": "dark"},
    {"BG": "#070707", "ME": "#242424", "OTHER": "#151515",
     "PANEL": "#050505", "ACCENT": "#5A3A3A",
     "TEXT": "#F3F3F3", "MUTED": "#A9B9C9", "NAME": "graphite"},
    {"BG": "#11161D", "ME": "#3D4B5E", "OTHER": "#1A2028",
     "PANEL": "#0E1117", "ACCENT": "#4B5F78",
     "TEXT": "#F5F7FA", "MUTED": "#AFC4D8", "NAME": "blue_ash"},
    {"BG": "#100E14", "ME": "#3E3548", "OTHER": "#1B1720",
     "PANEL": "#0B090E", "ACCENT": "#5B4668",
     "TEXT": "#F7F2F8", "MUTED": "#C2A9D0", "NAME": "muted_violet"},
    {"BG": "#0D100C", "ME": "#343D30", "OTHER": "#181C16",
     "PANEL": "#080A07", "ACCENT": "#4C573F",
     "TEXT": "#F2F5EF", "MUTED": "#B9C7A8", "NAME": "olive_night"},
    {"BG": "#C9C9C4", "ME": "#AEB4BA", "OTHER": "#D7D7D1",
     "PANEL": "#BDBDB8", "ACCENT": "#8A7777",
     "TEXT": "#181818", "MUTED": "#465160", "NAME": "soft_grey"},
    {"BG": "#020202", "ME": "#241106", "OTHER": "#090909",
     "PANEL": "#040404", "ACCENT": "#E06A1A",
     "TEXT": "#F4F1ED", "MUTED": "#C87942", "NAME": "black_ember"},
    {"BG": "#020304", "ME": "#071820", "OTHER": "#080A0C",
     "PANEL": "#030405", "ACCENT": "#1C6F88",
     "TEXT": "#EEF6F8", "MUTED": "#6DA9B9", "NAME": "void_cyan"},
    {"BG": "#030202", "ME": "#1A0709", "OTHER": "#0A0707",
     "PANEL": "#050303", "ACCENT": "#7A2028",
     "TEXT": "#F4EEEE", "MUTED": "#B15D66", "NAME": "blood_carbon"},
    {"BG": "#020302", "ME": "#08180D", "OTHER": "#070A07",
     "PANEL": "#030503", "ACCENT": "#2E7A3D",
     "TEXT": "#EEF5EF", "MUTED": "#78AE7D", "NAME": "deep_matrix"},
]


def theme_get(theme: dict, key: str) -> str:
    if key in theme:
        return theme[key]
    fallbacks = {
        "PANEL":  theme.get("BG", "#121212"),
        "ACCENT": theme.get("ME", "#3b4757"),
        "TEXT":   "#ffffff",
        "MUTED":  "#9aa4b2",
        "NAME":   "theme",
    }
    return fallbacks.get(key, "")


def apply_theme_globals(th: dict) -> None:
    """Подменяет глобальные цвета на основе темы."""
    global BG, BAR, TOP_EDGE, TEXT, MUTED, ROW, ROW_HOV, ROW_ACT
    BG       = theme_get(th, "BG")
    BAR      = theme_get(th, "PANEL")
    TOP_EDGE = theme_get(th, "OTHER")
    TEXT     = theme_get(th, "TEXT")
    MUTED    = theme_get(th, "MUTED")
    ROW      = theme_get(th, "OTHER")
    ROW_HOV  = theme_get(th, "ME")
    ROW_ACT  = theme_get(th, "ACCENT")


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
    def __init__(self, master, idx: int, track: dict, on_click,
                 on_right=None, on_artist=None):
        super().__init__(master, fg_color=ROW, corner_radius=0, height=40)
        self.pack_propagate(False)
        self.idx = idx
        self.track = track
        self.on_click = on_click
        self.on_right = on_right
        self.on_artist = on_artist
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
            cursor="hand2",
        )
        self.artist_lbl.pack(side="left")

        dur_ms = track.get("duration", 0) or 0
        self.dur_lbl = ctk.CTkLabel(self, text=fmt_time(dur_ms / 1000),
                                    text_color=MUTED, font=F_SMALL, width=50)
        self.dur_lbl.pack(side="right", padx=12)

        for w in (self, self.title_lbl, self.dur_lbl):
            w.bind("<Enter>", self._enter)
            w.bind("<Leave>", self._leave)
            w.bind("<Button-1>", self._click)
            w.bind("<Button-3>", self._right_click)

        # клик по нику артиста — открыть его страницу (без репостов)
        self.artist_lbl.bind("<Enter>", self._enter)
        self.artist_lbl.bind("<Leave>", self._leave)
        self.artist_lbl.bind("<Button-1>", self._artist_click)
        self.artist_lbl.bind("<Button-3>", self._right_click)

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

    def _artist_click(self, _e=None):
        if self.on_artist:
            user = self.track.get("user") or {}
            if user.get("id"):
                self.on_artist(user)
        return "break"

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
        self.title("scrawdog")
        self.geometry("1280x720")
        self.minsize(640, 360)

        self.cfg = load_cfg()
        self._theme_idx: int = self.cfg.get("theme_idx", 0) % len(THEMES)
        apply_theme_globals(THEMES[self._theme_idx])
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

        self.sc: Optional[SoundCloud] = None
        self.player = Player(on_end=self._on_track_end)
        self.player.set_volume(0.7)
        self.queue: list[dict] = []
        self.queue_idx: int = -1
        self.rows: list[TrackRow] = []
        self._volume = 0.7
        self._key_buf: str = ""
        self._key_buf_ts: float = 0.0
        self._theme_picker = None
        # последний показанный вид — чтобы перерендерить при смене темы
        # ("tracks", list) | ("playlists", list) | ("message", str) | None
        self._last_view: Optional[tuple] = None

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
        self.top_bar = top

        # для перетаскивания окна
        top.bind("<Button-1>", self._drag_start)
        top.bind("<B1-Motion>", self._drag_move)

        # тонкая нижняя кромка
        self.top_edge_line = ctk.CTkFrame(self, fg_color=TOP_EDGE, height=1,
                                          corner_radius=0)
        self.top_edge_line.pack(fill="x")

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
        # пакуем — иначе при одновременном place'е placeholder'а и
        # pack'е tracks_box контент уезжает в нижнюю половину окна

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
        elif ks == "t":
            self._toggle_theme_picker()

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
    def _kill_tracks_box(self):
        # CTkScrollableFrame.destroy() удаляет только внутренний tk.Frame,
        # а реальный _parent_frame остаётся в layout'е — поэтому каждый
        # повторный показ списка отъедал у предыдущего половину места.
        if self.tracks_box is None:
            return
        try:
            self.tracks_box._parent_frame.destroy()
        except Exception:
            try: self.tracks_box.destroy()
            except Exception: pass
        self.tracks_box = None

    def _show_message(self, msg: str):
        self._kill_tracks_box()
        self.placeholder.configure(text=msg, text_color=MUTED)
        try: self.placeholder.pack_forget()
        except Exception: pass
        self.placeholder.pack(fill="both", expand=True)
        self._last_view = ("message", msg)

    def _ensure_tracks_box(self):
        try: self.placeholder.pack_forget()
        except Exception: pass
        self._kill_tracks_box()
        self.tracks_box = ctk.CTkScrollableFrame(
            self.main_area, fg_color=BG,
            scrollbar_button_color=BAR,
            scrollbar_button_hover_color=TOP_EDGE,
        )
        self.tracks_box.pack(fill="both", expand=True)

    # ============== API ==============
    def _init_api(self):
        token = self.cfg.get("oauth_token")

        def work():
            try:
                self.sc = SoundCloud(oauth_token=token)
            except Exception as e:
                err = e
                self.after(0, lambda: self._show_message(f"connection failed:\n{err}"))

        threading.Thread(target=work, daemon=True).start()

    def _ask_token(self):
        # своя двух-полевая форма (CTkInputDialog поддерживает только одно поле)
        m = ctk.CTkToplevel(self)
        m.title("Login")
        m.geometry("420x200")
        m.configure(fg_color=BG)
        m.attributes("-topmost", True)
        m.after(50, m.focus_force)

        ctk.CTkLabel(
            m, text="Open soundcloud.com (logged in) → F12 →\n"
                    "Application → Cookies → copy 'oauth_token'",
            text_color=MUTED, font=F_SMALL, justify="left",
        ).pack(padx=14, pady=(12, 8), anchor="w")

        ctk.CTkLabel(m, text="oauth_token", text_color=TEXT,
                     font=F_SMALL, anchor="w").pack(fill="x", padx=14)
        tok_var = ctk.StringVar(value=self.cfg.get("oauth_token", ""))
        ctk.CTkEntry(m, textvariable=tok_var, fg_color=ROW,
                     border_width=0, text_color=TEXT,
                     font=F_BODY).pack(fill="x", padx=14, pady=(2, 12))

        def save():
            tok = tok_var.get().strip()
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
        self._last_view = ("playlists", pls)
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
        self._last_view = ("tracks", tracks)
        if not tracks:
            self._show_message("nothing found")
            return
        for i, t in enumerate(tracks):
            row = TrackRow(self.tracks_box, i, t, self._on_track_click,
                           on_right=self._show_track_menu,
                           on_artist=self._show_user_tracks)
            row.pack(fill="x", pady=1)
            self.rows.append(row)
        # подсветить активный трек, если он в этой выборке
        if 0 <= self.queue_idx < len(self.rows):
            self.rows[self.queue_idx].set_active(True)

    def _show_user_tracks(self, user: dict):
        """Открыть страницу артиста — только его треки, без репостов."""
        if not self.sc:
            self._show_message("connecting…")
            return
        uid = user.get("id")
        uname = user.get("username") or "?"
        if not uid:
            return
        self._ensure_tracks_box()
        self._show_message(f"loading {uname}…")

        def work():
            try:
                tracks = self.sc.user_tracks(uid, limit=50)
            except Exception as e:
                self.after(0, lambda: self._show_message(str(e)))
                return
            self.after(0, lambda: self._set_tracks(tracks))

        threading.Thread(target=work, daemon=True).start()

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

    # ============== темы (T) ==============
    def _apply_theme(self, idx: int):
        idx = idx % len(THEMES)
        self._theme_idx = idx
        apply_theme_globals(THEMES[idx])
        self.cfg["theme_idx"] = idx
        try: save_cfg(self.cfg)
        except Exception: pass

        # обновить статичные виджеты
        try: self.configure(fg_color=BG)
        except Exception: pass
        for w, kw in (
            (getattr(self, "main_area", None),     {"fg_color": BG}),
            (getattr(self, "top_bar", None),       {"fg_color": BAR}),
            (getattr(self, "top_edge_line", None), {"fg_color": TOP_EDGE}),
            (getattr(self, "entry", None),         {"fg_color": BAR, "text_color": TEXT}),
            (getattr(self, "seek_bar", None),      {"fg_color": BAR}),
            (getattr(self, "placeholder", None),   {"text_color": MUTED}),
        ):
            if w is not None:
                try: w.configure(**kw)
                except Exception: pass
        if self.tracks_box is not None:
            try:
                self.tracks_box.configure(
                    fg_color=BG, scrollbar_button_color=BAR,
                    scrollbar_button_hover_color=TOP_EDGE,
                )
            except Exception: pass

        # перерендер контента
        view = self._last_view
        if view is None:
            return
        kind, data = view
        if kind == "tracks":
            self._set_tracks(data)
        elif kind == "playlists":
            self._ensure_tracks_box()
            for w in self.tracks_box.winfo_children():
                w.destroy()
            self._render_playlists(data)
        elif kind == "message":
            self._show_message(data)

    def _toggle_theme_picker(self):
        if getattr(self, "_theme_picker", None) is not None:
            try: self._theme_picker.destroy()
            except Exception: pass
            self._theme_picker = None
            return
        self._show_theme_picker()

    def _show_theme_picker(self):
        w, h = 360, min(560, 80 + len(THEMES) * 56)
        self.update_idletasks()
        try:
            x = self.winfo_rootx() + (self.winfo_width() - w) // 2
            y = self.winfo_rooty() + (self.winfo_height() - h) // 2
        except Exception:
            x, y = 200, 100

        m = ctk.CTkToplevel(self)
        m.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
        m.configure(fg_color=BAR)
        m.attributes("-topmost", True)
        m.overrideredirect(True)

        top = ctk.CTkFrame(m, fg_color=BAR, height=12, corner_radius=0)
        top.pack(side="top", fill="x")
        top.pack_propagate(False)
        ctk.CTkLabel(top, text="themes", text_color=MUTED,
                     font=F_BAR).place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkFrame(m, fg_color=TOP_EDGE, height=1,
                     corner_radius=0).pack(side="top", fill="x")

        # перетаскивание
        drag = {"x": 0, "y": 0}
        def start(e):
            drag["x"] = e.x_root - m.winfo_x()
            drag["y"] = e.y_root - m.winfo_y()
        def move(e):
            m.geometry(f"+{e.x_root - drag['x']}+{e.y_root - drag['y']}")
        top.bind("<Button-1>", start)
        top.bind("<B1-Motion>", move)

        body = ctk.CTkScrollableFrame(
            m, fg_color=BAR, scrollbar_button_color=ROW,
            scrollbar_button_hover_color=TOP_EDGE,
        )
        body.pack(fill="both", expand=True, padx=6, pady=6)

        def pick(i: int):
            self._apply_theme(i)
            try: m.destroy()
            except Exception: pass
            self._theme_picker = None

        for i, th in enumerate(THEMES):
            is_cur = (i == self._theme_idx)
            row = ctk.CTkFrame(
                body, fg_color=theme_get(th, "ACCENT") if is_cur
                else theme_get(th, "PANEL"),
                corner_radius=0, height=48,
            )
            row.pack(fill="x", pady=2, padx=2)
            row.pack_propagate(False)

            name = theme_get(th, "NAME") or f"theme {i}"
            ctk.CTkLabel(
                row, text=name, text_color=theme_get(th, "TEXT"),
                font=F_BODY, anchor="w", width=140,
            ).pack(side="left", padx=10)

            for key in ("BG", "ME", "OTHER", "ACCENT"):
                sw = ctk.CTkFrame(row, fg_color=theme_get(th, key),
                                  width=20, height=20, corner_radius=0)
                sw.pack(side="left", padx=3, pady=14)
                sw.pack_propagate(False)
                sw.bind("<Button-1>", lambda _e, idx=i: pick(idx))

            row.bind("<Button-1>", lambda _e, idx=i: pick(idx))
            for child in row.winfo_children():
                child.bind("<Button-1>", lambda _e, idx=i: pick(idx))

        def on_t(_e=None):
            try: m.destroy()
            except Exception: pass
            self._theme_picker = None
            return "break"

        def on_esc(_e=None):
            return on_t()

        m.bind("<KeyPress-t>", on_t)
        m.bind("<KeyPress-T>", on_t)
        m.bind("<Escape>", on_esc)
        m.after(60, m.focus_force)
        self._theme_picker = m

    def _on_close(self):
        try:
            self.player.shutdown()
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    App().mainloop()

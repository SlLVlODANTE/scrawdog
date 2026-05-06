"""Минимальная обёртка над публичными эндпоинтами SoundCloud.

Использует client_id, извлекаемый со страницы soundcloud.com (так же,
как scdl и soundcloud-lib). Для приватных вещей (мои плейлисты, лайки)
нужен oauth_token — берётся из cookies браузера (см. README).
"""
from __future__ import annotations

import re
import requests
from typing import Optional

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
API = "https://api-v2.soundcloud.com"

# зашитые публичные client_id, которые используются в open-source клиентах
# (scdl, soundcloud-lib и т.п.). Если SoundCloud один отзовёт — попробуем другой.
FALLBACK_CLIENT_IDS = [
    "iZIs9mchVcX5lhVRyQGGAYlNPVldzAoX",
    "a3e059563d7fd3372b49b37f00a00bcf",
    "2t9loNQH90kzJcsFCODdigxfp325aq4z",
    "T6cBLt8SUkuYpvRSrMD1ePeKTQHmCpth",
]


class SoundCloud:
    def __init__(self, oauth_token: Optional[str] = None,
                 forced_client_id: Optional[str] = None):
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
        self.client_id: Optional[str] = None
        self.oauth_token = oauth_token
        if oauth_token:
            self.s.headers["Authorization"] = f"OAuth {oauth_token}"

        if forced_client_id:
            # доверяем заданному вручную
            self.client_id = forced_client_id
            if self._client_id_works():
                return
        # пробуем выдрать со страницы
        try:
            self._scrape_client_id()
            if self._client_id_works():
                return
        except Exception:
            pass
        # fallback: перебираем зашитые
        for cid in FALLBACK_CLIENT_IDS:
            self.client_id = cid
            if self._client_id_works():
                return
        raise RuntimeError(
            "Не удалось получить рабочий client_id. "
            "SoundCloud мог обновить ключи. "
            "Попробуй позже или задай client_id вручную в config.json "
            "(поле \"client_id\")."
        )

    # ---------- client_id ----------
    def _client_id_works(self) -> bool:
        if not self.client_id:
            return False
        try:
            r = self.s.get(f"{API}/search/tracks",
                           params={"client_id": self.client_id, "q": "test", "limit": 1},
                           timeout=10)
            return r.status_code == 200
        except Exception:
            return False

    def _scrape_client_id(self) -> None:
        for page in ("https://soundcloud.com/discover",
                     "https://soundcloud.com/"):
            try:
                html = self.s.get(page, timeout=10).text
            except Exception:
                continue
            if not html or "<script" not in html:
                continue
            scripts = re.findall(r'<script[^>]+src="([^"]+)"', html)
            for url in reversed(scripts):
                try:
                    js = self.s.get(url, timeout=10).text
                except Exception:
                    continue
                for pat in (
                    r'client_id\s*[:=]\s*"([a-zA-Z0-9]{20,})"',
                    r'client_id=([a-zA-Z0-9]{20,})',
                    r'"client_id":"([a-zA-Z0-9]{20,})"',
                ):
                    m = re.search(pat, js)
                    if m:
                        self.client_id = m.group(1)
                        return

    def _params(self, **extra) -> dict:
        p = {"client_id": self.client_id}
        p.update(extra)
        return p

    # ---------- API ----------
    def search_tracks(self, q: str, limit: int = 20) -> list[dict]:
        r = self.s.get(f"{API}/search/tracks", params=self._params(q=q, limit=limit))
        r.raise_for_status()
        return r.json().get("collection", [])

    def me(self) -> dict:
        r = self.s.get(f"{API}/me", params=self._params())
        r.raise_for_status()
        return r.json()

    def my_playlists(self, limit: int = 50) -> list[dict]:
        me = self.me()
        r = self.s.get(
            f"{API}/users/{me['id']}/playlists",
            params=self._params(limit=limit),
        )
        r.raise_for_status()
        return r.json().get("collection", [])

    def my_likes(self, limit: int = 50) -> list[dict]:
        me = self.me()
        r = self.s.get(
            f"{API}/users/{me['id']}/track_likes",
            params=self._params(limit=limit),
        )
        r.raise_for_status()
        items = r.json().get("collection", [])
        return [it["track"] for it in items if it.get("track")]

    def playlist(self, playlist_id: int) -> dict:
        r = self.s.get(f"{API}/playlists/{playlist_id}", params=self._params())
        r.raise_for_status()
        return r.json()

    def like_track(self, track_id: int) -> bool:
        """Лайкнуть трек. Нужен oauth_token."""
        if not self.oauth_token:
            raise RuntimeError("OAuth token required to like")
        # пробуем несколько известных эндпоинтов
        for url in (
            f"{API}/me/track_likes/{track_id}",
            f"{API}/users/{self.me()['id']}/track_likes/{track_id}",
        ):
            r = self.s.put(url, params=self._params())
            if r.status_code in (200, 201):
                return True
        raise RuntimeError(f"like failed: HTTP {r.status_code} {r.text[:120]}")

    def unlike_track(self, track_id: int) -> bool:
        if not self.oauth_token:
            raise RuntimeError("OAuth token required")
        for url in (
            f"{API}/me/track_likes/{track_id}",
            f"{API}/users/{self.me()['id']}/track_likes/{track_id}",
        ):
            r = self.s.delete(url, params=self._params())
            if r.ok:
                return True
        return False

    def add_to_playlist(self, playlist_id: int, track_id: int) -> bool:
        """Добавить трек в плейлист (получаем текущий список и PUT обновляем)."""
        if not self.oauth_token:
            raise RuntimeError("OAuth token required")
        pl = self.playlist(playlist_id)
        existing = []
        for t in pl.get("tracks", []) or []:
            tid = t.get("id") if isinstance(t, dict) else t
            if tid:
                existing.append(int(tid))
        if track_id in existing:
            return True
        existing.append(track_id)
        body = {"playlist": {"tracks": [{"id": tid} for tid in existing]}}
        r = self.s.put(
            f"{API}/playlists/{playlist_id}",
            params=self._params(),
            json=body,
        )
        if not r.ok:
            raise RuntimeError(f"add_to_playlist: HTTP {r.status_code} {r.text[:120]}")
        return True

    def stream_url(self, track: dict) -> Optional[str]:
        """Возвращает прямой HLS/прогрессив URL для воспроизведения."""
        media = track.get("media", {}).get("transcodings", [])
        if not media:
            return None
        # предпочитаем прогрессив mp3, fallback на hls
        chosen = None
        for t in media:
            fmt = t.get("format", {})
            if t.get("format", {}).get("protocol") == "progressive" and "mpeg" in fmt.get("mime_type", ""):
                chosen = t
                break
        if chosen is None:
            chosen = media[0]
        url = chosen["url"]
        r = self.s.get(url, params=self._params())
        r.raise_for_status()
        return r.json().get("url")

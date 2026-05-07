# scrawdog

Минималистичный десктоп-клиент SoundCloud на Python + customtkinter + libmpv.

## Возможности
- Поиск треков по SoundCloud
- Воспроизведение прямо из клиента (стрим, без скачивания)
- Прогресс-бар, перемотка, громкость, next/prev
- Свои плейлисты и лайки (нужен OAuth токен)
- Страница артиста по клику на ник (только его треки, без репостов)
- Несколько тёмных/светлых тем — переключаются по `T`

## Запуск из исходников

1. Установи Python 3.10+
2. Скачай **libmpv-2** для Windows x64:
   https://sourceforge.net/projects/mpv-player-windows/files/libmpv/
   Из архива возьми `libmpv-2.dll` и положи в эту же папку.
3. ```
   pip install -r requirements.txt
   python main.py
   ```

## Сборка одного .exe

1. Положи `libmpv-2.dll` в папку проекта.
2. Запусти `build.bat`.
3. Готовый файл: `dist\scrawdog.exe` (~70-90 МБ, всё внутри).

## Установщик (Inno Setup)

1. Сначала собери `.exe` (см. выше).
2. Установи [Inno Setup 6](https://jrsoftware.org/isdl.php).
3. Запусти `build_installer.bat`.
4. Готовый установщик: `installer\scrawdog Setup.exe`.

## OAuth токен (для своих плейлистов и лайков)

SoundCloud не выдаёт публичные ключи приложений с 2021 г., поэтому
приватные данные читаются с твоим личным токеном из браузера:

1. Залогинься на https://soundcloud.com
2. F12 → **Application** → **Cookies** → `https://soundcloud.com`
3. Скопируй значение cookie **`oauth_token`**
   (выглядит как `2-1234567-...`)
4. В клиенте набери на клавиатуре `login`, вставь токен, Save.

Токен сохраняется локально в `%APPDATA%\SCMini\config.json`.

## Заметки
- `client_id` извлекается со страницы soundcloud.com автоматически
  (так делают `scdl`, `soundcloud-lib` и др.) — от тебя ничего не нужно.
- Это неофициальный клиент. Используй на свой риск, для личного прослушивания.

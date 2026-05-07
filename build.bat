@echo off
REM Сборка одного .exe со встроенным libmpv.
REM Перед запуском положи libmpv-2.dll рядом с этим .bat.

if not exist libmpv-2.dll (
    echo [!] libmpv-2.dll не найден.
    echo Скачай libmpv-2 для Windows ^(x64^) с
    echo https://sourceforge.net/projects/mpv-player-windows/files/libmpv/
    echo и распакуй libmpv-2.dll рядом с этим build.bat
    pause
    exit /b 1
)

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

pyinstaller --noconfirm --onefile --windowed ^
  --name "scrawdog" ^
  --icon "icon.ico" ^
  --add-binary "libmpv-2.dll;." ^
  --add-data "icon.ico;." ^
  main.py

echo.
echo Done: dist\scrawdog.exe
pause

@echo off
chcp 65001 >nul
echo ============================================
echo  Сборка Faceit Analytics через Nuitka
echo ============================================
cd /d "F:\faceit_analytic"
python -m nuitka ^
    --standalone ^
    --onefile ^
    --enable-plugin=pyside6 ^
    --include-package=src ^
    --include-package=pyqtgraph ^
    --include-package=aiohttp ^
    --include-package=orjson ^
    --include-package=browser_cookie3 ^
    --include-data-dir=data=data ^
    --output-dir=build\dist ^
    --output-filename=FaceitAnalytics.exe ^
    --assume-yes-for-downloads ^
    --show-progress ^
    main.py
echo.
echo Готово! exe: build\dist\FaceitAnalytics.exe
pause

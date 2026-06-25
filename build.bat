@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo ============================================================
echo   通用测试管理工具  --  打包脚本
echo ============================================================
echo.

:: ── 1. 检查 Python ──────────────────────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 python，请安装 Python 3.10+ 并加入 PATH。
    exit /b 1
)
for /f "delims=" %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
echo [OK] %PY_VER%

:: ── 2. 安装 / 升级依赖 ──────────────────────────────────────
echo [步骤 1/4] 安装/升级依赖...
python -m pip install --upgrade pip >nul
python -m pip install --quiet -r requirements.txt pillow pyinstaller
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络或手动执行：
    echo        python -m pip install -r requirements.txt pillow pyinstaller
    exit /b 1
)
echo [OK] 依赖已就绪

:: ── 3. 生成图标 ──────────────────────────────────────────────
echo [步骤 2/4] 生成图标...
python resources\make_icon.py
if errorlevel 1 (
    echo [警告] 图标生成失败，将使用默认图标继续打包。
    set "ICON_ARG="
) else (
    set "ICON_ARG=--icon resources\\app.ico"
)

:: ── 4. 清理旧产物 ────────────────────────────────────────────
echo [步骤 3/4] 清理旧打包目录...
if exist "dist\ATETest" (
    rmdir /s /q "dist\ATETest"
)
if exist "build\ATETest" (
    rmdir /s /q "build\ATETest"
)

:: ── 5. PyInstaller 打包 ──────────────────────────────────────
echo [步骤 4/4] 执行 PyInstaller...
echo.

python -m PyInstaller ^
    --noconfirm ^
    --onedir ^
    --windowed ^
    --name "ATETest" ^
    %ICON_ARG% ^
    --add-data "resources;resources" ^
    --add-data "test_plans;test_plans" ^
    --add-data "test_scripts;test_scripts" ^
    --add-data "reports;reports" ^
    --paths "." ^
    --hidden-import "PyQt5.sip" ^
    --hidden-import "yaml" ^
    --hidden-import "openpyxl" ^
    main.py

if errorlevel 1 goto :fail

:: ── 6. 完成 ─────────────────────────────────────────────────
echo.
echo ============================================================
echo   打包成功！
echo   输出目录: %~dp0dist\ATETest\
echo   可执行文件: dist\ATETest\ATETest.exe
echo ============================================================
echo.
pause
exit /b 0

:fail
echo.
echo ============================================================
echo   打包失败，请检查上方错误信息。
echo ============================================================
echo.
pause
exit /b 1

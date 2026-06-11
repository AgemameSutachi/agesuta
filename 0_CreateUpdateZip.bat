@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem ==========================================
rem  自己アップデート処理
rem ==========================================
set "MASTER_BAT=F:\GoogleDrive\develop\developing\server_manager\0_CreateUpdateZip.bat"
rem ※PowerShell呼び出し名に合わせて CreateUpdateZip.ps1 としています
set "MASTER_PS1=F:\GoogleDrive\develop\developing\server_manager\CreateUpdateZip.ps1"

set "LOCAL_BAT=%~f0"
set "LOCAL_PS1=%~dp0CreateUpdateZip.ps1"

rem --- 1. BATファイルの更新チェックと自己再起動 ---
if exist "%MASTER_BAT%" (
        rem ％％~tA でファイルの更新日時を取得します
    for %%A in ("%MASTER_BAT%") do set "TIME_M_BAT=%%~tA"
    for %%A in ("%LOCAL_BAT%") do set "TIME_L_BAT=%%~tA"
    
    if not "!TIME_M_BAT!"=="!TIME_L_BAT!" (
        echo [Update] バッチファイルを最新版に更新しています...
                rem 実行中のBAT自身を上書きするため、（） でブロック化してメモリ上に読み込ませてから実行します
        (
            copy /y "%MASTER_BAT%" "%LOCAL_BAT%" > nul
            cmd /c "%LOCAL_BAT%"
            exit /b
        )
    )
)

rem --- 2. PS1ファイルの更新チェック ---
if exist "%MASTER_PS1%" (
    for %%A in ("%MASTER_PS1%") do set "TIME_M_PS1=%%~tA"
    
    if exist "%LOCAL_PS1%" (
        for %%A in ("%LOCAL_PS1%") do set "TIME_L_PS1=%%~tA"
    ) else (
        set "TIME_L_PS1="
    )
    
    if not "!TIME_M_PS1!"=="!TIME_L_PS1!" (
        echo [Update] PowerShellスクリプトを最新版に更新しています...
        copy /y "%MASTER_PS1%" "%LOCAL_PS1%" > nul
    )
)

rem ==========================================
rem  メイン処理
rem ==========================================
set "ZIP_NAME=system_update.zip"

echo ====================================================
echo  Antigravity Update ZIP Creator (Generic)
echo ====================================================
echo.

if exist "%ZIP_NAME%" del "%ZIP_NAME%"

echo Checking project structure...

powershell -NoProfile -ExecutionPolicy Bypass -File ".\CreateUpdateZip.ps1"

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] ZIP creation failed.
    pause
    exit /b 1
)

echo.
echo ====================================================
echo  Success!
echo  The file '%ZIP_NAME%' is ready to be deployed.
echo ====================================================
pause

@echo off
@REM 開発用のvenv作成するスクリプト
echo 環境を作成します
cd /d %~dp0

if not exist "%UserProfile%\temp\" (
    mkdir "%UserProfile%\temp\"
    echo ディレクトリ作成: "%UserProfile%\temp\"
)
if not exist "%UserProfile%\temp\venv\" (
    mkdir "%UserProfile%\temp\venv\"
    echo ディレクトリ作成: "%UserProfile%\temp\venv\"
)

set DIRECTORY_PATH=%~dp0
for %%i in ("%DIRECTORY_PATH:~0,-1%") do set THIS_DIRECTORY=%%~ni

if exist %UserProfile%\temp\venv\%THIS_DIRECTORY% (
    echo 環境が存在するため、作成しません: %UserProfile%\temp\venv\%THIS_DIRECTORY%
    if exist %UserProfile%\temp\venv\%THIS_DIRECTORY%\Scripts\Activate.bat (
        call %UserProfile%\temp\venv\%THIS_DIRECTORY%\Scripts\Activate.bat
        echo アクティベート完了
        cd /d %~dp0
        pip install -U certifi
        pip freeze >requirements.txt
        echo ライブラリインストール完了
        call deactivate
    ) else (
        echo アクティベート失敗
        call deactivate
    )
    echo %DIRECTORY_PATH%env\Scripts\activate.ps1
    echo %DIRECTORY_PATH%env\Scripts\activate.ps1 | clip
) else (
    echo 環境作成: %UserProfile%\temp\venv\%THIS_DIRECTORY%
    python -m venv %UserProfile%\temp\venv\%THIS_DIRECTORY%
    if exist %UserProfile%\temp\venv\%THIS_DIRECTORY%\Scripts\Activate.bat (
        call %UserProfile%\temp\venv\%THIS_DIRECTORY%\Scripts\Activate.bat
        echo 環境作成完了
        cd /d %~dp0
        python.exe -m pip install --upgrade pip
        if exist ".\requirements.txt" (
            pip install -r .\requirements.txt
        )
        pip freeze >requirements.txt
        ipython kernel install --user --name=%THIS_DIRECTORY%
        call deactivate
        echo ライブラリインストール完了 
        echo %UserProfile%\temp\venv\%THIS_DIRECTORY%\Scripts\activate.ps1 | clip
        echo クリップボードにコピーしました。: %UserProfile%\temp\venv\%THIS_DIRECTORY%\Scripts\activate.ps1
    ) else (
        echo 環境作成失敗
        call deactivate
    )
)
pause
exit /b

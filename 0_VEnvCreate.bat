@echo off
chcp 65001 > nul
@REM For developmentvenvcreation script
echo create environment
cd /d %~dp0

if not exist "%UserProfile%\temp\" (
    mkdir "%UserProfile%\temp\"
    echo Create directory: "%UserProfile%\temp\"
)
if not exist "%UserProfile%\temp\venv\" (
    mkdir "%UserProfile%\temp\venv\"
    echo Create directory: "%UserProfile%\temp\venv\"
)

set DIRECTORY_PATH=%~dp0
for %%i in ("%DIRECTORY_PATH:~0,-1%") do set THIS_DIRECTORY=%%~ni

if exist %UserProfile%\temp\venv\%THIS_DIRECTORY% (
    echo As environment exists、will not create: %UserProfile%\temp\venv\%THIS_DIRECTORY%
    if exist %UserProfile%\temp\venv\%THIS_DIRECTORY%\Scripts\Activate.bat (
        call %UserProfile%\temp\venv\%THIS_DIRECTORY%\Scripts\Activate.bat
        echo Activation completed
        cd /d %~dp0
        pip install -U agesuta
        pip install -U certifi
        pip install pyinstaller
        pip freeze >requirements.txt
        echo Library installation completed
        call deactivate
    ) else (
        echo Activation failed
        call deactivate
    )
    echo %DIRECTORY_PATH%env\Scripts\activate.ps1
    echo %DIRECTORY_PATH%env\Scripts\activate.ps1 | clip
) else (
    echo Create Environment: %UserProfile%\temp\venv\%THIS_DIRECTORY%
    python -m venv %UserProfile%\temp\venv\%THIS_DIRECTORY%
    if exist %UserProfile%\temp\venv\%THIS_DIRECTORY%\Scripts\Activate.bat (
        call %UserProfile%\temp\venv\%THIS_DIRECTORY%\Scripts\Activate.bat
        echo Environment creation completed
        cd /d %~dp0
        python.exe -m pip install --upgrade pip
        if exist ".\requirements.txt" (
            pip install -r .\requirements.txt
        )
        pip install -U agesuta
        pip install pyinstaller
        pip install ipykernel
        pip freeze >requirements.txt
        ipython kernel install --user --name=%THIS_DIRECTORY%
        call deactivate
        echo Library installation completed 
        git init 
        git add .
        git commit -m "Execute %~nx0"
        echo %UserProfile%\temp\venv\%THIS_DIRECTORY%\Scripts\activate.ps1 | clip
        echo Copied to clipboard。: %UserProfile%\temp\venv\%THIS_DIRECTORY%\Scripts\activate.ps1
    ) else (
        echo Environment creation failed
        call deactivate
    )
)
pause
exit /b

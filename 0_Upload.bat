@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

rem For developmentvenv activation and PyPIupload automation batch
echo pipにアップロードをStartします
cd /d %~dp0

rem Checking and creating temporary and venv directories
if not exist "%UserProfile%\temp\" (
    mkdir "%UserProfile%\temp\"
    echo Create directory: "%UserProfile%\temp\"
)
if not exist "%UserProfile%\temp\venv\" (
    mkdir "%UserProfile%\temp\venv\"
    echo Create directory: "%UserProfile%\temp\venv\"
)

rem Get current directory name
set DIRECTORY_PATH=%~dp0
for %%i in ("%DIRECTORY_PATH:~0,-1%") do set THIS_DIRECTORY=%%~ni

rem venvpath construction
set "VENV_PATH=%UserProfile%\temp\venv\%THIS_DIRECTORY%"
echo Virtual environment path: "%VENV_PATH%"

rem venvCheck if exists
if exist "%VENV_PATH%" (
    echo Virtual environment detected: "%VENV_PATH%"
        rem venvCheck if activation script exists
    if exist "%VENV_PATH%\Scripts\Activate.bat" (
        echo Activating virtual environment...
        call "%VENV_PATH%\Scripts\Activate.bat"
        echo Activation completed
        cd /d %~dp0

                rem version.txtRead version from
        set "VERSION="
        for /f "usebackq delims=" %%i in (".\agesuta\version.txt") do (
            echo %%i
            set "VERSION=%%i"
        )

                rem Remove newline code from version info - CR and LFsupported
        if "!VERSION:~-2!"=="\r\n" set "VERSION=!VERSION:~0,-2!"
        if "!VERSION:~-1!"=="\n" set "VERSION=!VERSION:~0,-1!"
        if "!VERSION:~-1!"=="\r" set "VERSION=!VERSION:~0,-1!"

        if "!VERSION!"=="" (
            echo Error: Could not read version from .\agesuta\version.txt or version is empty.
            call deactivate
            goto :end
        )

        echo version: !VERSION!

                rem build関連コマンドのExecute
        cd /d %~dp0
        echo Cleaning dist directory...
        if exist dist (
            rmdir /s /q dist
        )

        echo Building sdist...
        python setup.py sdist

        echo Building bdist_wheel...
        python setup.py bdist_wheel

                rem TestPyPIuploading to
        echo Uploading to TestPyPI...
        twine upload --repository testpypi dist/*
        if errorlevel 1 (
            echo Error uploading to TestPyPI. Aborting.
            call deactivate
            goto :end
        )

                rem PyPIuploading to
        echo Uploading to PyPI...
        twine upload --repository pypi dist/*
        if errorlevel 1 (
            echo Error uploading to PyPI. Aborting.
            call deactivate
            goto :end
        )

                rem GitSafe handling of commit
        echo GitChecking change status of...
        set "HAS_CHANGES="
        for /f "tokens=*" %%a in ('git status --porcelain') do set HAS_CHANGES=1

        if defined HAS_CHANGES (
            echo Uncommitted changes detected。GitCreate commit...
            git add .
            SET /P INPUTSTR="Please enter commit message: "
            echo Committing with message: !VERSION! !INPUTSTR!
            git commit -m "!VERSION! !INPUTSTR!"
            if errorlevel 1 (
                echo Error during git commit. Aborting.
                call deactivate
                goto :end
            )
        ) else (
            echo Working tree はクリーンです。新規のGitコミット作成をSkipします。
        )

        echo Pushing to origin main...
        git push origin main
        if errorlevel 1 (
            echo Error during git push. Aborting.
            call deactivate
            goto :end
        )

                rem GitHub CLIrelease and tag creation using
        echo Creating GitHub release and tag: !VERSION!
        gh release create !VERSION! --title "!VERSION!" --notes "Release version !VERSION!"
        if errorlevel 1 (
            echo Error creating GitHub release. Please check if gh CLI is installed and authenticated.
            echo If the tag already exists, this command will fail.
            call deactivate
            goto :end
        )

        echo Release !VERSION! created successfully.

                rem venvdeactivate
        call deactivate
        echo Deactivation completed

    ) else (
        echo Error: Activation script not found: "%VENV_PATH%\Scripts\Activate.bat"
    )
    echo .

) else (
    echo Error: Virtual environment not found: "%VENV_PATH%"
    echo 仮想環境を作成するには、親フォルダで `python -m venv "%VENV_PATH%"` をExecuteしてください。
)

:end
pause
endlocal
exit /b

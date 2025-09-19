@echo off
setlocal enabledelayedexpansion

rem 開発用のvenv作成・アクティベートとpipアップロードスクリプト
echo pipにアップロードします
cd /d %~dp0

rem 一時ディレクトリとvenvディレクトリの存在確認と作成
if not exist "%UserProfile%\temp\" (
    mkdir "%UserProfile%\temp\"
    echo ディレクトリ作成: "%UserProfile%\temp\"
)
if not exist "%UserProfile%\temp\venv\" (
    mkdir "%UserProfile%\temp\venv\"
    echo ディレクトリ作成: "%UserProfile%\temp\venv\"
)

rem 現在のディレクトリ名を取得
set DIRECTORY_PATH=%~dp0
for %%i in ("%DIRECTORY_PATH:~0,-1%") do set THIS_DIRECTORY=%%~ni

rem venvのパスを構築
set "VENV_PATH=%UserProfile%\temp\venv\%THIS_DIRECTORY%"
echo "%VENV_PATH%"
rem venvが存在するか確認
if exist "%VENV_PATH%" (
    echo 環境が存在する: "%VENV_PATH%"
    rem venvのアクティベートスクリプトが存在するか確認
    if exist "%VENV_PATH%\Scripts\Activate.bat" (
        echo 環境をアクティベートします...
        call "%VENV_PATH%\Scripts\Activate.bat"
        echo アクティベート完了
        cd /d %~dp0

        rem version.txtからバージョン情報を読み込み、改行コードを削除
        set "VERSION="
        for /f "usebackq delims=" %%i in (".\agesuta\version.txt") do (
            echo %%i
            set "VERSION=%%i"
        )

        rem バージョン情報から改行コードを削除（CRとLFの両方に対応）
        rem 末尾がCRLFの場合
        if "!VERSION:~-2!"=="\r\n" set "VERSION=!VERSION:~0,-2!"
        rem 末尾がLFの場合
        if "!VERSION:~-1!"=="\n" set "VERSION=!VERSION:~0,-1!"
        rem 末尾がCRの場合
        if "!VERSION:~-1!"=="\r" set "VERSION=!VERSION:~0,-1!"


        if "!VERSION!"=="" (
            echo Error: Could not read version from .\agesuta\version.txt or version is empty.
            call deactivate
            goto :end
        )

        echo Version read: !VERSION!

        rem 元のビルド関連コマンド
        cd /d %~dp0
        echo Cleaning dist directory...
        rmdir /s /q dist
        rem /s: サブディレクトリを含むすべてのファイルとサブディレクトリを削除
        rem /q: 確認メッセージを表示しない（クワイエットモード）
        rem dist: 削除対象のディレクトリ名

        echo Building sdist...
        python setup.py sdist

        echo Building bdist_wheel...
        python setup.py bdist_wheel

        rem TestPyPIへのアップロード
        echo Uploading to TestPyPI...
        twine upload --repository testpypi dist/*
        if errorlevel 1 (
            echo Error uploading to TestPyPI. Aborting.
            call deactivate
            goto :end
        )

        rem PyPIへのアップロード
        echo Uploading to PyPI...
        twine upload --repository pypi dist/*
        if errorlevel 1 (
            echo Error uploading to PyPI. Aborting.
            call deactivate
            goto :end
        )

        rem Git操作
        echo Adding files to Git...
        git add .

        SET /P INPUTSTR="コミットメッセージを入力"
        rem コミットメッセージにバージョン情報を使用
        echo Committing with message: !VERSION! !INPUTSTR!
        git commit -m "!VERSION! !INPUTSTR!"
        if errorlevel 1 (
            echo Error during git commit. Aborting.
            call deactivate
            goto :end
        )

        echo Pushing to origin main...
        git push origin main
        if errorlevel 1 (
            echo Error during git push. Aborting.
            call deactivate
            goto :end
        )

        rem GitHub CLIを使用してリリースを作成し、タグ付け
        rem 事前にGitHub CLIのインストールと認証が必要です
        echo Creating GitHub release and tag: !VERSION!
        gh release create !VERSION! --title "!VERSION!" --notes "Release version !VERSION!"
        if errorlevel 1 (
            echo Error creating GitHub release. Please check if gh CLI is installed and authenticated.
            echo If the tag already exists, this command will fail.
            call deactivate
            goto :end
        )

        echo Release !VERSION! created successfully.

        rem venvをディアクティベート
        call deactivate
        echo ディアクティベート完了

    ) else (
        echo エラー: アクティベートスクリプトが見つかりません: "%VENV_PATH%\Scripts\Activate.bat"
    )
    echo 完了

) else (
    echo 環境なし: "%VENV_PATH%"
    echo venvを作成するには、手動で `python -m venv "%VENV_PATH%"` を実行してください。
)

:end
pause
endlocal
exit /b

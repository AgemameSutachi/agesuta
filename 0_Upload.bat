@echo off
setlocal enabledelayedexpansion

rem 開発用venvのアクティベートおよびPyPIアップロード自動化バッチ
echo pipにアップロードを開始します
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

rem venvのパス構築
set "VENV_PATH=%UserProfile%\temp\venv\%THIS_DIRECTORY%"
echo 仮想環境パス: "%VENV_PATH%"

rem venvが存在するか確認
if exist "%VENV_PATH%" (
    echo 仮想環境を検出しました: "%VENV_PATH%"
    rem venvのアクティベートスクリプトが存在するか確認
    if exist "%VENV_PATH%\Scripts\Activate.bat" (
        echo 仮想環境をアクティベート中...
        call "%VENV_PATH%\Scripts\Activate.bat"
        echo アクティベート完了
        cd /d %~dp0

        rem version.txtからバージョン読み込み
        set "VERSION="
        for /f "usebackq delims=" %%i in (".\agesuta\version.txt") do (
            echo %%i
            set "VERSION=%%i"
        )

        rem バージョン情報から改行コードを削除 - CRおよびLFに対応します
        if "!VERSION:~-2!"=="\r\n" set "VERSION=!VERSION:~0,-2!"
        if "!VERSION:~-1!"=="\n" set "VERSION=!VERSION:~0,-1!"
        if "!VERSION:~-1!"=="\r" set "VERSION=!VERSION:~0,-1!"

        if "!VERSION!"=="" (
            echo Error: Could not read version from .\agesuta\version.txt or version is empty.
            call deactivate
            goto :end
        )

        echo バージョン: !VERSION!

        rem ビルド関連コマンドの実行
        cd /d %~dp0
        echo Cleaning dist directory...
        if exist dist (
            rmdir /s /q dist
        )

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

        rem Gitコミットの安全な処理
        echo Gitの変更状況を確認しています...
        set "HAS_CHANGES="
        for /f "tokens=*" %%a in ('git status --porcelain') do set HAS_CHANGES=1

        if defined HAS_CHANGES (
            echo 未コミットの変更を検出しました。Gitコミットを作成します...
            git add .
            SET /P INPUTSTR="コミットメッセージを入力してください: "
            echo Committing with message: !VERSION! !INPUTSTR!
            git commit -m "!VERSION! !INPUTSTR!"
            if errorlevel 1 (
                echo Error during git commit. Aborting.
                call deactivate
                goto :end
            )
        ) else (
            echo Working tree はクリーンです。新規のGitコミット作成をスキップします。
        )

        echo Pushing to origin main...
        git push origin main
        if errorlevel 1 (
            echo Error during git push. Aborting.
            call deactivate
            goto :end
        )

        rem GitHub CLIを使用したリリースとタグの作成
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
    echo .

) else (
    echo エラー: 仮想環境が見つかりません: "%VENV_PATH%"
    echo 仮想環境を作成するには、親フォルダで `python -m venv "%VENV_PATH%"` を実行してください。
)

:end
pause
endlocal
exit /b

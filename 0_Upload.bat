@echo off
setlocal enabledelayedexpansion

rem �J���p��venv�쐬�E�A�N�e�B�x�[�g��pip�A�b�v���[�h�X�N���v�g
echo pip�ɃA�b�v���[�h���܂�
cd /d %~dp0

rem �ꎞ�f�B���N�g����venv�f�B���N�g���̑��݊m�F�ƍ쐬
if not exist "%UserProfile%\temp\" (
    mkdir "%UserProfile%\temp\"
    echo �f�B���N�g���쐬: "%UserProfile%\temp\"
)
if not exist "%UserProfile%\temp\venv\" (
    mkdir "%UserProfile%\temp\venv\"
    echo �f�B���N�g���쐬: "%UserProfile%\temp\venv\"
)

rem ���݂̃f�B���N�g�������擾
set DIRECTORY_PATH=%~dp0
for %%i in ("%DIRECTORY_PATH:~0,-1%") do set THIS_DIRECTORY=%%~ni

rem venv�̃p�X���\�z
set "VENV_PATH=%UserProfile%\temp\venv\%THIS_DIRECTORY%"
echo "%VENV_PATH%"
rem venv�����݂��邩�m�F
if exist "%VENV_PATH%" (
    echo �������݂���: "%VENV_PATH%"
    rem venv�̃A�N�e�B�x�[�g�X�N���v�g�����݂��邩�m�F
    if exist "%VENV_PATH%\Scripts\Activate.bat" (
        echo �����A�N�e�B�x�[�g���܂�...
        call "%VENV_PATH%\Scripts\Activate.bat"
        echo �A�N�e�B�x�[�g����
        cd /d %~dp0

        rem version.txt����o�[�W��������ǂݍ��݁A���s�R�[�h���폜
        set "VERSION="
        for /f "usebackq delims=" %%i in (".\agesuta\version.txt") do (
            echo %%i
            set "VERSION=%%i"
        )

        rem �o�[�W������񂩂���s�R�[�h���폜�iCR��LF�̗����ɑΉ��j
        rem ������CRLF�̏ꍇ
        if "!VERSION:~-2!"=="\r\n" set "VERSION=!VERSION:~0,-2!"
        rem ������LF�̏ꍇ
        if "!VERSION:~-1!"=="\n" set "VERSION=!VERSION:~0,-1!"
        rem ������CR�̏ꍇ
        if "!VERSION:~-1!"=="\r" set "VERSION=!VERSION:~0,-1!"


        if "!VERSION!"=="" (
            echo Error: Could not read version from .\agesuta\version.txt or version is empty.
            call deactivate
            exit /b 1
        )

        echo aaa
        echo Version read: !VERSION!
        echo bbb
        pause

        rem ���̃r���h�֘A�R�}���h
        cd /d %~dp0
        echo Cleaning build directory...
        rem rm -rf build  <-- Unix/Linux�R�}���h�̂��߃R�����g�A�E�g
        rmdir /s /q build  rem <-- Windows�Ńf�B���N�g�����폜����R�}���h
        rem /s: �T�u�f�B���N�g�����܂ނ��ׂẴt�@�C���ƃT�u�f�B���N�g�����폜
        rem /q: �m�F���b�Z�[�W��\�����Ȃ��i�N���C�G�b�g���[�h�j
        rem build: �폜�Ώۂ̃f�B���N�g����

        echo Building sdist...
        python setup.py sdist

        echo Building bdist_wheel...
        python setup.py bdist_wheel

        rem TestPyPI�ւ̃A�b�v���[�h
        echo Uploading to TestPyPI...
        twine upload --repository testpypi dist/*
        if errorlevel 1 (
            echo Error uploading to TestPyPI. Aborting.
            call deactivate
            exit /b 1
        )

        rem PyPI�ւ̃A�b�v���[�h
        echo Uploading to PyPI...
        twine upload --repository pypi dist/*
        if errorlevel 1 (
            echo Error uploading to PyPI. Aborting.
            call deactivate
            exit /b 1
        )

        rem Git����
        echo Adding files to Git...
        git add .

        rem �R�~�b�g���b�Z�[�W�Ƀo�[�W���������g�p
        echo Committing with message: !VERSION!
        git commit -m "!VERSION!"
        if errorlevel 1 (
            echo Error during git commit. Aborting.
            call deactivate
            exit /b 1
        )

        echo Pushing to origin main...
        git push origin main
        if errorlevel 1 (
            echo Error during git push. Aborting.
            call deactivate
            exit /b 1
        )

        rem GitHub CLI���g�p���ă����[�X���쐬���A�^�O�t��
        rem ���O��GitHub CLI�̃C���X�g�[���ƔF�؂��K�v�ł�
        echo Creating GitHub release and tag: !VERSION!
        gh release create !VERSION! --title "!VERSION!" --notes "Release version !VERSION!"
        if errorlevel 1 (
            echo Error creating GitHub release. Please check if gh CLI is installed and authenticated.
            echo If the tag already exists, this command will fail.
            call deactivate
            exit /b 1
        )

        echo Release !VERSION! created successfully.

        rem venv���f�B�A�N�e�B�x�[�g
        call deactivate
        echo �f�B�A�N�e�B�x�[�g����

    ) else (
        echo �G���[: �A�N�e�B�x�[�g�X�N���v�g��������܂���: "%VENV_PATH%\Scripts\Activate.bat"
    )
    rem venv�p�X���N���b�v�{�[�h�ɃR�s�[ (PowerShell���K�v)
    echo PowerShell���g�p����venv�p�X���N���b�v�{�[�h�ɃR�s�[���܂�...
    echo "%VENV_PATH%\Scripts\activate.ps1" | clip
    echo �N���b�v�{�[�h�ɃR�s�[���܂����B
) else (
    echo ���Ȃ�: "%VENV_PATH%"
    echo venv���쐬����ɂ́A�蓮�� `python -m venv "%VENV_PATH%"` �����s���Ă��������B
)

pause
endlocal
exit /b

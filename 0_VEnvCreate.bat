@echo off
@REM �J���p��venv�쐬����X�N���v�g
echo ����쐬���܂�
cd /d %~dp0

if not exist "%UserProfile%\temp\" (
    mkdir "%UserProfile%\temp\"
    echo �f�B���N�g���쐬: "%UserProfile%\temp\"
)
if not exist "%UserProfile%\temp\venv\" (
    mkdir "%UserProfile%\temp\venv\"
    echo �f�B���N�g���쐬: "%UserProfile%\temp\venv\"
)

set DIRECTORY_PATH=%~dp0
for %%i in ("%DIRECTORY_PATH:~0,-1%") do set THIS_DIRECTORY=%%~ni

if exist %UserProfile%\temp\venv\%THIS_DIRECTORY% (
    echo �������݂��邽�߁A�쐬���܂���: %UserProfile%\temp\venv\%THIS_DIRECTORY%
    if exist %UserProfile%\temp\venv\%THIS_DIRECTORY%\Scripts\Activate.bat (
        call %UserProfile%\temp\venv\%THIS_DIRECTORY%\Scripts\Activate.bat
        echo �A�N�e�B�x�[�g����
        cd /d %~dp0
        pip install -U certifi
        pip freeze >requirements.txt
        echo ���C�u�����C���X�g�[������
        call deactivate
    ) else (
        echo �A�N�e�B�x�[�g���s
        call deactivate
    )
    echo %DIRECTORY_PATH%env\Scripts\activate.ps1
    echo %DIRECTORY_PATH%env\Scripts\activate.ps1 | clip
) else (
    echo ���쐬: %UserProfile%\temp\venv\%THIS_DIRECTORY%
    python -m venv %UserProfile%\temp\venv\%THIS_DIRECTORY%
    if exist %UserProfile%\temp\venv\%THIS_DIRECTORY%\Scripts\Activate.bat (
        call %UserProfile%\temp\venv\%THIS_DIRECTORY%\Scripts\Activate.bat
        echo ���쐬����
        cd /d %~dp0
        python.exe -m pip install --upgrade pip
        if exist ".\requirements.txt" (
            pip install -r .\requirements.txt
        )
        pip freeze >requirements.txt
        ipython kernel install --user --name=%THIS_DIRECTORY%
        call deactivate
        echo ���C�u�����C���X�g�[������ 
        echo %UserProfile%\temp\venv\%THIS_DIRECTORY%\Scripts\activate.ps1 | clip
        echo �N���b�v�{�[�h�ɃR�s�[���܂����B: %UserProfile%\temp\venv\%THIS_DIRECTORY%\Scripts\activate.ps1
    ) else (
        echo ���쐬���s
        call deactivate
    )
)
pause
exit /b

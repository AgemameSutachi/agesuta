@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "ZIP_NAME=system_update.zip"

echo ====================================================
echo  Antigravity Update ZIP Creator (Generic)
echo ====================================================
echo.

if exist "%ZIP_NAME%" del "%ZIP_NAME%"

echo Checking project structure...

rem PowerShell を使って、EXEビルド (dist) かソースコードプロジェクトかを自動判定して ZIP化します。
powershell -NoProfile -ExecutionPolicy Bypass -Command "^
    $exclude = @('.git', '.antigravitycli', '.vscode', '.idea', 'venv', '.venv', 'env', 'node_modules', '__pycache__', 'storage', 'system_update.zip', '0_CreateUpdateZip.bat', '.env');^
    if (Test-Path 'dist') {^
        Write-Host '[EXE Detected] dist directory found. Packaging dist content only...' -ForegroundColor Cyan;^
        $files = Get-ChildItem -Path dist -Recurse -File;^
        Compress-Archive -Path $files.FullName -DestinationPath 'system_update.zip' -Force;^
    } else {^
        Write-Host '[Source Detected] Source code project. Packaging with exclude rules...' -ForegroundColor Yellow;^
        $files = Get-ChildItem -Path . -Recurse -File | Where-Object {^
            $path = $_.FullName;^
            $excludeThis = $false;^
            foreach ($pattern in $exclude) {^
                if ($path -like '*\' + $pattern + '*' -or $path -like '*/' + $pattern + '*') {^
                    $excludeThis = $true;^
                    break;^
                }^
            }^
            if ($_.Name -like '*.db' -or $_.Name -like '*.sqlite3') {^
                $excludeThis = $true;^
            }^
            -not $excludeThis;^
        };^
        Compress-Archive -Path $files.FullName -DestinationPath 'system_update.zip' -Force;^
    }^
"

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

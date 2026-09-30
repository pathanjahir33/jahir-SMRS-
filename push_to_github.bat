@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo    SMART METER READING SYSTEM - GITHUB PUSH HELPER
echo ========================================================
echo.

:: Check if git is installed
where git >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Git is not installed or not in PATH!
    echo Please install Git from https://git-scm.com/
    pause
    exit /b 1
)

:: Set repository URL
set REPO_URL=https://github.com/pathanjahir33/jahir-SMRS-.git
echo [*] Target Repository: !REPO_URL!
echo.

:: Initialize git repository if not already initialized
if not exist .git (
    echo [*] Initializing Git repository...
    git init
    git branch -M main
) else (
    echo [*] Existing Git repository detected.
    git branch -M main
)

:: Set or update remote origin
git remote get-url origin >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [*] Adding remote origin...
    git remote add origin !REPO_URL!
) else (
    echo [*] Updating remote origin...
    git remote set-url origin !REPO_URL!
)

echo.
echo [*] Staging project files (excluding .env, *.db, __pycache__)...
git add .

echo.
set COMMIT_MSG=Initial commit: Smart Meter Reading System (SMRS)
echo [*] Committing changes as: "!COMMIT_MSG!"...
git commit -m "!COMMIT_MSG!"

echo.
echo [*] Pushing to GitHub (main branch)...
git push -u origin main

if %ERRORLEVEL% equ 0 (
    echo.
    echo ========================================================
    echo  SUCCESS: Project successfully pushed to GitHub!
    echo  View repository: https://github.com/pathanjahir33/jahir-SMRS-
    echo ========================================================
) else (
    echo.
    echo [!] Push was rejected or encountered an issue.
    echo [*] Attempting to pull and rebase in case GitHub repo has initial files...
    git pull origin main --rebase
    git push -u origin main
    if !ERRORLEVEL! equ 0 (
        echo.
        echo ========================================================
        echo  SUCCESS: Project successfully pushed after rebase!
        echo ========================================================
    ) else (
        echo.
        echo [NOTE] If GitHub asks for authentication:
        echo   1. Use GitHub Personal Access Token (PAT) as password, OR
        echo   2. Sign in via the GitHub Credential Manager prompt, OR
        echo   3. Use GitHub Desktop to publish this folder.
    )
)

echo.
pause

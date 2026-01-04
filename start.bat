@echo off
setlocal

echo ========================================
echo       LLM Council - Start Script
echo ========================================
echo.

REM Check for uv
where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] 'uv' is not installed. Please install it first using:
    echo pip install uv
    echo or visit https://github.com/astral-sh/uv
    pause
    exit /b 1
)

REM Check for npm
where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] 'npm' is not installed. Please install Node.js first.
    pause
    exit /b 1
)

REM 1. Backend Setup
echo [Backend] Syncing dependencies...
call uv sync
if %errorlevel% neq 0 (
    echo [ERROR] Failed to sync backend dependencies.
    pause
    exit /b 1
)

REM 2. Frontend Setup
if not exist "frontend\node_modules" (
    echo [Frontend] Installing dependencies...
    cd frontend
    call npm install
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install frontend dependencies.
        cd ..
        pause
        exit /b 1
    )
    cd ..
)

REM 3. Check Environment
if not exist ".env" (
    echo.
    echo [WARNING] .env file not found!
    echo Please create a .env file in the root directory with:
    echo OPENROUTER_API_KEY=sk-or-v1-...
    echo.
    pause
)

echo.
echo Starting services...
echo.

REM Start Backend
echo Starting Backend (http://localhost:8001)...
start "LLM Council Backend" cmd /k "uv run python -m backend.main"

REM Wait a moment for backend to initialize
timeout /t 3 /nobreak >nul

REM Start Frontend
echo Starting Frontend (http://localhost:5173)...
cd frontend
start "LLM Council Frontend" cmd /k "npm run dev"

echo.
echo ========================================
echo      LLM Council is now running!
echo ========================================
echo.
echo Backend:  http://localhost:8001
echo Frontend: http://localhost:5173
echo.
echo Press any key to exit this launcher (servers will keep running)...
pause >nul

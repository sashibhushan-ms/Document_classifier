@echo off
echo Starting Docx Formula Mover...

:: Start Backend
echo Starting Backend Server...
start "Docx Backend" cmd /k "python src/server.py"

:: Start Frontend
echo Starting Frontend...
cd frontend
start "Docx Frontend" cmd /k "npm run dev"

echo Done. Backend running on http://localhost:5000. Frontend running on http://localhost:5173 (or 5174).
pause

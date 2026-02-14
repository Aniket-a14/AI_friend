@echo off
start cmd /k "cd backend && uvicorn main:app --reload --port 8000"
start cmd /k "cd frontend && npm run dev"
echo AI Friend is starting...
echo Backend: http://localhost:8000
echo Frontend: http://localhost:3000

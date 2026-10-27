@echo off
where pyw >nul 2>nul && (start "" pyw -3 "%~dp0launch.pyw" & exit /b 0)
where pythonw >nul 2>nul && (start "" pythonw "%~dp0launch.pyw" & exit /b 0)
echo Python 3.11 or later not found. Please install Python first.
pause

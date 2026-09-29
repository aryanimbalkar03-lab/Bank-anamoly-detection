@echo off
color 0B
echo ===============================================================
echo      ENTERPRISE FINANCIAL ANOMALY DETECTION PLATFORM
echo ===============================================================
echo.
echo [1/3] Downloading authentic Kaggle dataset...
python download_data.py
echo.
echo [2/3] Initializing PostgreSQL and injecting synthetic defects...
powershell.exe -ExecutionPolicy Bypass -File init_db.ps1
echo.
echo [3/3] Executing ETL, DAMA Rules, and Machine Learning Model...
powershell.exe -ExecutionPolicy Bypass -File resume.ps1
echo.
echo ===============================================================
echo PIPELINE EXECUTION COMPLETE! Check the dashboard for results.
echo ===============================================================
pause

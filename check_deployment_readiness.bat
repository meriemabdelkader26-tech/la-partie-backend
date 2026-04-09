@echo off
REM Check if data files are tracked by git and will be deployed

echo ========================================
echo CHECKING DATA FILES FOR DEPLOYMENT
echo ========================================
echo.

echo 1. Checking if data files exist locally...
echo.
if exist "data\influenceurs_recommendation_ready.csv" (
    echo    [OK] data\influenceurs_recommendation_ready.csv EXISTS
) else (
    echo    [FAIL] data\influenceurs_recommendation_ready.csv NOT FOUND
)

if exist "data\influenceurs_clean.csv" (
    echo    [OK] data\influenceurs_clean.csv EXISTS
) else (
    echo    [FAIL] data\influenceurs_clean.csv NOT FOUND
)

if exist "api\data\influenceurs_recommendation_ready.csv" (
    echo    [OK] api\data\influenceurs_recommendation_ready.csv EXISTS
) else (
    echo    [FAIL] api\data\influenceurs_recommendation_ready.csv NOT FOUND
)

echo.
echo 2. Checking if files are tracked by git...
echo.
git ls-files data/*.csv api/data/*.csv 2>nul
if errorlevel 1 (
    echo    [WARNING] No CSV files are tracked by git!
    echo    [ACTION REQUIRED] Run: git add data/*.csv api/data/*.csv
) else (
    echo    [OK] Files are tracked by git
)

echo.
echo 3. Checking .gitignore...
echo.
findstr /C:"*.csv" .gitignore >nul
if not errorlevel 1 (
    echo    [WARNING] .gitignore contains "*.csv" - files may be excluded!
    echo    [ACTION] Check .gitignore and comment out: *.csv
) else (
    echo    [OK] *.csv not found in .gitignore
)

findstr /C:"data/" .gitignore >nul
if not errorlevel 1 (
    echo    [WARNING] .gitignore contains "data/" - directory may be excluded!
    echo    [ACTION] Check .gitignore and comment out: data/
) else (
    echo    [OK] data/ not found in .gitignore
)

echo.
echo 4. Checking .dockerignore...
echo.
findstr /C:"*.csv" .dockerignore >nul
if not errorlevel 1 (
    findstr /C:"# *.csv" .dockerignore >nul
    if errorlevel 1 (
        echo    [FAIL] .dockerignore contains uncommented "*.csv"
        echo    [ACTION] Comment it out: # *.csv
    ) else (
        echo    [OK] *.csv is commented out in .dockerignore
    )
) else (
    echo    [OK] *.csv not found in .dockerignore
)

echo.
echo ========================================
echo SUMMARY
echo ========================================
echo.
echo If all checks pass, you can deploy:
echo    gcloud builds submit --config cloudbuild.yaml
echo.
echo After deployment, check logs:
echo    gcloud run logs read influBridge --region us-central1 --limit 100
echo.
pause

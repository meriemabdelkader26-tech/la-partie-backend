@echo off
echo ============================================================
echo COMPLETE FIX FOR DATA FILES NOT LOADING IN CLOUD RUN
echo ============================================================
echo.

echo STEP 1: Check what files exist locally
echo ------------------------------------------------------------
echo CSV files found:
dir /b data\*.csv 2>nul
dir /b api\data\*.csv 2>nul
echo.

echo STEP 2: Check what's tracked by git
echo ------------------------------------------------------------
echo Currently tracked CSV files:
git ls-files data/*.csv api/data/*.csv 2>nul
if errorlevel 1 echo    NONE TRACKED - This is why deployment fails!
echo.

echo STEP 3: Add data files to git (FORCING add to override any excludes)
echo ------------------------------------------------------------
git add -f data/*.csv
git add -f data/*.json
git add -f data/*.npy
git add -f api/data/*.csv
git add -f api/data/*.json  
git add -f api/data/*.npy
echo Done.
echo.

echo STEP 2: Commit the data files
echo ------------------------------------------------------------
git commit -m "Add data files for production deployment"
echo.

echo STEP 3: Verify files are staged
echo ------------------------------------------------------------
echo Data files in git:
git ls-files data/*.csv api/data/*.csv
echo.

echo STEP 4: Check .dockerignore
echo ------------------------------------------------------------
type .dockerignore | findstr /C:"csv"
echo.
echo NOTE: Make sure lines with *.csv and data/*.csv are COMMENTED OUT (have # in front)
echo.

echo STEP 5: Ready to deploy
echo ------------------------------------------------------------
echo Run this command to deploy:
echo    gcloud builds submit --config cloudbuild.yaml
echo.
echo Or if using docker directly:
echo    gcloud run deploy influBridge --source . --region us-central1
echo.
echo ============================================================
echo IMPORTANT: After deployment, check the build logs!
echo.
echo Look for the "VERIFYING DATA FILES" section in the build output.
echo It should show: "✓ influenceurs_recommendation_ready.csv found"
echo ============================================================
pause

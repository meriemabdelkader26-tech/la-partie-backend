# Google Cloud Run REST API Fix

## Problem

The REST API endpoints (like `/api/recommend/`) were returning 500 errors on Google Cloud Run while working fine locally. GraphQL API worked fine.

## Root Causes

1. **Missing data files** - CSV files weren't being found in production
2. **No error logging** - Generic 500 error with no details
3. **Missing hostname** - Google Cloud Run domain not in ALLOWED_HOSTS

## Changes Made

### 1. Enhanced Error Logging (`api/views.py`)

- Added comprehensive logging throughout the recommender system
- Added detailed traceback information for debugging
- Log all file path checks during initialization
- Log request parameters and results

### 2. Improved Data File Loading (`api/views.py`)

- Added more potential file paths to check
- Added `/app/data/` and `/app/api/data/` paths for Docker
- Detailed logging of which paths are checked and found

### 3. Logging Configuration (`influBridge/settings.py`)

- Added Django logging configuration
- Logs go to console (stdout) for Cloud Run
- API module logs at DEBUG level
- Root logger at INFO level

### 4. ALLOWED_HOSTS Update (`influBridge/settings.py`)

- Added `influBridge-251801873872.us-central1.run.app`
- Added wildcard Cloud Run domains (`.run.app`, `.a.run.app`)

### 5. Dockerfile Verification (`Dockerfile`)

- Added commands to verify data files are copied
- Lists all CSV files in the image during build

## Deployment Steps

### Step 1: Rebuild and Deploy

```bash
# Build and deploy to Google Cloud Run
gcloud builds submit --config cloudbuild.yaml

# OR if using direct deployment:
gcloud run deploy influBridge \\
  --source . \\
  --region us-central1 \\
  --platform managed \\
  --allow-unauthenticated
```

### Step 2: Check Logs

After deployment, check the logs to see initialization details:

```bash
gcloud run logs read influBridge --region us-central1 --limit 100
```

Look for these log lines:

- ✓ `Initializing recommender. BASE_DIR: /app`
- ✓ `Checking X possible data file locations...`
- ✓ `Using data file: /app/data/influenceurs_recommendation_ready.csv`
- ✓ `Données chargées: X influenceurs`

### Step 3: Test the API

```bash
# Test the recommend endpoint
curl "https://influBridge-251801873872.us-central1.run.app/api/recommend/?category=Fashion&country=USA&n=5"

# Test health check
curl "https://influBridge-251801873872.us-central1.run.app/api/health/"

# Test stats
curl "https://influBridge-251801873872.us-central1.run.app/api/stats/"
```

## If Issues Persist

### Check 1: Verify Data Files in Container

```bash
# Get service name
gcloud run services list --region us-central1

# Check files in the running container
gcloud run services describe influBridge --region us-central1

# View logs
gcloud run logs read influBridge --region us-central1 --limit 200 | grep -i "data\\|error\\|csv"
```

### Check 2: Environment Variables

Make sure these are set in Cloud Run:

```bash
gcloud run services update influBridge \\
  --region us-central1 \\
  --set-env-vars DEBUG=False \\
  --set-env-vars ALLOWED_HOSTS=influBridge-251801873872.us-central1.run.app
```

### Check 3: Check Build Logs

```bash
gcloud builds list --limit 5
gcloud builds log <BUILD_ID>
```

Look for the "Checking for data files..." output to see if CSV files are present.

## Expected Log Output (Success)

When working correctly, you should see:

```
INFO Initializing recommender. BASE_DIR: /app
INFO Current working directory: /app
INFO Checking 8 possible data file locations...
INFO 1. /app/data/influenceurs_recommendation_ready.csv - FOUND
✓ Using data file: /app/data/influenceurs_recommendation_ready.csv
✓ Données chargées: 1500 influenceurs
✓ Columns: ['influencer_name', 'category', 'country', 'followers', 'engagement_rate', 'global_score']
✓ Feature matrix created: (1500, 5)
✓ Matrice de similarité: (1500, 1500)
✓ Categories: 15, Countries: 25
```

## Common Issues

### Issue: "No data file found"

**Solution:** Check that data files are in your repository and not gitignored:

```bash
# In your local repo
ls -la data/*.csv
git status data/

# Make sure data files are tracked
git add data/influenceurs_recommendation_ready.csv
git commit -m "Include data files for deployment"
```

### Issue: Still getting 500 errors

**Solution:** Check the actual error in logs:

```bash
gcloud run logs read influBridge --region us-central1 --limit 200 | grep -i error
```

### Issue: CSV files present but not loading

**Solution:** Check file permissions in Dockerfile:

```dockerfile
# Ensure files are readable
RUN chmod -R 755 /app/data/
```

## Rollback

If you need to rollback:

```bash
gcloud run services replace previous-revision.yaml --region us-central1
```

## Additional Notes

- Logs now show detailed information about file paths and data loading
- All errors include traceback information for debugging
- The recommender initialization is logged step-by-step
- Request parameters and results are logged for each API call

## Testing Different Categories

Valid test URLs:

```
# Fashion
https://influBridge-251801873872.us-central1.run.app/api/recommend/?category=Fashion&country=USA&n=10

# Technology
https://influBridge-251801873872.us-central1.run.app/api/recommend/?category=Technology&country=Canada&n=5

# Get all categories
https://influBridge-251801873872.us-central1.run.app/api/categories/

# Get all countries
https://influBridge-251801873872.us-central1.run.app/api/countries/
```

# Google Cloud Deployment Guide

This guide explains how to deploy your InfluBridge Django application to Google Cloud.

## Prerequisites

1. **Google Cloud Account**: Create an account at [cloud.google.com](https://cloud.google.com)
2. **Google Cloud SDK**: Install the gcloud CLI tool
   ```bash
   # Download from: https://cloud.google.com/sdk/docs/install
   ```
3. **Docker**: Install Docker Desktop (for local testing)

## Deployment Options

You have two main options for deploying to Google Cloud:

### Option 1: Cloud Run (Recommended for Containerized Apps)

**Advantages:**

- Fully managed serverless platform
- Auto-scaling (scales to zero when no traffic)
- Pay only for what you use
- Easy CI/CD integration
- Better for modern containerized applications

### Option 2: App Engine

**Advantages:**

- Simpler configuration
- Built-in versioning and traffic splitting
- Good for traditional web applications

---

## Option 1: Deploy to Cloud Run

### Step 1: Set Up Google Cloud Project

```bash
# Login to Google Cloud
gcloud auth login

# Create a new project (or use existing)
gcloud projects create influBridge-app --name="InfluBridge"

# Set the project
gcloud config set project influBridge-app

# Enable required APIs
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
```

### Step 2: Set Up Database (Cloud SQL)

```bash
# Create PostgreSQL instance
gcloud sql instances create influBridge-db \
    --database-version=POSTGRES_15 \
    --tier=db-f1-micro \
    --region=us-central1

# Create database
gcloud sql databases create influBridge \
    --instance=influBridge-db

# Create database user
gcloud sql users create dbuser \
    --instance=influBridge-db \
    --password=YOUR_SECURE_PASSWORD

# Get connection string
gcloud sql instances describe influBridge-db
```

### Step 3: Build and Deploy with Cloud Build

```bash
# Build the Docker image and deploy
gcloud builds submit --config cloudbuild.yaml

# Or manual deployment:
# Build the image
gcloud builds submit --tag gcr.io/influBridge-app/influBridge

# Deploy to Cloud Run
gcloud run deploy influBridge \
    --image gcr.io/influBridge-app/influBridge \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --memory 512Mi \
    --cpu 1 \
    --max-instances 10 \
    --set-env-vars "DEBUG=False" \
    --set-env-vars "SECRET_KEY=your-secret-key-here" \
    --set-env-vars "DATABASE_URL=postgresql://dbuser:password@/influBridge?host=/cloudsql/influBridge-app:us-central1:influBridge-db" \
    --set-env-vars "ALLOWED_HOSTS=*"
```

### Step 4: Set Up Environment Variables (Recommended: Use Secret Manager)

```bash
# Create secrets in Secret Manager
echo -n "your-secret-key-here" | gcloud secrets create django-secret-key --data-file=-
echo -n "postgresql://..." | gcloud secrets create database-url --data-file=-

# Update Cloud Run service to use secrets
gcloud run services update influBridge \
    --update-secrets=SECRET_KEY=django-secret-key:latest \
    --update-secrets=DATABASE_URL=database-url:latest
```

### Step 5: Run Database Migrations

```bash
# Get the Cloud Run service URL
gcloud run services describe influBridge --region us-central1

# Run migrations (via Cloud Run job or manually)
gcloud run jobs create influBridge-migrate \
    --image gcr.io/influBridge-app/influBridge \
    --region us-central1 \
    --command python \
    --args "manage.py,migrate"

# Execute the job
gcloud run jobs execute influBridge-migrate
```

---

## Option 2: Deploy to App Engine

### Step 1: Set Up Google Cloud Project

```bash
# Login and set project (same as above)
gcloud auth login
gcloud config set project influBridge-app

# Enable App Engine
gcloud app create --region=us-central
```

### Step 2: Set Up Database

Same as Cloud Run (use Cloud SQL)

### Step 3: Configure Environment Variables

Edit `app.yaml` and add your environment variables, or use:

```bash
# Create .env file for App Engine (not recommended for production)
# Better: use Google Cloud Secret Manager

gcloud secrets create django-secret-key --data-file=<(echo -n "your-secret-key")
```

### Step 4: Deploy

```bash
# Deploy the application
gcloud app deploy

# Deploy with specific version
gcloud app deploy --version v1

# View your application
gcloud app browse
```

### Step 5: Run Migrations

```bash
# Connect to Cloud SQL Proxy
cloud_sql_proxy -instances=influBridge-app:us-central1:influBridge-db=tcp:5432

# In another terminal
python manage.py migrate
```

---

## Environment Variables Configuration

Create these environment variables in Google Cloud (Secret Manager recommended):

### Required Variables:

- `SECRET_KEY`: Django secret key
- `DATABASE_URL`: PostgreSQL connection string
- `DEBUG`: Set to `False` in production
- `ALLOWED_HOSTS`: Your Cloud Run/App Engine URL

### Optional Variables:

- `CSRF_TRUSTED_ORIGINS`: Your frontend URL
- Any API keys or third-party service credentials

---

## Database Connection String Format

For Cloud SQL PostgreSQL:

```
# For Cloud Run (with Cloud SQL Proxy)
postgresql://USER:PASSWORD@/DATABASE?host=/cloudsql/PROJECT_ID:REGION:INSTANCE_NAME

# For local connection via proxy
postgresql://USER:PASSWORD@localhost:5432/DATABASE
```

---

## Local Docker Testing

Before deploying, test your Docker container locally:

```bash
# Build the image
docker build -t influBridge .

# Run the container
docker run -p 8080:8080 \
    -e SECRET_KEY="your-secret-key" \
    -e DATABASE_URL="your-database-url" \
    -e DEBUG="False" \
    -e ALLOWED_HOSTS="localhost,127.0.0.1" \
    influBridge

# Access at http://localhost:8080
```

---

## Continuous Deployment (CI/CD)

### Using Cloud Build Triggers:

1. Connect your GitHub/GitLab repository
2. Create a build trigger:

```bash
gcloud builds triggers create github \
    --repo-name=influBridge \
    --repo-owner=YOUR_GITHUB_USERNAME \
    --branch-pattern="^main$" \
    --build-config=cloudbuild.yaml
```

3. Every push to `main` branch will automatically build and deploy

---

## Monitoring and Logs

```bash
# View Cloud Run logs
gcloud run services logs read influBridge --region us-central1

# View App Engine logs
gcloud app logs tail -s default

# View in Cloud Console
# Navigate to: Logging > Logs Explorer
```

---

## Cost Estimation

### Cloud Run:

- **Free tier**: 2 million requests/month
- **Compute**: ~$0.00002400/vCPU-second
- **Memory**: ~$0.00000250/GiB-second
- **Estimated**: $10-50/month for small traffic

### App Engine:

- **F2 Instance**: ~$0.10/hour when running
- **Estimated**: $73/month for always-on instance

### Cloud SQL:

- **db-f1-micro**: ~$7.67/month
- **db-g1-small**: ~$25/month

---

## Common Commands

```bash
# View deployed services
gcloud run services list  # For Cloud Run
gcloud app services list  # For App Engine

# View service details
gcloud run services describe influBridge --region us-central1

# Update service with new environment variable
gcloud run services update influBridge --set-env-vars "NEW_VAR=value"

# View logs
gcloud run services logs tail influBridge

# Delete service
gcloud run services delete influBridge
gcloud app services delete default
```

---

## Troubleshooting

### Issue: Container fails to start

- Check logs: `gcloud run services logs read influBridge`
- Verify environment variables are set correctly
- Test Docker image locally first

### Issue: Database connection errors

- Verify Cloud SQL instance is running
- Check connection string format
- Ensure Cloud SQL proxy is configured (for Cloud Run)

### Issue: Static files not loading

- Run `python manage.py collectstatic` in Dockerfile
- Configure WhiteNoise properly in settings.py
- Check STATIC_ROOT and STATIC_URL settings

---

## Security Best Practices

1. **Never commit secrets**: Use Secret Manager or environment variables
2. **Set DEBUG=False**: In production
3. **Use HTTPS**: Cloud Run/App Engine provide this automatically
4. **Restrict ALLOWED_HOSTS**: List specific domains
5. **Database backups**: Enable automated backups in Cloud SQL
6. **Use IAM**: Control access to your services
7. **Enable Cloud Armor**: For DDoS protection (optional)

---

## Next Steps

1. Set up custom domain
2. Configure SSL certificate (automatic with Cloud Run/App Engine)
3. Set up monitoring and alerting
4. Configure backup strategy
5. Implement CI/CD pipeline
6. Set up staging environment

For more information, visit:

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [App Engine Documentation](https://cloud.google.com/appengine/docs)
- [Cloud SQL Documentation](https://cloud.google.com/sql/docs)

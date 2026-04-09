#!/bin/bash
# Script to check Cloud Run logs for data file loading issues

echo "=========================================="
echo "FETCHING CLOUD RUN LOGS"
echo "=========================================="
echo ""

echo "Looking for data file initialization logs..."
echo ""

gcloud run logs read influBridge \
  --region us-central1 \
  --limit 200 \
  --format "value(textPayload)" 2>/dev/null | \
  grep -i "data\|csv\|initializing\|recommender\|error\|found\|not found" | \
  head -50

echo ""
echo "=========================================="
echo "Checking for specific error patterns..."
echo "=========================================="
echo ""

# Check for data loading errors
gcloud run logs read influBridge \
  --region us-central1 \
  --limit 100 \
  --format "value(textPayload)" 2>/dev/null | \
  grep -i "no data file found\|data not available" | \
  head -10

echo ""
echo "=========================================="
echo "Full recent logs:"
echo "=========================================="
gcloud run logs read influBridge \
  --region us-central1 \
  --limit 30

echo ""
echo "=========================================="
echo "To see live logs:"
echo "  gcloud run logs tail influBridge --region us-central1"
echo "=========================================="

#!/bin/bash
# HisaabKitaab — Cloud Run deploy script
set -e

export PATH=/opt/homebrew/share/google-cloud-sdk/bin:$PATH

PROJECT="hisaabkitaab-7485"
SERVICE="hisaabkitaab"
REGION="asia-south1"

# Load local .env values
set -a; source .env 2>/dev/null || true; set +a

# Write env vars to a temp YAML file — avoids shell escaping issues with JSON
TMPFILE=$(mktemp /tmp/hk-env-XXXXXX.yaml)
python3 - <<'PYEOF' > "$TMPFILE"
import json, os

creds = json.load(open('serviceAccountKey.json'))
creds_str = json.dumps(creds)  # single-line JSON, no single quotes in JSON so YAML-safe

print(f"ENV: production")
print(f"SECRET_KEY: {os.environ.get('SECRET_KEY', '')}")
print(f"GOOGLE_CLIENT_ID: {os.environ.get('GOOGLE_CLIENT_ID', '')}")
print(f"GOOGLE_CLIENT_SECRET: {os.environ.get('GOOGLE_CLIENT_SECRET', '')}")
# Single-quoted YAML string — JSON uses only double quotes so no escaping needed
print(f"FIREBASE_CREDENTIALS: '{creds_str}'")
PYEOF

echo "🚀 Deploying $SERVICE to Cloud Run ($REGION)..."

gcloud run deploy "$SERVICE" \
  --source . \
  --project "$PROJECT" \
  --region "$REGION" \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 1 \
  --memory 256Mi \
  --cpu 1 \
  --env-vars-file "$TMPFILE"

rm -f "$TMPFILE"

echo ""
echo "✅ Deploy complete!"
echo ""
echo "Next steps:"
echo "  1. Copy the Service URL printed above"
echo "  2. Go to https://console.cloud.google.com/apis/credentials"
echo "     → Edit your OAuth 2.0 Client → add to Authorised redirect URIs:"
echo "     <Service URL>/auth/callback"
echo "  3. Run this to set REDIRECT_URI (replace the URL):"
echo ""
echo "  gcloud run services update $SERVICE --region $REGION \\"
echo "    --update-env-vars REDIRECT_URI=<Service URL>/auth/callback"

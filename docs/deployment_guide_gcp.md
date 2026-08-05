# Google Cloud Run (GCP) Deployment Guide

This guide describes how to deploy your Flask backend to **Google Cloud Run**. 

Cloud Run is a fully managed serverless platform that automatically scales your containers. Since we can allocate up to **8 GB of RAM** per container, it is perfect for running parallel Playwright browser crawls.

---

## Prerequisites

1. A **Google Cloud Platform (GCP)** account with an active billing account.
2. The **Google Cloud SDK (gcloud CLI)** installed on your machine.
   * [Download & Install gcloud CLI](https://cloud.google.com/sdk/docs/install)
3. A remote PostgreSQL database (like your Supabase instance).

---

## Step 1: Initialize Google Cloud CLI

Open your terminal and authenticate the `gcloud` CLI with your Google account:

1. **Log in to GCP:**
   ```bash
   gcloud auth login
   ```
   *(This will open a browser window to authenticate with your Google Account).*

2. **Create or select a GCP project:**
   Find your Project ID in the GCP Console, or create a new one:
   ```bash
   gcloud projects create klypup-pricing-intelligence --set-as-default
   ```
   *Note: If you already have a project, set it as default:*
   ```bash
   gcloud config set project YOUR_PROJECT_ID
   ```

3. **Enable the required APIs (Cloud Build, Cloud Run, Artifact Registry):**
   ```bash
   gcloud services enable run.googleapis.com build.googleapis.com artifactregistry.googleapis.com
   ```

---

## Step 2: Deploy to Google Cloud Run

To build your Docker image and deploy it, you can run a single command from your local terminal. Make sure you are in the **`backend`** directory of your project:

```bash
cd backend
```

Run the following command (with your Supabase connection string and other environment variables):

```bash
gcloud run deploy dynamic-pricing-backend `
  --source . `
  --platform managed `
  --region asia-southeast1 `
  --memory 2Gi `
  --cpu 1 `
  --timeout 300 `
  --port 8080 `
  --allow-unauthenticated `
  --set-env-vars "DATABASE_URL=postgresql://postgres.[username]:[password]@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres" `
  --set-env-vars "GROQ_API_KEY=your_groq_api_key" `
  --set-env-vars "AI_PROVIDER=groq" `
  --set-env-vars "SECRET_KEY=your_secret_key" `
  --set-env-vars "JWT_SECRET_KEY=your_jwt_secret" `
  --set-env-vars "SMTP_HOST=smtp.gmail.com" `
  --set-env-vars "SMTP_PORT=587" `
  --set-env-vars "SMTP_USER=your_smtp_user_email" `
  --set-env-vars "SMTP_PASS=your_smtp_app_password" `
  --set-env-vars "SMTP_SENDER=your_smtp_sender_email" `
  --set-env-vars "TWILIO_ACCOUNT_SID=your_twilio_account_sid" `
  --set-env-vars "TWILIO_AUTH_TOKEN=your_twilio_auth_token" `
  --set-env-vars "TWILIO_WHATSAPP_FROM=whatsapp:+14155238886" `
  --set-env-vars "STRIPE_SECRET_KEY=your_stripe_secret_key" `
  --set-env-vars "STRIPE_PUBLISHABLE_KEY=your_stripe_publishable_key" `
  --set-env-vars "CORS_ORIGINS=*"
```

*(Note: In Windows PowerShell, use the backtick `` ` `` for line continuation. In Linux or macOS bash, use the backslash `\` instead).*

### What this command does:
1. `--source .`: Uploads your backend code and builds it using your local `Dockerfile` via Google Cloud Build.
2. `--memory 2Gi`: Allocates **2 GB of RAM** to your container (you can increase this to `4Gi` or `8Gi` if you run many parallel web crawlers).
3. `--cpu 1`: Allocates 1 vCPU.
4. `--allow-unauthenticated`: Makes your backend API public.
5. `--set-env-vars`: Inject all your credentials and database configurations securely.

---

## Step 3: Access Your Deployed Backend

Once the deployment completes, the CLI will output your service URL, which will look like:
`https://dynamic-pricing-backend-xxxxx-xx.a.run.app`

Open that URL in your browser, and you should see the confirmation:
```json
{
  "success": true,
  "message": "Backend running"
}
```

# Hugging Face Spaces Deployment Guide: Flask Backend

This guide outlines the step-by-step process to deploy your Flask backend to Hugging Face Spaces using the custom **Docker SDK**.

---

## Prerequisites

Before starting, ensure you have:
1. A **Hugging Face Account**. If you don't have one, sign up at [huggingface.co](https://huggingface.co/).
2. **Git** installed and configured locally.
3. Access to a remote **PostgreSQL Database** (e.g., Supabase or Neon). 
   
> [!IMPORTANT]
> Since Hugging Face Spaces runs in an ephemeral container environment, your local SQLite database (`klypup.db`) is **not suitable** because its data will be lost every time the Space sleeps or restarts. You must use an external database like **Supabase** or **Neon**.

---

## Step 1: Set Up an External PostgreSQL Database

If you do not already have an external database, you can create a free one:

### Option A: Supabase (Recommended)
1. Go to [supabase.com](https://supabase.com/) and create a free account.
2. Create a new project.
3. Under **Project Settings > Database**, find your connection string.
4. Copy the **URI** connection string. It will look like this:
   `postgresql://postgres.[username]:[password]@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres`

### Option B: Neon Database
1. Go to [neon.tech](https://neon.tech/) and sign up.
2. Create a new project and select **PostgreSQL**.
3. Copy the database connection string from the dashboard.

---

## Step 2: Create a Hugging Face Space

1. Go to [huggingface.co/spaces](https://huggingface.co/spaces).
2. Click **Create new Space** (top right).
3. Fill in the Space settings:
   - **Space Owner**: Your username or organization.
   - **Space Name**: Enter a name (e.g., `dynamic-pricing-backend`).
   - **License**: Choose your preference (e.g., `mit` or `apache-2.0`).
   - **SDK**: Select **Docker** (Crucial!).
   - **Docker Template**: Select **Blank** (do not select Gradio/Streamlit Docker templates).
   - **Space Hardware**: Choose **CPU Basic (Free)**.
   - **Visibility**: **Public** or **Private** (we recommend **Private** if you have proprietary code or configuration).
4. Click **Create Space**.

---

## Step 3: Add Environment Variables & Secrets to Hugging Face

To keep API keys and database credentials secure, you must define them as **Secrets** in the Hugging Face Space settings.

1. In your newly created Space, click the **Settings** tab (top right).
2. Scroll down to the **Variables and secrets** section.
3. Click **New secret** to add each of the following keys from your local `.env`:

| Secret Name | Description / Example Value |
| :--- | :--- |
| `DATABASE_URL` | Your Supabase or Neon PostgreSQL connection string. |
| `SECRET_KEY` | A random secure string (e.g. `your_secret_key`). |
| `JWT_SECRET_KEY` | A random secure string for JWT generation. |
| `GROQ_API_KEY` | `gsk_...` (Your Groq API key). |
| `AI_PROVIDER` | `groq` |
| `STRIPE_SECRET_KEY` | `sk_test_...` (Your Stripe secret key). |
| `STRIPE_PUBLISHABLE_KEY` | `pk_test_...` (Your Stripe publishable key). |
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | `your_smtp_user_email` |
| `SMTP_PASS` | `your_smtp_app_password` |
| `SMTP_SENDER` | `your_smtp_sender_email` |
| `TWILIO_ACCOUNT_SID` | `AC0bae...` |
| `TWILIO_AUTH_TOKEN` | `589d3...` |
| `TWILIO_WHATSAPP_FROM`| `whatsapp:+14155238886` |
| `CORS_ORIGINS` | `*` (or your frontend's deployed URL to allow cross-origin requests). |

---

## Step 4: Push the Backend Code to Hugging Face

Because Hugging Face Space is configured as a git repository, you need to push the files inside the `backend` directory to the Space's remote. 

Here are the commands to execute from your terminal inside the **`backend`** directory of your project:

### 1. Initialize Git inside `backend/` (if it isn't already)
```bash
cd backend
git init
```

### 2. Add Hugging Face as a remote
Get the git clone URL from the Hugging Face Space page (e.g., `https://huggingface.co/spaces/username/space-name`).
```bash
git remote add hf https://huggingface.co/spaces/your-username/your-space-name
```

### 3. Add files and commit
```bash
git add .
git commit -m "Deploy backend to Hugging Face Spaces"
```

### 4. Push to Hugging Face
> [!NOTE]
> Hugging Face uses `main` as the default branch name.
```bash
git push -f hf master:main
```
*(If your local branch is named `main` instead of `master`, run `git push -f hf main`)*

---

## Step 5: Monitor the Build & Verify

1. Go back to your Hugging Face Space webpage.
2. You will see the status change to **Building** 🛠️.
3. You can click on the status to view the Docker build logs. Playwright and dependencies will be installed automatically.
4. Once completed, the status will change to **Running** 🟢.
5. Visit the Space's app link. It will look like:
   `https://[username]-[space-name].hf.space/`
6. You should see the default JSON response:
   ```json
   {
     "success": true,
     "message": "Backend running"
   }
   ```

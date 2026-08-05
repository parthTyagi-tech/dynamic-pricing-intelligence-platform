# Oracle Cloud Infrastructure (OCI) Always Free Deployment Guide

This guide describes how to set up an **Always Free** virtual machine on **Oracle Cloud** with **24 GB of RAM and 4 ARM CPUs** to run your Flask backend and parallel web crawlers 24/7 at no cost.

---

## Step 1: Sign Up for Oracle Cloud Free Tier
1. Go to **[oracle.com/cloud/free/](https://www.oracle.com/cloud/free/)** and click **Start for free**.
2. Enter your email, select your country, and choose a **Home Region** close to you (e.g., **India West (Mumbai)** or **India South (Hyderabad)**).
   * *Note: Once chosen, your Home Region cannot be changed, and "Always Free" resources are provisioned in this region.*
3. Provide your address and verify your phone number.
4. **Payment Verification:** Add a Visa or Mastercard (Credit or Debit card with international transactions enabled). 
   * Oracle will initiate a temporary verification hold of approximately ₹70-80 (about $1 USD) to verify the card. This hold is **fully refunded/released** immediately by Oracle.

---

## Step 2: Create Your "Always Free" VM Instance
Once logged into your Oracle Cloud Console:
1. Click the burger menu (**☰** top-left) and select **Compute** > **Instances**.
2. Click **Create instance**.
3. Configure the VM:
   * **Name**: `klypup-backend`
   * **Placement**: Leave as default.
   * **Image and shape**:
     * Click **Edit**.
     * Under **Image**, select **Canonical Ubuntu (22.04 or 24.04)**.
     * Under **Shape**, click **Change shape**. Select **Ampere** (ARM-based processor), check **VM.Standard.A1.Flex**, and assign:
       * **4 OCPUs**
       * **24 GB of RAM**
       * *(This is 100% "Always Free Eligible" and gives you massive memory capacity).*
   * **Networking**: Leave defaults (it will create a Virtual Cloud Network and assign a Public IP).
   * **Add SSH keys**: 
     * Select **Generate a key pair for me**.
     * Click **Save private key** (This downloads a `.key` or `.pem` file. **Do not lose this file!** You need it to connect to the server).
   * **Boot volume**: Leave default size.
4. Click **Create** (at the bottom). The VM will take 1–2 minutes to provision and turn **Running (Green)**. Note its **Public IP Address**.

---

## Step 3: Open Network Ports (OCI Ingress Rules)
By default, Oracle blocks all incoming traffic to your VM. We must tell OCI to let web traffic reach your Flask server on port `5000`:

1. On your VM Instance Details page, click the link under **Virtual cloud network** (e.g. `vcn-xxxxxxxx`).
2. Click **Security Lists** in the left sidebar, then click the Default Security List.
3. Click **Add Ingress Rules** and enter:
   * **Source Type**: `CIDR`
   * **Source CIDR**: `0.0.0.0/0` (Allows requests from anywhere)
   * **IP Protocol**: `TCP`
   * **Destination Port Range**: `5000` *(This is the port your Flask API runs on)*
4. Click **Add Ingress Rules**.

---

## Step 4: Connect to your VM & Install Docker
Open a terminal on your local computer (Command Prompt, PowerShell, or Git Bash) and SSH into the machine:

1. **Change permissions on your downloaded SSH key** (in terminal):
   ```bash
   # Linux/macOS only (skip on Windows):
   chmod 400 ssh-key-xxxx.key
   ```
2. **Connect via SSH:**
   ```bash
   ssh -i /path/to/your/ssh-key-xxxx.key ubuntu@<YOUR_VM_PUBLIC_IP>
   ```
3. **Update the VM and install Docker:**
   Once connected to the remote Ubuntu terminal, run:
   ```bash
   sudo apt update && sudo apt upgrade -y
   sudo apt install -y docker.io docker-compose git
   
   # Add your user to the docker group so you don't need 'sudo' for docker commands
   sudo usermod -aG docker $USER
   newgrp docker
   ```
4. **Open the local OS firewall ports:**
   Oracle Ubuntu images have default local iptables rules that block incoming traffic even after configuring Step 3. Run this to open port 5000:
   ```bash
   sudo iptables -I INPUT 6 -p tcp --dport 5000 -j ACCEPT
   sudo netfilter-persistent save
   ```

---

## Step 5: Clone and Run Your Project
Inside your SSH session on the OCI VM:

1. **Clone your repository:**
   ```bash
   git clone <your-github-repo-url>
   cd <your-repo-folder-name>/backend
   ```
2. **Create the environment file (`.env`):**
   ```bash
   nano .env
   ```
   Paste the backend configurations (including your Supabase database URL and API keys):
   ```env
    SECRET_KEY=your_secret_key
    JWT_SECRET_KEY=your_jwt_secret
    DATABASE_URL=postgresql://postgres.[username]:[password]@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres
    GROQ_API_KEY=your_groq_api_key
    AI_PROVIDER=groq
    PARALLEL_CRAWLING=true
    # ... (add Twilio, Stripe, and SMTP keys)
   ```
   *(Press `Ctrl + O` and `Enter` to save, then `Ctrl + X` to exit).*

3. **Build and Run the Docker container:**
   ```bash
   docker build -t klypup-backend .
   docker run -d -p 5000:5000 --name backend-service --restart unless-stopped klypup-backend
   ```

4. **Verify it is running:**
   Access `http://<YOUR_VM_PUBLIC_IP>:5000` in your browser. You should see:
   ```json
   {
     "success": true,
     "message": "Backend running"
   }
   ```

---

## Step 6: Link Your Vercel Frontend
Now go to your **Vercel Dashboard** and update the environment variable `VITE_API_URL` to point to your permanent VM:
`http://<YOUR_VM_PUBLIC_IP>:5000/api`
*(Redeploy the frontend on Vercel to apply the change).*

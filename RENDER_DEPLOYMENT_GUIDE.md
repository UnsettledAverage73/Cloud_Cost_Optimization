# 🚀 Deploying CloudPulse on Render.com

This guide provides step-by-step instructions for hosting both the **FastAPI Backend** and **Next.js Frontend** (along with a managed **PostgreSQL Database**) on **Render.com**.

---

## 🌟 Method 1: 1-Click Blueprint Deployment (Recommended)

CloudPulse includes a production-ready [`render.yaml`](file:///home/unsettledaverage73/cost-cloud-dashboard/Cloud_Cost_Optimization/render.yaml) blueprint. Render will automatically configure the database, backend, frontend, environment variables, and network linking in one go.

### Step 1: Push Code to GitHub / GitLab
Make sure your changes are pushed to your remote git repository:
```bash
git add .
git commit -m "feat: add Render.com deployment files and blueprint"
git push origin main
```

### Step 2: Open Render Dashboard
1. Go to [dashboard.render.com](https://dashboard.render.com/).
2. Click **New +** in the top navigation bar.
3. Select **Blueprint**.
4. Connect your GitHub/GitLab account and select your `Cloud_Cost_Optimization` repository.

### Step 3: Review & Apply Blueprint
Render will automatically detect [`render.yaml`](file:///home/unsettledaverage73/cost-cloud-dashboard/Cloud_Cost_Optimization/render.yaml) and create:
1. **`cloudpulse-db`**: Free managed PostgreSQL database.
2. **`cloudpulse-backend`**: Python web service with automatic database linking and healthcheck (`/api/v2/database/status`).
3. **`cloudpulse-frontend`**: Next.js 16 web service with proxy pointing to the backend.

Click **Apply**.

---

## 🛠️ Method 2: Manual Service Creation

If you prefer to configure the services individually in the Render UI without Blueprint:

### 1. Create Managed PostgreSQL Database
1. In Render, click **New +** -> **PostgreSQL**.
2. **Name:** `cloudpulse-db`
3. **Database:** `cloudpulse_db`
4. **User:** `postgres`
5. **Region:** Oregon (US West)
6. **Plan:** Free
7. Click **Create Database**. Copy the **Internal Database URL** once created.

---

### 2. Create Backend Web Service
1. Click **New +** -> **Web Service**.
2. Connect your repository.
3. Configure settings:
   - **Name:** `cloudpulse-backend`
   - **Region:** Oregon (same as DB)
   - **Branch:** `main`
   - **Root Directory:** *(leave blank)*
   - **Runtime:** `Python 3`
   - **Build Command:** `./backend/render_build.sh`
   - **Start Command:** `cd backend && PYTHONPATH=. uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Health Check Path:** `/api/v2/database/status`
   - **Plan:** Free
4. Under **Environment Variables**, add:
   - `DATABASE_URL`: *(paste the Internal Database URL from Step 1)*
   - `PYTHONPATH`: `/opt/render/project/src/backend`
   - `GROQ_API_KEY`: *(your optional Groq API key for the Copilot)*
   - `AWS_ACCESS_KEY_ID`: *(optional AWS credentials or use CloudFormation onboarding)*
   - `AWS_SECRET_ACCESS_KEY`: *(optional)*
   - `AWS_DEFAULT_REGION`: `us-east-1`
5. Click **Create Web Service**. Note your backend URL (e.g. `https://cloudpulse-backend.onrender.com`).

---

### 3. Create Frontend Web Service
1. Click **New +** -> **Web Service**.
2. Connect the same repository.
3. Configure settings:
   - **Name:** `cloudpulse-frontend`
   - **Region:** Oregon
   - **Branch:** `main`
   - **Root Directory:** `frontend`
   - **Runtime:** `Node`
   - **Build Command:** `npm install && npm run build`
   - **Start Command:** `npm run start -- -p $PORT`
   - **Plan:** Free
4. Under **Environment Variables**, add:
   - `NODE_VERSION`: `22.12.0`
   - `NEXT_TELEMETRY_DISABLED`: `1`
   - `BACKEND_URL`: `https://cloudpulse-backend.onrender.com` *(or internal name `cloudpulse-backend`)*
5. Click **Create Web Service**.

---

## 🔍 Verifying Your Deployment

Once both services show **Live**:

1. **Verify Backend Health & TimescaleDB/PostgreSQL:**
   ```bash
   curl -s https://cloudpulse-backend.onrender.com/api/v2/database/status
   ```
   Should return:
   ```json
   {
     "status": "connected",
     "postgres_version": "PostgreSQL 16...",
     "timescaledb_version": "..."
   }
   ```

2. **Verify Frontend UI:**
   Open `https://cloudpulse-frontend.onrender.com` in your browser. The dashboard will load with live telemetry and FinOps insights.

3. **Verify Multi-OS Agent:**
   Any host (Linux or Windows) can now stream in-guest metrics to your Render-hosted backend:
   ```bash
   # Linux 1-Liner:
   curl -fsSL "https://cloudpulse-backend.onrender.com/api/v2/agent/install-script?os=linux" | bash
   
   # Windows PowerShell 1-Liner:
   irm "https://cloudpulse-backend.onrender.com/api/v2/agent/install-script?os=windows" | iex
   ```

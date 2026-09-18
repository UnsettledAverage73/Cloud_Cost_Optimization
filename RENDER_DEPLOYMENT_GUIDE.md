# 🚀 Deploying CloudPulse on Render.com: Static Site (Frontend) + Web Service (Backend)

This guide walks you through deploying CloudPulse on **Render.com** using:
1. 🖥️ **Frontend:** Hosted as a **Static Site** (100% Free forever on Render CDN with unlimited bandwidth).
2. ⚙️ **Backend:** Hosted as a **Web Service** (Python FastAPI running on Render's managed compute).
3. 🗄️ **Database:** Hosted as a **PostgreSQL Database** on Render (Free tier).

---

## 📋 Architecture Flow

```mermaid
flowchart LR
    Browser["User Browser / Client"]
    StaticCDN["Render Static Site\n(cloudpulse-frontend.onrender.com)\nNext.js Static Export (out/)"]
    BackendWS["Render Web Service\n(cloudpulse-backend.onrender.com)\nFastAPI Python 3"]
    RenderDB[(Render PostgreSQL\ncloudpulse_db)]

    Browser -->|1. Load Static HTML/JS/CSS| StaticCDN
    Browser -->|2. Direct API calls (NEXT_PUBLIC_API_URL)| BackendWS
    BackendWS -->|3. SQL Queries & Telemetry| RenderDB
```

---

## 🛠️ Step 1: Push Code to GitHub

Make sure your latest changes (including `output: 'export'` and `apiUrl` helpers) are pushed to GitHub:

```bash
git add .
git commit -m "feat: configure static site export for frontend and web service for backend"
git push origin master
git push origin master:main
```

---

## 🗄️ Step 2: Create PostgreSQL Database on Render

1. Log into your [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** $\rightarrow$ **PostgreSQL**.
3. Fill in the details:
   - **Name:** `cloudpulse-db`
   - **Database:** `cloudpulse_db`
   - **User:** `postgres`
   - **Region:** `Oregon (US West)` *(or your preferred region)*
   - **Plan:** `Free`
4. Click **Create Database**.
5. Once created, copy the **Internal Database URL** (e.g. `postgresql://postgres:password@dpg-xxxx-a:5432/cloudpulse_db`).

---

## ⚙️ Step 3: Create Backend Web Service on Render

1. In Render Dashboard, click **New +** $\rightarrow$ **Web Service**.
2. Connect your GitHub repository: `Cloud_Cost_Optimization`.
3. Configure the settings:
   - **Name:** `cloudpulse-backend`
   - **Region:** `Oregon` *(same region as your database)*
   - **Branch:** `master` (or `main`)
   - **Root Directory:** *(leave blank)*
   - **Runtime:** `Python 3`
   - **Build Command:**
     ```bash
     ./backend/render_build.sh
     ```
   - **Start Command:**
     ```bash
     cd backend && PYTHONPATH=. uvicorn main:app --host 0.0.0.0 --port $PORT
     ```
   - **Plan:** `Free`
4. Expand **Advanced** and configure **Health Check Path**:
   - **Health Check Path:** `/api/v2/database/status`
5. Under **Environment Variables**, add:
   | Key | Value | Notes |
   |:---|:---|:---|
   | `DATABASE_URL` | *(paste Internal Database URL from Step 2)* | Connects backend to database |
   | `PYTHON_VERSION` | `3.12.8` | Stable Python runtime |
   | `PYTHONPATH` | `/opt/render/project/src/backend` | Ensures clean imports |
   | `GROQ_API_KEY` | *(optional)* | For LLM Copilot |
   | `AWS_DEFAULT_REGION` | `us-east-1` | Default AWS region |
6. Click **Create Web Service**.
7. Wait until the service status turns **Live**. Note your Backend URL:
   `https://cloudpulse-backend.onrender.com`

---

## 🖥️ Step 4: Create Frontend Static Site on Render

1. In Render Dashboard, click **New +** $\rightarrow$ **Static Site**.
2. Connect the same repository: `Cloud_Cost_Optimization`.
3. Configure the settings:
   - **Name:** `cloudpulse-frontend`
   - **Branch:** `master` (or `main`)
   - **Root Directory:** `frontend`
   - **Build Command:**
     ```bash
     npm install && npm run build
     ```
   - **Publish Directory:**
     ```
     out
     ```
4. Under **Environment Variables**, add:
   | Key | Value |
   |:---|:---|
   | `NEXT_PUBLIC_API_URL` | `https://cloudpulse-backend.onrender.com` *(use your actual backend URL from Step 3)* |
   | `NODE_VERSION` | `22.12.0` |
5. Under **Redirects/Rewrites** (optional but recommended for SPA navigation):
   - **Type:** `Rewrite`
   - **Source:** `/*`
   - **Destination:** `/index.html`
6. Click **Create Static Site**.
7. Render will install dependencies, build the Next.js static export to `out/`, and deploy it to Render's global CDN!

---

## ✅ Step 5: Verification Checklist

1. **Verify Backend Health:**
   ```bash
   curl https://cloudpulse-backend.onrender.com/api/v2/database/status
   ```
   Expected response:
   ```json
   {
     "status": "connected",
     "postgres_version": "PostgreSQL 16...",
     "timescaledb_version": "..."
   }
   ```

2. **Verify Frontend UI:**
   Open `https://cloudpulse-frontend.onrender.com` in your web browser. The dashboard will load with live telemetry from the backend.

3. **Verify Multi-OS In-Guest Agent:**
   Any server or laptop can stream metrics to your live Render backend:
   ```bash
   # Linux / macOS 1-liner:
   curl -fsSL "https://cloudpulse-backend.onrender.com/api/v2/agent/install-script?os=linux" | bash
   
   # Windows PowerShell 1-liner:
   irm "https://cloudpulse-backend.onrender.com/api/v2/agent/install-script?os=windows" | iex
   ```

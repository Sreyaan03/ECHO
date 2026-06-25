# 🚀 ECHO Deployment Guide

Follow these steps to deploy the ECHO app for free so you can share a working interactive demo on LinkedIn!

---

## Step 1: Push Code to GitHub
ECHO needs to be in a public or private GitHub repository to connect to hosting services.

1. Initialize git (if not already done) and commit the changes:
   ```bash
   git init
   git add .
   git commit -m "feat: correlated demographics and folder restructure"
   ```
2. Create a repository on GitHub (e.g. `echo-simulator`).
3. Link your local repo and push:
   ```bash
   git remote add origin <your-github-repo-url>
   git branch -M main
   git push -u origin main
   ```

---

## Step 2: Deploy the Backend (FastAPI) on Render
We will host the Python backend on **Render.com** (has a free tier).

1. Go to [Render.com](https://render.com) and sign up/log in with GitHub.
2. Click **New +** and select **Web Service**.
3. Connect your GitHub repository.
4. Set the following details:
   - **Name:** `echo-backend`
   - **Runtime:** `Python`
   - **Build Command:** `pip install -r backend/requirements.txt`
   - **Start Command:** `uvicorn backend.server:app --host 0.0.0.0 --port $PORT`
   - **Plan:** `Free`
5. Under **Environment Variables**, add:
   - `GROQ_API_KEY`: `<your_groq_api_key>` (or `GEMINI_API_KEY` if you use it for narrative classification).
6. Click **Deploy Web Service**. 
7. Once deployed, copy the service URL (e.g. `https://echo-backend.onrender.com`).

---

## Step 3: Deploy the Frontend (React + Vite) on Vercel
We will host the React frontend on **Vercel.com** (has a fast free tier).

1. Go to [Vercel.com](https://vercel.com) and log in with GitHub.
2. Click **Add New** -> **Project**.
3. Import your GitHub repository.
4. Set the following details:
   - **Framework Preset:** `Vite`
   - **Root Directory:** `frontend` (Click edit and select the `frontend` folder)
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`
5. Under **Environment Variables**, add:
   - Name: `VITE_API_BASE_URL`
   - Value: `https://echo-backend.onrender.com/api` (Replace with your actual Render URL + `/api`)
6. Click **Deploy**.
7. Vercel will build the frontend and give you a live production URL (e.g. `https://echo-simulator.vercel.app`).

---

## Step 4: Verify Your Deployment
Open your live Vercel URL, type in a narrative, and hit **Initialize**.
The frontend will communicate with your FastAPI backend on Render, classify the narrative via the LLM, and start the simulation!

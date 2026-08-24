# Deploying Chelsy Packaging Orders to the Internet (Render, free tier)

This puts a real, clickable link online that anyone (interviewers included)
can open — not just something running on your own computer. Render's free
tier costs nothing and is enough for a portfolio project.

Everything in the codebase is already configured for this (production
database support, static file serving, secret key from environment
variables) — these are the account/click steps on Render's side.

---

## Step 1: Put the code on GitHub

Render deploys from a GitHub repository, so the code needs to live there first.

1. Go to [github.com](https://github.com), sign up if you don't have an account (free).
2. Click **New repository** (green button, top right). Name it `chelsy-packaging-orders`. Keep it **Public** (needed for Render's free tier to see it) or **Private** (also fine, just link your GitHub account to Render later). Don't tick "Add a README" — you already have one.
3. On your own computer, in a terminal **inside your `carton_factory` folder**:
   ```
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/chelsy-packaging-orders.git
   git push -u origin main
   ```
   (Replace `YOUR-USERNAME` with your actual GitHub username. If `git` isn't recognized, install it from [git-scm.com](https://git-scm.com/downloads) first.)

**Important — do NOT commit your real `db.sqlite3` or `media` folder** if they contain real customer data. Create a file named `.gitignore` in the project root first:
```
db.sqlite3
media/
staticfiles/
venv/
__pycache__/
*.pyc
.env
```

---

## Step 2: Create a Render account and database

1. Go to [render.com](https://render.com) → sign up (free, can use your GitHub account to sign up — this also connects them automatically).
2. From the Render dashboard, click **New +** → **Blueprint**.
3. Connect your `chelsy-packaging-orders` GitHub repo. Render will detect the `render.yaml` file already included in this project and set up both the web service and the free PostgreSQL database automatically from it.
4. Click **Apply** / **Create**. It'll start building — this takes a few minutes the first time.

---

## Step 3: Add your Cloudinary image storage key

Once the service exists (even mid-deploy):
1. In the Render dashboard, click into your web service.
2. Go to **Environment** in the left sidebar.
3. Add a variable: key `CLOUDINARY_URL`, value = your Cloudinary URL from your Cloudinary dashboard (see the "File storage" section in the main README for how to get this).
4. Save — Render will automatically redeploy with the new setting.

---

## Step 4: Create your admin login on the live site

Render gives you a **Shell** tab for your web service (dashboard → your service → Shell). Open it and run:
```
python manage.py createsuperuser
```
Same as running it locally — pick a username and password.

---

## Step 5: Visit your live site

Render shows your live URL at the top of the service page — something like:
```
https://chelsy-packaging-orders.onrender.com
```
That's the link to actually share, put on a CV, or click through in an interview.

---

## A few things specific to the free tier

- **The free web service "sleeps"** after 15 minutes of no traffic, and takes ~30-50 seconds to wake up on the next visit. Totally normal for a free-tier demo — just don't be surprised by the first load being slow.
- **The free PostgreSQL database expires after 90 days** on Render's free tier. For a portfolio project you click through occasionally, this is fine — just re-create it (Step 2) if it lapses. For an actually-in-use factory system, you'd want a paid database plan instead.
- **Updating the live site later:** commit and push your changes to GitHub (`git add .`, `git commit -m "..."`, `git push`) — Render automatically redeploys whenever you push to `main`.

---

## If something goes wrong

Render's dashboard → your service → **Logs** tab shows exactly what happened during build/deploy, in the same style as the terminal errors you've been sending me screenshots of. Send me a screenshot of that and I'll debug it the same way.

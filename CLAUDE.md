# HisaabKitaab — Project Guide

Splitwise-like expense splitting app for Indian friend groups (built for the "BINGO" gang).
FastAPI + vanilla HTML/CSS/JS frontend, Firebase Firestore. No groups: one gang. Every account is auto-friends with every other account (`connect_everyone` in routers/auth.py, runs on each login), so anyone who signs in can split with everyone.

---

## Stack

| Layer    | Tech |
|----------|------|
| Backend  | Python 3.11, FastAPI, Uvicorn |
| Frontend | Vanilla HTML/CSS/JS SPA (no framework), mobile-first |
| Auth     | Mobile number + password (stored as plain text in Firestore, compared directly — by design, keep it simple) |
| Database | Firebase Firestore (Admin SDK) |
| Sessions | Starlette SessionMiddleware (signed cookie, 7-day) |
| Hosting  | Render.com free tier |
| Local    | `uvicorn main:app --port 7485 --reload` |

---

## Structure

```
main.py              FastAPI app, sessions, global error handler
routers/auth.py      POST /auth/login (mobile+password, creates account on first use), GET /auth/logout
routers/api.py       friends, expenses, settlements, dashboard, insights
services/calculator.py   expense_shares (equal/exact), pair_balances (per-friend balance)
services/firebase.py     Admin SDK init (env var or file)
services/logger.py       log_error() → Firestore logs
static/              index.html, style.css (bingo theme), app.js (hash router + all views)
scripts/             check_logs.py, clear_logs.py, wipe_all.py (deletes ALL data, needs --yes)
```
`services/auth.py` and `services/groups.py` are unused Streamlit leftovers.

---

## Environment Variables

| Variable | Where | Purpose |
|----------|-------|---------|
| `SECRET_KEY` | `.env` / Render | Session signing |
| `GOOGLE_APPLICATION_CREDENTIALS` | `.env` (local) | Path to serviceAccountKey.json |
| `FIREBASE_CREDENTIALS` | Render | serviceAccountKey.json as a JSON string |
| `ENV` | Render | `production` (Secure cookie) |

Google OAuth variables (`GOOGLE_CLIENT_*`, `REDIRECT_URI`) are no longer used.

---

## Firestore

| Collection | Fields |
|-----------|--------|
| `users/{mobile}` | uid (=mobile), name, mobile, upi, password, friends[] (mutual) |
| `expenses/{id}` | description, amount, paid_by, split_among[], split_amounts{}?, participants[], note, tags[], created_by, created_at |
| `settlements/{id}` | from_uid, to_uid, amount, participants[], note, tags[], created_by, created_at |
| `logs/{id}` | error logs |

Tags are `#hashtags` parsed from description / note. Balances are pairwise (me ↔ each friend), no cross-simplification.

---

## API (all under /api, session required)

- `GET /me`, `PUT /me/upi`
- `GET /friends`, `POST /friends {mobile}`, `GET /friends/{uid}`, `DELETE /friends/{uid}` (balance must be 0)
- `POST /expenses`, `GET|PUT|DELETE /expenses/{id}` (edit/delete: creator or payer)
- `POST /settlements` (capped at actual debt)
- `GET /dashboard`, `GET /insights?days=0|30|90`

## Frontend routes

`#/` home · `#/friends` · `#/friends/{uid}` · `#/add[?friend=uid|edit=id]` · `#/insights` · `#/account` · `#/login`

Features: UPI deep-link "Pay" button, WhatsApp remind/invite messages, exact-amount splits, optional `#labels`, insights (category, month, label, friend).

---

## Deployment (Render)

Live: `https://hisaabkitaab-svgo.onrender.com`. Push to `main` → Render auto-deploys from GitHub (`RavindraMedhat/HisaabKitaab`).
Free tier sleeps after 15 min idle; ping `/api/me` every 14 min (UptimeRobot) to avoid cold starts.
Local and live share one Firestore database.

# HisaabKitaab — Project Guide

Splitwise-like expense splitting app for Indian users.
Built with FastAPI + plain HTML/CSS/JS frontend, Firebase Firestore, Google OAuth.

---

## Stack

| Layer      | Tech |
|------------|------|
| Backend    | Python 3.11, FastAPI, Uvicorn |
| Frontend   | Vanilla HTML/CSS/JS SPA (no framework) |
| Auth       | Google OAuth2 (server-side flow) + PKCE |
| Database   | Firebase Firestore (Admin SDK) |
| Sessions   | Starlette SessionMiddleware (signed cookie, 7-day) |
| Hosting    | Render.com free tier |
| Local port | 7485 |

---

## Project Structure

```
MySplitwise/
├── main.py                  # FastAPI app, session middleware, global error handler
├── routers/
│   ├── auth.py              # Google OAuth login/callback/logout with PKCE
│   └── api.py               # All REST endpoints (groups, expenses, settlements, invites)
├── services/
│   ├── firebase.py          # Firebase Admin SDK init (env var or file)
│   ├── calculator.py        # Debt simplification algorithm
│   └── logger.py            # log_error() — writes failures to Firestore logs collection
├── static/
│   ├── index.html           # SPA shell, PWA meta tags
│   ├── style.css            # Mobile-first design system (iOS-style, CSS tokens)
│   └── app.js               # Hash router + all views + API calls
├── scripts/
│   ├── check_logs.py        # View Firebase error logs in terminal
│   └── clear_logs.py        # Clear all Firebase error logs
├── Dockerfile               # python:3.11-slim, port ${PORT:-8080}
├── .dockerignore            # excludes .env, serviceAccountKey.json, __pycache__
├── .env                     # local dev secrets (never commit)
├── render.env               # Render paste-ready env vars (never commit)
└── serviceAccountKey.json   # Firebase service account (never commit)
```

---

## Environment Variables

| Variable | Where set | Purpose |
|----------|-----------|---------|
| `SECRET_KEY` | `.env` / Render | Starlette session signing key |
| `GOOGLE_CLIENT_ID` | `.env` / Render | OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | `.env` / Render | OAuth client secret |
| `GOOGLE_APPLICATION_CREDENTIALS` | `.env` (local) | Path to serviceAccountKey.json |
| `FIREBASE_CREDENTIALS` | Render only | Full serviceAccountKey.json as JSON string |
| `REDIRECT_URI` | Render only | `https://<render-url>/auth/callback` |
| `ENV` | Render only | Set to `production` (enables Secure cookie flag) |

---

## Local Dev

```bash
# Start
uvicorn main:app --port 7485 --reload

# Check Firebase logs
python scripts/check_logs.py

# Tail logs live
python scripts/check_logs.py --tail

# Clear logs
python scripts/clear_logs.py
```

---

## Firestore Collections

| Collection | Purpose |
|------------|---------|
| `users/{uid}` | User profile (uid, name, email, picture) |
| `groups/{gid}` | Group doc (name, members[], created_by, created_at) |
| `groups/{gid}/expenses/{eid}` | Expense (description, amount, paid_by, split_among[], created_at) |
| `groups/{gid}/settlements/{sid}` | Settlement (from_uid, to_uid, amount, note, created_at) |
| `invites/{id}` | Invite (group_id, invited_uid, invited_by, status: pending/accepted/declined) |
| `logs/{id}` | Error logs (level, message, exception, traceback, extra, timestamp) |

---

## API Endpoints

### Auth
| Method | Path | Description |
|--------|------|-------------|
| GET | `/auth/login` | Start Google OAuth (PKCE) |
| GET | `/auth/callback` | OAuth callback, sets session |
| GET | `/auth/logout` | Clear session |

### User
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/me` | Current user info |
| GET | `/api/dashboard` | Net balance, recent activity, invite count |

### Groups
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/groups` | List user's groups |
| POST | `/api/groups` | Create group |
| GET | `/api/groups/{gid}` | Group detail (members, expenses, settlements, transactions, is_creator) |
| DELETE | `/api/groups/{gid}` | Delete group (creator only, must be settled) |
| POST | `/api/groups/{gid}/leave` | Leave group (non-creator, must be settled) |

### Members
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/groups/{gid}/members` | Send invite (creator only) |
| DELETE | `/api/groups/{gid}/members/{uid}` | Remove member (creator only, balance must be 0) |

### Expenses
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/groups/{gid}/expenses` | Add expense |
| PUT | `/api/groups/{gid}/expenses/{eid}` | Edit expense (creator or payer) |
| DELETE | `/api/groups/{gid}/expenses/{eid}` | Delete expense (creator or payer) |

### Settlements
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/groups/{gid}/settlements` | Record settlement (capped at actual debt) |

### Invites
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/invites` | Pending invites for current user |
| POST | `/api/invites/{id}/accept` | Accept invite (adds to group) |
| POST | `/api/invites/{id}/decline` | Decline invite |

---

## Frontend SPA Routes

| Hash | View |
|------|------|
| `#/` | Dashboard (net balance, recent activity, invite badge) |
| `#/groups` | Groups list + create group |
| `#/groups/{gid}` | Group detail (expenses, settle up, members, edit/delete) |
| `#/add?group={gid}` | Add expense form |
| `#/invites` | Pending invites (accept/decline) |
| `#/account` | User profile + sign out |
| `#/login` | Google sign-in page |

---

## Validation Rules (29 checks)

- Group name: non-empty, max 60 chars
- Expense: description non-empty (max 200), amount > 0 (max ₹10L), paid_by must be member, split_among non-empty and all members
- Settlement: amount > 0, from ≠ to, both must be members, requester must be party, capped at actual debt
- Invite: email format valid, user must exist, can't invite self, no duplicate pending invites
- Remove member: balance must be 0
- Leave group: balance must be 0
- Delete group: all debts must be settled

---

## Deployment (Render)

Live URL: `https://hisaabkitaab-svgo.onrender.com`

Deploy: push to `main` branch → Render auto-deploys from GitHub (`RavindraMedhat/HisaabKitaab`).

Generate `render.env` (paste into Render env vars UI):
```bash
python3 -c "
import json
creds = json.dumps(json.load(open('serviceAccountKey.json')))
print(f'ENV=production')
print(f'SECRET_KEY=...')
print(f'GOOGLE_CLIENT_ID=...')
print(f'GOOGLE_CLIENT_SECRET=...')
print(f'FIREBASE_CREDENTIALS={creds}')
print(f'REDIRECT_URI=https://hisaabkitaab-svgo.onrender.com/auth/callback')
"
```

---

## Known Issues / History

- **PKCE required**: newer `google-auth-oauthlib` versions send `code_challenge` in auth URL; `code_verifier` must be stored in session during login and passed to `fetch_token` in callback. Fixed in `routers/auth.py`.
- **Render free tier**: sleeps after 15 min idle. Use UptimeRobot (free) to ping `/api/me` every 14 min to prevent cold starts.
- **Google Cloud billing**: Cloud Run requires billing even for free tier. Using Render instead.

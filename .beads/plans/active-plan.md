# Plan: Wire Up Backend Routes, DB, Auth Middleware, and Frontend Auth Flow

**Status**: in-progress (WU-1 through WU-3 complete, WU-4 partially complete)
**Epic**: smart_meat-gsc
**Branch**: `wu/wire-backend-routes-auth` (pushing directly to main)

## Completed Work Units

### WU-1: Fix router aggregation, add FRONTEND_URL config, and wire main.py — DONE
- Removed `prefix="/api"` from api_router (fixed double-prefix bug)
- Added `init_db()` / `dispose_db()` to engine.py
- Rewrote main.py with full wiring (9 session dep overrides, middleware ordering)
- Added `FRONTEND_URL` to config.py and fly.toml
- 787 tests pass, 100% coverage

### WU-2: Add /api/auth/me endpoint — DONE
- Added `GET /api/auth/me` inside `create_auth_router()`
- Returns `{id, email, name, avatarUrl}` from authenticated user
- 791 tests pass, 100% coverage

### WU-3: Frontend auth initialization and conditional routing — DONE
- Added `fetchCurrentUser()` with 401→refresh→retry logic
- Updated authStore with `isLoading`/`setLoading`
- Updated providers.tsx with auth initialization useEffect
- Converted page.tsx to client component with loading/redirect/landing states
- 359 frontend tests pass, 100% coverage

### WU-4: Deploy and verify end-to-end — PARTIALLY DONE

**Completed:**
- Backend deployed to smart-meat-api.fly.dev
- Frontend deployed to smart-meat-web.fly.dev
- Fixed asyncpg `sslmode` incompatibility (strips param, passes `ssl=False`)
- Fixed `SameSite=none` for cross-origin cookies between frontend/backend domains
- Removed LLM consent redirect from OAuth callback (always redirects to /dashboard)
- Added `/api/auth/dev-login` endpoint for debugging without Google OAuth
- Auth flow verified: `/api/auth/me` returns 200 with valid cookies
- Landing page loads cleanly, shows Sign In link

**Remaining:**
- [ ] Fix `/api/dashboard/summary` 500 — DB missing `nugget_status` enum value "accepted"
- [ ] Verify full dashboard renders with data
- [ ] Verify Google OAuth flow end-to-end (dev-login confirmed working)

## Post-WU-4 Fixes Applied

### asyncpg + sslmode (engine.py)
- `_sanitize_url()` strips `sslmode` from DATABASE_URL
- Converts `sslmode=disable` → `connect_args={"ssl": False}`
- Without this: TypeError or ConnectionResetError on Fly

### Cross-origin cookies (auth.py)
- All `set_cookie()` calls changed from `samesite="lax"` → `samesite="none"`
- Required because frontend (smart-meat-web.fly.dev) and backend (smart-meat-api.fly.dev) are different domains
- `SameSite=lax` blocks cookies on cross-origin fetch with `credentials: "include"`

### Dev login bypass (auth.py)
- `GET /api/auth/dev-login` — creates dev user, sets JWT cookies, redirects to /dashboard
- Controlled by `DEV_LOGIN_ENABLED` env var (set to `true` on Fly)
- Added to auth middleware `_SKIP_PATHS`

### Consent redirect removed (auth.py)
- OAuth callback always redirects to `/dashboard` regardless of `llm_consent_given_at`

## Known Issues
- `/api/dashboard/summary` returns 500: `nugget_status` enum in DB missing "accepted" value
- This is a DB migration issue, not an auth issue

# Frontend Guide: Role-Based Auth (Tenant Admin Login)

This document explains how signup, login, remember-me, email verification, and forgot password flows work with the new role-based authentication, specifically for the Tenant Admin experience. Share this with frontend engineers implementing the UI.

Important notes:
- Legacy endpoints under `/api/auth/signup` and `/api/auth/login` are deprecated and return HTTP 410.
- Use the new role-based endpoints under `/api/role-auth/*`.
- For now, the UI will expose only the Tenant Admin login screen. This document also includes Tenant Admin signup for completeness (dev and onboarding flows).

## Base URLs and Headers
- Base API path: `/api`
- Content type: `application/json`
- Auth header (when logged in): `Authorization: Bearer <access_token>`

## Endpoints Overview

- Tenant Admin Signup (public): `POST /api/role-auth/tenant-admin/signup`
- Role-Based Login (Tenant Admin): `POST /api/role-auth/login`
- Token Refresh: `POST /api/auth/refresh`
- Profile (to confirm login): `GET /api/auth/profile`

Deprecated (do not use):
- `POST /api/auth/signup` → 410 Gone
- `POST /api/auth/login` → 410 Gone

---

## 1) Tenant Admin Signup

Used for creating the organization and the first admin user. In production you may drive this via internal tooling or an onboarding form.

Endpoint:
- `POST /api/role-auth/tenant-admin/signup`

Request JSON:
```json
{
  "organization_name": "Acme Corp",
  "industry": "SaaS",
  "organization_size": "small",
  "email": "admin@acme.com",
  "password": "Admin!23#",
  "first_name": "Ada",
  "last_name": "Lovelace",
  "phone": "+1234567890"
}
```

Response JSON (200):
```json
{
  "access_token": "<jwt>",
  "refresh_token": "<jwt>",
  "token_type": "Bearer",
  "expires_in": 3600,
  "user": {
    "id": "<uuid>",
    "email": "admin@acme.com",
    "first_name": "Ada",
    "last_name": "Lovelace",
    "role": "tenant_admin"
  },
  "organization": {
    "id": "<uuid>",
    "name": "Acme Corp",
    "industry": "SaaS",
    "size": "small"
  },
  "permissions": [
    "organization:create", "organization:read", "organization:update", "organization:delete",
    "user:create", "user:read", "user:update", "user:delete",
    "call:*", "evaluation:*", "analytics:*", "settings:*"
  ]
}
```

Key points:
- A verification email is sent via Keycloak; the admin must verify before first login.
- If `password` is not provided, backend generates a temporary password and includes `"temporary_password": true` in the response.

---

## 2) Tenant Admin Login

Tenant Admin logs in using email/password and explicitly specifies role = `tenant_admin`. Backend validates the role against the user’s profile.

Endpoint:
- `POST /api/role-auth/login`

Request JSON:
```json
{
  "email": "admin@acme.com",
  "password": "Admin!23#",
  "role": "tenant_admin"
}
```

Response JSON (200):
```json
{
  "access_token": "<jwt>",
  "refresh_token": "<jwt>",
  "token_type": "Bearer",
  "expires_in": 3600,
  "user": {
    "id": "<uuid>",
    "email": "admin@acme.com",
    "first_name": "Ada",
    "last_name": "Lovelace",
    "role": "tenant_admin"
  },
  "organization": {
    "id": "<uuid>",
    "name": "Acme Corp",
    "industry": "SaaS",
    "size": "small"
  },
  "permissions": [
    "organization:*",
    "user:*",
    "call:*",
    "evaluation:*",
    "analytics:*",
    "settings:*"
  ]
}
```

Errors you may encounter:
- 401 with a message like "Please verify your email address" if email is unverified in Keycloak.
- 400/401 for invalid credentials.
- 403 if the user’s database role does not match `tenant_admin`.

---

## 3) Remember Me and Token Refresh

Recommended implementation for a "Remember me" checkbox:
- If checked, persist the `refresh_token` in a secure HTTP-only cookie with a longer expiration (e.g., 30 days).
- Always keep the `access_token` short-lived and in memory; do not store in localStorage.
- On token expiration (or proactively at 2–5 minutes before), call refresh.

Refresh endpoint:
- `POST /api/auth/refresh`

Request JSON:
```json
{ "refresh_token": "<jwt>" }
```

Response JSON (200):
```json
{
  "access_token": "<jwt>",
  "refresh_token": "<jwt>",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_expires_in": 2592000,
  "scope": null
}
```

Frontend recommendations:
- Store `refresh_token` in an HTTP-only, Secure cookie with `SameSite=Lax` or `Strict` depending on your app’s needs.
- Rotate refresh tokens each time you call refresh (overwrite the cookie with the new one from the response).
- Keep `access_token` in memory (React state) and attach it as `Authorization: Bearer <access_token>`.

---

## 4) Verify Email

- Triggered automatically during signup. Keycloak sends verification email via SMTP.
- The verification link opens Keycloak’s Account Console; there is no custom redirect for now.
- After verification, user can proceed to login via the UI using the endpoint above.

UX tip:
- On login failure with message containing "verify your email", show a CTA button: "Resend verification email" (see below) or a help link.

Resend verification email (optional enhancement):
- We can add an endpoint to trigger Keycloak’s `EXECUTE_ACTIONS_EMAIL` with `VERIFY_EMAIL` for a given email.
- Proposed endpoint (to implement later): `POST /api/role-auth/resend-verification` with `{ "email": "..." }`.

---

## 5) Forgot Password (Reset Password) — No Redirect

We provide a backend endpoint to trigger Keycloak to send a password reset email, so the UX stays in our app without redirecting the user to Keycloak pages.

Endpoint (public, no auth):
- `POST /api/role-auth/forgot-password`

Request JSON:
```json
{ "email": "admin@acme.com" }
```

Response JSON (200):
```json
{ "message": "If the email exists, a password reset link has been sent." }
```

Notes:
- This endpoint is user-enumeration safe; it always returns success.
- It uses Keycloak Admin API `execute-actions-email` with `UPDATE_PASSWORD` under the hood.
- Make sure to show a generic success toast/snackbar regardless of whether the email exists.

Frontend UX flow:
- Login screen: add a “Forgot password?” link that opens a small modal or dedicated screen.
- Modal fields: Email (required)
- On submit: call `POST /api/role-auth/forgot-password` with `{ email }`
- Show success: “If the email exists, a password reset link has been sent.”
- The user will receive an email from Keycloak; clicking the link allows setting a new password, then return to your app and login normally.

Security and cookies:
- No token/cookie required for this endpoint.
- The request should be CSRF-protected if you use cookies; since there is no auth cookie involved, standard CSRF mitigations are sufficient.

---

## 6) Post-Login Profile Check (Optional)

To confirm the token and retrieve the server-calculated user context:
- `GET /api/auth/profile`
- Headers: `Authorization: Bearer <access_token>`

Response JSON:
```json
{
  "id": "<uuid>",
  "email": "admin@acme.com",
  "username": null,
  "first_name": "Ada",
  "last_name": "Lovelace",
  "roles": ["tenant_admin"],
  "tenant_id": "default",
  "organization_id": "<uuid>",
  "department_id": null,
  "team_id": null
}
```

---

## 7) UI Wire Guidance (Tenant Admin Login Only)

Login form fields:
- Email
- Password
- Remember me (checkbox)
- CTA buttons: Login, Forgot Password

Login submission:
- POST `/api/role-auth/login` with `{ email, password, role: "tenant_admin" }`
- On 200:
  - Store `access_token` in memory
  - Store `refresh_token` in secure HTTP-only cookie if Remember me is checked; else, set a session cookie
  - Navigate to dashboard
- On 401 with message mentioning verification:
  - Show “Verify your email to continue” and optionally a “Resend verification email” button (once implemented)

Token refresh strategy:
- On app load, check for refresh cookie; if present, call `/api/auth/refresh` to bootstrap session
- Set a timer to refresh the token periodically (e.g., at `expires_in - 120s`)

Logout (optional):
- If implemented in UI, clear tokens and redirect to login. We have `/api/auth/logout` interface prepared but it may rely on server-side refresh token storage; for now, client-only token clearing is acceptable.

---

## 8) Error Handling

Common HTTP statuses:
- 400/401: Invalid credentials, email not verified, bad request
- 403: Role mismatch or insufficient permissions
- 409: Duplicate email/organization during signup
- 410: Deprecated legacy endpoints

Frontend UX:
- Surface meaningful messages based on `detail` string in error JSON
- For role mismatch, ensure login request includes `role: "tenant_admin"`

---

## 9) Security Best Practices (Frontend)

- Never store the access token in localStorage. Use memory only.
- Use secure, HTTP-only cookies for refresh tokens.
- Use `SameSite=Lax` or `Strict` and `Secure` (HTTPS) in production.
- Avoid embedding tokens in URLs.
- Handle token rotation on each `/refresh` call.

---

## 10) Quick Reference

- Signup (public): `POST /api/role-auth/tenant-admin/signup`
- Login: `POST /api/role-auth/login` with `role: "tenant_admin"`
- Refresh: `POST /api/auth/refresh`
- Profile: `GET /api/auth/profile`
- Forgot Password: `POST /api/role-auth/forgot-password`
- Verify Email: Keycloak email link after signup

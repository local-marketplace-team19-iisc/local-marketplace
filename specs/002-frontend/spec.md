# Spec — Feature 002: Frontend (Architectural Contract)

> Canonical contract for the frontend feature. Derived from the input
> `002-frontend-SPEC.md` plus the decisions resolved with the user (D1–D4 below).
> Authority order (conflicts resolve upward): `specs/constitution.md` → `SPEC.md` →
> `docs/architecture.md`. This file is the feature's `spec.md` per Constitution P3.
> The original input `002-frontend-SPEC.md` is retained unchanged as the source brief.

## 1. Goal

A modern, responsive React presentation layer for the AI-Driven NLP-Based Local
Marketplace, serving both **Customers** (conversational product search, results,
cart/orders) and **Vendors** (onboarding, product management). The frontend holds
**no business logic** (C-04); NLP, ranking, pricing, inventory, and storage stay in
backend services. It integrates over **REST** (C-03) and is configurable via env (C-05).

## 2. Resolved decisions

| # | Topic | Decision | Authority/Reason |
| :- | :-- | :-- | :-- |
| **D1** | React version | **React 19+** (C-01). Conflict with `SPEC.md` §5 ("React 18") is **logged in `docs/architecture.md`** and flagged for a human PR to reconcile the master spec. | User decision; P5 forbids AI editing `SPEC.md`. |
| **D2** | State management | **React Context API + `useReducer`** (C-02). The `src/store/` folder is kept but files are **Context providers/reducers** (`authContext`, `productContext`, `chatbotContext`, combined `store.jsx`), **not** Redux slices. No Redux dependency. | C-02 is explicit; layout naming overruled. |
| **D3** | Backend integration | **Mock against an assumed REST contract** (see §6). A service layer is toggled by `VITE_USE_MOCKS`; real backend wired later via `VITE_API_BASE_URL`. | Backend currently exposes only `GET /health`. |
| **D4** | Frontend `CLAUDE.md` + `plan.md` location | Both placed in **`specs/002-frontend/`**. | User request. (A `CLAUDE.md` there is informational, not auto-loaded.) |

## 3. Constraints (from input spec)

C-01 React 19+ · C-02 Context API · C-03 REST only · C-04 no business logic in UI ·
C-05 endpoints via env vars · C-06 Chrome/Firefox/Edge/Safari · C-07 mobile/tablet/desktop ·
C-08 JWT auth · C-09 no sensitive data in browser storage · C-10 consume only documented APIs.

**Implementation notes:**
- **C-08/C-09:** JWT is held **in memory** (Context) only — never `localStorage`/
  `sessionStorage`. Page refresh loses the session (documented limitation; production
  target is an httpOnly cookie issued by the backend).
- **C-05/C-10:** `VITE_API_BASE_URL` + `VITE_USE_MOCKS`; the "documented API" is §6 here
  and `frontend/API_INTEGRATION_GUIDE.md` until the backend publishes `openapi.json`.

## 4. Tooling & layout

- **Build:** Vite (React 19; CRA deprecated). **Deviation from input layout:** Vite's
  `index.html` lives at the `frontend/` root, not under `public/`. `public/` holds
  static assets (`favicon.ico`, `logo.png`).
- **Styling:** plain CSS + global `index.css` (no UI framework) for a lean, fast build.
- **Routing:** `react-router-dom`; protected routes via a `ProtectedRoute` wrapper.
- Folder structure follows the input spec §3 except the `index.html` location (above)
  and `store/` file semantics (D2).

## 5. Acceptance criteria

Inherits **AC-01 … AC-20** from `002-frontend-SPEC.md` §4 verbatim. Verification mapping
lives in `plan.md` and `frontend/TEST_CASES.md`. Binary deliverables are substituted:
`TEST_CASES.xlsx` → `TEST_CASES.md`; `SCREENSHOTS/*.png` captured manually post-build.

## 6. Assumed REST API contract (mocked now; backend to confirm)

Base `${VITE_API_BASE_URL}` (default `http://localhost:8000`), JSON, Bearer JWT.

| Area | Endpoint | Notes |
| :-- | :-- | :-- |
| Auth | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me` | `role: customer|vendor`; returns `{token,user}`. |
| Products | `GET /api/products?query=&page=`, `GET /api/products/:id`, `POST/PUT/DELETE /api/products[/:id]` | vendor CRUD = AC-13/14/15. |
| Search | `GET /api/search?q=` | returns Name, Price, Vendor, Rating, Availability (AC-10). |
| Chatbot | `POST /api/chat` `{message,sessionId}` → `{reply,listings?}` | AC-11/12. |
| Orders | `GET /api/orders`, `POST /api/orders` | multi-vendor cart → one order number (SPEC §3). |

## 7. Open `[NEEDS CLARIFICATION]`

- `[NEEDS CLARIFICATION: backend to confirm/replace the §6 contract and publish docs/api/openapi.json]`
- `[NEEDS CLARIFICATION: UI component library desired? default = plain CSS]`
- `[NEEDS CLARIFICATION: must TEST_CASES be a true .xlsx? default = .md]`

## 8. Out of scope

Backend, DB, auth issuance, NLP/ranking, real order persistence, and any non-`frontend/`
file (except the living `docs/architecture.md` log). Owned by other features (P6).

# Local Marketplace — Frontend

React 19 + Vite presentation layer for the AI-Driven NLP-Based Local Marketplace.
Feature `002-frontend`. The frontend is a **presentation layer only** — all business
logic (NLP, ranking, pricing, inventory, persistence) lives in backend services.

> Spec & decisions: `../specs/002-frontend/spec.md` · Dry-run/phases:
> `../specs/002-frontend/plan.md` · Governance: `../specs/constitution.md`.

## Stack

- **React 19** + **Vite 6** (build tool)
- **react-router-dom 7** for routing
- **React Context API** for state (no Redux) — see `src/store/`
- **ESLint 9** (+ jsx-a11y) for quality/accessibility
- Plain CSS with design tokens (`src/index.css`)

## Prerequisites

- Node.js ≥ 18 (developed on Node 24, npm 11)

## Environment variables (`.env`)

Copy `.env.example` → `.env`. Never commit `.env` (gitignored). Placeholders only.

| Variable | Default | Purpose |
| :-- | :-- | :-- |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend REST base URL |
| `VITE_USE_MOCKS` | `true` | When `true`, the service layer returns mock data instead of calling the backend |

## Scripts

```bash
npm install      # install dependencies
npm run dev      # start Vite dev server (http://localhost:5173)
npm run build    # production build → build/
npm run preview  # serve the production build (http://localhost:4173)
npm run lint     # ESLint (+ jsx-a11y)
```

## Mock mode & demo accounts

With `VITE_USE_MOCKS=true` (default) the app runs entirely against an in-memory mock of
the assumed REST contract (see `API_INTEGRATION_GUIDE.md`). Demo logins:

| Role | Email | Password |
| :-- | :-- | :-- |
| Customer | `customer@demo.com` | `demo1234` |
| Vendor | `vendor@demo.com` | `demo1234` |

## NLP, voice & image input (AC-09/11/13/14/15)

- **Search** (customers): text, **voice** (mic), or **image** upload → matched products.
- **Chatbot** (AC-11): **voice, text, and image** — attach an image or dictate a message.
- **Auto-fill products** (vendors): describe a product in a prompt (typed or **dictated**)
  or upload an image → extracted fields pre-fill the Add/Edit form for review, then save.
- **Delete by description** (vendors): type or say "remove the milk" → confirm → delete.

**Voice** uses the browser **Web Speech API** (Chrome/Edge; the mic is hidden where
unsupported, e.g. Firefox) — aligns with the master spec's "voice→text". **Image/NLP** in
mock mode are **heuristic, not real vision** (prompt parsing / image filename); they call
`POST /api/search/image`, `POST /api/extract/product`, and `POST /api/chat` (multipart),
wired to a real backend by flipping `VITE_USE_MOCKS`. See `API_INTEGRATION_GUIDE.md`.

## Switching to the real backend

1. Set `VITE_USE_MOCKS=false` and `VITE_API_BASE_URL` to the backend URL.
2. Ensure the backend implements the contract in `API_INTEGRATION_GUIDE.md` (or update
   that doc + the service layer to match the published `openapi.json`).
No UI/component changes are required — only the service layer is affected.

## Docker

```bash
docker build -t marketplace-frontend .
docker run -p 8080:80 marketplace-frontend   # http://localhost:8080
```
Multi-stage build (Node → nginx) serving the static `build/` with SPA fallback.

## Project structure

```
src/
  assets/        images, icons, shared styles (forms.css)
  components/    common/ (Button, Loader, Modal, Navbar)
                 products/ (ProductCard, ProductList, ProductDetails)
                 chatbot/ (ChatWindow, ChatInput, MessageBubble)
  pages/         Login, Register, Search, Product, Favorites, Orders,
                 Chatbot, Dashboard, Vendor
  services/      apiClient + auth/product/search/chatbot/order; _mocks/
  store/         Context providers (auth/product/chatbot) + AppProviders
  hooks/         useAuth, useProducts, useChat
  routes/        AppRoutes, ProtectedRoute
  utils/         constants, validators, helpers
```

## Notes & deviations from the original spec layout

- **`index.html` is at the project root** (Vite convention), not under `public/`.
  `public/` holds static assets.
- **Logo/favicon are SVG** (`logo.svg`, `favicon.svg`) instead of `logo.png`/
  `favicon.ico` (text-authorable placeholders).
- **State management is Context API** (constraint C-02); the `store/` folder holds
  Context providers, not Redux slices.
- **Build output is `build/`** (not Vite's default `dist/`) to match the spec.
- See the other docs in this folder: `UI_DESIGN.md`, `COMPONENT_DOCUMENTATION.md`,
  `ROUTING_DOCUMENTATION.md`, `API_INTEGRATION_GUIDE.md`, `TEST_CASES.md`.

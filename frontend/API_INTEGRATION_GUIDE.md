# API Integration Guide — Frontend

How the frontend talks to the backend, and the **assumed REST contract** it currently
mocks. This contract is the frontend's working assumption (decision **D3**) — it is
**not** a backend commitment. `[NEEDS CLARIFICATION]`: the backend team should confirm or
replace these shapes and publish `docs/api/openapi.json`.

## Configuration

| Variable | Default | Meaning |
| :-- | :-- | :-- |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Base URL for all requests |
| `VITE_USE_MOCKS` | `true` | `true` → in-memory mock layer; `false` → real `fetch` |

All requests go through `src/services/apiClient.js`, which:
- prefixes `VITE_API_BASE_URL`,
- sets `Content-Type: application/json`,
- attaches `Authorization: Bearer <token>` when authenticated,
- routes to the mock dispatcher when `VITE_USE_MOCKS=true`,
- normalizes failures into an `ApiError { message, status, data }`.

## Authentication (C-08 / C-09)

- The JWT is stored **in memory only** (module variable in `apiClient`), set via
  `setAuthToken` on login/register and cleared on logout.
- It is **never** written to `localStorage`/`sessionStorage` (C-09), so a full page
  refresh ends the session. **Production target:** an httpOnly cookie issued by the
  backend — deferred to the auth/backend feature.

## Assumed contract

Base: `${VITE_API_BASE_URL}`. JSON request/response. `🔒` = requires Bearer token.

### Auth
| Method | Path | Body | Response |
| :-- | :-- | :-- | :-- |
| POST | `/api/auth/register` | `{ name, email, password, role: "customer"\|"vendor" }` | `{ token, user }` |
| POST | `/api/auth/login` | `{ email, password }` | `{ token, user }` |
| GET 🔒 | `/api/auth/me` | — | `{ user }` |

`user` = `{ id, name, email, role, vendorId?, vendor? }` (vendor fields present for vendors).

### Products
| Method | Path | Notes |
| :-- | :-- | :-- |
| GET | `/api/products?query=` | `{ products: Product[] }` |
| GET | `/api/products/:id` | `{ product: Product }` |
| POST 🔒 | `/api/products` | vendor only; `{ product }` |
| PUT 🔒 | `/api/products/:id` | vendor only; `{ product }` |
| DELETE 🔒 | `/api/products/:id` | vendor only; `{ success, id }` |

`Product` = `{ id, name, price, vendorId, vendor, rating, stock, category, description, availability }`
(`availability` derived from `stock > 0`).

### Search
| Method | Path | Response |
| :-- | :-- | :-- |
| GET | `/api/search?q=` | `{ results: { id, name, price, vendor, rating, availability }[] }` — cheapest-first |

### Chatbot
| Method | Path | Body | Response |
| :-- | :-- | :-- | :-- |
| POST | `/api/chat` | `{ message, sessionId }` | `{ reply, listings?, sessionId }` |

### Orders
| Method | Path | Body | Response |
| :-- | :-- | :-- | :-- |
| GET 🔒 | `/api/orders` | — | `{ orders: Order[] }` |
| POST 🔒 | `/api/orders` | `{ items: { productId, vendorId?, qty }[] }` | `{ order }` |

`Order` = `{ orderNumber, userId, items[], total, vendors[], placedAt }`. A cart may span
multiple vendors and produces a single `orderNumber` (master SPEC §3); placing an order
decrements stock.

## Error handling

Failures throw `ApiError`; the UI shows a friendly message (AC-04) via error banners or
chat error bubbles. Mock handlers return realistic HTTP-style statuses
(`400/401/403/404/409`).

## Demo accounts (mock mode)

`customer@demo.com` / `vendor@demo.com`, password `demo1234`.

## Switching to the real backend

1. `VITE_USE_MOCKS=false`, set `VITE_API_BASE_URL`.
2. Confirm the backend matches the shapes above (or update `src/services/*` + this doc to
   match the published `openapi.json`).

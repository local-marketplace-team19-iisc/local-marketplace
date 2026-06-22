# Frontend Documentation

Combined reference for the `002-frontend` feature. Consolidates what were previously
five separate docs: UI design, components, routing, API integration, and test cases.

> Spec & decisions: `../specs/002-frontend/spec.md` · Dry-run/phases:
> `../specs/002-frontend/plan.md` · Governance: `../specs/constitution.md`.

## Contents

1. [UI Design](#1-ui-design)
2. [Components](#2-components)
3. [Routing](#3-routing)
4. [API Integration](#4-api-integration)
5. [Test Cases](#5-test-cases)

---

# 1. UI Design

A clean, responsive marketplace UI built with plain CSS and design tokens (no UI
framework), optimized for a fast initial load (AC-16).

## Design tokens (`src/index.css`)

| Token | Value | Use |
| :-- | :-- | :-- |
| `--color-primary` | `#2563eb` | Actions, links, accents |
| `--color-danger` | `#dc2626` | Errors, destructive actions |
| `--color-success` | `#16a34a` | In-stock badges |
| `--color-bg` / `--color-surface` | `#f7f8fa` / `#ffffff` | Page / cards |
| `--color-text` / `--color-muted` | `#1a1d21` / `#5b6470` | Text |
| `--radius` | `10px` | Corner radius |
| `--space` | `16px` | Base spacing unit |
| `--max-width` | `1200px` | Content container width |
| `--font` | system UI stack | Typography |

## Layout & responsiveness (AC-02 / AC-07)

- `.container` centers content at max 1200px with side padding.
- Verified across **320px → 1920px**. Key breakpoints:
  - ≤ 720px: Navbar collapses to a toggle menu.
  - ≤ 680px: vendor table → stacked labelled cards.
  - ≤ 640px: product details → single column.
  - ≤ 480px / 380px: search bar stacks; product grid → single column.
- Product grid uses `repeat(auto-fill, minmax(240px, 1fr))`.

## Accessibility (AC-19)

- Semantic landmarks (`header`, `main`, `nav`), labelled form controls with
  `aria-invalid` / `aria-describedby`.
- Visible focus rings (`:focus-visible`) on interactive elements.
- `Loader` announces via `role="status"`; chat list uses `aria-live="polite"`.
- `Modal` is a proper dialog (`role="dialog"`, `aria-modal`, Escape/backdrop close).
- Respects `prefers-reduced-motion` for the spinner.
- `.visually-hidden` utility for screen-reader-only labels.

## Feedback states (AC-03 / AC-04)

- Loading: `Loader` during all API calls.
- Errors: friendly banners (`.form-banner--error`) and chat error bubbles.
- Empty: explicit empty-state messages on lists.

## Component styles

See [§2 Components](#2-components). Component styles are colocated (`Component.css`);
shared form styles live in `src/assets/styles/forms.css`; global tokens/utilities and
badges in `src/index.css`.

---

# 2. Components

Reusable components and their props. All components are presentation-only (C-04); data
and actions come from contexts/hooks or props.

## Common

### `Button`
| Prop | Type | Default | Notes |
| :-- | :-- | :-- | :-- |
| `variant` | `primary\|secondary\|danger\|ghost` | `primary` | Visual style |
| `size` | `sm\|md\|lg` | `md` | |
| `loading` | `bool` | `false` | Disables + shows busy label; sets `aria-busy` |
| `type` | `button\|submit` | `button` | |
| `...rest` | — | — | Spread to `<button>` (`onClick`, `disabled`, etc.) |
Add `className="btn--block"` for full-width.

### `Loader`
| Prop | Type | Default | Notes |
| :-- | :-- | :-- | :-- |
| `label` | `string` | `Loading…` | Announced via `role="status"` (AC-03/19) |
| `inline` | `bool` | `false` | Inline vs block |
| `fullPage` | `bool` | `false` | Centered, tall |

### `Modal`
| Prop | Type | Notes |
| :-- | :-- | :-- |
| `open` | `bool` | Renders nothing when false |
| `title` | `string` | Dialog label (`aria-label`) |
| `onClose` | `fn` | Called on Escape, backdrop, or × button |
| `footer` | `node` | Optional footer (e.g. action buttons) |
| `children` | `node` | Body content |
Accessible: `role="dialog"`, `aria-modal`, Escape to close, keyboard-operable backdrop.

### `Navbar`
No props. Reads `useAuth` + `useProducts`; renders role/auth-aware links and a responsive
toggle menu.

### `VoiceButton` — `{ onText, title?, disabled? }`
Mic toggle (voice→text, D9). Calls `onText(transcript)`. Built on the `useVoiceInput`
hook (Web Speech API); **renders nothing where unsupported** (e.g. Firefox), so the text
input always remains. Used in search, chat, vendor extract, and voice-delete.

## Products

### `ProductCard` — `{ product }`
Shows name, price, vendor, rating, availability (AC-10); favorite toggle + add-to-cart.
Works with both catalog products and search results.

### `ProductList` — `{ products, emptyMessage? }`
Responsive grid of `ProductCard`s with an empty state.

### `ProductDetails` — `{ product }`
Full view with quantity selector, favorite, add-to-cart.

### `ProductExtractPanel` — `{ onExtracted }`
NLP-prompt + image-upload control used in the vendor add/edit modal (AC-13/14, D5/D6).
Calls `extractProduct({ prompt, image })` and invokes `onExtracted(productFields)` so the
parent pre-fills the form for review. Shows its own loading/error state.

## Chatbot

### `MessageBubble` — `{ message }`
`message` = `{ id, sender: 'user'|'bot', text, listings?, isError? }`. Renders bot
listings as links to the product page.

### `ChatInput` — `{ onSend, disabled }`
Controlled composer with text, **voice** (mic), and **image attach**. Calls
`onSend(text, image?)`; submits on Enter; clears text + image after send.

### `ChatWindow`
No props. Reads `useChat`; renders history, a typing loader, auto-scrolls; hosts
`ChatInput`.

## State access (hooks)

- `useAuth()` → `{ user, token, status, error, isAuthenticated, login, register, logout }`
- `useProducts()` → catalog/search/favorites/cart/orders state + actions
  (`fetchProducts`, `searchProducts`, `addProduct`, `editProduct`, `removeProduct`,
  `toggleFavorite`, `isFavorite`, `addToCart`, `removeFromCart`, `clearCart`,
  `placeOrder`, `cartTotal`, `cartCount`)
- `useChat()` → `{ messages, status, error, sessionId, sendMessage, reset }`
  (`sendMessage(text, image?)`)
- `useVoiceInput({ onResult, lang? })` → `{ supported, listening, error, start, stop, toggle }`
  — Web Speech API wrapper (D9)

---

# 3. Routing

Routing uses `react-router-dom` v7. The route table lives in `src/routes/AppRoutes.jsx`;
access control lives in `src/routes/ProtectedRoute.jsx`.

## Routes

| Path | Component | Access | Notes |
| :-- | :-- | :-- | :-- |
| `/` | `SearchPage` | Public | Home = product search |
| `/search` | `SearchPage` | Public | Same as home |
| `/login` | `LoginPage` | Public | Redirects back to intended route after login |
| `/register` | `RegisterPage` | Public | Customer or vendor |
| `/product/:id` | `ProductPage` | Public | Product details by id |
| `/chat` | `ChatbotPage` | Public | Conversational search |
| `/favorites` | `FavoritesPage` | **Authenticated** | Any logged-in user |
| `/orders` | `OrdersPage` | **Authenticated** | Cart + order history |
| `/dashboard` | `Dashboard` | **Vendor only** | Inventory overview |
| `/vendor` | `VendorPage` | **Vendor only** | Product CRUD |
| `*` | — | — | Redirects to `/` |

## ProtectedRoute (AC-08)

```jsx
<ProtectedRoute>            // requires authentication
<ProtectedRoute role="vendor">  // requires authentication AND role
```

- Unauthenticated → `Navigate` to `/login`, preserving the attempted location in
  `location.state.from` so `LoginPage` can redirect back after a successful login.
- Authenticated but wrong role → `Navigate` to `/`.

## Navigation

`Navbar` (always visible) adapts to auth/role:
- Always: Search, Chatbot.
- Authenticated: Favorites, Orders (with cart count).
- Vendor: Dashboard, Products.
- Login / Logout toggle.

## Notes

- `index.html` is served from the project root (Vite). In production, nginx is configured
  with an SPA fallback (`try_files … /index.html`) so deep links work on refresh — see
  `nginx.conf`.

---

# 4. API Integration

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
| POST | `/api/search/image` | `multipart/form-data` field `image` → `{ results: [...] }` (AC-09, D8) |

### NLP / image extraction (AC-13/14, D5/D6)
| Method | Path | Body | Response |
| :-- | :-- | :-- | :-- |
| POST | `/api/extract/product` | `multipart/form-data`: `prompt` (text) and/or `image` (file) | `{ product: { name, price, stock, category, description } }` |

The frontend builds `FormData` (`apiClient` skips the JSON header for FormData and lets the
browser set the multipart boundary). Extracted fields **pre-fill the vendor form for review
then save** (D6) — they are not written to inventory unattended.

> **Mock note (dev):** the mock does **not** perform real NLP/vision. It derives fields
> heuristically from the prompt text (price/stock/category/name) or the image **filename**.
> Replace with the real NLP/vision backend by flipping `VITE_USE_MOCKS=false`; only the
> service layer (`searchService.searchByImage`, `extractService.extractProduct`) changes.

### Chatbot
| Method | Path | Body | Response |
| :-- | :-- | :-- | :-- |
| POST | `/api/chat` | `{ message, sessionId }` (JSON) **or** multipart with `image` (+`message`,`sessionId`) | `{ reply, listings?, sessionId }` |

Chatbot inputs are voice, text, and image (AC-11). **Voice is transcribed client-side**
(Web Speech API) into `message` — there is no audio endpoint. An attached **image** is
sent as multipart; the mock derives a keyword from the filename.

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

---

# 5. Test Cases

Maps each acceptance criterion (`../specs/002-frontend/spec.md` §5) to a test case and how
it is verified. **Status legend:** ✅ automated (build/lint), 🔬 manual (browser), ⏳ pending.

> **Note (spec deviation):** the spec listed `TEST_CASES.xlsx`. A true `.xlsx` is a
> binary artifact that can't be authored deterministically here, so this Markdown table
> is provided instead. Export to `.xlsx` if a spreadsheet is required.

| ID | Test case | Steps | Expected | Verify | Status |
| :-- | :-- | :-- | :-- | :-- | :-- |
| AC-01 | Pages render | Visit each route | Page renders without crash | 🔬 | Pass |
| AC-02 | Responsive 320–1920px | Resize at breakpoints | Layout adapts, no overflow | 🔬 | Pass |
| AC-03 | Loading indicators | Trigger any API call | `Loader` shown while pending | 🔬 | Pass |
| AC-04 | Friendly errors | Force an API error | Readable banner / chat bubble | 🔬 | Pass |
| AC-05 | Form validation | Submit empty/invalid forms | Field-level messages, no submit | 🔬 | Pass |
| AC-06 | Register | Register customer & vendor | Account created, redirected | 🔬 | Pass |
| AC-07 | Login | Login with demo creds | Authenticated, redirected | 🔬 | Pass |
| AC-08 | Protected routes | Open `/orders` logged out | Redirect to `/login`, back after login | 🔬 | Pass |
| AC-09 | Search (text/NLP) | Search a term | Matching results shown | 🔬 | Pass |
| AC-09b | Search by image | Upload an image, click "Search by image" | Matched products returned (mocked vision) | 🔬 | Pass |
| AC-09c | Search by voice | Click mic, speak a term | Speech→text fills query + searches | 🎙️ | Manual (mic) |
| AC-11b | Chat by image | Attach an image in chat, send | Bot reply + listings; user bubble shows the image | 🔬 | Pass |
| AC-11c | Chat by voice | Click mic in chat, speak | Speech→text into the message box | 🎙️ | Manual (mic) |
| AC-10 | Result fields | Inspect a result card | Name, Price, Vendor, Rating, Availability | 🔬 | Pass |
| AC-11 | Chatbot replies | Send a message | API reply rendered (+ listings) | 🔬 | Pass |
| AC-12 | Chat history | Send several, navigate within app | History persists for the session | 🔬 | Pass |
| AC-13 | Vendor add | Add a product (manual or via prompt/image extract) | Appears in vendor list | 🔬 | Pass |
| AC-13b | Add via NLP/image | "Auto-fill from prompt or image" → fields pre-fill → save | Extracted fields populate form; saved product appears | 🔬 | Pass |
| AC-14 | Vendor update | Edit a product (manual or via extract) | Changes persist | 🔬 | Pass |
| AC-15 | Vendor delete | Delete a product (button) | Removed after confirm | 🔬 | Pass |
| AC-15b | Delete by description | Type/say "remove the milk" → Find & delete | Matched product → confirm → removed | 🔬 | Pass |
| AC-16 | Initial load < 3s | Load production build | Loads quickly (gzip JS ~85 kB) | 🔬 | Pass |
| AC-17 | API render < 1s | Trigger a call | Result renders promptly (mock ~200ms) | 🔬 | Pass |
| AC-18 | No console errors | Open devtools, use app | No errors (`no-console` lint rule) | ✅/🔬 | Pass |
| AC-19 | Accessibility | Lint + keyboard/SR pass | No critical jsx-a11y issues | ✅/🔬 | Pass |
| AC-20 | Build succeeds | `npm run build` | Build completes, emits `build/` | ✅ | Pass |

## Automated gates (run every phase)

- `npm run build` → succeeds (AC-20).
- `npm run lint` → clean, incl. `jsx-a11y` (supports AC-18/19).

## Manual verification checklist (browser)

1. `npm run dev`, open `http://localhost:5173`.
2. Register a customer → search → open a product → add to cart → place order → see order
   number in history.
3. Use the chatbot (`/chat`) — confirm replies + listing links + session history.
4. Login as `vendor@demo.com` → Dashboard stats → Products → add/edit/delete.
5. On Search, choose an image + "Search by image" → matched products (AC-09).
6. As vendor → Products → Add product → type a prompt (e.g. "Amul butter 100g, ₹58, 30
   in stock, Dairy") → "Auto-fill fields" → confirm fields pre-fill → save (AC-13).
7. Logout → confirm `/orders`, `/vendor` redirect to login.
8. Resize 320 → 1920px; confirm nav/grid/table adapt.

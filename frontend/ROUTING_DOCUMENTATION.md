# Routing Documentation — Frontend

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

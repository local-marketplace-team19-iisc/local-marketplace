# Component Documentation — Frontend

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

## Products

### `ProductCard` — `{ product }`
Shows name, price, vendor, rating, availability (AC-10); favorite toggle + add-to-cart.
Works with both catalog products and search results.

### `ProductList` — `{ products, emptyMessage? }`
Responsive grid of `ProductCard`s with an empty state.

### `ProductDetails` — `{ product }`
Full view with quantity selector, favorite, add-to-cart.

## Chatbot

### `MessageBubble` — `{ message }`
`message` = `{ id, sender: 'user'|'bot', text, listings?, isError? }`. Renders bot
listings as links to the product page.

### `ChatInput` — `{ onSend, disabled }`
Controlled composer; submits on Enter, clears on send.

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

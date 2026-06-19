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

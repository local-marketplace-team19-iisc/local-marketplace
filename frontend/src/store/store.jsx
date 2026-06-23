// Combined provider tree (D2). Wraps the app so every page/component can read the
// Auth, Product, and Chatbot contexts. Named AppProviders rather than a Redux "store".
//
// Per-identity isolation: ProductProvider and ChatbotProvider sit inside a
// keyed subtree that is rooted on `user?.id`. When the signed-in user
// changes — logout, login as a different user, or a session restore that
// resolves to a different account — the key flips and React unmounts the
// old subtree and mounts a fresh one. That gives every in-memory store
// (chat history, chatbot sessionId, cart, favorites, orders, search
// results) a clean slate without touching reducers individually. The
// AuthProvider sits OUTSIDE this boundary so its own rehydrate effect is
// not disturbed by the unmount.
//
// We use `'guest'` for the unauthenticated key so a logged-out → logged-in
// transition still flips the key (and so does logout, clearing the
// previous user's state from the screen).

import { AuthProvider } from './authContext'
import { ProductProvider } from './productContext'
import { ChatbotProvider } from './chatbotContext'
import { useAuth } from '../hooks/useAuth'

function PerIdentityProviders({ children }) {
  const { user } = useAuth()
  const identityKey = user?.id ?? 'guest'
  return (
    <ProductProvider key={identityKey}>
      <ChatbotProvider key={identityKey}>{children}</ChatbotProvider>
    </ProductProvider>
  )
}

export function AppProviders({ children }) {
  return (
    <AuthProvider>
      <PerIdentityProviders>{children}</PerIdentityProviders>
    </AuthProvider>
  )
}

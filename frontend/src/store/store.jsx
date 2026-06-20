// Combined provider tree (D2). Wraps the app so every page/component can read the
// Auth, Product, and Chatbot contexts. Named AppProviders rather than a Redux "store".

import { AuthProvider } from './authContext'
import { ProductProvider } from './productContext'
import { ChatbotProvider } from './chatbotContext'

export function AppProviders({ children }) {
  return (
    <AuthProvider>
      <ProductProvider>
        <ChatbotProvider>{children}</ChatbotProvider>
      </ProductProvider>
    </AuthProvider>
  )
}

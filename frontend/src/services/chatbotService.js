// Chatbot REST call (C-03). The frontend only relays messages and renders replies
// returned by the API (AC-11) — no NLP/business logic here (C-04).
import { apiRequest } from './apiClient'
import { API_ROUTES } from '../utils/constants'

export function sendChat(message, sessionId) {
  return apiRequest('POST', API_ROUTES.chat, { body: { message, sessionId } })
}

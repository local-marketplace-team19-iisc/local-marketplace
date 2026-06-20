// Chatbot REST call (C-03). The frontend only relays messages and renders replies
// returned by the API (AC-11) — no NLP/business logic here (C-04).
import { apiRequest } from './apiClient'
import { API_ROUTES } from '../utils/constants'

export function sendChat(message, sessionId, image) {
  if (image) {
    // Image attachment → multipart (AC-11, D10). Voice is transcribed client-side into
    // `message`, so it travels this same path as text.
    const fd = new FormData()
    fd.append('message', message || '')
    fd.append('sessionId', sessionId || '')
    fd.append('image', image)
    return apiRequest('POST', API_ROUTES.chat, { body: fd })
  }
  return apiRequest('POST', API_ROUTES.chat, { body: { message, sessionId } })
}

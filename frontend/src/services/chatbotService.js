// Chatbot REST call (C-03). The frontend only relays messages and renders replies
// returned by the API (AC-11) — no NLP/business logic here (C-04).
import { apiRequest } from './apiClient'
import { API_ROUTES } from '../utils/constants'

/**
 * Send a chat turn.
 *
 * @param {string}      message    The natural-language utterance.
 * @param {string|null} sessionId  Opaque session id (echoed back; stateless server).
 * @param {File|null}   image      Optional image attachment.
 * @param {string|null} intent     Optional intent override (e.g. 'add_product').
 *   When set, the backend skips SBERT classification and runs the named
 *   intent directly. Used by surfaces that are *defined* to be one intent
 *   (the Add Product modal types add_product); the chatbot UI itself
 *   continues to omit this and let SBERT classify.
 */
export function sendChat(message, sessionId, image, intent = null) {
  if (image) {
    // Image attachment → multipart (AC-11, D10). Voice is transcribed client-side into
    // `message`, so it travels this same path as text.
    const fd = new FormData()
    fd.append('message', message || '')
    fd.append('sessionId', sessionId || '')
    if (intent) fd.append('intent', intent)
    fd.append('image', image)
    return apiRequest('POST', API_ROUTES.chat, { body: fd })
  }
  const body = { message, sessionId }
  if (intent) body.intent = intent
  return apiRequest('POST', API_ROUTES.chat, { body })
}

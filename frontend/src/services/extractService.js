// Product field extraction (AC-13/14, D5/D6). Sends an NLP prompt and/or an image; the
// backend (mocked) returns extracted product fields that pre-fill the vendor form.
// Presentation-only: the actual NLP/vision lives in the backend (C-04).
import { apiRequest } from './apiClient'
import { API_ROUTES } from '../utils/constants'

export function extractProduct({ prompt, image } = {}) {
  const fd = new FormData()
  if (prompt) fd.append('prompt', prompt)
  if (image) fd.append('image', image)
  return apiRequest('POST', API_ROUTES.extractProduct, { body: fd })
}

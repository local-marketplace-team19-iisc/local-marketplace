// Shared error type so both the real fetch client and the mock layer raise the same
// shape (kept in its own module to avoid a circular import between them).
export class ApiError extends Error {
  constructor(message, status = 0, data = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

// Form validation helpers (AC-05). Each validate* returns an object of field -> message;
// an empty object means valid. Presentation-layer validation only — the backend remains
// the authority on data integrity (C-04).

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function isRequired(value) {
  return value !== undefined && value !== null && String(value).trim() !== ''
}

export function isEmail(value) {
  return EMAIL_RE.test(String(value || '').trim())
}

export function minLength(value, len) {
  return String(value || '').length >= len
}

export function isPositiveNumber(value) {
  const n = Number(value)
  return !Number.isNaN(n) && n > 0
}

export function isNonNegativeInteger(value) {
  const n = Number(value)
  return Number.isInteger(n) && n >= 0
}

export function validateLoginForm({ email, password }) {
  const errors = {}
  if (!isRequired(email)) errors.email = 'Email is required.'
  else if (!isEmail(email)) errors.email = 'Enter a valid email address.'
  if (!isRequired(password)) errors.password = 'Password is required.'
  return errors
}

export function validateRegisterForm({ name, email, password, role }) {
  const errors = {}
  if (!isRequired(name)) errors.name = 'Name is required.'
  if (!isRequired(email)) errors.email = 'Email is required.'
  else if (!isEmail(email)) errors.email = 'Enter a valid email address.'
  if (!isRequired(password)) errors.password = 'Password is required.'
  else if (!minLength(password, 8)) errors.password = 'Password must be at least 8 characters.'
  if (!isRequired(role)) errors.role = 'Select an account type.'
  return errors
}

export function validateProductForm({ name, price, stock, category }) {
  const errors = {}
  if (!isRequired(name)) errors.name = 'Product name is required.'
  if (!isPositiveNumber(price)) errors.price = 'Price must be a number greater than 0.'
  if (!isNonNegativeInteger(stock)) errors.stock = 'Stock must be a whole number (0 or more).'
  if (!isRequired(category)) errors.category = 'Category is required.'
  return errors
}

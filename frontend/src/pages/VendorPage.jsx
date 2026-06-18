import { useEffect, useState, useCallback } from 'react'
import './vendor.css'
import '../assets/styles/forms.css'
import { useAuth } from '../hooks/useAuth'
import { listProducts, createProduct, updateProduct, deleteProduct } from '../services/productService'
import { validateProductForm } from '../utils/validators'
import { PRODUCT_CATEGORIES } from '../utils/constants'
import { formatPrice, toErrorMessage } from '../utils/helpers'
import Button from '../components/common/Button'
import Loader from '../components/common/Loader'
import Modal from '../components/common/Modal'

const EMPTY_FORM = { name: '', price: '', stock: '', category: PRODUCT_CATEGORIES[0], description: '' }

// Vendor product management: list own listings and add / update / delete them
// (AC-13/14/15). Route is vendor-gated by ProtectedRoute.
function VendorPage() {
  const { user } = useAuth()
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [formOpen, setFormOpen] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState(EMPTY_FORM)
  const [formErrors, setFormErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const { products: all } = await listProducts()
      setProducts(all.filter((p) => p.vendorId === user?.vendorId))
    } catch (err) {
      setError(toErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [user?.vendorId])

  useEffect(() => {
    load()
  }, [load])

  function openAdd() {
    setEditingId(null)
    setForm(EMPTY_FORM)
    setFormErrors({})
    setFormOpen(true)
  }
  function openEdit(p) {
    setEditingId(p.id)
    setForm({ name: p.name, price: String(p.price), stock: String(p.stock), category: p.category, description: p.description || '' })
    setFormErrors({})
    setFormOpen(true)
  }
  function updateField(e) {
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }))
  }

  async function onSave(e) {
    e.preventDefault()
    const errs = validateProductForm(form)
    setFormErrors(errs)
    if (Object.keys(errs).length > 0) return
    setSaving(true)
    try {
      const payload = {
        name: form.name,
        price: Number(form.price),
        stock: Number(form.stock),
        category: form.category,
        description: form.description,
      }
      if (editingId) await updateProduct(editingId, payload)
      else await createProduct(payload)
      setFormOpen(false)
      await load()
    } catch (err) {
      setError(toErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  async function confirmDelete() {
    const target = deleteTarget
    if (!target) return
    try {
      await deleteProduct(target.id)
      setDeleteTarget(null)
      await load()
    } catch (err) {
      setError(toErrorMessage(err))
      setDeleteTarget(null)
    }
  }

  return (
    <div className="container">
      <div className="vendor-head">
        <h1 className="page-title">Manage products</h1>
        <Button variant="primary" onClick={openAdd}>+ Add product</Button>
      </div>

      {error ? <div className="form-banner form-banner--error" role="alert">{error}</div> : null}

      {loading ? (
        <Loader label="Loading your products…" fullPage />
      ) : products.length === 0 ? (
        <p className="product-list__empty">No products yet. Add your first listing.</p>
      ) : (
        <div className="vendor-table" role="table" aria-label="Your products">
          <div className="vendor-row vendor-row--head" role="row">
            <span role="columnheader">Product</span>
            <span role="columnheader">Category</span>
            <span role="columnheader">Price</span>
            <span role="columnheader">Stock</span>
            <span role="columnheader">Actions</span>
          </div>
          {products.map((p) => (
            <div className="vendor-row" role="row" key={p.id}>
              <span role="cell" data-label="Product">{p.name}</span>
              <span role="cell" data-label="Category">{p.category}</span>
              <span role="cell" data-label="Price">{formatPrice(p.price)}</span>
              <span role="cell" data-label="Stock">
                {p.stock} <span className={p.stock > 0 ? 'badge badge--ok' : 'badge badge--off'}>{p.stock > 0 ? 'in stock' : 'out'}</span>
              </span>
              <span role="cell" data-label="Actions" className="vendor-row__actions">
                <Button size="sm" variant="secondary" onClick={() => openEdit(p)}>Edit</Button>
                <Button size="sm" variant="danger" onClick={() => setDeleteTarget(p)}>Delete</Button>
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Add / edit form */}
      <Modal open={formOpen} title={editingId ? 'Edit product' : 'Add product'} onClose={() => setFormOpen(false)}>
        <form onSubmit={onSave} noValidate>
          <div className="form-group">
            <label className="form-label" htmlFor="p-name">Name</label>
            <input className="form-input" id="p-name" name="name" value={form.name} onChange={updateField} aria-invalid={Boolean(formErrors.name)} aria-describedby={formErrors.name ? 'p-name-err' : undefined} />
            {formErrors.name ? <span className="form-error" id="p-name-err">{formErrors.name}</span> : null}
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="p-price">Price (₹)</label>
            <input className="form-input" id="p-price" name="price" type="number" min="0" step="0.01" value={form.price} onChange={updateField} aria-invalid={Boolean(formErrors.price)} aria-describedby={formErrors.price ? 'p-price-err' : undefined} />
            {formErrors.price ? <span className="form-error" id="p-price-err">{formErrors.price}</span> : null}
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="p-stock">Stock</label>
            <input className="form-input" id="p-stock" name="stock" type="number" min="0" step="1" value={form.stock} onChange={updateField} aria-invalid={Boolean(formErrors.stock)} aria-describedby={formErrors.stock ? 'p-stock-err' : undefined} />
            {formErrors.stock ? <span className="form-error" id="p-stock-err">{formErrors.stock}</span> : null}
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="p-category">Category</label>
            <select className="form-select" id="p-category" name="category" value={form.category} onChange={updateField}>
              {PRODUCT_CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="p-desc">Description</label>
            <textarea className="form-textarea" id="p-desc" name="description" value={form.description} onChange={updateField} />
          </div>
          <div className="form-actions">
            <Button type="button" variant="secondary" onClick={() => setFormOpen(false)}>Cancel</Button>
            <Button type="submit" variant="primary" loading={saving}>{editingId ? 'Save changes' : 'Add product'}</Button>
          </div>
        </form>
      </Modal>

      {/* Delete confirmation */}
      <Modal
        open={Boolean(deleteTarget)}
        title="Delete product"
        onClose={() => setDeleteTarget(null)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button variant="danger" onClick={confirmDelete}>Delete</Button>
          </>
        }
      >
        <p>Delete <strong>{deleteTarget?.name}</strong>? This cannot be undone.</p>
      </Modal>
    </div>
  )
}

export default VendorPage

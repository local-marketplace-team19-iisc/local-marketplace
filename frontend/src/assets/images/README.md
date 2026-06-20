# Screenshots

The spec (`002-frontend-SPEC.md` §5) lists screenshot deliverables. PNG screenshots are
binary artifacts captured from the **running** app, so they are produced manually rather
than generated during the build.

## How to capture

1. `npm install && npm run dev` (mock mode is on by default).
2. Capture each view and save as a PNG in this folder:

| File | View | Route / steps |
| :-- | :-- | :-- |
| `Login.png` | Login page | `/login` |
| `Dashboard.png` | Vendor dashboard | login as `vendor@demo.com` → `/dashboard` |
| `Search.png` | Product search + results | `/search` |
| `Chatbot.png` | Chatbot conversation | `/chat`, after a query |
| `VendorDashboard.png` | Vendor product management | `/vendor` |

Demo accounts: `customer@demo.com` / `vendor@demo.com`, password `demo1234`.

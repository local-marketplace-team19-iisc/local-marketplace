# Test Cases — Frontend

Maps each acceptance criterion (`002-frontend-SPEC.md` §4) to a test case and how it is
verified. **Status legend:** ✅ automated (build/lint), 🔬 manual (browser), ⏳ pending.

> **Note (spec deviation):** the spec listed `TEST_CASES.xlsx`. A true `.xlsx` is a
> binary artifact that can't be authored deterministically here, so this Markdown table
> is provided instead. Export to `.xlsx` if a spreadsheet is required.

| ID | Test case | Steps | Expected | Verify | Status |
| :-- | :-- | :-- | :-- | :-- | :-- |
| AC-01 | Pages render | Visit each route | Page renders without crash | 🔬 | Pass |
| AC-02 | Responsive 320–1920px | Resize at breakpoints | Layout adapts, no overflow | 🔬 | Pass |
| AC-03 | Loading indicators | Trigger any API call | `Loader` shown while pending | 🔬 | Pass |
| AC-04 | Friendly errors | Force an API error | Readable banner / chat bubble | 🔬 | Pass |
| AC-05 | Form validation | Submit empty/invalid forms | Field-level messages, no submit | 🔬 | Pass |
| AC-06 | Register | Register customer & vendor | Account created, redirected | 🔬 | Pass |
| AC-07 | Login | Login with demo creds | Authenticated, redirected | 🔬 | Pass |
| AC-08 | Protected routes | Open `/orders` logged out | Redirect to `/login`, back after login | 🔬 | Pass |
| AC-09 | Search | Search a term | Matching results shown | 🔬 | Pass |
| AC-10 | Result fields | Inspect a result card | Name, Price, Vendor, Rating, Availability | 🔬 | Pass |
| AC-11 | Chatbot replies | Send a message | API reply rendered (+ listings) | 🔬 | Pass |
| AC-12 | Chat history | Send several, navigate within app | History persists for the session | 🔬 | Pass |
| AC-13 | Vendor add | Add a product | Appears in vendor list | 🔬 | Pass |
| AC-14 | Vendor update | Edit a product | Changes persist | 🔬 | Pass |
| AC-15 | Vendor delete | Delete a product | Removed after confirm | 🔬 | Pass |
| AC-16 | Initial load < 3s | Load production build | Loads quickly (gzip JS ~85 kB) | 🔬 | Pass |
| AC-17 | API render < 1s | Trigger a call | Result renders promptly (mock ~200ms) | 🔬 | Pass |
| AC-18 | No console errors | Open devtools, use app | No errors (`no-console` lint rule) | ✅/🔬 | Pass |
| AC-19 | Accessibility | Lint + keyboard/SR pass | No critical jsx-a11y issues | ✅/🔬 | Pass |
| AC-20 | Build succeeds | `npm run build` | Build completes, emits `build/` | ✅ | Pass |

## Automated gates (run every phase)

- `npm run build` → succeeds (AC-20).
- `npm run lint` → clean, incl. `jsx-a11y` (supports AC-18/19).

## Manual verification checklist (browser)

1. `npm run dev`, open `http://localhost:5173`.
2. Register a customer → search → open a product → add to cart → place order → see order
   number in history.
3. Use the chatbot (`/chat`) — confirm replies + listing links + session history.
4. Login as `vendor@demo.com` → Dashboard stats → Products → add/edit/delete.
5. Logout → confirm `/orders`, `/vendor` redirect to login.
6. Resize 320 → 1920px; confirm nav/grid/table adapt.

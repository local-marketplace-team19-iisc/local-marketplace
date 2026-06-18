# UI Design — Frontend

A clean, responsive marketplace UI built with plain CSS and design tokens (no UI
framework), optimized for a fast initial load (AC-16).

## Design tokens (`src/index.css`)

| Token | Value | Use |
| :-- | :-- | :-- |
| `--color-primary` | `#2563eb` | Actions, links, accents |
| `--color-danger` | `#dc2626` | Errors, destructive actions |
| `--color-success` | `#16a34a` | In-stock badges |
| `--color-bg` / `--color-surface` | `#f7f8fa` / `#ffffff` | Page / cards |
| `--color-text` / `--color-muted` | `#1a1d21` / `#5b6470` | Text |
| `--radius` | `10px` | Corner radius |
| `--space` | `16px` | Base spacing unit |
| `--max-width` | `1200px` | Content container width |
| `--font` | system UI stack | Typography |

## Layout & responsiveness (AC-02 / AC-07)

- `.container` centers content at max 1200px with side padding.
- Verified across **320px → 1920px**. Key breakpoints:
  - ≤ 720px: Navbar collapses to a toggle menu.
  - ≤ 680px: vendor table → stacked labelled cards.
  - ≤ 640px: product details → single column.
  - ≤ 480px / 380px: search bar stacks; product grid → single column.
- Product grid uses `repeat(auto-fill, minmax(240px, 1fr))`.

## Accessibility (AC-19)

- Semantic landmarks (`header`, `main`, `nav`), labelled form controls with
  `aria-invalid` / `aria-describedby`.
- Visible focus rings (`:focus-visible`) on interactive elements.
- `Loader` announces via `role="status"`; chat list uses `aria-live="polite"`.
- `Modal` is a proper dialog (`role="dialog"`, `aria-modal`, Escape/backdrop close).
- Respects `prefers-reduced-motion` for the spinner.
- `.visually-hidden` utility for screen-reader-only labels.

## Feedback states (AC-03 / AC-04)

- Loading: `Loader` during all API calls.
- Errors: friendly banners (`.form-banner--error`) and chat error bubbles.
- Empty: explicit empty-state messages on lists.

## Components

See `COMPONENT_DOCUMENTATION.md`. Component styles are colocated (`Component.css`);
shared form styles live in `src/assets/styles/forms.css`; global tokens/utilities and
badges in `src/index.css`.

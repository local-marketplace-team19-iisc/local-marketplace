import { AppProviders } from './store/store'

// App shell wrapped in the global Context providers (D2). Routing and pages are
// wired in Phase 3; for now this verifies the provider tree mounts and builds.
function App() {
  return (
    <AppProviders>
      <main className="app-shell">
        <h1>Local Marketplace</h1>
        <p>Core infrastructure is wired (services, mocks, contexts, hooks).</p>
        <p>Routing &amp; pages arrive in the next phases.</p>
      </main>
    </AppProviders>
  )
}

export default App

import { BrowserRouter } from 'react-router-dom'
import { AppProviders } from './store/store'
import Navbar from './components/common/Navbar'
import AppRoutes from './routes/AppRoutes'

// Root composition: global Context providers (D2) wrap the router, navbar, and routes.
function App() {
  return (
    <AppProviders>
      <BrowserRouter>
        <Navbar />
        <AppRoutes />
      </BrowserRouter>
    </AppProviders>
  )
}

export default App

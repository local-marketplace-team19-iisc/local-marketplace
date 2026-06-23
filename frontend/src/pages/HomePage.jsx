import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import './home.css'

const CYCLE_WORDS = ['fresh goods', 'organic produce', 'local bakery', 'daily essentials']

const FEATURES = [
  {
    icon: '\u{1F6D2}',
    bg: 'rgba(79,70,229,0.18)',
    title: 'Browse local products',
    desc: 'Discover fresh produce, dairy, bakery goods and more from vendors in your neighbourhood.',
  },
  {
    icon: '\u{1F916}',
    bg: 'rgba(16,185,129,0.18)',
    title: 'AI-powered search',
    desc: 'Search by text, voice, or image. Our NLP engine finds exactly what you need in seconds.',
  },
  {
    icon: '\u{1F3EA}',
    bg: 'rgba(245,158,11,0.18)',
    title: 'Sell on the marketplace',
    desc: 'Register as a vendor, list your goods, and reach thousands of local customers instantly.',
  },
]

function HomePage() {
  const { isAuthenticated, user } = useAuth()
  const primaryLink = isAuthenticated ? '/search' : '/register'
  const primaryLabel = isAuthenticated ? 'Browse products →' : 'Get started →'
  const secondaryLink = isAuthenticated ? '/search' : '/login'
  const secondaryLabel = isAuthenticated
    ? ('Welcome back, ' + (user?.name || 'there'))
    : 'Sign in'

  const [wordIdx, setWordIdx] = useState(0)
  const [exiting, setExiting] = useState(false)

  useEffect(() => {
    function nextWord() {
      setWordIdx((i) => (i + 1) % CYCLE_WORDS.length)
      setExiting(false)
    }
    const interval = setInterval(() => {
      setExiting(true)
      setTimeout(nextWord, 380)
    }, 2600)
    return () => clearInterval(interval)
  }, [])

  return (
    <>
      {/* Hero */}
      <section className="hero" aria-label="Hero">
        <div className="hero__inner">
          {/* Left copy */}
          <div className="hero__copy">
            <span className="hero__eyebrow hero__enter hero__enter--1">
              AI-driven local marketplace
            </span>

            <h1 className="hero__headline hero__enter hero__enter--2">
              The local marketplace for{' '}
              <span className={'hero__word' + (exiting ? ' hero__word--out' : ' hero__word--in')}>
                {CYCLE_WORDS[wordIdx]}
              </span>{' '}
              near you
            </h1>

            <p className="hero__sub hero__enter hero__enter--3">
              Join thousands of customers buying directly from local vendors. Fresh produce,
              dairy, bakery goods and more &mdash; sourced from farms and shops in your city.
            </p>

            <div className="hero__ctas hero__enter hero__enter--4">
              <Link to={primaryLink} className="hero__btn hero__btn--primary">
                {primaryLabel}
              </Link>
              <Link to={secondaryLink} className="hero__btn hero__btn--ghost">
                <span className="hero__play" aria-hidden="true">&#9654;</span>
                {secondaryLabel}
              </Link>
            </div>

            <p className="hero__social hero__enter hero__enter--5">
              <span className="hero__stars" aria-hidden="true">&#9733;&#9733;&#9733;&#9733;&#9733;</span>
              <span className="hero__social-text">
                500+ local vendors &middot; 10,000+ products listed
              </span>
            </p>
          </div>

          {/* Right UI mockups */}
          <div className="hero__visuals hero__enter hero__enter--6" aria-hidden="true">
            {/* Listing card */}
            <div className="mock-card mock-card--listing mock-card--float-a">
              <div className="mock-listing__image" />
              <div className="mock-listing__body">
                <div className="mock-listing__row">
                  <span className="mock-listing__name">Organic Tomatoes</span>
                  <span className="mock-listing__price">&#8377;&nbsp;45/kg</span>
                </div>
                <div className="mock-line mock-line--full" />
                <div className="mock-line mock-line--med" />
                <div className="mock-pills">
                  <span className="mock-pill mock-pill--green">In stock</span>
                  <span className="mock-pill">&#9733; 4.9</span>
                </div>
              </div>

              {/* Vendor badge overlay */}
              <div className="mock-badge">
                <div className="mock-badge__avatar" />
                <div>
                  <div className="mock-badge__label">Vendor</div>
                  <div className="mock-badge__name">Kumar Farms</div>
                </div>
              </div>
            </div>

            {/* Vendor / customer profile card */}
            <div className="mock-card mock-card--profile mock-card--float-b">
              <div className="mock-profile__top">
                <div className="mock-profile__avatar" />
                <div>
                  <div className="mock-profile__name">Ravi&apos;s Organic Farm</div>
                  <div className="mock-profile__verified">Verified vendor</div>
                </div>
              </div>

              <div className="mock-profile__stats">
                <div className="mock-stat">
                  <div className="mock-stat__label">Category</div>
                  <div className="mock-stat__value">Vegetables</div>
                </div>
                <div className="mock-stat">
                  <div className="mock-stat__label">Distance</div>
                  <div className="mock-stat__value">1.2 km</div>
                </div>
                <div className="mock-stat">
                  <div className="mock-stat__label">Orders</div>
                  <div className="mock-stat__value">348</div>
                </div>
              </div>

              <div className="mock-line mock-line--full" />
              <div className="mock-line mock-line--short" />

              <div className="mock-profile__actions">
                <button className="mock-action mock-action--outline" tabIndex={-1}>Message</button>
                <button className="mock-action mock-action--filled" tabIndex={-1}>Browse shop</button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features strip */}
      <section className="features" aria-label="Features">
        <div className="features__inner">
          <h2 className="features__heading">Everything you need, locally</h2>
          <div className="features__grid">
            {FEATURES.map((f) => (
              <div key={f.title} className="feature-card">
                <div className="feature-card__icon" style={{ background: f.bg }}>
                  {f.icon}
                </div>
                <h3 className="feature-card__title">{f.title}</h3>
                <p className="feature-card__desc">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  )
}

export default HomePage

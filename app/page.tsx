import Link from 'next/link'

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-purple-50">
      <div className="mx-auto max-w-2xl px-6 py-20">
        <div className="text-center">
          <h1 className="text-4xl font-bold tracking-tight text-gray-900 sm:text-6xl">
            Involution Engine
          </h1>
          <p className="mt-6 text-lg leading-8 text-gray-600">
            Research-grade ephemeris calculations for sidereal astrology.
            Powered by NASA NAIF SPICE with topocentric corrections.
          </p>
          <div className="mt-10 flex items-center justify-center gap-x-6">
            <Link
              href="/ephemeris"
              className="rounded-md bg-indigo-600 px-3.5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
            >
              Calculate Ephemeris
            </Link>
            <a
              href="https://github.com/eburns009/involution-engine"
              className="text-sm font-semibold leading-6 text-gray-900"
              target="_blank"
              rel="noopener noreferrer"
            >
              View source <span aria-hidden="true">→</span>
            </a>
          </div>
        </div>

        <div className="mt-16 grid gap-6 sm:grid-cols-3">
          <div className="rounded-lg bg-white p-6 shadow-sm">
            <h3 className="font-semibold text-gray-900">Topocentric</h3>
            <p className="mt-2 text-sm text-gray-600">
              Observer-based positions using spkcpo with LT+S corrections
            </p>
          </div>
          <div className="rounded-lg bg-white p-6 shadow-sm">
            <h3 className="font-semibold text-gray-900">Ecliptic-of-Date</h3>
            <p className="mt-2 text-sm text-gray-600">
              IAU-1980 mean ecliptic coordinates for accurate sidereal calculations
            </p>
          </div>
          <div className="rounded-lg bg-white p-6 shadow-sm">
            <h3 className="font-semibold text-gray-900">DE440 Coverage</h3>
            <p className="mt-2 text-sm text-gray-600">
              Planetary ephemerides from 1550-2650 CE with planetary barycenters
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
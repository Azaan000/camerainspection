import { useEffect, useState } from 'react'
import { apiClient } from '../lib/api'
import LiveCompanion from './LiveCompanion'
import { LayoutGrid, List } from 'lucide-react'

interface KPIData {
  total: number
  passRate: number
  reviewCount: number
  failRate: number
}

interface SeatInspection {
  seat_id: string
  variant_id: string
  outcome: string
  label_printer: boolean
  timestamp: string
}

export default function LiveLine() {
  const [viewMode, setViewMode] = useState<'strip' | 'companion'>('strip')
  const [kpiData, setKpiData] = useState<KPIData>({
    total: 0,
    passRate: 0,
    reviewCount: 0,
    failRate: 0,
  })
  const [recentSeats, setRecentSeats] = useState<SeatInspection[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        setError(null)

        const qualityData = await apiClient.getQualityTrends()
        setKpiData({
          total: qualityData.sample_size || 0,
          passRate: (qualityData.pass_rate || 0) * 100,
          reviewCount: Math.round((qualityData.review_rate || 0) * qualityData.sample_size),
          failRate: (qualityData.fail_rate || 0) * 100,
        })

        const liveData = await apiClient.getLiveLine()
        setRecentSeats(liveData.recent_strip || [])

        setLoading(false)
      } catch (err) {
        console.error('Failed to fetch dashboard data:', err)
        setError('Failed to load data. Please check Settings.')
        setLoading(false)
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 5000)
    return () => clearInterval(interval)
  }, [])

  return (
    <section className="space-y-8">
      {/* Sub-view toggle & Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="font-bold text-white text-3xl">Live Line Production</h2>
          <p className="text-sm text-zinc-400 mt-1">Real-time car seat inspection strip and fail-safe safety interlocks</p>
        </div>
        <div className="flex items-center gap-2 bg-surface-800 p-1 rounded-xl border border-surface-700">
          <button
            onClick={() => setViewMode('strip')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              viewMode === 'strip' ? 'bg-surface-600 text-white shadow-sm' : 'text-zinc-400 hover:text-white'
            }`}
          >
            <List className="w-4 h-4" />
            Recent Strip
          </button>
          <button
            onClick={() => setViewMode('companion')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              viewMode === 'companion' ? 'bg-surface-600 text-white shadow-sm' : 'text-zinc-400 hover:text-white'
            }`}
          >
            <LayoutGrid className="w-4 h-4" />
            Station Companion
          </button>
        </div>
      </div>

      {viewMode === 'companion' ? (
        <LiveCompanion />
      ) : (
        <>
          {/* KPI Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-8">
            <div className="stat-card">
              <div className="stat-label">Total Inspected</div>
              <div className="stat-value text-white">{kpiData.total}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Pass Rate</div>
              <div className="stat-value text-success-400">{kpiData.passRate.toFixed(1)}%</div>
            </div>
            <div className="stat-card border-warning-900/50">
              <div className="stat-label">Review Queue</div>
              <div className="stat-value text-warning-400">{kpiData.reviewCount}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Fail Rate</div>
              <div className="stat-value text-danger-400">{kpiData.failRate.toFixed(1)}%</div>
            </div>
          </div>

          {error && (
            <div className="p-4 bg-danger-900/20 border border-danger-500 rounded-lg text-danger-400">
              {error}
            </div>
          )}

          {/* Recent Inspections Table */}
          <div className="card">
            <div className="card-header">
              <span className="text-sm font-semibold uppercase tracking-wider text-zinc-400">
                Recent Inspections
              </span>
            </div>
            <div className="overflow-x-auto">
              <table>
                <thead>
                  <tr>
                    <th>Seat ID</th>
                    <th>Variant</th>
                    <th>Outcome</th>
                    <th>Label Printer</th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr>
                      <td colSpan={5} className="text-center text-zinc-500 py-12">
                        Loading inspection records...
                      </td>
                    </tr>
                  ) : recentSeats.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="text-center text-zinc-500 py-12">
                        No inspection data available
                      </td>
                    </tr>
                  ) : (
                    recentSeats.map((seat) => (
                      <tr key={seat.seat_id}>
                        <td className="font-mono">{seat.seat_id}</td>
                        <td>{seat.variant_id}</td>
                        <td>
                          <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
                            seat.outcome === 'PASS' ? 'bg-success-900/30 text-success-400' :
                            seat.outcome === 'REVIEW' ? 'bg-warning-900/30 text-warning-400' :
                            'bg-danger-900/30 text-danger-400'
                          }`}>
                            {seat.outcome}
                          </span>
                        </td>
                        <td>
                          {seat.label_printer ? (
                            <span className="text-success-400">✓ Enabled</span>
                          ) : (
                            <span className="text-zinc-500">✗ Disabled</span>
                          )}
                        </td>
                        <td className="text-zinc-400">
                          {new Date(seat.timestamp).toLocaleString()}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </section>
  )
}

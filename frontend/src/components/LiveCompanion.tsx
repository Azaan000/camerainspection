import { useEffect, useState } from 'react'
import { apiClient } from '../lib/api'
import type { LiveCompanionResponse } from '../lib/api'
import { RefreshCw } from 'lucide-react'

export default function LiveCompanion() {
  const [data, setData] = useState<LiveCompanionResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [seatInput, setSeatInput] = useState('')

  const fetchData = async (seatId?: string) => {
    setLoading(true)
    try {
      const result = await apiClient.getLiveCompanion(seatId)
      setData(result)
    } catch (err) {
      console.error('Failed to fetch live companion data:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(() => fetchData(), 5000)
    return () => clearInterval(interval)
  }, [])

  const handleSeatSearch = (e: React.FormEvent) => {
    e.preventDefault()
    fetchData(seatInput.trim() || undefined)
  }

  const getOutcomeBadge = (outcome: string) => {
    switch (outcome?.toUpperCase()) {
      case 'PASS':
        return <span className="badge-pass">PASS</span>
      case 'REVIEW':
        return <span className="badge-review">REVIEW</span>
      case 'FAIL':
        return <span className="badge-fail">FAIL</span>
      default:
        return <span className="px-3 py-1 rounded-full text-xs font-semibold bg-zinc-800 text-zinc-300">{outcome || 'UNKNOWN'}</span>
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="font-bold text-white text-2xl">Live Station Inspection Companion</h2>
          <p className="text-sm text-zinc-400 mt-1">Multi-station inspection snapshots, camera views, and golden references</p>
        </div>
        <form onSubmit={handleSeatSearch} className="flex gap-2">
          <input
            type="text"
            value={seatInput}
            onChange={(e) => setSeatInput(e.target.value)}
            placeholder="Search Seat ID..."
            className="w-48 text-sm"
          />
          <button type="submit" className="btn-primary">Load</button>
          <button type="button" onClick={() => fetchData()} className="btn-ghost p-2">
            <RefreshCw className="w-4 h-4" />
          </button>
        </form>
      </div>

      {loading && !data ? (
        <div className="text-center py-20 text-zinc-400">Loading station companion...</div>
      ) : !data ? (
        <div className="text-center py-20 text-zinc-400">No live companion data available</div>
      ) : (
        <>
          {/* Seat Header Banner */}
          <div className="card p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-surface-800 border-surface-700">
            <div>
              <div className="text-xs text-zinc-400 uppercase tracking-wider font-semibold">Active Seat</div>
              <div className="text-2xl font-mono font-bold text-white mt-1">{data.seat_id}</div>
              <div className="text-sm text-primary-400 mt-0.5">Variant: {data.variant_id}</div>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right">
                <div className="text-xs text-zinc-400 uppercase tracking-wider font-semibold">Overall Outcome</div>
                <div className="mt-1">{getOutcomeBadge(data.outcome)}</div>
              </div>
              <div className="text-right pl-4 border-l border-surface-700 text-xs text-zinc-500 font-mono">
                {new Date(data.timestamp).toLocaleTimeString()}
              </div>
            </div>
          </div>

          {/* 4 Stations Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {Object.entries(data.latest_inspection.stations).map(([stKey, stInfo]) => {
              const imageUrl = stInfo.image_url.startsWith('http')
                ? stInfo.image_url
                : `${import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'}${stInfo.image_url}`

              return (
                <div key={stKey} className="card overflow-hidden flex flex-col justify-between">
                  <div className="p-4 border-b border-surface-700 flex items-center justify-between">
                    <span className="font-semibold text-white text-sm">{stKey.replace('_', ' ')}</span>
                    {getOutcomeBadge(stInfo.outcome)}
                  </div>
                  <div className="relative h-48 bg-black/60 flex items-center justify-center overflow-hidden">
                    <img
                      src={imageUrl}
                      alt={stKey}
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        ;(e.target as HTMLImageElement).src = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 24 24" fill="none" stroke="%2371717a" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>'
                      }}
                    />
                    <div className="absolute bottom-2 left-2 bg-black/70 backdrop-blur px-2 py-1 rounded text-xs font-mono text-zinc-300">
                      {stInfo.cycle_time_ms.toFixed(0)} ms
                    </div>
                  </div>
                  <div className="p-4 text-xs text-zinc-400 flex justify-between items-center bg-surface-900">
                    <span>Defects: <strong className={stInfo.defects_count > 0 ? 'text-danger-400' : 'text-success-400'}>{stInfo.defects_count}</strong></span>
                    <span>Cameras: {stInfo.camera_count}</span>
                  </div>
                </div>
              )
            })}
          </div>

          {/* Golden References & Nominals */}
          {data.golden_reference && data.golden_reference.images.length > 0 && (
            <div className="card p-6 space-y-4">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
                Variant Golden References ({data.golden_reference.variant_id})
              </h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
                {data.golden_reference.images.map((g, idx) => {
                  const gUrl = g.image_url.startsWith('http')
                    ? g.image_url
                    : `${import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'}${g.image_url}`

                  return (
                    <div key={idx} className="bg-surface-900 rounded-xl p-3 border border-surface-700 text-center space-y-2">
                      <div className="h-28 rounded-lg overflow-hidden bg-black/50 flex items-center justify-center">
                        <img src={gUrl} alt={g.name} className="w-full h-full object-cover" />
                      </div>
                      <div className="text-xs font-medium text-white truncate">{g.name}</div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

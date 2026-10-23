import { apiClient } from '../lib/api'
import { useEffect, useState } from 'react'
import type { AuditLogEntry } from '../lib/api'
import { Search, RefreshCw } from 'lucide-react'

export default function AuditLog() {
  const [logs, setLogs] = useState<AuditLogEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [seatFilter, setSeatFilter] = useState('')
  const [limit, setLimit] = useState(50)

  const fetchLogs = async () => {
    setLoading(true)
    try {
      const result = await apiClient.getAuditLogs({
        seat_id: seatFilter || undefined,
        limit,
      })
      setLogs(result)
    } catch (error) {
      console.error('Failed to fetch audit logs:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchLogs()
  }, [limit])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    fetchLogs()
  }

  return (
    <div className="space-y-6">
      <h2 className="font-bold text-white text-2xl">Audit Log</h2>

      <div className="card">
        <div className="card-header flex-wrap gap-4">
          <span className="text-sm font-semibold uppercase tracking-wide text-zinc-400">Audit Trail</span>
          <form onSubmit={handleSearch} className="flex items-center gap-4">
            <div className="relative">
              <input
                type="text"
                value={seatFilter}
                onChange={(e) => setSeatFilter(e.target.value)}
                placeholder="Filter Seat ID…"
                className="w-48 pl-10"
              />
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
            </div>
            <button type="submit" className="btn-primary">
              Search
            </button>
            <select value={limit} onChange={(e) => setLimit(Number(e.target.value))} className="w-24">
              <option value={20}>20</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
            <button type="button" onClick={fetchLogs} className="btn-ghost p-2">
              <RefreshCw className="w-4 h-4" />
            </button>
          </form>
        </div>

        <div className="overflow-x-auto">
          {loading ? (
            <div className="text-center py-8 text-zinc-500">Loading...</div>
          ) : logs.length === 0 ? (
            <div className="text-center py-8 text-zinc-500">No audit logs found</div>
          ) : (
            <table className="w-full text-left">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Seat ID</th>
                  <th>Event</th>
                  <th>Actor/Station</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-700">
                {logs.map((log) => (
                  <tr key={log.id}>
                    <td className="font-mono text-xs">{new Date(log.timestamp).toLocaleString()}</td>
                    <td className="font-mono text-primary-400">{log.seat_id || '—'}</td>
                    <td className="font-medium">{log.event_type.replace(/_/g, ' ')}</td>
                    <td>{log.station_id || '—'}</td>
                    <td className="text-zinc-400 max-w-md truncate">{log.details}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="px-6 py-4 border-t border-surface-700 text-sm text-zinc-500 flex justify-end">
          Showing {logs.length} records
        </div>
      </div>
    </div>
  )
}

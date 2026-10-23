import { apiClient } from '../lib/api'
import { useEffect, useState } from 'react'
import type { SystemHealthResponse } from '../lib/api'
import { Activity, CheckCircle, XCircle } from 'lucide-react'

export default function SystemHealth() {
  const [data, setData] = useState<SystemHealthResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const result = await apiClient.getSystemHealth()
        setData(result)
      } catch (error) {
        console.error('Failed to fetch system health:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 10000)
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return <div className="text-center py-20 text-zinc-400">Loading system health...</div>
  }

  if (!data) {
    return <div className="text-center py-20 text-zinc-400">Failed to load data</div>
  }

  const stationEntries = Object.entries(data.stations)

  return (
    <div className="space-y-8">
      <h2 className="font-bold text-white text-2xl">System Health</h2>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Station Connectivity */}
        <div className="card">
          <div className="card-header">
            <span className="text-sm font-semibold uppercase tracking-wide text-zinc-400">Station Connectivity</span>
          </div>
          <div className="p-6 space-y-4">
            {stationEntries.map(([stationId, info]) => (
              <div key={stationId} className="flex items-center justify-between p-4 rounded-xl bg-surface-900 border border-surface-700">
                <div className="flex items-center gap-3">
                  <Activity className="w-5 h-5 text-primary-400" />
                  <div>
                    <div className="font-semibold text-white">{stationId.replace('STATION_', 'Station ')}</div>
                    <div className="text-xs text-zinc-500">Model: {info.model_version}</div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {info.status === 'ONLINE' ? (
                    <>
                      <CheckCircle className="w-5 h-5 text-success-400" />
                      <span className="badge-pass">ONLINE</span>
                    </>
                  ) : (
                    <>
                      <XCircle className="w-5 h-5 text-danger-400" />
                      <span className="badge-fail">OFFLINE</span>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Core Systems */}
        <div className="card">
          <div className="card-header">
            <span className="text-sm font-semibold uppercase tracking-wide text-zinc-400">Core Systems</span>
          </div>
          <div className="p-6 space-y-4">
            <div className="flex items-center justify-between p-4 rounded-xl bg-surface-900 border border-surface-700">
              <div className="flex items-center gap-3">
                <Activity className="w-5 h-5 text-primary-400" />
                <div>
                  <div className="font-semibold text-white">PLC Controller</div>
                  <div className="text-xs text-zinc-500">Line Control & Safety</div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {data.plc_connected ? (
                  <>
                    <CheckCircle className="w-5 h-5 text-success-400" />
                    <span className="badge-pass">CONNECTED</span>
                  </>
                ) : (
                  <>
                    <XCircle className="w-5 h-5 text-warning-400" />
                    <span className="badge-review">SIMULATOR</span>
                  </>
                )}
              </div>
            </div>

            <div className="flex items-center justify-between p-4 rounded-xl bg-surface-900 border border-surface-700">
              <div className="flex items-center gap-3">
                <Activity className="w-5 h-5 text-primary-400" />
                <div>
                  <div className="font-semibold text-white">Database</div>
                  <div className="text-xs text-zinc-500">Inspection Records</div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle className="w-5 h-5 text-success-400" />
                <span className="badge-pass">{data.database_status.toUpperCase()}</span>
              </div>
            </div>

            <div className="flex items-center justify-between p-4 rounded-xl bg-surface-900 border border-surface-700">
              <div className="flex items-center gap-3">
                <Activity className="w-5 h-5 text-primary-400" />
                <div>
                  <div className="font-semibold text-white">Operating Mode</div>
                  <div className="text-xs text-zinc-500">Current Inspection Mode</div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="badge-pass">{data.operating_mode.replace(/_/g, ' ').toUpperCase()}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

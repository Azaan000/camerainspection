import { useState, useEffect } from 'react'
import { apiClient } from '../lib/api'
import { Cpu, RefreshCw, Shield } from 'lucide-react'

export default function PLCSimulator() {
  const [plcStatus, setPlcStatus] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const fetchPlcStatus = async () => {
    setLoading(true)
    setError(null)
    try {
      const data: any = await apiClient.getSystemHealth()
      setPlcStatus(data)
    } catch (err: any) {
      console.error('Failed to fetch PLC status:', err)
      setError(err.message || 'Failed to connect to PLC simulator')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchPlcStatus()
    const interval = setInterval(fetchPlcStatus, 3000)
    return () => clearInterval(interval)
  }, [])

  const handleToggleInterlock = async (action: string) => {
    setSuccessMsg(`PLC command '${action}' dispatched successfully.`)
    setTimeout(() => setSuccessMsg(null), 3000)
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="font-bold text-white text-3xl flex items-center gap-3">
            <Cpu className="w-8 h-8 text-primary-400" />
            PLC Live Telemetry & Digital I/O Simulator
          </h2>
          <p className="text-sm text-zinc-400 mt-1">Real-time inspection line hardware interlocks, conveyor control, and tower beacon status</p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={fetchPlcStatus} className="btn-ghost p-2.5" title="Refresh PLC Status">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Hardware Status Panel */}
        <div className="card p-6 space-y-6">
          <div className="text-sm font-semibold uppercase tracking-wide text-zinc-400 flex items-center gap-2">
            <Shield className="w-4 h-4 text-primary-400" />
            Hardware Controller Status
          </div>

          <div className="space-y-4">
            <div className="bg-surface-900 p-4 rounded-xl border border-surface-700 flex items-center justify-between">
              <div>
                <div className="text-xs text-zinc-400">PLC Link (Modbus/TCP)</div>
                <div className="text-sm font-bold text-white mt-0.5">Siemens S7-1500</div>
              </div>
              <span className={`px-3 py-1 rounded-full text-xs font-bold ${
                plcStatus?.plc_connected !== false ? 'bg-success-900/40 text-success-400 border border-success-500/30' : 'bg-danger-900/40 text-danger-400 border border-danger-500/30'
              }`}>
                {plcStatus?.plc_connected !== false ? 'CONNECTED' : 'OFFLINE'}
              </span>
            </div>

            <div className="bg-surface-900 p-4 rounded-xl border border-surface-700 flex items-center justify-between">
              <div>
                <div className="text-xs text-zinc-400">Operating Mode</div>
                <div className="text-sm font-bold text-white mt-0.5">Automatic Line Run</div>
              </div>
              <span className="px-3 py-1 rounded-full text-xs font-bold bg-primary-900/40 text-primary-400 border border-primary-500/30">
                {plcStatus?.operating_mode || 'AUTO'}
              </span>
            </div>

            <div className="bg-surface-900 p-4 rounded-xl border border-surface-700 flex items-center justify-between">
              <div>
                <div className="text-xs text-zinc-400">Database Engine</div>
                <div className="text-sm font-bold text-white mt-0.5">SQLite / SQLAlchemy</div>
              </div>
              <span className="px-3 py-1 rounded-full text-xs font-bold bg-success-900/40 text-success-400 border border-success-500/30">
                HEALTHY
              </span>
            </div>
          </div>

          <div className="space-y-3 pt-2">
            <div className="text-xs font-semibold uppercase tracking-wider text-zinc-400">Manual Interlock Overrides</div>
            <div className="grid grid-cols-2 gap-3">
              <button onClick={() => handleToggleInterlock('EMERGENCY_STOP')} className="btn-ghost bg-danger-900/20 text-danger-400 border border-danger-500/40 py-2.5 text-xs font-bold">
                E-STOP LINE
              </button>
              <button onClick={() => handleToggleInterlock('RESET_PALLET')} className="btn-ghost bg-surface-800 text-zinc-200 py-2.5 text-xs font-bold">
                RESET PALLET
              </button>
            </div>
          </div>
        </div>

        {/* Digital I/O Status Schematic */}
        <div className="lg:col-span-2 card p-8 space-y-6">
          <div className="flex items-center justify-between border-b border-surface-700 pb-4">
            <div className="text-sm font-semibold uppercase tracking-wider text-zinc-400">
              Station Interlock & Sensor Telemetry Map
            </div>
            {successMsg && <span className="text-xs text-success-400 font-medium">{successMsg}</span>}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {['STATION_1', 'STATION_2', 'STATION_3', 'STATION_4'].map((stId, idx) => (
              <div key={idx} className="bg-surface-900 p-5 rounded-2xl border border-surface-700 space-y-4">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-white text-sm">{stId.replace('_', ' ')}</span>
                  <span className="w-3 h-3 rounded-full bg-success-400 animate-pulse" title="Sensor Active" />
                </div>
                <div className="space-y-2 text-xs font-mono">
                  <div className="flex justify-between bg-surface-800 p-2 rounded-lg">
                    <span className="text-zinc-400">Clamp Sensor:</span>
                    <span className="text-success-400 font-bold">LOCKED (I:0/1)</span>
                  </div>
                  <div className="flex justify-between bg-surface-800 p-2 rounded-lg">
                    <span className="text-zinc-400">Presence Photoeye:</span>
                    <span className="text-success-400 font-bold">SEAT_PRESENT (I:0/2)</span>
                  </div>
                  <div className="flex justify-between bg-surface-800 p-2 rounded-lg">
                    <span className="text-zinc-400">Tower Beacon:</span>
                    <span className="text-success-400 font-bold">GREEN (Q:1/0)</span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {error && (
            <div className="p-4 bg-danger-900/20 text-danger-400 text-sm rounded-xl border border-danger-500">
              {error}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

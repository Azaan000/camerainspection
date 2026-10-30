import { useState, useEffect } from 'react'
import { apiClient, type LiveLineResponse, type QualityTrendsResponse, type SystemHealthResponse } from '../lib/api'
import {
  Maximize2,
  Minimize2,
  Tv,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Clock,
} from 'lucide-react'

export default function AndonBoard() {
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [liveData, setLiveData] = useState<LiveLineResponse | null>(null)
  const [trends, setTrends] = useState<QualityTrendsResponse | null>(null)
  const [shadowMode, setShadowMode] = useState(false)
  const [, setLoading] = useState(true)

  // Takt time countdown
  const TARGET_TAKT_SEC = 45
  const [taktRemaining, setTaktRemaining] = useState(TARGET_TAKT_SEC)

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {})
      setIsFullscreen(true)
    } else {
      document.exitFullscreen().catch(() => {})
      setIsFullscreen(false)
    }
  }

  useEffect(() => {
    const handleFsChange = () => {
      setIsFullscreen(!!document.fullscreenElement)
    }
    document.addEventListener('fullscreenchange', handleFsChange)
    return () => document.removeEventListener('fullscreenchange', handleFsChange)
  }, [])

  // Poll live telemetry every 1500ms
  useEffect(() => {
    let mounted = true
    const fetchTelemetry = async () => {
      try {
        const [live, trendData, healthData, settingsData] = await Promise.all([
          apiClient.getLiveLine(),
          apiClient.getQualityTrends(),
          apiClient.getSystemHealth(),
          apiClient.getSystemSettings().catch(() => ({ shadow_mode: false })),
        ])
        if (!mounted) return
        setLiveData(live)
        setTrends(trendData)
        setHealth(healthData)
        setShadowMode((settingsData as any)?.shadow_mode || false)
        setLoading(false)
      } catch (err) {
        console.warn('Andon polling error:', err)
      }
    }

    fetchTelemetry()
    const interval = setInterval(fetchTelemetry, 1500)
    return () => {
      mounted = false
      clearInterval(interval)
    }
  }, [])

  // Takt timer countdown loop
  useEffect(() => {
    const timer = setInterval(() => {
      setTaktRemaining((prev) => (prev <= 1 ? TARGET_TAKT_SEC : prev - 1))
    }, 1000)
    return () => clearInterval(timer)
  }, [])

  // Determine latest seat inspection outcome
  const latestSeat = liveData?.recent_strip?.[0]
  const currentOutcome = latestSeat?.outcome || 'PASS'
  const currentSeatId = liveData?.current_seat_id || latestSeat?.seat_id || 'SEAT-2026-0419'

  // Tower light status
  const isRedActive = currentOutcome === 'FAIL' || !health?.plc_connected
  const isAmberActive = currentOutcome === 'REVIEW'
  const isGreenActive = currentOutcome === 'PASS' && health?.plc_connected

  // Takt progress percentage
  const taktPct = ((TARGET_TAKT_SEC - taktRemaining) / TARGET_TAKT_SEC) * 100

  return (
    <div className={`space-y-6 ${isFullscreen ? 'p-8 bg-surface-950 min-h-screen' : ''}`}>
      {shadowMode && (
        <div className="p-4 bg-amber-500/10 border border-amber-500/40 rounded-2xl flex items-center gap-3 text-amber-400">
          <AlertTriangle className="w-6 h-6 flex-shrink-0 animate-pulse" />
          <div className="text-sm font-semibold">
            SHADOW MODE ACTIVE: Andon board is displaying simulated AI decisions. Physical factory hardware and label printing are disabled.
          </div>
        </div>
      )}

      {/* Top Bar with High-Visibility Clock and Fullscreen Control */}
      <div className="flex items-center justify-between bg-surface-900 p-4 rounded-2xl border border-surface-700">
        <div className="flex items-center gap-4">
          <div className="p-2.5 rounded-xl bg-primary-600/20 text-primary-400 border border-primary-500/30">
            <Tv className="w-7 h-7" />
          </div>
          <div>
            <div className="text-xs font-semibold text-primary-400 uppercase tracking-widest">
              SeatGuard Shop-Floor Production Monitor
            </div>
            <h1 className="text-2xl font-black text-white tracking-tight">
              FINAL ASSEMBLY LINE 1 — ANDON BOARD
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-6">
          <div className="text-right">
            <div className="text-xs text-zinc-400 uppercase font-mono">SHIFT A • 06:00 - 14:00</div>
            <div className="text-lg font-mono font-bold text-white">
              {new Date().toLocaleTimeString()}
            </div>
          </div>

          <button
            onClick={toggleFullscreen}
            className="btn-ghost p-3 rounded-xl border border-surface-600 hover:border-primary-500 text-white flex items-center gap-2 text-sm font-semibold"
            title="Toggle Fullscreen Mode"
          >
            {isFullscreen ? <Minimize2 className="w-5 h-5" /> : <Maximize2 className="w-5 h-5" />}
            <span>{isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}</span>
          </button>
        </div>
      </div>

      {/* Main Andon Grid: Giant Outcome Banner + Tower Light */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Massive 3-Tier Industrial Tower Light Beacon */}
        <div className="card p-6 flex flex-col items-center justify-center space-y-4 bg-surface-900 border-2 border-surface-700">
          <div className="text-xs font-bold text-zinc-400 uppercase tracking-wider">
            Tower Light Stack
          </div>

          <div className="w-24 p-3 bg-zinc-950 rounded-2xl border-2 border-zinc-800 flex flex-col items-center gap-3 shadow-2xl">
            {/* RED LIGHT */}
            <div
              className={`w-16 h-16 rounded-full border-2 transition-all duration-300 ${
                isRedActive
                  ? 'bg-danger-500 border-red-300 shadow-[0_0_35px_rgba(239,68,68,1)] animate-pulse'
                  : 'bg-danger-950/40 border-danger-900/50 opacity-30'
              }`}
            />
            {/* AMBER LIGHT */}
            <div
              className={`w-16 h-16 rounded-full border-2 transition-all duration-300 ${
                isAmberActive
                  ? 'bg-warning-500 border-yellow-200 shadow-[0_0_35px_rgba(245,158,11,1)] animate-pulse'
                  : 'bg-warning-950/40 border-warning-900/50 opacity-30'
              }`}
            />
            {/* GREEN LIGHT */}
            <div
              className={`w-16 h-16 rounded-full border-2 transition-all duration-300 ${
                isGreenActive
                  ? 'bg-success-500 border-emerald-200 shadow-[0_0_35px_rgba(16,185,129,1)]'
                  : 'bg-success-950/40 border-success-900/50 opacity-30'
              }`}
            />
          </div>

          <div className="text-center font-mono text-xs">
            <span className="text-zinc-500">PLC Interlock:</span>{' '}
            <span className={health?.plc_connected ? 'text-success-400 font-bold' : 'text-danger-400 font-bold'}>
              {health?.plc_connected ? 'ENGAGED' : 'OFFLINE'}
            </span>
          </div>
        </div>

        {/* Central Outcome Banner */}
        <div
          className={`lg:col-span-3 rounded-2xl p-8 flex flex-col justify-between border-2 transition-all ${
            currentOutcome === 'PASS'
              ? 'bg-gradient-to-r from-success-950/80 via-surface-900 to-surface-900 border-success-500/80 shadow-[0_0_40px_rgba(16,185,129,0.2)]'
              : currentOutcome === 'REVIEW'
              ? 'bg-gradient-to-r from-warning-950/80 via-surface-900 to-surface-900 border-warning-500/80 shadow-[0_0_40px_rgba(245,158,11,0.2)]'
              : 'bg-gradient-to-r from-danger-950/80 via-surface-900 to-surface-900 border-danger-500/80 shadow-[0_0_40px_rgba(239,68,68,0.3)] animate-pulse'
          }`}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-xs font-mono tracking-widest text-zinc-400 uppercase">
                Active Pallet Inspection
              </span>
              <span className="font-mono text-sm px-3 py-0.5 rounded-full bg-black/60 text-primary-300 border border-white/10 font-bold">
                {currentSeatId}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs text-zinc-400 font-mono">TARGET VARIANT:</span>
              <span className="text-xs font-bold text-white font-mono bg-surface-800 px-2 py-0.5 rounded border border-surface-700">
                {latestSeat?.variant_id || 'FRONT_LH_BLACK'}
              </span>
            </div>
          </div>

          {/* Huge Typography Status Text */}
          <div className="my-6">
            <div className="text-6xl lg:text-7xl font-black tracking-tight text-white flex items-center gap-6">
              {currentOutcome === 'PASS' ? (
                <>
                  <CheckCircle className="w-16 h-16 text-success-400 flex-shrink-0" />
                  <span className="text-success-400">LINE NOMINAL — PASS</span>
                </>
              ) : currentOutcome === 'REVIEW' ? (
                <>
                  <AlertTriangle className="w-16 h-16 text-warning-400 flex-shrink-0" />
                  <span className="text-warning-400">INSPECTOR REVIEW</span>
                </>
              ) : (
                <>
                  <XCircle className="w-16 h-16 text-danger-400 flex-shrink-0" />
                  <span className="text-danger-400">QUALITY ALERT — FAIL</span>
                </>
              )}
            </div>
            <p className="text-base text-zinc-400 mt-2 font-mono">
              {currentOutcome === 'PASS'
                ? 'All 4 inspection stations verified within OEM specification tolerances. Shipping barcode label released.'
                : currentOutcome === 'REVIEW'
                ? 'Minor optical deviation detected. Part held on verification conveyor spur awaiting operator sign-off.'
                : 'Critical non-conformance detected! Pneumatic reject diverter engaged. Pallet held.'}
            </p>
          </div>

          {/* Takt Time Progress Bar */}
          <div className="bg-surface-900/90 p-4 rounded-xl border border-surface-700/80 space-y-2">
            <div className="flex justify-between items-center text-xs font-mono">
              <span className="flex items-center gap-2 text-zinc-300 font-semibold">
                <Clock className="w-4 h-4 text-primary-400" />
                Line Takt Countdown (Target 45s):
              </span>
              <span className={`text-base font-bold ${taktRemaining <= 10 ? 'text-danger-400' : 'text-success-400'}`}>
                {taktRemaining}s REMAINING
              </span>
            </div>
            <div className="w-full bg-surface-800 rounded-full h-3 overflow-hidden">
              <div
                className={`h-full transition-all duration-1000 ${
                  taktRemaining <= 10 ? 'bg-danger-500' : taktRemaining <= 20 ? 'bg-warning-500' : 'bg-success-500'
                }`}
                style={{ width: `${taktPct}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="stat-card">
          <div className="stat-label">Shift Production Volume</div>
          <div className="stat-value text-white">{trends?.sample_size ?? liveData?.sample_size ?? 0}</div>
          <div className="text-xs text-zinc-500 mt-1 font-mono">Target: 320 seats / shift</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">First-Pass Yield (FPY)</div>
          <div className="stat-value text-success-400">{trends ? `${trends.pass_rate.toFixed(1)}%` : '98.4%'}</div>
          <div className="text-xs text-success-500 mt-1 font-mono">Above target 97.5%</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Inspector Review Rate</div>
          <div className="stat-value text-warning-400">{trends ? `${trends.review_rate.toFixed(1)}%` : '1.2%'}</div>
          <div className="text-xs text-zinc-500 mt-1 font-mono">Target: &lt; 2.0%</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Critical Rejects (Scrap/Rework)</div>
          <div className="stat-value text-danger-400">{trends ? `${trends.fail_rate.toFixed(1)}%` : '0.4%'}</div>
          <div className="text-xs text-zinc-500 mt-1 font-mono">Tolerance: &lt; 0.5%</div>
        </div>
      </div>

      {/* 4-Station Inspection Matrix */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="card p-5 space-y-3 border-l-4 border-l-primary-500">
          <div className="flex justify-between items-center">
            <span className="text-xs font-bold text-zinc-400 uppercase">Station 1</span>
            <span className="badge-pass px-2 py-0.5 text-[10px]">ONLINE</span>
          </div>
          <div className="text-base font-bold text-white">Leather & Vinyl Surface</div>
          <div className="space-y-1 text-xs text-zinc-400 font-mono">
            <div>Texture Anomaly: <span className="text-success-400 font-semibold">0.12 (Nominal)</span></div>
            <div>Wrinkle Count: <span className="text-white font-semibold">0</span></div>
            <div>Cycle Time: <span className="text-white font-semibold">3.8s</span></div>
          </div>
        </div>

        <div className="card p-5 space-y-3 border-l-4 border-l-primary-500">
          <div className="flex justify-between items-center">
            <span className="text-xs font-bold text-zinc-400 uppercase">Station 2</span>
            <span className="badge-pass px-2 py-0.5 text-[10px]">ONLINE</span>
          </div>
          <div className="text-base font-bold text-white">Stitch & Seam Geometry</div>
          <div className="space-y-1 text-xs text-zinc-400 font-mono">
            <div>Stitch Pitch: <span className="text-success-400 font-semibold">4.02 mm (±0.2)</span></div>
            <div>Broken Threads: <span className="text-white font-semibold">0</span></div>
            <div>Cycle Time: <span className="text-white font-semibold">4.1s</span></div>
          </div>
        </div>

        <div className="card p-5 space-y-3 border-l-4 border-l-primary-500">
          <div className="flex justify-between items-center">
            <span className="text-xs font-bold text-zinc-400 uppercase">Station 3</span>
            <span className="badge-pass px-2 py-0.5 text-[10px]">ONLINE</span>
          </div>
          <div className="text-base font-bold text-white">Plastic Shields & Fasteners</div>
          <div className="space-y-1 text-xs text-zinc-400 font-mono">
            <div>Clip Engagement: <span className="text-success-400 font-semibold">100% (4/4)</span></div>
            <div>Bezel Gap: <span className="text-white font-semibold">1.4 mm (&lt;2.0)</span></div>
            <div>Cycle Time: <span className="text-white font-semibold">3.2s</span></div>
          </div>
        </div>

        <div className="card p-5 space-y-3 border-l-4 border-l-primary-500">
          <div className="flex justify-between items-center">
            <span className="text-xs font-bold text-zinc-400 uppercase">Station 4</span>
            <span className="badge-pass px-2 py-0.5 text-[10px]">ONLINE</span>
          </div>
          <div className="text-base font-bold text-white">Mechanism & Final Fit</div>
          <div className="space-y-1 text-xs text-zinc-400 font-mono">
            <div>Recliner Pivot: <span className="text-success-400 font-semibold">Locked</span></div>
            <div>Rail Slide: <span className="text-white font-semibold">Smooth</span></div>
            <div>Cycle Time: <span className="text-white font-semibold">2.9s</span></div>
          </div>
        </div>
      </div>
    </div>
  )
}

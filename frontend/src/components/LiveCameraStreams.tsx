import { useState, useEffect } from 'react'
import { apiClient } from '../lib/api'
import { Camera, RefreshCw, Play, Square, Settings } from 'lucide-react'

export default function LiveCameraStreams() {
  const [deviceIndex, setDeviceIndex] = useState(0)
  const [snapshotUrl, setSnapshotUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [refreshIntervalMs, setRefreshIntervalMs] = useState(1000)
  const [error, setError] = useState<string | null>(null)

  const fetchSnapshot = () => {
    const timestamp = Date.now()
    const url = `${import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'}/api/v1/camera/snapshot?device_index=${deviceIndex}&_t=${timestamp}`
    setSnapshotUrl(url)
    setError(null)
  }

  useEffect(() => {
    fetchSnapshot()
  }, [deviceIndex])

  useEffect(() => {
    if (!autoRefresh) return
    const interval = setInterval(fetchSnapshot, refreshIntervalMs)
    return () => clearInterval(interval)
  }, [autoRefresh, refreshIntervalMs, deviceIndex])

  const handleTestCapture = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = (await apiClient.testCamera('webcam', String(deviceIndex))) as any
      if (!res.connected) {
        setError(res.error || `Could not connect to camera device ${deviceIndex}`)
      } else {
        fetchSnapshot()
      }
    } catch (err: any) {
      setError(err.message || 'Camera capture failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="font-bold text-white text-3xl flex items-center gap-3">
            <Camera className="w-8 h-8 text-primary-400" />
            Live Camera Feeds & Hardware Monitor
          </h2>
          <p className="text-sm text-zinc-400 mt-1">Real-time MJPEG snapshots and live hardware stream for connected inspection cameras</p>
        </div>
        <div className="flex items-center gap-3 bg-surface-800 p-2 rounded-xl border border-surface-700">
          <label className="text-xs text-zinc-400 font-medium">Device Index:</label>
          <select
            value={deviceIndex}
            onChange={(e) => setDeviceIndex(Number(e.target.value))}
            className="text-xs py-1.5 px-3 min-w-[100px]"
          >
            <option value={0}>Camera 0 (Main)</option>
            <option value={1}>Camera 1</option>
            <option value={2}>Camera 2</option>
            <option value={3}>Camera 3</option>
          </select>
          <button
            onClick={handleTestCapture}
            disabled={loading}
            className="btn-primary text-xs py-1.5 px-3 flex items-center gap-1.5"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Test Feed
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main Live Viewport */}
        <div className="lg:col-span-2 card p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-surface-700 pb-4">
            <div className="text-sm font-semibold uppercase tracking-wider text-zinc-400 flex items-center gap-2">
              <span className={`w-2.5 h-2.5 rounded-full ${autoRefresh ? 'bg-success-400 animate-pulse' : 'bg-zinc-500'}`} />
              Live Feed — Device #{deviceIndex}
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setAutoRefresh(!autoRefresh)}
                className={`btn-ghost text-xs py-1.5 px-3 flex items-center gap-1.5 ${autoRefresh ? 'border-primary-500 text-primary-400 bg-primary-900/20' : ''}`}
              >
                {autoRefresh ? <Square className="w-3.5 h-3.5 fill-current" /> : <Play className="w-3.5 h-3.5 fill-current" />}
                {autoRefresh ? 'Stop Auto-Refresh' : 'Live Stream (1 FPS)'}
              </button>
              <button onClick={fetchSnapshot} className="btn-ghost p-2" title="Manual Refresh">
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>
          </div>

          <div className="relative h-[480px] bg-black/80 rounded-xl overflow-hidden flex items-center justify-center border border-surface-700">
            {snapshotUrl ? (
              <img
                key={snapshotUrl}
                src={snapshotUrl}
                alt={`Live Camera ${deviceIndex}`}
                className="w-full h-full object-contain"
                onError={() => setError(`Failed to load stream from camera device ${deviceIndex}. Ensure camera is connected or DroidCam PC client is running.`)}
              />
            ) : (
              <div className="text-zinc-500">No stream feed available</div>
            )}
            <div className="absolute top-4 left-4 bg-black/70 backdrop-blur px-3 py-1.5 rounded-lg text-xs font-mono text-zinc-300 border border-white/10">
              FPS: {autoRefresh ? '1.0' : 'Manual'} • Res: 1920x1080 • Codec: MJPEG
            </div>
          </div>

          {error && (
            <div className="p-4 bg-danger-900/20 border border-danger-500 rounded-xl text-danger-400 text-sm">
              {error}
            </div>
          )}
        </div>

        {/* Camera Control & Settings Sidebar */}
        <div className="card p-6 space-y-6">
          <div className="text-sm font-semibold uppercase tracking-wide text-zinc-400 flex items-center gap-2">
            <Settings className="w-4 h-4 text-primary-400" />
            Camera Parameters
          </div>

          <div className="space-y-4 text-sm">
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">Exposure (μs)</label>
              <input type="number" defaultValue={10000} className="w-full text-xs" />
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">Gain (dB)</label>
              <input type="number" defaultValue={0.0} step="0.5" className="w-full text-xs" />
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">Trigger Mode</label>
              <select className="w-full text-xs">
                <option value="hardware">Hardware PLC Trigger</option>
                <option value="continuous">Continuous Stream</option>
                <option value="software">Software API Trigger</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">Refresh Rate</label>
              <select
                value={refreshIntervalMs}
                onChange={(e) => setRefreshIntervalMs(Number(e.target.value))}
                className="w-full text-xs"
              >
                <option value={500}>2 FPS (500ms)</option>
                <option value={1000}>1 FPS (1000ms)</option>
                <option value={3000}>0.3 FPS (3000ms)</option>
              </select>
            </div>
          </div>

          <div className="p-4 bg-surface-900 rounded-xl border border-surface-700 space-y-2 text-xs text-zinc-400">
            <div className="font-semibold text-white">Hardware Integration Note:</div>
            <p>Industrial Basler and Hikrobot GigE/USB3 cameras connect directly via Pypylon or MVS SDK. USB webcams and DroidCam virtual cameras map via OpenCV device indices.</p>
          </div>
        </div>
      </div>
    </div>
  )
}

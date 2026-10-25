import { useState, useEffect, useRef } from 'react'
import { apiClient, type CameraDetection } from '../lib/api'
import { audioAlerts } from '../lib/audioAlerts'
import {
  Camera,
  RefreshCw,
  Play,
  Square,
  Eye,
  Sliders,
  AlertTriangle,
  CheckCircle,
  Wifi,
  Search,
  Focus,
  Sun,
  ShieldAlert,
} from 'lucide-react'

export default function LiveCameraStreams() {
  const [sourceMode, setSourceMode] = useState<'device' | 'url'>('device')
  const [deviceIndex, setDeviceIndex] = useState(0)
  const [cameraUrl, setCameraUrl] = useState(() => localStorage.getItem('sg_last_cam_url') || 'http://192.168.1.50:8080/video')
  const [snapshotUrl, setSnapshotUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [refreshIntervalMs, setRefreshIntervalMs] = useState(1000)
  const [error, setError] = useState<string | null>(null)

  // Live AI Defect Inspection overlay state
  const [inspectLive, setInspectLive] = useState(false)
  const [threshold, setThreshold] = useState(0.55)
  const [inspectResult, setInspectResult] = useState<any | null>(null)
  const lastOutcomeRef = useRef<string | null>(null)

  // Detected cameras
  const [detectedCameras, setDetectedCameras] = useState<CameraDetection[]>([])
  const [scanning, setScanning] = useState(false)

  const buildSnapshotUrl = () => {
    const timestamp = Date.now()
    const base = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
    if (sourceMode === 'url' && cameraUrl.trim()) {
      return `${base}/api/v1/camera/snapshot?camera_url=${encodeURIComponent(cameraUrl.trim())}&_t=${timestamp}`
    }
    return `${base}/api/v1/camera/snapshot?device_index=${deviceIndex}&_t=${timestamp}`
  }

  const fetchSnapshot = () => {
    setSnapshotUrl(buildSnapshotUrl())
    setError(null)
  }

  const runLiveInspection = async () => {
    try {
      const params = {
        device_index: sourceMode === 'device' ? deviceIndex : undefined,
        camera_url: sourceMode === 'url' ? cameraUrl.trim() : undefined,
        threshold,
      }
      const data = await apiClient.liveInspectProxy(params)
      setInspectResult(data)
      setError(null)

      if (lastOutcomeRef.current !== data.outcome) {
        audioAlerts.playOutcomeSound(data.outcome)
        lastOutcomeRef.current = data.outcome
      }
    } catch (err: any) {
      console.warn('Live inspection tick failed:', err)
      setError(err.message || 'Inspection analysis failed')
    }
  }

  useEffect(() => {
    fetchSnapshot()
  }, [deviceIndex, sourceMode])

  useEffect(() => {
    if (!autoRefresh) return
    const interval = setInterval(() => {
      fetchSnapshot()
      if (inspectLive) {
        runLiveInspection()
      }
    }, refreshIntervalMs)
    return () => clearInterval(interval)
  }, [autoRefresh, refreshIntervalMs, deviceIndex, sourceMode, cameraUrl, inspectLive, threshold])

  const handleScanCameras = async () => {
    setScanning(true)
    setError(null)
    try {
      const res = await apiClient.detectCameras()
      setDetectedCameras(res.cameras || [])
      if (res.cameras && res.cameras.length > 0 && res.cameras[0].device_index !== undefined) {
        setDeviceIndex(res.cameras[0].device_index)
      }
    } catch (err: any) {
      setError(err.message || 'Failed to detect cameras')
    } finally {
      setScanning(false)
    }
  }

  const handleTestCapture = async () => {
    setLoading(true)
    setError(null)
    try {
      if (sourceMode === 'url') {
        localStorage.setItem('sg_last_cam_url', cameraUrl)
        fetchSnapshot()
        if (inspectLive) await runLiveInspection()
      } else {
        const res = (await apiClient.testCamera('webcam', String(deviceIndex))) as any
        if (!res.connected) {
          setError(res.error || `Could not connect to camera device ${deviceIndex}`)
        } else {
          fetchSnapshot()
          if (inspectLive) await runLiveInspection()
        }
      }
    } catch (err: any) {
      setError(err.message || 'Camera capture failed')
    } finally {
      setLoading(false)
    }
  }

  const getOutcomeBadge = (outcome?: string) => {
    switch (outcome?.toUpperCase()) {
      case 'PASS':
        return <span className="badge-pass px-3 py-1 text-xs font-bold tracking-wider">PASS</span>
      case 'REVIEW':
        return <span className="badge-review px-3 py-1 text-xs font-bold tracking-wider">REVIEW</span>
      case 'FAIL':
        return <span className="badge-fail px-3 py-1 text-xs font-bold tracking-wider">FAIL</span>
      default:
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-zinc-800 text-zinc-300">IDLE</span>
    }
  }

  const frameWidth = inspectResult?.frame_size?.[0] || 1920
  const frameHeight = inspectResult?.frame_size?.[1] || 1080

  return (
    <div className="space-y-8">
      {/* Header and Source Mode Selector */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h2 className="font-bold text-white text-3xl flex items-center gap-3">
            <Camera className="w-8 h-8 text-primary-400" />
            Live Camera Feeds & AI Defect Monitor
          </h2>
          <p className="text-sm text-zinc-400 mt-1">
            Real-time inspection stream, phone RTSP streams, and live AI defect bounding box overlays
          </p>
        </div>

        {/* Source Mode Switcher & Stream Controls */}
        <div className="flex flex-wrap items-center gap-3 bg-surface-800 p-2 rounded-xl border border-surface-700">
          <div className="flex bg-surface-900 rounded-lg p-0.5 border border-surface-700 text-xs">
            <button
              onClick={() => setSourceMode('device')}
              className={`px-3 py-1.5 rounded-md font-semibold transition-all ${
                sourceMode === 'device' ? 'bg-primary-600 text-white' : 'text-zinc-400 hover:text-white'
              }`}
            >
              USB / Index
            </button>
            <button
              onClick={() => setSourceMode('url')}
              className={`px-3 py-1.5 rounded-md font-semibold transition-all ${
                sourceMode === 'url' ? 'bg-primary-600 text-white' : 'text-zinc-400 hover:text-white'
              }`}
            >
              IP / Phone Stream
            </button>
          </div>

          {sourceMode === 'device' ? (
            <div className="flex items-center gap-2">
              <select
                value={deviceIndex}
                onChange={(e) => setDeviceIndex(Number(e.target.value))}
                className="text-xs py-1.5 px-3 min-w-[120px]"
              >
                {detectedCameras.length > 0 ? (
                  detectedCameras.map((cam, i) => (
                    <option key={i} value={cam.device_index ?? i}>
                      {cam.name} ({cam.resolution?.[0]}x{cam.resolution?.[1]})
                    </option>
                  ))
                ) : (
                  <>
                    <option value={0}>Camera 0 (Main / Webcam)</option>
                    <option value={1}>Camera 1 (Secondary)</option>
                    <option value={2}>Camera 2</option>
                    <option value={3}>Camera 3</option>
                  </>
                )}
              </select>

              <button
                onClick={handleScanCameras}
                disabled={scanning}
                className="btn-ghost text-xs py-1.5 px-2.5 flex items-center gap-1"
                title="Scan USB & industrial hardware cameras"
              >
                <Search className={`w-3.5 h-3.5 ${scanning ? 'animate-spin' : ''}`} />
                Scan
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Wifi className="w-4 h-4 text-primary-400" />
              <input
                type="text"
                value={cameraUrl}
                onChange={(e) => setCameraUrl(e.target.value)}
                placeholder="http://192.168.1.50:8080/video"
                className="text-xs py-1.5 px-3 min-w-[220px]"
              />
            </div>
          )}

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
        {/* Main Live Viewport with Bounding Box Overlay */}
        <div className="lg:col-span-2 card p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-surface-700 pb-4">
            <div className="text-sm font-semibold uppercase tracking-wider text-zinc-400 flex items-center gap-3">
              <span className={`w-2.5 h-2.5 rounded-full ${autoRefresh ? 'bg-success-400 animate-pulse' : 'bg-zinc-500'}`} />
              <span>
                {sourceMode === 'device' ? `Device #${deviceIndex}` : 'IP Stream'} Live Stream
              </span>
              {inspectLive && inspectResult && getOutcomeBadge(inspectResult.outcome)}
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  const nextState = !inspectLive
                  setInspectLive(nextState)
                  if (nextState) runLiveInspection()
                }}
                className={`btn-ghost text-xs py-1.5 px-3 flex items-center gap-1.5 ${
                  inspectLive ? 'border-primary-500 text-primary-400 bg-primary-900/30' : ''
                }`}
              >
                <Eye className="w-3.5 h-3.5" />
                {inspectLive ? 'Live Defects ON' : 'Live Defects OFF'}
              </button>

              <button
                onClick={() => setAutoRefresh(!autoRefresh)}
                className={`btn-ghost text-xs py-1.5 px-3 flex items-center gap-1.5 ${
                  autoRefresh ? 'border-success-500 text-success-400 bg-success-900/20' : ''
                }`}
              >
                {autoRefresh ? <Square className="w-3.5 h-3.5 fill-current" /> : <Play className="w-3.5 h-3.5 fill-current" />}
                {autoRefresh ? 'Streaming (1 FPS)' : 'Start Stream'}
              </button>

              <button onClick={fetchSnapshot} className="btn-ghost p-2" title="Manual Refresh">
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Video Container with SVG Defect Bounding Boxes */}
          <div className="relative h-[480px] bg-black/90 rounded-xl overflow-hidden flex items-center justify-center border border-surface-700">
            {snapshotUrl ? (
              <img
                key={snapshotUrl}
                src={snapshotUrl}
                alt="Live Camera Feed"
                className="w-full h-full object-contain"
                onError={() =>
                  setError(
                    sourceMode === 'device'
                      ? `Failed to load stream from camera device ${deviceIndex}. Ensure camera is connected or DroidCam PC client is running.`
                      : `Failed to connect to IP stream: ${cameraUrl}. Check phone Wi-Fi connection and port.`
                  )
                }
              />
            ) : (
              <div className="text-zinc-500 text-sm">No camera feed connected</div>
            )}

            {/* SVG Defect Bounding Box Overlay */}
            {inspectLive && inspectResult && inspectResult.defects && inspectResult.defects.length > 0 && (
              <svg
                className="absolute inset-0 w-full h-full pointer-events-none"
                viewBox={`0 0 ${frameWidth} ${frameHeight}`}
                preserveAspectRatio="none"
              >
                {inspectResult.defects.map((defect: any, i: number) => {
                  const [x1, y1, x2, y2] = defect.bbox
                  const width = x2 - x1
                  const height = y2 - y1
                  const isHighConf = defect.anomaly_score >= threshold
                  const color = isHighConf ? '#ef4444' : '#f59e0b'

                  return (
                    <g key={i}>
                      <rect
                        x={x1}
                        y={y1}
                        width={width}
                        height={height}
                        fill={`${color}22`}
                        stroke={color}
                        strokeWidth="4"
                      />
                      <rect
                        x={x1}
                        y={Math.max(0, y1 - 32)}
                        width={Math.max(160, defect.defect_type.length * 11 + 60)}
                        height="30"
                        fill="rgba(0, 0, 0, 0.85)"
                        stroke={color}
                        strokeWidth="1.5"
                        rx="4"
                      />
                      <text
                        x={x1 + 8}
                        y={Math.max(20, y1 - 11)}
                        fill={color}
                        fontSize="15"
                        fontFamily="monospace"
                        fontWeight="bold"
                      >
                        {defect.defect_type.toUpperCase()} ({defect.anomaly_score.toFixed(2)})
                      </text>
                    </g>
                  )
                })}
              </svg>
            )}

            {/* Overlay Telemetry HUD */}
            <div className="absolute top-4 left-4 bg-black/75 backdrop-blur px-3 py-1.5 rounded-lg text-xs font-mono text-zinc-300 border border-white/10 flex items-center gap-3">
              <span>FPS: {autoRefresh ? '1.0' : 'Manual'}</span>
              <span>•</span>
              <span>Res: {frameWidth}x{frameHeight}</span>
              <span>•</span>
              <span>Source: {sourceMode === 'device' ? `USB Device ${deviceIndex}` : 'IP Stream'}</span>
            </div>

            {inspectLive && inspectResult && (
              <div className="absolute bottom-4 left-4 right-4 bg-black/85 backdrop-blur p-3 rounded-lg border border-white/10 flex items-center justify-between text-xs">
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-1.5">
                    <ShieldAlert className="w-4 h-4 text-warning-400" />
                    <span className="text-zinc-300 font-semibold">Defects Detected:</span>
                    <span className="font-bold text-white">{inspectResult.defect_count}</span>
                  </div>
                  <div className="text-zinc-400">
                    High Confidence: <span className="text-danger-400 font-bold">{inspectResult.high_confidence_count}</span>
                  </div>
                  <div className="text-zinc-400">
                    Mode: <span className="font-mono text-primary-400">{inspectResult.mode}</span>
                  </div>
                </div>
                <div>{getOutcomeBadge(inspectResult.outcome)}</div>
              </div>
            )}
          </div>

          {/* Focus Sharpness & Exposure Meters */}
          {inspectResult?.metrics && (
            <div className="grid grid-cols-2 gap-4 bg-surface-900 p-4 rounded-xl border border-surface-700 text-xs">
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-zinc-400">
                  <span className="flex items-center gap-1.5 font-medium">
                    <Focus className="w-3.5 h-3.5 text-primary-400" />
                    Lens Focus Sharpness (Laplacian):
                  </span>
                  <span className={`font-bold font-mono ${
                    inspectResult.metrics.focus_status === 'sharp' ? 'text-success-400' : inspectResult.metrics.focus_status === 'fair' ? 'text-warning-400' : 'text-danger-400'
                  }`}>
                    {inspectResult.metrics.sharpness} ({inspectResult.metrics.focus_status.toUpperCase()})
                  </span>
                </div>
                <div className="w-full bg-surface-800 rounded-full h-2 overflow-hidden">
                  <div
                    className={`h-full transition-all ${
                      inspectResult.metrics.focus_status === 'sharp' ? 'bg-success-400' : inspectResult.metrics.focus_status === 'fair' ? 'bg-warning-400' : 'bg-danger-400'
                    }`}
                    style={{ width: `${Math.min(100, (inspectResult.metrics.sharpness / 200) * 100)}%` }}
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-zinc-400">
                  <span className="flex items-center gap-1.5 font-medium">
                    <Sun className="w-3.5 h-3.5 text-warning-400" />
                    Lighting Exposure (Mean Lum):
                  </span>
                  <span className={`font-bold font-mono ${
                    inspectResult.metrics.exposure_status === 'good' ? 'text-success-400' : 'text-warning-400'
                  }`}>
                    {inspectResult.metrics.brightness} ({inspectResult.metrics.exposure_status.toUpperCase()})
                  </span>
                </div>
                <div className="w-full bg-surface-800 rounded-full h-2 overflow-hidden">
                  <div
                    className={`h-full transition-all ${
                      inspectResult.metrics.exposure_status === 'good' ? 'bg-success-400' : 'bg-warning-400'
                    }`}
                    style={{ width: `${Math.min(100, (inspectResult.metrics.brightness / 255) * 100)}%` }}
                  />
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="p-4 bg-danger-900/20 border border-danger-500 rounded-xl text-danger-400 text-sm flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <div>{error}</div>
            </div>
          )}
        </div>

        {/* Camera Control & Settings Sidebar */}
        <div className="card p-6 space-y-6">
          <div className="text-sm font-semibold uppercase tracking-wide text-zinc-400 flex items-center gap-2">
            <Sliders className="w-4 h-4 text-primary-400" />
            Inspection & Stream Settings
          </div>

          <div className="space-y-4 text-sm">
            <div>
              <div className="flex justify-between text-xs font-medium text-zinc-400 mb-1">
                <span>Anomaly Threshold</span>
                <span className="text-white font-mono">{threshold.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min="0.2"
                max="0.9"
                step="0.05"
                value={threshold}
                onChange={(e) => setThreshold(Number(e.target.value))}
                className="w-full accent-primary-500"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">Trigger Mode</label>
              <select className="w-full text-xs">
                <option value="hardware">Hardware PLC Interlock Trigger</option>
                <option value="continuous">Continuous Stream Polling</option>
                <option value="software">Manual Software Snapshot</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">Refresh Cadence</label>
              <select
                value={refreshIntervalMs}
                onChange={(e) => setRefreshIntervalMs(Number(e.target.value))}
                className="w-full text-xs"
              >
                <option value={500}>2 FPS (500ms)</option>
                <option value={1000}>1 FPS (1000ms)</option>
                <option value={2000}>0.5 FPS (2000ms)</option>
                <option value={5000}>0.2 FPS (5000ms)</option>
              </select>
            </div>
          </div>

          <div className="p-4 bg-surface-900 rounded-xl border border-surface-700 space-y-3 text-xs text-zinc-400">
            <div className="font-semibold text-white flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-success-400" />
              Phone & Webcam Setup Guide:
            </div>
            <ul className="space-y-1 list-disc list-inside text-zinc-400">
              <li>
                <strong>Phone Camera</strong>: Run <em>IP Webcam</em> or <em>DroidCam</em> on phone, switch source to <em>IP / Phone Stream</em>, and paste URL.
              </li>
              <li>
                <strong>USB Webcams</strong>: Plug in USB camera, click <em>Scan</em>, and select device index.
              </li>
              <li>
                <strong>Industrial GigE</strong>: Basler/Hikrobot cameras connect via Gigabit Ethernet on subnet.
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

import { useState, useRef } from 'react'
import { apiClient } from '../lib/api'
import { audioAlerts } from '../lib/audioAlerts'
import {
  Upload,
  Camera,
  CheckCircle,
  Sliders,
  Eye,
  RefreshCw,
  Layers,
  Split,
  Wifi,
  AlertTriangle,
} from 'lucide-react'

export default function StationTester() {
  const [sourceMode, setSourceMode] = useState<'upload' | 'camera'>('upload')
  const [selectedStation, setSelectedStation] = useState('STATION_1')
  const [variantId, setVariantId] = useState('FRONT_LH_BLACK')
  const [cameraName, setCameraName] = useState('main')
  const [threshold, setThreshold] = useState(0.55)

  // File upload state
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)

  // Camera capture state
  const [camMode, setCamMode] = useState<'device' | 'url'>('device')
  const [deviceIndex, setDeviceIndex] = useState(0)
  const [cameraUrl, setCameraUrl] = useState(() => localStorage.getItem('sg_last_cam_url') || 'http://192.168.1.50:8080/video')
  const [capturedBlob, setCapturedBlob] = useState<Blob | null>(null)
  const [capturing, setCapturing] = useState(false)

  // Test execution state
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Comparison view mode
  const [viewMode, setViewMode] = useState<'toggle' | 'split'>('toggle')
  const [showAnnotated, setShowAnnotated] = useState(true)
  const [splitPosition, setSplitPosition] = useState(50)
  const splitContainerRef = useRef<HTMLDivElement>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const f = e.target.files[0]
      setFile(f)
      setPreviewUrl(URL.createObjectURL(f))
      setCapturedBlob(null)
      setResult(null)
      setError(null)
    }
  }

  const handleCaptureLiveCamera = async () => {
    setCapturing(true)
    setError(null)
    try {
      const timestamp = Date.now()
      const base = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
      const url =
        camMode === 'url' && cameraUrl.trim()
          ? `${base}/api/v1/camera/snapshot?camera_url=${encodeURIComponent(cameraUrl.trim())}&_t=${timestamp}`
          : `${base}/api/v1/camera/snapshot?device_index=${deviceIndex}&_t=${timestamp}`

      const res = await fetch(url, {
        headers: {
          'X-API-Key': apiClient.getApiKey() || 'sg_dev_secret_key_2026',
        },
      })
      if (!res.ok) {
        throw new Error(`Camera capture failed (${res.status} ${res.statusText})`)
      }
      const blob = await res.blob()
      setCapturedBlob(blob)
      setPreviewUrl(URL.createObjectURL(blob))
      setFile(null)
      setResult(null)
    } catch (err: any) {
      setError(err.message || 'Failed to capture from live camera')
    } finally {
      setCapturing(false)
    }
  }

  const handleTest = async (e: React.FormEvent) => {
    e.preventDefault()

    let buffer: ArrayBuffer
    if (sourceMode === 'upload') {
      if (!file) {
        setError('Please select an image file first.')
        return
      }
      buffer = await file.arrayBuffer()
    } else {
      if (!capturedBlob) {
        setError('Please capture a camera frame first.')
        return
      }
      buffer = await capturedBlob.arrayBuffer()
    }

    setLoading(true)
    setError(null)
    try {
      const res = await apiClient.injectStationImage(selectedStation, cameraName, variantId, buffer)
      setResult(res)
      setShowAnnotated(true)
      audioAlerts.playOutcomeSound(res.outcome)
    } catch (err: any) {
      console.error('Station test failed:', err)
      setError(err.message || 'Failed to process inspection test')
    } finally {
      setLoading(false)
    }
  }

  const handleSplitMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!splitContainerRef.current || viewMode !== 'split') return
    const rect = splitContainerRef.current.getBoundingClientRect()
    const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width))
    setSplitPosition((x / rect.width) * 100)
  }

  const getOutcomeBadge = (outcome: string) => {
    switch (outcome?.toUpperCase()) {
      case 'PASS':
        return <span className="badge-pass px-3 py-1 text-sm font-bold">PASS</span>
      case 'REVIEW':
        return <span className="badge-review px-3 py-1 text-sm font-bold">REVIEW</span>
      case 'FAIL':
        return <span className="badge-fail px-3 py-1 text-sm font-bold">FAIL</span>
      default:
        return <span className="px-3 py-1 rounded-full text-xs font-semibold bg-zinc-800 text-zinc-300">{outcome}</span>
    }
  }

  const annotatedUrl = result?.annotated_image_url
    ? result.annotated_image_url.startsWith('http')
      ? result.annotated_image_url
      : `${import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'}${result.annotated_image_url}`
    : null

  const activeDisplayUrl = showAnnotated && annotatedUrl ? annotatedUrl : previewUrl

  return (
    <div className="space-y-8">
      <div>
        <h2 className="font-bold text-white text-3xl flex items-center gap-3">
          <Camera className="w-8 h-8 text-primary-400" />
          Manual Station Testing & Image Injector
        </h2>
        <p className="text-sm text-zinc-400 mt-1">
          Upload an inspection frame or capture directly from physical hardware / smartphone cameras to test vision AI & tolerance limits
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Configuration & Upload / Camera Form */}
        <div className="card p-8 space-y-6">
          <div className="flex items-center justify-between border-b border-surface-700 pb-4">
            <div className="text-sm font-semibold uppercase tracking-wide text-zinc-400 flex items-center gap-2">
              <Sliders className="w-4 h-4 text-primary-400" />
              Inspection Parameters
            </div>

            {/* Source Mode Switcher */}
            <div className="flex bg-surface-900 rounded-lg p-0.5 border border-surface-700 text-xs">
              <button
                type="button"
                onClick={() => setSourceMode('upload')}
                className={`px-3 py-1.5 rounded-md font-semibold transition-all ${
                  sourceMode === 'upload' ? 'bg-primary-600 text-white' : 'text-zinc-400 hover:text-white'
                }`}
              >
                Upload File
              </button>
              <button
                type="button"
                onClick={() => setSourceMode('camera')}
                className={`px-3 py-1.5 rounded-md font-semibold transition-all ${
                  sourceMode === 'camera' ? 'bg-primary-600 text-white' : 'text-zinc-400 hover:text-white'
                }`}
              >
                Camera Capture
              </button>
            </div>
          </div>

          <form onSubmit={handleTest} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-zinc-400 mb-2">Target Station</label>
              <select
                value={selectedStation}
                onChange={(e) => setSelectedStation(e.target.value)}
                className="w-full text-sm"
              >
                <option value="STATION_1">Station 1: Leather Surface & Texture</option>
                <option value="STATION_2">Station 2: Stitch & Seam Inspection</option>
                <option value="STATION_3">Station 3: Plastic Shield & Components</option>
                <option value="STATION_4">Station 4: Mechanism & Final Fit</option>
              </select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-zinc-400 mb-2">Seat Variant</label>
                <select
                  value={variantId}
                  onChange={(e) => setVariantId(e.target.value)}
                  className="w-full text-sm"
                >
                  <option value="FRONT_LH_BLACK">Front LH Black</option>
                  <option value="FRONT_RH_BLACK">Front RH Black</option>
                  <option value="FRONT_LH_BEIGE">Front LH Beige</option>
                  <option value="REAR_BENCH">Rear Bench</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-400 mb-2">Camera / View Name</label>
                <input
                  type="text"
                  value={cameraName}
                  onChange={(e) => setCameraName(e.target.value)}
                  placeholder="main, top, side..."
                  className="w-full text-sm"
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-sm font-medium text-zinc-400 mb-2">
                <span>Anomaly Threshold</span>
                <span className="font-mono text-white">{threshold.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min="0.2"
                max="0.9"
                step="0.05"
                value={threshold}
                onChange={(e) => setThreshold(parseFloat(e.target.value))}
                className="w-full accent-primary-500 bg-surface-900"
              />
            </div>

            {/* Source Input: File Upload or Live Camera Capture */}
            {sourceMode === 'upload' ? (
              <div>
                <label className="block text-sm font-medium text-zinc-400 mb-2">Test Image File</label>
                <div className="border-2 border-dashed border-surface-700 rounded-2xl p-6 text-center hover:border-primary-500 transition-colors bg-surface-900 cursor-pointer relative">
                  <input
                    type="file"
                    accept="image/*"
                    onChange={handleFileChange}
                    className="absolute inset-0 opacity-0 cursor-pointer"
                  />
                  <Upload className="w-10 h-10 text-zinc-500 mx-auto mb-2" />
                  <div className="text-sm font-medium text-zinc-300">
                    {file ? file.name : 'Click to upload or drag & drop image'}
                  </div>
                  <div className="text-xs text-zinc-500 mt-1">PNG, JPG, JPEG up to 20MB</div>
                </div>
              </div>
            ) : (
              <div className="p-4 bg-surface-900 rounded-xl border border-surface-700 space-y-4">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-zinc-300">Live Camera Ingestion</span>
                  <div className="flex bg-surface-800 rounded p-0.5 border border-surface-700">
                    <button
                      type="button"
                      onClick={() => setCamMode('device')}
                      className={`px-2 py-1 rounded text-xs ${camMode === 'device' ? 'bg-primary-600 text-white' : 'text-zinc-400'}`}
                    >
                      Device Index
                    </button>
                    <button
                      type="button"
                      onClick={() => setCamMode('url')}
                      className={`px-2 py-1 rounded text-xs ${camMode === 'url' ? 'bg-primary-600 text-white' : 'text-zinc-400'}`}
                    >
                      IP Stream
                    </button>
                  </div>
                </div>

                {camMode === 'device' ? (
                  <div>
                    <label className="block text-xs font-medium text-zinc-400 mb-1">Device Index</label>
                    <select
                      value={deviceIndex}
                      onChange={(e) => setDeviceIndex(Number(e.target.value))}
                      className="w-full text-xs"
                    >
                      <option value={0}>Camera 0 (Default / Webcam)</option>
                      <option value={1}>Camera 1 (Secondary)</option>
                      <option value={2}>Camera 2</option>
                      <option value={3}>Camera 3</option>
                    </select>
                  </div>
                ) : (
                  <div>
                    <label className="block text-xs font-medium text-zinc-400 mb-1 flex items-center gap-1.5">
                      <Wifi className="w-3 h-3 text-primary-400" />
                      Phone / Network Stream URL
                    </label>
                    <input
                      type="text"
                      value={cameraUrl}
                      onChange={(e) => setCameraUrl(e.target.value)}
                      placeholder="http://192.168.1.50:8080/video"
                      className="w-full text-xs"
                    />
                  </div>
                )}

                <button
                  type="button"
                  onClick={handleCaptureLiveCamera}
                  disabled={capturing}
                  className="w-full btn-ghost border border-primary-500/50 text-primary-300 py-2.5 flex items-center justify-center gap-2 text-xs font-semibold"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${capturing ? 'animate-spin' : ''}`} />
                  {capturing ? 'Acquiring Frame...' : 'Capture Snapshot from Camera'}
                </button>
              </div>
            )}

            <button
              type="submit"
              disabled={loading || (sourceMode === 'upload' ? !file : !capturedBlob)}
              className="w-full btn-primary py-3 flex items-center justify-center gap-2 text-base font-semibold shadow-lg shadow-primary-600/30"
            >
              <Camera className="w-5 h-5" />
              {loading ? 'Running Station Inspection...' : 'Run Station Test'}
            </button>
          </form>

          {error && (
            <div className="p-4 rounded-xl bg-danger-900/20 border border-danger-500 text-danger-400 text-sm flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <div>{error}</div>
            </div>
          )}
        </div>

        {/* Results & Inspection Output with Split Comparison View */}
        <div className="card p-8 space-y-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
                Inspection Result & Defect Overlay
              </div>
              {result && annotatedUrl && (
                <div className="flex items-center gap-2 bg-surface-900 p-1 rounded-lg border border-surface-700 text-xs">
                  <button
                    onClick={() => setViewMode('toggle')}
                    className={`px-2.5 py-1 rounded font-medium transition-colors flex items-center gap-1 ${
                      viewMode === 'toggle' ? 'bg-primary-600 text-white' : 'text-zinc-400 hover:text-white'
                    }`}
                  >
                    <Layers className="w-3.5 h-3.5" />
                    Toggle
                  </button>
                  <button
                    onClick={() => setViewMode('split')}
                    className={`px-2.5 py-1 rounded font-medium transition-colors flex items-center gap-1 ${
                      viewMode === 'split' ? 'bg-primary-600 text-white' : 'text-zinc-400 hover:text-white'
                    }`}
                  >
                    <Split className="w-3.5 h-3.5" />
                    Split Slider
                  </button>
                </div>
              )}
            </div>

            {/* Split Comparison Slider or Toggle View */}
            {previewUrl && (
              <div className="mb-6">
                {viewMode === 'split' && annotatedUrl ? (
                  <div
                    ref={splitContainerRef}
                    onMouseMove={handleSplitMouseMove}
                    className="relative rounded-xl overflow-hidden bg-black/60 h-72 border border-surface-700 cursor-ew-resize select-none"
                  >
                    {/* Underlying Annotated Image */}
                    <img
                      src={annotatedUrl}
                      alt="Annotated Inspection Result"
                      className="absolute inset-0 w-full h-full object-contain"
                    />

                    {/* Clipped Original Image on Top */}
                    <div
                      className="absolute inset-0 overflow-hidden"
                      style={{ clipPath: `inset(0 ${100 - splitPosition}% 0 0)` }}
                    >
                      <img
                        src={previewUrl}
                        alt="Raw Input Image"
                        className="absolute inset-0 w-full h-full object-contain"
                      />
                    </div>

                    {/* Draggable Divider Line */}
                    <div
                      className="absolute top-0 bottom-0 w-0.5 bg-primary-400 shadow-[0_0_8px_rgba(99,102,241,0.8)]"
                      style={{ left: `${splitPosition}%` }}
                    >
                      <div className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-6 h-6 rounded-full bg-primary-600 border-2 border-white flex items-center justify-center text-[10px] text-white font-bold">
                        ↔
                      </div>
                    </div>

                    {/* Labels */}
                    <div className="absolute bottom-2 left-2 bg-black/75 px-2 py-0.5 rounded text-[11px] font-mono text-zinc-300">
                      RAW INPUT
                    </div>
                    <div className="absolute bottom-2 right-2 bg-black/75 px-2 py-0.5 rounded text-[11px] font-mono text-primary-400">
                      AI DEFECTS
                    </div>
                  </div>
                ) : (
                  <div>
                    <div className="rounded-xl overflow-hidden bg-black/60 h-72 flex items-center justify-center border border-surface-700 relative">
                      <img src={activeDisplayUrl || ''} alt="Inspection view" className="w-full h-full object-contain" />
                    </div>

                    {annotatedUrl && (
                      <div className="flex justify-center gap-2 mt-2">
                        <button
                          onClick={() => setShowAnnotated(false)}
                          className={`text-xs px-3 py-1 rounded-md font-medium transition-colors ${
                            !showAnnotated ? 'bg-primary-600 text-white' : 'bg-surface-900 text-zinc-400'
                          }`}
                        >
                          Raw Frame
                        </button>
                        <button
                          onClick={() => setShowAnnotated(true)}
                          className={`text-xs px-3 py-1 rounded-md font-medium transition-colors flex items-center gap-1 ${
                            showAnnotated ? 'bg-primary-600 text-white' : 'bg-surface-900 text-zinc-400'
                          }`}
                        >
                          <Eye className="w-3.5 h-3.5" />
                          Annotated Faults
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {!result && !loading && !previewUrl && (
              <div className="text-center py-16 text-zinc-500 bg-surface-900 rounded-2xl border border-surface-700">
                <Camera className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
                <p>Upload an image or capture a live frame to run station test.</p>
              </div>
            )}

            {loading && (
              <div className="text-center py-16 text-zinc-400 bg-surface-900 rounded-2xl border border-surface-700 space-y-3">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary-500 mx-auto" />
                <p className="text-sm font-medium">Executing Station Inspection Pipeline...</p>
              </div>
            )}

            {result && !loading && (
              <div className="space-y-6 bg-surface-900 p-6 rounded-2xl border border-surface-700">
                <div className="flex items-center justify-between border-b border-surface-700 pb-4">
                  <div>
                    <div className="text-xs text-zinc-400 uppercase tracking-wider font-semibold">Station Target</div>
                    <div className="text-lg font-bold text-white">{result.station_id}</div>
                  </div>
                  <div>
                    <div className="text-xs text-zinc-400 uppercase tracking-wider font-semibold text-right">Outcome</div>
                    <div className="mt-1">{getOutcomeBadge(result.outcome)}</div>
                  </div>
                </div>

                {/* Defects List */}
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-3">
                    Detected Defects ({result.defects?.length || 0})
                  </div>
                  {result.defects?.length === 0 ? (
                    <div className="text-success-400 text-sm flex items-center gap-2 bg-success-900/20 p-3 rounded-xl border border-success-500/30">
                      <CheckCircle className="w-4 h-4 flex-shrink-0" />
                      No defects detected. Surface verified compliant.
                    </div>
                  ) : (
                    <div className="space-y-2 max-h-48 overflow-y-auto">
                      {result.defects.map((def: any, idx: number) => (
                        <div key={idx} className="bg-surface-800 p-3 rounded-xl border border-surface-700 flex items-center justify-between text-sm">
                          <div>
                            <span className="font-semibold text-white capitalize">{def.defect_type?.replace(/_/g, ' ')}</span>
                            {def.area_px && <span className="text-xs text-zinc-400 ml-2">({def.area_px} px²)</span>}
                          </div>
                          <span className="font-mono text-warning-400 font-semibold">
                            Score: {(def.anomaly_score ?? def.confidence ?? 0).toFixed(2)}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Measurements */}
                {result.measurements && Object.keys(result.measurements).length > 0 && (
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-3">
                      Extracted Measurements
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                      {Object.entries(result.measurements).map(([k, v]: [string, any], idx) => (
                        <div key={idx} className="bg-surface-800 p-2.5 rounded-lg border border-surface-700 flex justify-between">
                          <span className="text-zinc-400">{k}:</span>
                          <span className="text-white font-semibold">{typeof v === 'number' ? v.toFixed(2) : String(v)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

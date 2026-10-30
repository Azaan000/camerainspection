import { useState, useRef, useEffect } from 'react'
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
  Maximize2,
  X,
  Check,
  Crop,
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
  const [imageDimensions, setImageDimensions] = useState<{ width: number; height: number }>({ width: 2592, height: 1944 })

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

  // Comparison view mode & Custom ROI override state
  const [viewMode, setViewMode] = useState<'toggle' | 'split'>('toggle')
  const [showAnnotated, setShowAnnotated] = useState(true)
  const [flexibleMode, setFlexibleMode] = useState(false)
  const [splitPosition, setSplitPosition] = useState(50)
  const [customRoi, setCustomRoi] = useState<{ x: number; y: number; w: number; h: number } | null>(null)
  const [saveDefaultRoi, setSaveDefaultRoi] = useState(false)
  const [showRoiEditor, setShowRoiEditor] = useState(false)

  // Full Visual ROI Calibrator Modal state
  const [isRoiModalOpen, setIsRoiModalOpen] = useState(false)
  const [modalRoi, setModalRoi] = useState<{ x: number; y: number; w: number; h: number }>({ x: 150, y: 300, w: 2300, h: 400 })
  const [modalDragState, setModalDragState] = useState<{
    type: 'move' | 'nw' | 'ne' | 'sw' | 'se' | 'n' | 's' | 'e' | 'w'
    startX: number
    startY: number
    initialRoi: { x: number; y: number; w: number; h: number }
  } | null>(null)
  const modalImgRef = useRef<HTMLImageElement>(null)

  // Embedded preview drag state
  const [isDraggingRoi, setIsDraggingRoi] = useState(false)
  const [resizingHandle, setResizingHandle] = useState<string | null>(null)
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 })
  const imagePreviewRef = useRef<HTMLDivElement>(null)
  const previewImgRef = useRef<HTMLImageElement>(null)
  const splitContainerRef = useRef<HTMLDivElement>(null)

  // Default ROI boxes per station scaled to image dimensions
  const getDefaultRoiForStation = (st: string, imgW = imageDimensions.width, imgH = imageDimensions.height) => {
    if (imgW === 2592 && imgH === 1944) {
      switch (st) {
        case 'STATION_1': return { x: 200, y: 250, w: 2100, h: 1400 } // Leather seating face
        case 'STATION_2': return { x: 150, y: 300, w: 2300, h: 400 }  // Main stitch seam
        case 'STATION_3': return { x: 300, y: 300, w: 1900, h: 1300 } // Plastic shield & components
        case 'STATION_4': return { x: 250, y: 250, w: 2000, h: 1400 } // Mechanism & final fit
        default: return { x: 150, y: 300, w: 2300, h: 400 }
      }
    }
    // Proportional fallback for arbitrary resolutions
    switch (st) {
      case 'STATION_1':
        return { x: Math.round(imgW * 0.08), y: Math.round(imgH * 0.12), w: Math.round(imgW * 0.84), h: Math.round(imgH * 0.72) }
      case 'STATION_2':
        return { x: Math.round(imgW * 0.06), y: Math.round(imgH * 0.2), w: Math.round(imgW * 0.88), h: Math.round(imgH * 0.35) }
      case 'STATION_3':
        return { x: Math.round(imgW * 0.1), y: Math.round(imgH * 0.15), w: Math.round(imgW * 0.8), h: Math.round(imgH * 0.7) }
      case 'STATION_4':
        return { x: Math.round(imgW * 0.08), y: Math.round(imgH * 0.12), w: Math.round(imgW * 0.84), h: Math.round(imgH * 0.72) }
      default:
        return { x: Math.round(imgW * 0.06), y: Math.round(imgH * 0.2), w: Math.round(imgW * 0.88), h: Math.round(imgH * 0.35) }
    }
  }

  const activeRoi = customRoi || getDefaultRoiForStation(selectedStation)

  // Smooth window mouse tracking for Full Modal Visual Calibrator
  useEffect(() => {
    if (!modalDragState || !modalImgRef.current) return

    const handleMouseMove = (e: MouseEvent) => {
      if (!modalImgRef.current) return
      const rect = modalImgRef.current.getBoundingClientRect()
      if (rect.width <= 0 || rect.height <= 0) return

      const scaleX = imageDimensions.width / rect.width
      const scaleY = imageDimensions.height / rect.height
      const dx = (e.clientX - modalDragState.startX) * scaleX
      const dy = (e.clientY - modalDragState.startY) * scaleY

      const init = modalDragState.initialRoi
      const maxW = imageDimensions.width
      const maxH = imageDimensions.height

      let newX = init.x
      let newY = init.y
      let newW = init.w
      let newH = init.h

      switch (modalDragState.type) {
        case 'move':
          newX = Math.max(0, Math.min(maxW - init.w, Math.round(init.x + dx)))
          newY = Math.max(0, Math.min(maxH - init.h, Math.round(init.y + dy)))
          break
        case 'se':
          newW = Math.max(40, Math.min(maxW - init.x, Math.round(init.w + dx)))
          newH = Math.max(40, Math.min(maxH - init.y, Math.round(init.h + dy)))
          break
        case 'nw': {
          const targetX = Math.max(0, Math.min(init.x + init.w - 40, Math.round(init.x + dx)))
          const targetY = Math.max(0, Math.min(init.y + init.h - 40, Math.round(init.y + dy)))
          newX = targetX
          newY = targetY
          newW = init.w + (init.x - targetX)
          newH = init.h + (init.y - targetY)
          break
        }
        case 'ne': {
          const targetY = Math.max(0, Math.min(init.y + init.h - 40, Math.round(init.y + dy)))
          newY = targetY
          newW = Math.max(40, Math.min(maxW - init.x, Math.round(init.w + dx)))
          newH = init.h + (init.y - targetY)
          break
        }
        case 'sw': {
          const targetX = Math.max(0, Math.min(init.x + init.w - 40, Math.round(init.x + dx)))
          newX = targetX
          newW = init.w + (init.x - targetX)
          newH = Math.max(40, Math.min(maxH - init.y, Math.round(init.h + dy)))
          break
        }
        case 'n': {
          const targetY = Math.max(0, Math.min(init.y + init.h - 40, Math.round(init.y + dy)))
          newY = targetY
          newH = init.h + (init.y - targetY)
          break
        }
        case 's':
          newH = Math.max(40, Math.min(maxH - init.y, Math.round(init.h + dy)))
          break
        case 'w': {
          const targetX = Math.max(0, Math.min(init.x + init.w - 40, Math.round(init.x + dx)))
          newX = targetX
          newW = init.w + (init.x - targetX)
          break
        }
        case 'e':
          newW = Math.max(40, Math.min(maxW - init.x, Math.round(init.w + dx)))
          break
      }

      setModalRoi({ x: newX, y: newY, w: newW, h: newH })
    }

    const handleMouseUp = () => {
      setModalDragState(null)
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [modalDragState, imageDimensions])

  // Smooth window mouse tracking for embedded preview
  useEffect(() => {
    if (!isDraggingRoi && !resizingHandle) return

    const handleMouseMove = (e: MouseEvent) => {
      const container = previewImgRef.current || imagePreviewRef.current
      if (!container) return
      const rect = container.getBoundingClientRect()
      if (rect.width <= 0 || rect.height <= 0) return

      const scaleX = imageDimensions.width / rect.width
      const scaleY = imageDimensions.height / rect.height
      const dx = (e.clientX - dragStart.x) * scaleX
      const dy = (e.clientY - dragStart.y) * scaleY
      setDragStart({ x: e.clientX, y: e.clientY })

      setCustomRoi((prev) => {
        const curr = prev || getDefaultRoiForStation(selectedStation, imageDimensions.width, imageDimensions.height)
        const maxW = imageDimensions.width
        const maxH = imageDimensions.height

        if (resizingHandle === 'se') {
          return {
            x: curr.x,
            y: curr.y,
            w: Math.max(50, Math.min(maxW - curr.x, Math.round(curr.w + dx))),
            h: Math.max(50, Math.min(maxH - curr.y, Math.round(curr.h + dy))),
          }
        } else if (resizingHandle === 'nw') {
          const newX = Math.max(0, Math.min(curr.x + curr.w - 50, Math.round(curr.x + dx)))
          const newY = Math.max(0, Math.min(curr.y + curr.h - 50, Math.round(curr.y + dy)))
          return {
            x: newX,
            y: newY,
            w: curr.w + (curr.x - newX),
            h: curr.h + (curr.y - newY),
          }
        } else if (resizingHandle === 'ne') {
          const newY = Math.max(0, Math.min(curr.y + curr.h - 50, Math.round(curr.y + dy)))
          return {
            x: curr.x,
            y: newY,
            w: Math.max(50, Math.min(maxW - curr.x, Math.round(curr.w + dx))),
            h: curr.h + (curr.y - newY),
          }
        } else if (resizingHandle === 'sw') {
          const newX = Math.max(0, Math.min(curr.x + curr.w - 50, Math.round(curr.x + dx)))
          return {
            x: newX,
            y: curr.y,
            w: curr.w + (curr.x - newX),
            h: Math.max(50, Math.min(maxH - curr.y, Math.round(curr.h + dy))),
          }
        } else {
          // Full box drag
          return {
            x: Math.max(0, Math.min(maxW - curr.w, Math.round(curr.x + dx))),
            y: Math.max(0, Math.min(maxH - curr.h, Math.round(curr.y + dy))),
            w: curr.w,
            h: curr.h,
          }
        }
      })
    }

    const handleMouseUp = () => {
      setIsDraggingRoi(false)
      setResizingHandle(null)
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDraggingRoi, resizingHandle, dragStart, selectedStation, imageDimensions])

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const f = e.target.files[0]
      setFile(f)
      const url = URL.createObjectURL(f)
      setPreviewUrl(url)
      setCapturedBlob(null)
      setResult(null)
      setError(null)
      const img = new Image()
      img.onload = () => {
        setImageDimensions({ width: img.naturalWidth, height: img.naturalHeight })
      }
      img.src = url
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
      const blobUrl = URL.createObjectURL(blob)
      setPreviewUrl(blobUrl)
      setFile(null)
      setResult(null)
      const img = new Image()
      img.onload = () => {
        setImageDimensions({ width: img.naturalWidth, height: img.naturalHeight })
      }
      img.src = blobUrl
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
      const res = await apiClient.injectStationImage(
        selectedStation,
        cameraName,
        variantId,
        buffer,
        flexibleMode,
        threshold,
        customRoi || undefined,
        saveDefaultRoi
      )
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

            {/* Flexible Testing Mode Toggle */}
            <div className="flex items-center justify-between p-3 bg-surface-900 rounded-xl border border-surface-700">
              <div>
                <div className="text-sm font-medium text-white">Flexible Testing Mode</div>
                <div className="text-xs text-zinc-400">Bypass strict ROI/calibration bounds for uncalibrated uploads</div>
              </div>
              <input
                type="checkbox"
                checked={flexibleMode}
                onChange={(e) => setFlexibleMode(e.target.checked)}
                className="w-4 h-4 accent-primary-500 rounded bg-surface-800 border-surface-600 cursor-pointer"
              />
            </div>

            {/* Custom ROI Adjustment & Tuning Panel */}
            <div className="p-4 bg-surface-900 rounded-xl border border-surface-700 space-y-3">
              <div className="flex items-center justify-between">
                <div className="text-xs font-semibold uppercase tracking-wider text-zinc-300">Custom Inspection ROI & Bounding Box</div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setModalRoi(customRoi || getDefaultRoiForStation(selectedStation, imageDimensions.width, imageDimensions.height))
                      setIsRoiModalOpen(true)
                    }}
                    disabled={!previewUrl}
                    className="text-xs text-cyan-400 hover:text-cyan-300 font-medium flex items-center gap-1 disabled:opacity-40"
                    title={!previewUrl ? "Upload or capture an image first" : "Open full visual ROI calibrator"}
                  >
                    <Crop className="w-3.5 h-3.5" />
                    Set Visually...
                  </button>
                  <span className="text-zinc-600">|</span>
                  <button
                    type="button"
                    onClick={() => setShowRoiEditor(!showRoiEditor)}
                    className="text-xs text-primary-400 hover:underline font-medium"
                  >
                    {showRoiEditor ? 'Hide Manual' : 'Manual Coordinates...'}
                  </button>
                </div>
              </div>

              {showRoiEditor && (
                <div className="space-y-3 pt-2 border-t border-surface-800 text-xs">
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-zinc-400 mb-1">ROI X</label>
                      <input
                        type="number"
                        value={customRoi?.x ?? 150}
                        onChange={(e) => setCustomRoi(prev => ({ x: Number(e.target.value), y: prev?.y ?? 300, w: prev?.w ?? 2300, h: prev?.h ?? 400 }))}
                        className="w-full text-xs font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-zinc-400 mb-1">ROI Y</label>
                      <input
                        type="number"
                        value={customRoi?.y ?? 300}
                        onChange={(e) => setCustomRoi(prev => ({ x: prev?.x ?? 150, y: Number(e.target.value), w: prev?.w ?? 2300, h: prev?.h ?? 400 }))}
                        className="w-full text-xs font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-zinc-400 mb-1">Width (W)</label>
                      <input
                        type="number"
                        value={customRoi?.w ?? 2300}
                        onChange={(e) => setCustomRoi(prev => ({ x: prev?.x ?? 150, y: prev?.y ?? 300, w: Number(e.target.value), h: prev?.h ?? 400 }))}
                        className="w-full text-xs font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-zinc-400 mb-1">Height (H)</label>
                      <input
                        type="number"
                        value={customRoi?.h ?? 400}
                        onChange={(e) => setCustomRoi(prev => ({ x: prev?.x ?? 150, y: prev?.y ?? 300, w: prev?.w ?? 2300, h: Number(e.target.value) }))}
                        className="w-full text-xs font-mono"
                      />
                    </div>
                  </div>

                  <div className="flex items-center justify-between pt-2">
                    <label className="flex items-center gap-2 cursor-pointer text-zinc-300">
                      <input
                        type="checkbox"
                        checked={saveDefaultRoi}
                        onChange={(e) => setSaveDefaultRoi(e.target.checked)}
                        className="w-3.5 h-3.5 accent-primary-500 rounded bg-surface-850 border-surface-700"
                      />
                      Save as station default ROI config
                    </label>
                    <button
                      type="button"
                      onClick={() => setCustomRoi(null)}
                      className="text-zinc-500 hover:text-zinc-300 underline text-[11px]"
                    >
                      Reset Default
                    </button>
                  </div>
                </div>
              )}
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
                    <label className="text-xs font-medium text-zinc-400 mb-1 flex items-center gap-1.5">
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
                    <div
                      ref={imagePreviewRef}
                      className="rounded-xl overflow-hidden bg-black/60 h-72 flex items-center justify-center border border-surface-700 relative group"
                    >
                      <img src={activeDisplayUrl || ''} alt="Inspection view" className="w-full h-full object-contain" />

                      {/* Active Visual ROI Overlay indicator */}
                      {previewUrl && (
                        <div
                          onClick={() => {
                            setModalRoi(customRoi || getDefaultRoiForStation(selectedStation, imageDimensions.width, imageDimensions.height))
                            setIsRoiModalOpen(true)
                          }}
                          className="absolute border-2 border-cyan-400 bg-cyan-500/10 shadow-[0_0_15px_rgba(6,182,212,0.4)] cursor-pointer rounded transition-all hover:bg-cyan-500/20 group/roi z-10"
                          style={{
                            left: `${(activeRoi.x / imageDimensions.width) * 100}%`,
                            top: `${(activeRoi.y / imageDimensions.height) * 100}%`,
                            width: `${(activeRoi.w / imageDimensions.width) * 100}%`,
                            height: `${(activeRoi.h / imageDimensions.height) * 100}%`,
                          }}
                          title="Click to open Full Visual ROI Calibrator"
                        >
                          <div className="absolute top-1 left-1 bg-black/85 backdrop-blur-sm px-1.5 py-0.5 rounded text-[10px] font-mono text-cyan-300 pointer-events-none flex items-center gap-1 border border-cyan-500/30">
                            <Crop className="w-2.5 h-2.5 text-cyan-400" />
                            <span>ROI: {selectedStation} ({activeRoi.w}×{activeRoi.h})</span>
                          </div>
                          <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover/roi:opacity-100 transition-opacity bg-black/40 backdrop-blur-[1px]">
                            <span className="text-[11px] font-semibold text-white bg-cyan-600 px-2.5 py-1 rounded shadow-md flex items-center gap-1.5">
                              <Maximize2 className="w-3 h-3" />
                              Open Visual Calibrator
                            </span>
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Dedicated Visual ROI Calibrator Bar below preview */}
                    {previewUrl && (
                      <div className="mt-3 p-3 bg-surface-900 rounded-xl border border-surface-700 flex flex-wrap items-center justify-between gap-2.5">
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => {
                              setModalRoi(customRoi || getDefaultRoiForStation(selectedStation, imageDimensions.width, imageDimensions.height))
                              setIsRoiModalOpen(true)
                            }}
                            className="btn-primary py-1.5 px-3.5 text-xs flex items-center gap-2 font-semibold shadow-md shadow-primary-600/30 bg-gradient-to-r from-primary-600 to-cyan-600 hover:from-primary-500 hover:to-cyan-500"
                          >
                            <Crop className="w-4 h-4 text-white" />
                            <span>Set ROI Visually</span>
                          </button>

                          {customRoi && (
                            <button
                              type="button"
                              onClick={() => setCustomRoi(null)}
                              className="text-xs text-zinc-400 hover:text-white px-2.5 py-1.5 rounded-lg bg-surface-800 hover:bg-surface-700 border border-surface-700 transition-colors"
                              title="Reset to station default ROI"
                            >
                              Reset ROI
                            </button>
                          )}
                        </div>

                        <div className="text-[11px] font-mono text-zinc-400 flex items-center gap-1.5">
                          <span className="text-zinc-500 font-sans">Active ROI:</span>
                          <span className="text-cyan-400 font-semibold bg-surface-850 px-2 py-0.5 rounded border border-surface-700">
                            {activeRoi.w}×{activeRoi.h}
                          </span>
                          <span className="text-zinc-500">at ({activeRoi.x}, {activeRoi.y})</span>
                        </div>
                      </div>
                    )}

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

            {/* Full Visual ROI Calibrator Modal */}
            {isRoiModalOpen && previewUrl && (
              <div
                className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/95 backdrop-blur-md overflow-y-auto"
                onClick={(e) => { if (e.target === e.currentTarget) setIsRoiModalOpen(false) }}
              >
                <div className="bg-surface-900 rounded-2xl border border-surface-700 shadow-2xl w-full max-w-7xl max-h-[92vh] flex flex-col overflow-hidden my-auto">
                  {/* Modal Header */}
                  <div className="flex items-center justify-between px-6 py-4 border-b border-surface-700 bg-surface-850 rounded-t-2xl flex-shrink-0">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
                        <Crop className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="text-base font-bold text-white">Visual ROI Calibrator — {selectedStation}</div>
                        <div className="text-xs text-zinc-400">Drag box to position, drag handles or edges to resize. Full resolution view ({imageDimensions.width} × {imageDimensions.height} px).</div>
                      </div>
                    </div>
                    <button
                      onClick={() => setIsRoiModalOpen(false)}
                      className="text-zinc-400 hover:text-white hover:bg-surface-800 rounded-xl p-2 transition-colors"
                    >
                      <X className="w-5 h-5" />
                    </button>
                  </div>

                  {/* Preset Row */}
                  <div className="flex items-center gap-2.5 px-6 py-3 bg-surface-850 border-b border-surface-700 flex-shrink-0 flex-wrap">
                    <span className="text-xs text-zinc-400 font-semibold uppercase tracking-wider mr-1">Quick Presets:</span>
                    {[
                      { label: 'Full Image', value: () => ({ x: 0, y: 0, w: imageDimensions.width, h: imageDimensions.height }) },
                      { label: 'Station Default', value: () => getDefaultRoiForStation(selectedStation, imageDimensions.width, imageDimensions.height) },
                      { label: 'Center 80%', value: () => ({
                        x: Math.round(imageDimensions.width * 0.1),
                        y: Math.round(imageDimensions.height * 0.1),
                        w: Math.round(imageDimensions.width * 0.8),
                        h: Math.round(imageDimensions.height * 0.8),
                      })},
                      { label: 'Center Seam Strip', value: () => ({
                        x: Math.round(imageDimensions.width * 0.05),
                        y: Math.round(imageDimensions.height * 0.35),
                        w: Math.round(imageDimensions.width * 0.9),
                        h: Math.round(imageDimensions.height * 0.3),
                      })},
                    ].map(({ label, value }) => (
                      <button
                        key={label}
                        type="button"
                        onClick={() => setModalRoi(value())}
                        className="text-xs px-3.5 py-1.5 rounded-xl bg-surface-800 border border-surface-700 text-zinc-300 hover:border-cyan-500 hover:text-cyan-300 transition-colors font-medium shadow-sm"
                      >
                        {label}
                      </button>
                    ))}
                    <div className="ml-auto text-xs font-mono text-zinc-300 bg-surface-800 px-3 py-1.5 rounded-xl border border-surface-700 flex items-center gap-2 shadow-inner">
                      <span className="text-zinc-400">Active ROI:</span>
                      <span className="text-cyan-400 font-bold">{modalRoi.w} × {modalRoi.h}</span>
                      <span className="text-zinc-500">at</span>
                      <span className="text-zinc-200">({modalRoi.x}, {modalRoi.y})</span>
                    </div>
                  </div>

                  {/* Image Canvas Area - Centered & Fully Visible */}
                  <div className="relative flex-1 bg-black/95 flex items-center justify-center p-4 overflow-auto min-h-0 w-full">
                    <div className="relative flex items-center justify-center w-full h-full select-none" style={{ cursor: modalDragState ? 'grabbing' : 'default' }}>
                      <img
                        ref={modalImgRef}
                        src={previewUrl}
                        alt="ROI calibration canvas"
                        className="max-h-full max-w-full w-auto h-auto object-contain rounded-xl border border-surface-700 shadow-2xl block"
                        draggable={false}
                      />

                      {/* ROI Overlay Box */}
                      <div
                        className="absolute border-2 border-cyan-400 bg-cyan-500/15 cursor-grab active:cursor-grabbing shadow-[0_0_30px_rgba(6,182,212,0.5)] rounded-md"
                        style={{
                          left: `${(modalRoi.x / imageDimensions.width) * 100}%`,
                          top: `${(modalRoi.y / imageDimensions.height) * 100}%`,
                          width: `${(modalRoi.w / imageDimensions.width) * 100}%`,
                          height: `${(modalRoi.h / imageDimensions.height) * 100}%`,
                        }}
                        onMouseDown={(e) => {
                          e.preventDefault()
                          e.stopPropagation()
                          setModalDragState({ type: 'move', startX: e.clientX, startY: e.clientY, initialRoi: { ...modalRoi } })
                        }}
                      >
                        {/* ROI info label */}
                        <div className="absolute top-2 left-2 bg-black/90 backdrop-blur-md px-2.5 py-1 rounded-lg text-xs font-mono text-cyan-300 border border-cyan-500/40 pointer-events-none flex items-center gap-2 shadow-lg">
                          <Crop className="w-3.5 h-3.5 text-cyan-400 flex-shrink-0" />
                          <span className="font-bold">ROI: {modalRoi.w} × {modalRoi.h}</span>
                        </div>

                        {/* N handle */}
                        <div className="absolute -top-2.5 left-1/2 -translate-x-1/2 w-6 h-3 bg-cyan-400 rounded-md cursor-ns-resize border border-cyan-200 hover:bg-cyan-300 transition-colors shadow-md"
                          onMouseDown={(e) => { e.stopPropagation(); e.preventDefault(); setModalDragState({ type: 'n', startX: e.clientX, startY: e.clientY, initialRoi: { ...modalRoi } }) }} />
                        {/* S handle */}
                        <div className="absolute -bottom-2.5 left-1/2 -translate-x-1/2 w-6 h-3 bg-cyan-400 rounded-md cursor-ns-resize border border-cyan-200 hover:bg-cyan-300 transition-colors shadow-md"
                          onMouseDown={(e) => { e.stopPropagation(); e.preventDefault(); setModalDragState({ type: 's', startX: e.clientX, startY: e.clientY, initialRoi: { ...modalRoi } }) }} />
                        {/* W handle */}
                        <div className="absolute top-1/2 -left-2.5 -translate-y-1/2 w-3 h-6 bg-cyan-400 rounded-md cursor-ew-resize border border-cyan-200 hover:bg-cyan-300 transition-colors shadow-md"
                          onMouseDown={(e) => { e.stopPropagation(); e.preventDefault(); setModalDragState({ type: 'w', startX: e.clientX, startY: e.clientY, initialRoi: { ...modalRoi } }) }} />
                        {/* E handle */}
                        <div className="absolute top-1/2 -right-2.5 -translate-y-1/2 w-3 h-6 bg-cyan-400 rounded-md cursor-ew-resize border border-cyan-200 hover:bg-cyan-300 transition-colors shadow-md"
                          onMouseDown={(e) => { e.stopPropagation(); e.preventDefault(); setModalDragState({ type: 'e', startX: e.clientX, startY: e.clientY, initialRoi: { ...modalRoi } }) }} />
                        {/* NW corner */}
                        <div className="absolute -top-3 -left-3 w-6 h-6 bg-white border-2 border-cyan-500 rounded-full cursor-nwse-resize hover:bg-cyan-200 hover:scale-125 transition-all shadow-lg"
                          onMouseDown={(e) => { e.stopPropagation(); e.preventDefault(); setModalDragState({ type: 'nw', startX: e.clientX, startY: e.clientY, initialRoi: { ...modalRoi } }) }} />
                        {/* NE corner */}
                        <div className="absolute -top-3 -right-3 w-6 h-6 bg-white border-2 border-cyan-500 rounded-full cursor-nesw-resize hover:bg-cyan-200 hover:scale-125 transition-all shadow-lg"
                          onMouseDown={(e) => { e.stopPropagation(); e.preventDefault(); setModalDragState({ type: 'ne', startX: e.clientX, startY: e.clientY, initialRoi: { ...modalRoi } }) }} />
                        {/* SW corner */}
                        <div className="absolute -bottom-3 -left-3 w-6 h-6 bg-white border-2 border-cyan-500 rounded-full cursor-nesw-resize hover:bg-cyan-200 hover:scale-125 transition-all shadow-lg"
                          onMouseDown={(e) => { e.stopPropagation(); e.preventDefault(); setModalDragState({ type: 'sw', startX: e.clientX, startY: e.clientY, initialRoi: { ...modalRoi } }) }} />
                        {/* SE corner */}
                        <div className="absolute -bottom-3 -right-3 w-6 h-6 bg-white border-2 border-cyan-500 rounded-full cursor-nwse-resize hover:bg-cyan-200 hover:scale-125 transition-all shadow-lg"
                          onMouseDown={(e) => { e.stopPropagation(); e.preventDefault(); setModalDragState({ type: 'se', startX: e.clientX, startY: e.clientY, initialRoi: { ...modalRoi } }) }} />

                        {/* Crosshair guides */}
                        <div className="absolute top-0 bottom-0 left-1/2 -translate-x-px w-px bg-cyan-400/40 pointer-events-none border-l border-dashed border-cyan-400/40" />
                        <div className="absolute left-0 right-0 top-1/2 -translate-y-px h-px bg-cyan-400/40 pointer-events-none border-t border-dashed border-cyan-400/40" />
                      </div>
                    </div>
                  </div>

                  {/* Footer Actions */}
                  <div className="flex items-center justify-between gap-4 px-6 py-4 border-t border-surface-700 bg-surface-850 rounded-b-2xl flex-shrink-0">
                    <div className="flex items-center gap-3">
                      <label className="flex items-center gap-2 cursor-pointer text-zinc-200 text-xs font-semibold select-none bg-surface-800 px-3 py-2 rounded-xl border border-surface-700 hover:border-cyan-500/50 transition-colors">
                        <input
                          type="checkbox"
                          checked={saveDefaultRoi}
                          onChange={(e) => setSaveDefaultRoi(e.target.checked)}
                          className="w-4 h-4 accent-cyan-500 rounded bg-surface-900 border-surface-600"
                        />
                        Save permanently to station YAML default config
                      </label>
                    </div>
                    <div className="flex items-center gap-3">
                      <button
                        type="button"
                        onClick={() => setIsRoiModalOpen(false)}
                        className="text-xs px-5 py-2.5 rounded-xl bg-surface-800 border border-surface-700 text-zinc-300 hover:text-white hover:border-surface-600 transition-colors font-semibold"
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setCustomRoi({ ...modalRoi })
                          setIsRoiModalOpen(false)
                        }}
                        className="text-xs px-6 py-2.5 rounded-xl bg-gradient-to-r from-cyan-600 to-primary-600 hover:from-cyan-500 hover:to-primary-500 text-white font-bold shadow-lg shadow-cyan-600/30 transition-all flex items-center gap-2"
                      >
                        <Check className="w-4 h-4" />
                        Apply ROI & Test
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}


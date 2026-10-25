import { useState, useEffect, useRef } from 'react'
import { apiClient } from '../lib/api'
import {
  Trash2,
  CheckCircle,
  Sliders,
  Camera,
  Target,
  RefreshCw,
  Upload,
  Plus,
  Save,
  AlertTriangle,
} from 'lucide-react'

export interface ROIItem {
  id?: string
  name: string
  x: number
  y: number
  width: number
  height: number
  active?: boolean
  type?: 'inspection' | 'mask'
}

export default function ROIEditor() {
  const [stationId, setStationId] = useState('STATION_1')
  const [cameraName, setCameraName] = useState('main')
  const [rois, setRois] = useState<ROIItem[]>([])
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Backdrop image
  const [backdropUrl, setBackdropUrl] = useState<string | null>(null)
  const [acquiringFrame, setAcquiringFrame] = useState(false)

  // Interaction dragging & resizing state
  const containerRef = useRef<HTMLDivElement>(null)
  const [dragAction, setDragAction] = useState<{
    mode: 'move' | 'resize'
    roiIndex: number
    startX: number
    startY: number
    initialRoi: ROIItem
    handle?: string
  } | null>(null)

  const NATIVE_W = 1920
  const NATIVE_H = 1080

  const fetchRois = async () => {
    setLoading(true)
    setError(null)
    setSuccessMsg(null)
    try {
      const data: any = await apiClient.getStationROIs(stationId, cameraName)
      if (Array.isArray(data)) {
        setRois(data.map((r, i) => ({ ...r, type: r.type || 'inspection', id: r.id || `roi_${i}` })))
      } else if (data && data.rois) {
        setRois(data.rois.map((r: any, i: number) => ({ ...r, type: r.type || 'inspection', id: r.id || `roi_${i}` })))
      } else {
        loadStationPresets(stationId)
      }
    } catch (err: any) {
      console.warn('Failed to fetch ROIs, loading station defaults:', err)
      loadStationPresets(stationId)
    } finally {
      setLoading(false)
    }
  }

  const loadStationPresets = (station: string) => {
    switch (station) {
      case 'STATION_1':
        setRois([
          { name: 'cushion_center', x: 320, y: 200, width: 900, height: 600, active: true, type: 'inspection' },
          { name: 'backrest_bolster', x: 1250, y: 150, width: 450, height: 750, active: true, type: 'inspection' },
          { name: 'clamp_exclusion', x: 200, y: 880, width: 350, height: 160, active: true, type: 'mask' },
        ])
        break
      case 'STATION_2':
        setRois([
          { name: 'left_seam_line', x: 150, y: 120, width: 300, height: 840, active: true, type: 'inspection' },
          { name: 'right_seam_line', x: 1470, y: 120, width: 300, height: 840, active: true, type: 'inspection' },
          { name: 'headrest_stitch', x: 600, y: 80, width: 720, height: 260, active: true, type: 'inspection' },
        ])
        break
      case 'STATION_3':
        setRois([
          { name: 'side_shield_bezel', x: 250, y: 220, width: 850, height: 650, active: true, type: 'inspection' },
          { name: 'recliner_lever', x: 1150, y: 350, width: 500, height: 400, active: true, type: 'inspection' },
        ])
        break
      case 'STATION_4':
        setRois([
          { name: 'pivot_hinge', x: 400, y: 300, width: 600, height: 500, active: true, type: 'inspection' },
          { name: 'rail_track_latch', x: 1100, y: 250, width: 550, height: 600, active: true, type: 'inspection' },
        ])
        break
      default:
        setRois([
          { name: 'inspection_zone_main', x: 200, y: 150, width: 1000, height: 700, active: true, type: 'inspection' },
        ])
    }
  }

  useEffect(() => {
    fetchRois()
  }, [stationId, cameraName])

  const handleCaptureCamera = async () => {
    setAcquiringFrame(true)
    setError(null)
    try {
      const timestamp = Date.now()
      const base = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
      const url = `${base}/api/v1/camera/snapshot?_t=${timestamp}`
      const res = await fetch(url, {
        headers: { 'X-API-Key': apiClient.getApiKey() || 'sg_dev_secret_key_2026' },
      })
      if (!res.ok) throw new Error('Live camera snapshot failed')
      const blob = await res.blob()
      setBackdropUrl(URL.createObjectURL(blob))
    } catch (err: any) {
      setError(err.message || 'Could not acquire live camera backdrop')
    } finally {
      setAcquiringFrame(false)
    }
  }

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setBackdropUrl(URL.createObjectURL(e.target.files[0]))
    }
  }

  const handleAddRoi = () => {
    const newRoi: ROIItem = {
      name: `zone_${rois.length + 1}`,
      x: 400 + rois.length * 40,
      y: 250 + rois.length * 30,
      width: 450,
      height: 350,
      active: true,
      type: 'inspection',
    }
    setRois([...rois, newRoi])
    setSelectedIdx(rois.length)
  }

  const handleDeleteRoi = (index: number) => {
    const updated = rois.filter((_, i) => i !== index)
    setRois(updated)
    if (selectedIdx === index) setSelectedIdx(null)
    else if (selectedIdx !== null && selectedIdx > index) setSelectedIdx(selectedIdx - 1)
  }

  const handleRoiChange = (index: number, field: keyof ROIItem, value: any) => {
    const updated = [...rois]
    updated[index] = { ...updated[index], [field]: value }
    setRois(updated)
  }

  // Mouse handlers for dragging & resizing ROIs on SVG
  const getSvgCoordinates = (e: React.MouseEvent) => {
    if (!containerRef.current) return { x: 0, y: 0 }
    const rect = containerRef.current.getBoundingClientRect()
    const clientX = e.clientX - rect.left
    const clientY = e.clientY - rect.top
    const scaleX = NATIVE_W / rect.width
    const scaleY = NATIVE_H / rect.height
    return {
      x: Math.round(clientX * scaleX),
      y: Math.round(clientY * scaleY),
    }
  }

  const handleMouseDown = (e: React.MouseEvent, index: number, handle?: string) => {
    e.stopPropagation()
    setSelectedIdx(index)
    const { x, y } = getSvgCoordinates(e)
    setDragAction({
      mode: handle ? 'resize' : 'move',
      roiIndex: index,
      startX: x,
      startY: y,
      initialRoi: { ...rois[index] },
      handle,
    })
  }

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!dragAction) return
    const { x, y } = getSvgCoordinates(e)
    const deltaX = x - dragAction.startX
    const deltaY = y - dragAction.startY
    const { initialRoi, roiIndex, mode, handle } = dragAction

    const updated = [...rois]
    const cur = { ...initialRoi }

    if (mode === 'move') {
      cur.x = Math.max(0, Math.min(NATIVE_W - cur.width, initialRoi.x + deltaX))
      cur.y = Math.max(0, Math.min(NATIVE_H - cur.height, initialRoi.y + deltaY))
    } else if (mode === 'resize') {
      if (handle === 'br') {
        cur.width = Math.max(50, Math.min(NATIVE_W - cur.x, initialRoi.width + deltaX))
        cur.height = Math.max(50, Math.min(NATIVE_H - cur.y, initialRoi.height + deltaY))
      } else if (handle === 'tl') {
        const newX = Math.max(0, Math.min(initialRoi.x + initialRoi.width - 50, initialRoi.x + deltaX))
        const newY = Math.max(0, Math.min(initialRoi.y + initialRoi.height - 50, initialRoi.y + deltaY))
        cur.width = initialRoi.width + (initialRoi.x - newX)
        cur.height = initialRoi.height + (initialRoi.y - newY)
        cur.x = newX
        cur.y = newY
      }
    }

    updated[roiIndex] = cur
    setRois(updated)
  }

  const handleMouseUp = () => {
    setDragAction(null)
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    setSuccessMsg(null)
    try {
      await apiClient.updateStationROIs(stationId, { camera_name: cameraName, rois })
      setSuccessMsg('ROI configuration successfully synced with machine vision edge node.')
    } catch (err: any) {
      setError(err.message || 'Failed to save ROI configuration')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-8" onMouseUp={handleMouseUp} onMouseMove={handleMouseMove}>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="font-bold text-white text-3xl flex items-center gap-3">
            <Target className="w-8 h-8 text-primary-400" />
            Interactive Canvas ROI & Masking Editor
          </h2>
          <p className="text-sm text-zinc-400 mt-1">
            Draw, drag, resize, and configure inspection zones and exclusion masks for edge nodes
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3 bg-surface-800 p-2 rounded-xl border border-surface-700">
          <select
            value={stationId}
            onChange={(e) => setStationId(e.target.value)}
            className="text-xs py-1.5 px-3"
          >
            <option value="STATION_1">Station 1: Leather Surface</option>
            <option value="STATION_2">Station 2: Stitch & Seam</option>
            <option value="STATION_3">Station 3: Plastic Shield</option>
            <option value="STATION_4">Station 4: Mechanism & Fit</option>
          </select>
          <input
            type="text"
            value={cameraName}
            onChange={(e) => setCameraName(e.target.value)}
            placeholder="Camera name"
            className="text-xs py-1.5 px-3 w-28"
          />
          <button onClick={fetchRois} className="btn-ghost p-2" title="Refresh">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Interactive SVG Canvas Area */}
        <div className="lg:col-span-2 card p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-surface-700 pb-4">
            <div className="text-sm font-semibold uppercase tracking-wider text-zinc-400 flex items-center gap-2">
              <Sliders className="w-4 h-4 text-primary-400" />
              Viewport: {stationId} ({cameraName})
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleCaptureCamera}
                disabled={acquiringFrame}
                className="btn-ghost text-xs py-1 px-2.5 flex items-center gap-1.5"
                title="Acquire live camera snapshot as backdrop"
              >
                <Camera className={`w-3.5 h-3.5 ${acquiringFrame ? 'animate-spin' : ''}`} />
                {acquiringFrame ? 'Capturing...' : 'Live Backdrop'}
              </button>

              <label className="btn-ghost text-xs py-1 px-2.5 flex items-center gap-1.5 cursor-pointer">
                <Upload className="w-3.5 h-3.5" />
                Upload Image
                <input type="file" accept="image/*" onChange={handleFileUpload} className="hidden" />
              </label>

              <button
                onClick={handleAddRoi}
                className="btn-primary text-xs py-1 px-3 flex items-center gap-1"
              >
                <Plus className="w-3.5 h-3.5" />
                Add Zone
              </button>
            </div>
          </div>

          {/* Interactive Canvas Viewport */}
          <div
            ref={containerRef}
            className="relative h-[520px] bg-black/95 rounded-xl overflow-hidden flex items-center justify-center border border-surface-700 select-none cursor-crosshair"
            onClick={() => setSelectedIdx(null)}
          >
            {backdropUrl && (
              <img
                src={backdropUrl}
                alt="Camera Backdrop"
                className="absolute inset-0 w-full h-full object-contain pointer-events-none opacity-60"
              />
            )}

            <svg
              className="absolute inset-0 w-full h-full"
              viewBox={`0 0 ${NATIVE_W} ${NATIVE_H}`}
              preserveAspectRatio="none"
            >
              <defs>
                <pattern id="maskHatch" width="20" height="20" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
                  <line x1="0" y1="0" x2="0" y2="20" stroke="#f43f5e" strokeWidth="3" opacity="0.4" />
                </pattern>
              </defs>

              {rois.map((roi, idx) => {
                const isSelected = selectedIdx === idx
                const isMask = roi.type === 'mask'
                const strokeColor = isMask ? '#f43f5e' : isSelected ? '#6366f1' : '#3b82f6'
                const fillColor = isMask ? 'url(#maskHatch)' : isSelected ? 'rgba(99, 102, 241, 0.25)' : 'rgba(59, 130, 246, 0.15)'

                return (
                  <g key={idx}>
                    {/* Main Draggable Bounding Box */}
                    <rect
                      x={roi.x}
                      y={roi.y}
                      width={roi.width}
                      height={roi.height}
                      fill={fillColor}
                      stroke={strokeColor}
                      strokeWidth={isSelected ? '5' : '3'}
                      strokeDasharray={roi.active === false ? '10 10' : 'none'}
                      className="cursor-move"
                      onMouseDown={(e) => handleMouseDown(e, idx)}
                    />

                    {/* Zone Name Label Tag */}
                    <rect
                      x={roi.x}
                      y={Math.max(0, roi.y - 36)}
                      width={Math.max(160, roi.name.length * 14 + 50)}
                      height="32"
                      fill="rgba(15, 23, 42, 0.9)"
                      stroke={strokeColor}
                      strokeWidth="2"
                      rx="4"
                    />
                    <text
                      x={roi.x + 10}
                      y={Math.max(22, roi.y - 14)}
                      fill={isMask ? '#f87171' : '#a5b4fc'}
                      fontSize="18"
                      fontFamily="monospace"
                      fontWeight="bold"
                    >
                      {isMask ? '[MASK] ' : ''}{roi.name}
                    </text>

                    {/* Resize Handles for Selected ROI */}
                    {isSelected && (
                      <>
                        <circle
                          cx={roi.x}
                          cy={roi.y}
                          r="10"
                          fill="#ffffff"
                          stroke="#6366f1"
                          strokeWidth="3"
                          className="cursor-nwse-resize"
                          onMouseDown={(e) => handleMouseDown(e, idx, 'tl')}
                        />
                        <circle
                          cx={roi.x + roi.width}
                          cy={roi.y + roi.height}
                          r="10"
                          fill="#ffffff"
                          stroke="#6366f1"
                          strokeWidth="3"
                          className="cursor-nwse-resize"
                          onMouseDown={(e) => handleMouseDown(e, idx, 'br')}
                        />
                      </>
                    )}
                  </g>
                )
              })}
            </svg>

            <div className="absolute top-4 left-4 bg-black/80 px-3 py-1.5 rounded-lg text-xs font-mono text-zinc-300 border border-white/10 flex items-center gap-3">
              <span>Drag to move</span>
              <span>•</span>
              <span>White handles to resize</span>
              <span>•</span>
              <span>Native 1920x1080</span>
            </div>
          </div>
        </div>

        {/* ROI Parameter Adjuster Form */}
        <div className="card p-6 space-y-6 flex flex-col justify-between">
          <form onSubmit={handleSave} className="space-y-6">
            <div className="flex items-center justify-between border-b border-surface-700 pb-3">
              <div className="text-sm font-semibold uppercase tracking-wide text-zinc-400 flex items-center gap-2">
                <Target className="w-4 h-4 text-primary-400" />
                Configured Zones ({rois.length})
              </div>
              <button
                type="button"
                onClick={handleAddRoi}
                className="btn-ghost text-xs py-1 px-2.5 flex items-center gap-1"
              >
                <Plus className="w-3.5 h-3.5" />
                Add
              </button>
            </div>

            {loading ? (
              <div className="text-center py-10 text-zinc-400">Loading ROIs...</div>
            ) : (
              <div className="space-y-4 max-h-[360px] overflow-y-auto pr-2">
                {rois.map((roi, idx) => {
                  const isSelected = selectedIdx === idx
                  return (
                    <div
                      key={idx}
                      onClick={() => setSelectedIdx(idx)}
                      className={`p-4 rounded-xl border transition-all cursor-pointer ${
                        isSelected
                          ? 'bg-surface-800 border-primary-500 shadow-md shadow-primary-500/10'
                          : 'bg-surface-900 border-surface-700 hover:border-surface-600'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-3">
                        <input
                          type="text"
                          value={roi.name}
                          onChange={(e) => handleRoiChange(idx, 'name', e.target.value)}
                          className="text-xs font-semibold w-36 py-1 px-2"
                        />
                        <div className="flex items-center gap-2">
                          <select
                            value={roi.type || 'inspection'}
                            onChange={(e) => handleRoiChange(idx, 'type', e.target.value)}
                            className="text-[11px] py-1 px-1.5 bg-surface-800"
                          >
                            <option value="inspection">Inspect</option>
                            <option value="mask">Mask Zone</option>
                          </select>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              handleDeleteRoi(idx)
                            }}
                            className="text-zinc-500 hover:text-danger-400 p-1"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                        <div>
                          <label className="text-[10px] text-zinc-500">X (px)</label>
                          <input
                            type="number"
                            value={roi.x}
                            onChange={(e) => handleRoiChange(idx, 'x', Number(e.target.value))}
                            className="w-full text-xs py-1 px-2"
                          />
                        </div>
                        <div>
                          <label className="text-[10px] text-zinc-500">Y (px)</label>
                          <input
                            type="number"
                            value={roi.y}
                            onChange={(e) => handleRoiChange(idx, 'y', Number(e.target.value))}
                            className="w-full text-xs py-1 px-2"
                          />
                        </div>
                        <div>
                          <label className="text-[10px] text-zinc-500">Width (px)</label>
                          <input
                            type="number"
                            value={roi.width}
                            onChange={(e) => handleRoiChange(idx, 'width', Number(e.target.value))}
                            className="w-full text-xs py-1 px-2"
                          />
                        </div>
                        <div>
                          <label className="text-[10px] text-zinc-500">Height (px)</label>
                          <input
                            type="number"
                            value={roi.height}
                            onChange={(e) => handleRoiChange(idx, 'height', Number(e.target.value))}
                            className="w-full text-xs py-1 px-2"
                          />
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}

            <button
              type="submit"
              disabled={saving}
              className="w-full btn-primary py-3 flex items-center justify-center gap-2 font-semibold shadow-lg shadow-primary-600/30"
            >
              <Save className="w-4 h-4" />
              {saving ? 'Syncing with Station...' : 'Save & Sync ROIs'}
            </button>
          </form>

          {successMsg && (
            <div className="p-3 bg-success-900/20 border border-success-500 rounded-xl text-success-400 text-xs flex items-center gap-2">
              <CheckCircle className="w-4 h-4 flex-shrink-0" />
              {successMsg}
            </div>
          )}

          {error && (
            <div className="p-3 bg-danger-900/20 border border-danger-500 rounded-xl text-danger-400 text-xs flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              {error}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

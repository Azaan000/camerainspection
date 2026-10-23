import { useState, useEffect } from 'react'
import { apiClient } from '../lib/api'
import { Target, Save, RefreshCw, CheckCircle, Sliders } from 'lucide-react'

export default function ROIEditor() {
  const [stationId, setStationId] = useState('STATION_1')
  const [cameraName, setCameraName] = useState('main')
  const [rois, setRois] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const fetchRois = async () => {
    setLoading(true)
    setError(null)
    setSuccessMsg(null)
    try {
      const data: any = await apiClient.getStationROIs(stationId, cameraName)
      if (Array.isArray(data)) {
        setRois(data)
      } else if (data && data.rois) {
        setRois(data.rois)
      } else {
        setRois([
          { name: 'leather_center', x: 100, y: 150, width: 800, height: 600, active: true },
          { name: 'seam_left', x: 50, y: 100, width: 300, height: 800, active: true },
        ])
      }
    } catch (err: any) {
      console.error('Failed to fetch ROIs:', err)
      // Default fallback ROIs
      setRois([
        { name: 'primary_inspection_zone', x: 120, y: 100, width: 1024, height: 768, active: true },
        { name: 'edge_stitching', x: 50, y: 50, width: 400, height: 900, active: true },
      ])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchRois()
  }, [stationId, cameraName])

  const handleRoiChange = (index: number, field: string, value: any) => {
    const updated = [...rois]
    updated[index] = { ...updated[index], [field]: value }
    setRois(updated)
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    setSuccessMsg(null)
    try {
      await apiClient.updateStationROIs(stationId, { camera_name: cameraName, rois })
      setSuccessMsg('ROI configuration successfully updated and synced with inspection edge nodes.')
    } catch (err: any) {
      setError(err.message || 'Failed to save ROI configuration')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="font-bold text-white text-3xl flex items-center gap-3">
            <Target className="w-8 h-8 text-primary-400" />
            Interactive ROI & Inspection Zone Editor
          </h2>
          <p className="text-sm text-zinc-400 mt-1">Configure bounding boxes, masking areas, and inspection sub-zones per station and camera view</p>
        </div>
        <div className="flex items-center gap-3 bg-surface-800 p-2 rounded-xl border border-surface-700">
          <select
            value={stationId}
            onChange={(e) => setStationId(e.target.value)}
            className="text-xs py-1.5 px-3"
          >
            <option value="STATION_1">Station 1: Leather Surface</option>
            <option value="STATION_2">Station 2: Stitch & Seam</option>
            <option value="STATION_3">Station 3: Plastic Shield</option>
            <option value="STATION_4">Station 4: Final Fit</option>
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
        {/* ROI Canvas Preview Area */}
        <div className="lg:col-span-2 card p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-surface-700 pb-4">
            <div className="text-sm font-semibold uppercase tracking-wider text-zinc-400 flex items-center gap-2">
              <Sliders className="w-4 h-4 text-primary-400" />
              ROI Preview Map — {stationId} ({cameraName})
            </div>
            <div className="text-xs font-mono text-zinc-400">Resolution: 1920x1080</div>
          </div>

          <div className="relative h-[480px] bg-black/90 rounded-xl overflow-hidden flex items-center justify-center border border-surface-700">
            {/* Visual SVG overlay representing ROIs */}
            <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 1920 1080" preserveAspectRatio="none">
              <rect x="0" y="0" width="1920" height="1080" fill="rgba(0,0,0,0.5)" />
              {rois.map((roi, idx) => (
                <g key={idx}>
                  <rect
                    x={roi.x || 0}
                    y={roi.y || 0}
                    width={roi.width || 200}
                    height={roi.height || 200}
                    fill={roi.active !== false ? 'rgba(59, 130, 246, 0.15)' : 'rgba(100, 100, 100, 0.1)'}
                    stroke={roi.active !== false ? '#3b82f6' : '#71717a'}
                    strokeWidth="4"
                    strokeDasharray={roi.active !== false ? 'none' : '8 8'}
                  />
                  <text
                    x={(roi.x || 0) + 15}
                    y={(roi.y || 0) + 35}
                    fill="white"
                    fontSize="24"
                    fontFamily="monospace"
                    fontWeight="bold"
                  >
                    {roi.name || `ROI #${idx + 1}`}
                  </text>
                </g>
              ))}
            </svg>
            <div className="text-zinc-500 text-sm z-10 bg-surface-900/80 px-4 py-2 rounded-xl backdrop-blur border border-surface-700">
              Interactive Bounding Box Overlay Active
            </div>
          </div>
        </div>

        {/* ROI Parameter Adjuster Form */}
        <div className="card p-6 space-y-6 flex flex-col justify-between">
          <form onSubmit={handleSave} className="space-y-6">
            <div className="text-sm font-semibold uppercase tracking-wide text-zinc-400 flex items-center gap-2">
              <Target className="w-4 h-4 text-primary-400" />
              Configure ROI Zones ({rois.length})
            </div>

            {loading ? (
              <div className="text-center py-10 text-zinc-400">Loading ROIs...</div>
            ) : (
              <div className="space-y-4 max-h-[380px] overflow-y-auto pr-2">
                {rois.map((roi, idx) => (
                  <div key={idx} className="bg-surface-900 p-4 rounded-xl border border-surface-700 space-y-3">
                    <div className="flex items-center justify-between">
                      <input
                        type="text"
                        value={roi.name || ''}
                        onChange={(e) => handleRoiChange(idx, 'name', e.target.value)}
                        className="text-xs font-semibold w-36"
                      />
                      <label className="flex items-center gap-2 text-xs text-zinc-400 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={roi.active !== false}
                          onChange={(e) => handleRoiChange(idx, 'active', e.target.checked)}
                          className="rounded accent-primary-500"
                        />
                        Active
                      </label>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                      <div>
                        <label className="text-[10px] text-zinc-500">X Offset</label>
                        <input
                          type="number"
                          value={roi.x || 0}
                          onChange={(e) => handleRoiChange(idx, 'x', Number(e.target.value))}
                          className="w-full text-xs"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] text-zinc-500">Y Offset</label>
                        <input
                          type="number"
                          value={roi.y || 0}
                          onChange={(e) => handleRoiChange(idx, 'y', Number(e.target.value))}
                          className="w-full text-xs"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] text-zinc-500">Width</label>
                        <input
                          type="number"
                          value={roi.width || 0}
                          onChange={(e) => handleRoiChange(idx, 'width', Number(e.target.value))}
                          className="w-full text-xs"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] text-zinc-500">Height</label>
                        <input
                          type="number"
                          value={roi.height || 0}
                          onChange={(e) => handleRoiChange(idx, 'height', Number(e.target.value))}
                          className="w-full text-xs"
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {error && <div className="p-3 bg-danger-900/20 text-danger-400 text-xs rounded-xl border border-danger-500">{error}</div>}
            {successMsg && <div className="p-3 bg-success-900/20 text-success-400 text-xs rounded-xl border border-success-500 flex items-center gap-2"><CheckCircle className="w-4 h-4 flex-shrink-0" />{successMsg}</div>}

            <button
              type="submit"
              disabled={saving}
              className="w-full btn-primary py-3 flex items-center justify-center gap-2 text-sm font-semibold shadow-lg shadow-primary-600/30"
            >
              <Save className="w-4 h-4" />
              {saving ? 'Saving ROIs...' : 'Save & Sync ROIs'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}

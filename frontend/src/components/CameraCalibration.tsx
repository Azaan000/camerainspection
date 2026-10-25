import { useState, useEffect } from 'react'
import { apiClient, type CalibrationsListResponse } from '../lib/api'
import {
  Crosshair,
  Camera,
  RefreshCw,
  CheckCircle,
  AlertTriangle,
  Upload,
  Sliders,
  Award,
  Layers,
} from 'lucide-react'

export default function CameraCalibration() {
  const [cameraName, setCameraName] = useState('station1_cushion_cam')
  const [category, setCategory] = useState<'leather' | 'stitch' | 'plastic' | 'mechanism' | 'generic'>('leather')
  const [patternType, setPatternType] = useState('checkerboard')
  const [squareSizeMm, setSquareSizeMm] = useState(10.0)
  const [innerCols, setInnerCols] = useState(7)
  const [innerRows, setInnerRows] = useState(5)
  const [operatorId, setOperatorId] = useState('TECH_OP_04')

  // Acquisition mode: live stream or file upload
  const [acquisitionMode, setAcquisitionMode] = useState<'live' | 'file'>('live')
  const [deviceIndex, setDeviceIndex] = useState(0)
  const [cameraUrl, setCameraUrl] = useState('')
  const [uploadedFile, setUploadedFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)

  // Calibration action state
  const [calibrating, setCalibrating] = useState(false)
  const [lastResult, setLastResult] = useState<any | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Calibrations registry
  const [calibrationsData, setCalibrationsData] = useState<CalibrationsListResponse | null>(null)
  const [loadingList, setLoadingList] = useState(false)

  const fetchCalibrations = async () => {
    setLoadingList(true)
    try {
      const data = await apiClient.getCalibrations()
      setCalibrationsData(data)
    } catch (err: any) {
      console.warn('Failed to load calibrations list:', err)
    } finally {
      setLoadingList(false)
    }
  }

  useEffect(() => {
    fetchCalibrations()
  }, [])

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const f = e.target.files[0]
      setUploadedFile(f)
      setPreviewUrl(URL.createObjectURL(f))
      setError(null)
    }
  }

  const handleCaptureLive = async () => {
    setError(null)
    try {
      const timestamp = Date.now()
      const base = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
      const url = cameraUrl.trim()
        ? `${base}/api/v1/camera/snapshot?camera_url=${encodeURIComponent(cameraUrl.trim())}&_t=${timestamp}`
        : `${base}/api/v1/camera/snapshot?device_index=${deviceIndex}&_t=${timestamp}`
      setPreviewUrl(url)
    } catch (err: any) {
      setError('Could not capture frame from live camera')
    }
  }

  const handleRunCalibration = async (e: React.FormEvent) => {
    e.preventDefault()
    setCalibrating(true)
    setError(null)
    setLastResult(null)

    try {
      let imageBuffer: ArrayBuffer | undefined = undefined
      if (acquisitionMode === 'file' && uploadedFile) {
        imageBuffer = await uploadedFile.arrayBuffer()
      }

      const res = await apiClient.calibrateCamera({
        camera_name: cameraName.trim(),
        category,
        pattern_type: patternType,
        square_size_mm: squareSizeMm,
        inner_cols: innerCols,
        inner_rows: innerRows,
        operator_id: operatorId.trim(),
        device_index: acquisitionMode === 'live' && !cameraUrl.trim() ? deviceIndex : undefined,
        camera_url: acquisitionMode === 'live' && cameraUrl.trim() ? cameraUrl.trim() : undefined,
        imageBuffer,
      })

      setLastResult(res)
      fetchCalibrations()
    } catch (err: any) {
      setError(err.message || 'Calibration calculation failed. Ensure checkerboard corners are fully visible.')
    } finally {
      setCalibrating(false)
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="font-bold text-white text-3xl flex items-center gap-3">
            <Crosshair className="w-8 h-8 text-primary-400" />
            Camera Metrological Calibration
          </h2>
          <p className="text-sm text-zinc-400 mt-1">
            Sub-pixel checkerboard corner detection, physical mm-to-pixel scaling factor, and OEM resolution target validation
          </p>
        </div>
        <button
          onClick={fetchCalibrations}
          className="btn-ghost text-xs py-2 px-3 flex items-center gap-1.5 self-start"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loadingList ? 'animate-spin' : ''}`} />
          Refresh Records
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Wizard Form */}
        <div className="card p-8 space-y-6">
          <div className="text-sm font-semibold uppercase tracking-wide text-zinc-400 flex items-center gap-2 border-b border-surface-700 pb-3">
            <Sliders className="w-4 h-4 text-primary-400" />
            Calibration Setup & Target Parameters
          </div>

          <form onSubmit={handleRunCalibration} className="space-y-5">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Camera View ID</label>
                <input
                  type="text"
                  value={cameraName}
                  onChange={(e) => setCameraName(e.target.value)}
                  placeholder="station1_cushion_cam"
                  className="w-full text-xs"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Inspection Category</label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value as any)}
                  className="w-full text-xs"
                >
                  <option value="leather">Leather Surface (0.15 - 0.20 mm/px)</option>
                  <option value="stitch">Stitch & Seam (0.08 - 0.10 mm/px)</option>
                  <option value="plastic">Plastic Components (0.15 - 0.25 mm/px)</option>
                  <option value="mechanism">Mechanism & Track (0.12 - 0.22 mm/px)</option>
                  <option value="generic">Generic Surface</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Square Size (mm)</label>
                <input
                  type="number"
                  step="0.5"
                  value={squareSizeMm}
                  onChange={(e) => setSquareSizeMm(Number(e.target.value))}
                  className="w-full text-xs"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Inner Cols</label>
                <input
                  type="number"
                  value={innerCols}
                  onChange={(e) => setInnerCols(Number(e.target.value))}
                  className="w-full text-xs"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Inner Rows</label>
                <input
                  type="number"
                  value={innerRows}
                  onChange={(e) => setInnerRows(Number(e.target.value))}
                  className="w-full text-xs"
                  required
                />
              </div>
            </div>

            {/* Target Pattern & Operator */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Target Pattern Type</label>
                <select
                  value={patternType}
                  onChange={(e) => setPatternType(e.target.value)}
                  className="w-full text-xs"
                >
                  <option value="checkerboard">OpenCV Chessboard Grid</option>
                  <option value="two_marks">Fiducial Twin Mark Distance</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Certified Inspector ID</label>
                <input
                  type="text"
                  value={operatorId}
                  onChange={(e) => setOperatorId(e.target.value)}
                  className="w-full text-xs"
                  required
                />
              </div>
            </div>

            {/* Acquisition Mode Switch */}
            <div className="p-4 bg-surface-900 rounded-xl border border-surface-700 space-y-4">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-zinc-300">Calibration Frame Acquisition</span>
                <div className="flex bg-surface-800 rounded p-0.5 border border-surface-700">
                  <button
                    type="button"
                    onClick={() => setAcquisitionMode('live')}
                    className={`px-3 py-1 rounded text-xs font-medium transition-all ${
                      acquisitionMode === 'live' ? 'bg-primary-600 text-white' : 'text-zinc-400'
                    }`}
                  >
                    Live Camera
                  </button>
                  <button
                    type="button"
                    onClick={() => setAcquisitionMode('file')}
                    className={`px-3 py-1 rounded text-xs font-medium transition-all ${
                      acquisitionMode === 'file' ? 'bg-primary-600 text-white' : 'text-zinc-400'
                    }`}
                  >
                    Upload File
                  </button>
                </div>
              </div>

              {acquisitionMode === 'live' ? (
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-[11px] text-zinc-400 mb-1">Device Index</label>
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
                    <div>
                      <label className="block text-[11px] text-zinc-400 mb-1">Or IP/Phone Stream URL</label>
                      <input
                        type="text"
                        value={cameraUrl}
                        onChange={(e) => setCameraUrl(e.target.value)}
                        placeholder="http://192.168.1.50:8080/video"
                        className="w-full text-xs"
                      />
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={handleCaptureLive}
                    className="w-full btn-ghost text-xs py-2 flex items-center justify-center gap-1.5"
                  >
                    <Camera className="w-3.5 h-3.5 text-primary-400" />
                    Preview Target Live Frame
                  </button>
                </div>
              ) : (
                <div className="border border-dashed border-surface-700 rounded-xl p-4 text-center cursor-pointer hover:border-primary-500 relative bg-surface-800">
                  <input
                    type="file"
                    accept="image/*"
                    onChange={handleFileChange}
                    className="absolute inset-0 opacity-0 cursor-pointer"
                  />
                  <Upload className="w-6 h-6 text-zinc-400 mx-auto mb-1" />
                  <div className="text-xs text-zinc-300">
                    {uploadedFile ? uploadedFile.name : 'Select or drop checkerboard image'}
                  </div>
                </div>
              )}
            </div>

            <button
              type="submit"
              disabled={calibrating}
              className="w-full btn-primary py-3 flex items-center justify-center gap-2 text-base font-semibold shadow-lg shadow-primary-600/30"
            >
              <Crosshair className={`w-5 h-5 ${calibrating ? 'animate-spin' : ''}`} />
              {calibrating ? 'Computing Sub-Pixel Corners...' : 'Execute Camera Calibration'}
            </button>
          </form>

          {error && (
            <div className="p-4 rounded-xl bg-danger-900/20 border border-danger-500 text-danger-400 text-xs flex items-start gap-2.5">
              <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <div>{error}</div>
            </div>
          )}
        </div>

        {/* Live Preview & Result Validation */}
        <div className="card p-8 space-y-6 flex flex-col justify-between">
          <div className="space-y-4">
            <div className="text-sm font-semibold uppercase tracking-wide text-zinc-400 flex items-center gap-2 border-b border-surface-700 pb-3">
              <Award className="w-4 h-4 text-primary-400" />
              Calibration Preview & Target Validation
            </div>

            {/* Viewport */}
            <div className="h-64 rounded-xl bg-black/80 border border-surface-700 overflow-hidden flex items-center justify-center relative">
              {previewUrl ? (
                <img src={previewUrl} alt="Calibration Target Frame" className="w-full h-full object-contain" />
              ) : (
                <div className="text-center text-zinc-500 text-xs space-y-2">
                  <Crosshair className="w-8 h-8 mx-auto text-zinc-600" />
                  <p>Capture a live target or upload a checkerboard image to preview</p>
                </div>
              )}
            </div>

            {/* Results Display */}
            {lastResult && (
              <div className="bg-surface-900 p-5 rounded-xl border border-surface-700 space-y-4">
                <div className="flex items-center justify-between border-b border-surface-700 pb-3">
                  <div>
                    <div className="text-[10px] text-zinc-400 uppercase font-semibold">Camera</div>
                    <div className="text-sm font-bold text-white">{lastResult.camera_name}</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-zinc-400 uppercase font-semibold text-right">Target Range</div>
                    <div className="text-xs font-mono text-zinc-300">
                      {lastResult.target_range_mm ? `${lastResult.target_range_mm[0]} - ${lastResult.target_range_mm[1]} mm/px` : 'N/A'}
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-[10px] text-zinc-400 uppercase font-semibold">Pixel Resolution</div>
                    <div className="text-2xl font-mono font-bold text-primary-400">
                      {lastResult.pixel_size_mm.toFixed(4)}{' '}
                      <span className="text-xs text-zinc-400 font-normal">mm/px</span>
                    </div>
                  </div>
                  <div>
                    {lastResult.in_target_range ? (
                      <span className="badge-pass px-3 py-1 text-xs font-bold flex items-center gap-1">
                        <CheckCircle className="w-3.5 h-3.5" />
                        IN TOLERANCE
                      </span>
                    ) : (
                      <span className="badge-review px-3 py-1 text-xs font-bold flex items-center gap-1">
                        <AlertTriangle className="w-3.5 h-3.5" />
                        OUT OF TARGET RANGE
                      </span>
                    )}
                  </div>
                </div>

                <div className="text-xs text-zinc-400">
                  Calibration record persisted to <code className="text-zinc-200">{lastResult.saved_file}</code>
                </div>
              </div>
            )}
          </div>

          <div className="p-4 bg-surface-900 rounded-xl border border-surface-700 text-xs text-zinc-400 space-y-2">
            <div className="font-semibold text-white flex items-center gap-1.5">
              <CheckCircle className="w-4 h-4 text-primary-400" />
              Automotive Metrology Standards:
            </div>
            <p>
              Cameras must be calibrated every 30 days or after any physical lens adjustments. Ensure the checkerboard covers at least 40% of the field of view with uniform illumination.
            </p>
          </div>
        </div>
      </div>

      {/* Calibration Registry Table */}
      <div className="card p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-surface-700 pb-3">
          <div className="text-sm font-semibold uppercase tracking-wider text-zinc-400 flex items-center gap-2">
            <Layers className="w-4 h-4 text-primary-400" />
            Active Calibration Records ({calibrationsData?.calibrations.length || 0})
          </div>
        </div>

        {loadingList ? (
          <div className="text-center py-8 text-zinc-400 text-xs">Loading calibration records...</div>
        ) : calibrationsData && calibrationsData.calibrations.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-surface-900 text-zinc-400 uppercase text-[10px] tracking-wider border-b border-surface-700">
                <tr>
                  <th className="p-3">Camera Name</th>
                  <th className="p-3">Category</th>
                  <th className="p-3">Pixel Size (mm/px)</th>
                  <th className="p-3">Target Range</th>
                  <th className="p-3">Calibrated At</th>
                  <th className="p-3">Operator</th>
                  <th className="p-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-700/60 font-mono">
                {calibrationsData.calibrations.map((cal, i) => {
                  const target = calibrationsData.resolution_targets?.[cal.category]
                  const inRange = target ? cal.pixel_size_mm >= target[0] && cal.pixel_size_mm <= target[1] : true

                  return (
                    <tr key={i} className="hover:bg-surface-800/50 transition-colors">
                      <td className="p-3 font-semibold text-white font-sans">{cal.camera_name}</td>
                      <td className="p-3 capitalize">{cal.category}</td>
                      <td className="p-3 font-bold text-primary-400">{cal.pixel_size_mm.toFixed(4)}</td>
                      <td className="p-3 text-zinc-400">
                        {target ? `${target[0]} - ${target[1]}` : '—'}
                      </td>
                      <td className="p-3 text-zinc-400 font-sans">
                        {new Date(cal.calibrated_at).toLocaleDateString()}
                      </td>
                      <td className="p-3 text-zinc-300 font-sans">{cal.operator_id}</td>
                      <td className="p-3 font-sans">
                        {inRange ? (
                          <span className="badge-pass px-2 py-0.5 text-[10px] font-bold">VALID</span>
                        ) : (
                          <span className="badge-review px-2 py-0.5 text-[10px] font-bold">OUT OF RANGE</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-8 text-zinc-500 text-xs">
            No camera calibration records found on disk. Run calibration above to establish baseline.
          </div>
        )}
      </div>
    </div>
  )
}

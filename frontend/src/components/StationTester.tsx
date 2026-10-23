import { useState } from 'react'
import { apiClient } from '../lib/api'
import { Upload, Camera, CheckCircle, Sliders, Eye } from 'lucide-react'

export default function StationTester() {
  const [selectedStation, setSelectedStation] = useState('STATION_1')
  const [variantId, setVariantId] = useState('FRONT_LH_BLACK')
  const [cameraName, setCameraName] = useState('main')
  const [threshold, setThreshold] = useState(0.55)
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showAnnotated, setShowAnnotated] = useState(true)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const f = e.target.files[0]
      setFile(f)
      setPreviewUrl(URL.createObjectURL(f))
      setResult(null)
      setError(null)
    }
  }

  const handleTest = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) {
      alert('Please select an image file first.')
      return
    }

    setLoading(true)
    setError(null)
    try {
      const buffer = await file.arrayBuffer()
      const url = `/api/v1/stations/${selectedStation}/inject-image?camera_name=${encodeURIComponent(cameraName)}&variant_id=${encodeURIComponent(variantId)}`

      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'X-API-Key': apiClient.getApiKey() || 'sg_dev_secret_key_2026',
          'Content-Type': 'application/octet-stream',
        },
        body: buffer,
      })

      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Server returned ${res.status}: ${errText}`)
      }

      const data = await res.json()
      setResult(data)
      setShowAnnotated(true)
    } catch (err: any) {
      console.error('Station test failed:', err)
      setError(err.message || 'Failed to process inspection test')
    } finally {
      setLoading(false)
    }
  }

  const getOutcomeBadge = (outcome: string) => {
    switch (outcome?.toUpperCase()) {
      case 'PASS':
        return <span className="badge-pass px-3 py-1 text-sm">PASS</span>
      case 'REVIEW':
        return <span className="badge-review px-3 py-1 text-sm">REVIEW</span>
      case 'FAIL':
        return <span className="badge-fail px-3 py-1 text-sm">FAIL</span>
      default:
        return <span className="px-3 py-1 rounded-full text-xs font-semibold bg-zinc-800 text-zinc-300">{outcome}</span>
    }
  }

  const activeDisplayUrl = showAnnotated && result?.annotated_image_url
    ? (result.annotated_image_url.startsWith('http') ? result.annotated_image_url : `${import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'}${result.annotated_image_url}`)
    : previewUrl

  return (
    <div className="space-y-8">
      <div>
        <h2 className="font-bold text-white text-3xl">Manual Station Testing & Image Injector</h2>
        <p className="text-sm text-zinc-400 mt-1">Upload an inspection image, select station parameters, and test AI defect detection models & limits</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Configuration & Upload Form */}
        <div className="card p-8 space-y-6">
          <div className="text-sm font-semibold uppercase tracking-wide text-zinc-400 flex items-center gap-2">
            <Sliders className="w-4 h-4 text-primary-400" />
            Inspection Parameters
          </div>

          <form onSubmit={handleTest} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-zinc-400 mb-2">Target Station</label>
              <select
                value={selectedStation}
                onChange={(e) => setSelectedStation(e.target.value)}
                className="w-full text-sm"
              >
                <option value="STATION_1">Station 1: Leather Surface Inspection</option>
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
                <label className="block text-sm font-medium text-zinc-400 mb-2">Camera / View</label>
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
              <label className="block text-sm font-medium text-zinc-400 mb-2">
                Anomaly Threshold ({threshold.toFixed(2)})
              </label>
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

            <button
              type="submit"
              disabled={loading || !file}
              className="w-full btn-primary py-3 flex items-center justify-center gap-2 text-base font-semibold shadow-lg shadow-primary-600/30"
            >
              <Camera className="w-5 h-5" />
              {loading ? 'Running AI Inference...' : 'Run Station Test'}
            </button>
          </form>

          {error && (
            <div className="p-4 rounded-xl bg-danger-900/20 border border-danger-500 text-danger-400 text-sm">
              {error}
            </div>
          )}
        </div>

        {/* Results & Inspection Output */}
        <div className="card p-8 space-y-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
                Inspection Result Output & Fault Overlay
              </div>
              {result && result.annotated_image_url && (
                <div className="flex items-center gap-2 bg-surface-900 p-1 rounded-lg border border-surface-700 text-xs">
                  <button
                    onClick={() => setShowAnnotated(false)}
                    className={`px-3 py-1 rounded-md font-medium transition-colors ${!showAnnotated ? 'bg-primary-600 text-white' : 'text-zinc-400 hover:text-white'}`}
                  >
                    Original
                  </button>
                  <button
                    onClick={() => setShowAnnotated(true)}
                    className={`px-3 py-1 rounded-md font-medium transition-colors flex items-center gap-1 ${showAnnotated ? 'bg-primary-600 text-white' : 'text-zinc-400 hover:text-white'}`}
                  >
                    <Eye className="w-3.5 h-3.5" />
                    Annotated Faults
                  </button>
                </div>
              )}
            </div>

            {activeDisplayUrl && (
              <div className="mb-6 rounded-xl overflow-hidden bg-black/60 h-64 flex items-center justify-center border border-surface-700 relative">
                <img src={activeDisplayUrl} alt="Inspection view" className="w-full h-full object-contain" />
              </div>
            )}

            {!result && !loading && (
              <div className="text-center py-16 text-zinc-500 bg-surface-900 rounded-2xl border border-surface-700">
                <Camera className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
                <p>Upload an image and run station test to view results & fault overlay.</p>
              </div>
            )}

            {loading && (
              <div className="text-center py-16 text-zinc-400 bg-surface-900 rounded-2xl border border-surface-700 space-y-3">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary-500 mx-auto" />
                <p className="text-sm font-medium">Executing PatchCore AI & Limits Evaluator...</p>
              </div>
            )}

            {result && !loading && (
              <div className="space-y-6 bg-surface-900 p-6 rounded-2xl border border-surface-700">
                <div className="flex items-center justify-between border-b border-surface-700 pb-4">
                  <div>
                    <div className="text-xs text-zinc-400 uppercase tracking-wider font-semibold">Station</div>
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
                      No defects detected. Clean surface verified.
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

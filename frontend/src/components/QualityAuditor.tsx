import { useState, useEffect } from 'react'
import { apiClient, type DefectRecord } from '../lib/api'
import { ShieldCheck, CheckCircle, RefreshCw, Filter } from 'lucide-react'

export default function QualityAuditor() {
  const [defects, setDefects] = useState<DefectRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedDefect, setSelectedDefect] = useState<DefectRecord | null>(null)
  const [inspectorId, setInspectorId] = useState('AUDITOR_01')
  const [notes, setNotes] = useState('')
  const [isFalsePositive, setIsFalsePositive] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const fetchDefects = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await apiClient.getDefectGallery({ limit: 50 })
      setDefects(data)
      if (data.length > 0 && !selectedDefect) {
        setSelectedDefect(data[0])
      }
    } catch (err: any) {
      console.error('Failed to load audit defects:', err)
      setError(err.message || 'Failed to load audit items')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchDefects()
  }, [])

  const handleSubmitFeedback = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedDefect) return

    setSubmitting(true)
    setError(null)
    setSuccessMsg(null)
    try {
      await apiClient.recordDefectFeedback(selectedDefect.id, {
        is_false_positive: isFalsePositive,
        inspector_notes: notes,
        inspector_id: inspectorId,
      })
      setSuccessMsg(`Feedback successfully recorded for defect #${selectedDefect.id}. Active learning model updated.`)
      setNotes('')
      fetchDefects()
    } catch (err: any) {
      setError(err.message || 'Failed to record auditor feedback')
    } finally {
      setSubmitting(false)
    }
  }

  const resolveImageUrl = (url: string) => {
    if (!url) return ''
    if (url.startsWith('http')) return url
    return `${import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'}${url}`
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="font-bold text-white text-3xl flex items-center gap-3">
            <ShieldCheck className="w-8 h-8 text-primary-400" />
            Quality Auditor Sampling & Active Learning
          </h2>
          <p className="text-sm text-zinc-400 mt-1">Audit AI inspection decisions, submit false-positive corrections, and feed training active learning loop</p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={fetchDefects} className="btn-ghost p-2.5" title="Refresh Audit Queue">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Defect Audit Queue List */}
        <div className="card p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-surface-700 pb-4">
            <div className="text-sm font-semibold uppercase tracking-wider text-zinc-400 flex items-center gap-2">
              <Filter className="w-4 h-4 text-primary-400" />
              Recent Defects ({defects.length})
            </div>
          </div>

          {loading ? (
            <div className="text-center py-16 text-zinc-400">Loading audit queue...</div>
          ) : defects.length === 0 ? (
            <div className="text-center py-16 text-zinc-500">No defects found for audit sampling.</div>
          ) : (
            <div className="space-y-3 max-h-[520px] overflow-y-auto pr-2">
              {defects.map((item) => (
                <div
                  key={item.id}
                  onClick={() => setSelectedDefect(item)}
                  className={`p-4 rounded-xl border cursor-pointer transition-all ${
                    selectedDefect?.id === item.id
                      ? 'bg-primary-900/30 border-primary-500 shadow-lg'
                      : 'bg-surface-900 border-surface-700 hover:border-surface-600'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-bold text-white text-sm capitalize">{item.defect_type?.replace(/_/g, ' ')}</span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      item.outcome === 'FAIL' ? 'bg-danger-900/40 text-danger-400 border border-danger-500/30' : 'bg-warning-900/40 text-warning-400 border border-warning-500/30'
                    }`}>
                      {item.outcome}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs text-zinc-400 font-mono">
                    <span>Station: {item.station_id}</span>
                    <span>Seat: {item.seat_id}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Auditor Verification Panel */}
        <div className="lg:col-span-2 card p-8 space-y-6">
          {selectedDefect ? (
            <div className="space-y-6">
              <div className="flex items-center justify-between border-b border-surface-700 pb-4">
                <div>
                  <div className="text-xs text-zinc-400 uppercase tracking-wider font-semibold">Audit Item #{selectedDefect.id}</div>
                  <h3 className="text-xl font-bold text-white capitalize mt-0.5">{selectedDefect.defect_type?.replace(/_/g, ' ')}</h3>
                </div>
                <div className="text-right">
                  <div className="text-xs text-zinc-400 font-mono">Confidence</div>
                  <div className="text-lg font-mono font-bold text-warning-400">
                    {((selectedDefect.confidence ?? 0) * 100).toFixed(1)}%
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="h-64 bg-black/80 rounded-xl overflow-hidden flex items-center justify-center border border-surface-700">
                  <img
                    src={resolveImageUrl(selectedDefect.image_url)}
                    alt="Defect Inspection"
                    className="w-full h-full object-contain"
                  />
                </div>

                <div className="space-y-4 bg-surface-900 p-6 rounded-xl border border-surface-700">
                  <div className="text-xs font-semibold uppercase tracking-wider text-zinc-400">Inspection Details</div>
                  <div className="space-y-2 text-xs font-mono text-zinc-300">
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Seat ID:</span>
                      <span className="text-white">{selectedDefect.seat_id}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Station ID:</span>
                      <span className="text-white">{selectedDefect.station_id}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Camera / View:</span>
                      <span className="text-white">{selectedDefect.camera_name || 'main'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Measured Delta:</span>
                      <span className="text-white">{selectedDefect.delta !== null ? selectedDefect.delta.toFixed(2) : 'N/A'}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Auditor Feedback Form */}
              <form onSubmit={handleSubmitFeedback} className="space-y-5 bg-surface-900 p-6 rounded-xl border border-surface-700">
                <div className="text-sm font-semibold uppercase tracking-wide text-zinc-400 flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-primary-400" />
                  Auditor Decision & Active Learning Feedback
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-zinc-400 mb-1">Auditor ID</label>
                    <input
                      type="text"
                      value={inspectorId}
                      onChange={(e) => setInspectorId(e.target.value)}
                      className="w-full text-xs"
                      required
                    />
                  </div>
                  <div className="flex items-center pt-5">
                    <label className="flex items-center gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={isFalsePositive}
                        onChange={(e) => setIsFalsePositive(e.target.checked)}
                        className="w-4 h-4 rounded accent-danger-500"
                      />
                      <span className="text-sm font-medium text-danger-400">Mark as False Positive (AI Error)</span>
                    </label>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1">Auditor Notes & Corrective Comments</label>
                  <textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Enter notes on defect severity, lighting variation, or root cause..."
                    rows={3}
                    className="w-full text-xs"
                  />
                </div>

                {error && <div className="p-3 bg-danger-900/20 text-danger-400 text-xs rounded-xl border border-danger-500">{error}</div>}
                {successMsg && <div className="p-3 bg-success-900/20 text-success-400 text-xs rounded-xl border border-success-500 flex items-center gap-2"><CheckCircle className="w-4 h-4 flex-shrink-0" />{successMsg}</div>}

                <button
                  type="submit"
                  disabled={submitting}
                  className="w-full btn-primary py-3 flex items-center justify-center gap-2 text-sm font-semibold shadow-lg shadow-primary-600/30"
                >
                  <CheckCircle className="w-4 h-4" />
                  {submitting ? 'Submitting Feedback...' : 'Submit Auditor Verification & Retrain Sample'}
                </button>
              </form>
            </div>
          ) : (
            <div className="text-center py-24 text-zinc-500">Select a defect item from the audit queue to inspect and verify.</div>
          )}
        </div>
      </div>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { apiClient } from '../lib/api'
import type { DefectRecord } from '../lib/api'
import { X, ShieldCheck } from 'lucide-react'

export default function DefectGallery() {
  const [defects, setDefects] = useState<DefectRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedStation, setSelectedStation] = useState('')
  const [selectedDefectType, setSelectedDefectType] = useState('')
  const [activeDefect, setActiveDefect] = useState<DefectRecord | null>(null)
  const [feedbackSuccess, setFeedbackSuccess] = useState(false)
  const [isFalsePositive, setIsFalsePositive] = useState(false)
  const [correctedType, setCorrectedType] = useState('')
  const [inspectorNotes, setInspectorNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const fetchDefects = async () => {
    setLoading(true)
    try {
      const data = await apiClient.getDefectGallery({
        limit: 48,
        station_id: selectedStation || undefined,
        defect_type: selectedDefectType || undefined,
      })
      setDefects(data)
    } catch (err) {
      console.error('Failed to fetch defects:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchDefects()
  }, [selectedStation, selectedDefectType])

  const handleFeedbackSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!activeDefect) return
    setSubmitting(true)
    try {
      await apiClient.recordDefectFeedback(activeDefect.id, {
        is_false_positive: isFalsePositive,
        new_defect_type: correctedType || undefined,
        inspector_notes: inspectorNotes || undefined,
      })
      setFeedbackSuccess(true)
      setTimeout(() => {
        setFeedbackSuccess(false)
        setActiveDefect(null)
      }, 1500)
    } catch (err) {
      console.error('Failed to record defect feedback:', err)
      alert('Failed to submit feedback')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-6">
        <div>
          <h2 className="font-bold text-white text-3xl">Defect Gallery & Active Learning</h2>
          <p className="text-sm text-zinc-400 mt-1">Review inspection defects and submit validator feedback for model retraining</p>
        </div>
        <div className="flex gap-4">
          <select
            value={selectedDefectType}
            onChange={(e) => setSelectedDefectType(e.target.value)}
            className="min-w-[160px] text-sm py-2"
          >
            <option value="">All Types</option>
            <option value="scratch">Scratch</option>
            <option value="stain">Stain</option>
            <option value="cut">Cut</option>
            <option value="pinhole">Pinhole</option>
            <option value="broken_thread">Broken Thread</option>
            <option value="skip_stitch">Skip Stitch</option>
            <option value="wrong_color">Wrong Color</option>
            <option value="shield_gap">Shield Gap</option>
            <option value="recliner_angle">Recliner Angle</option>
          </select>
          <select
            value={selectedStation}
            onChange={(e) => setSelectedStation(e.target.value)}
            className="min-w-[160px] text-sm py-2"
          >
            <option value="">All Stations</option>
            <option value="STATION_1">Station 1</option>
            <option value="STATION_2">Station 2</option>
            <option value="STATION_3">Station 3</option>
            <option value="STATION_4">Station 4</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-20 text-zinc-500">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500 mx-auto mb-4" />
          <p>Loading defect gallery...</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {defects.length === 0 ? (
            <div className="col-span-full text-center py-20 text-zinc-500">
              No defects found matching criteria
            </div>
          ) : (
            defects.map((defect) => {
              const imgUrl = defect.image_url.startsWith('http')
                ? defect.image_url
                : `${import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'}${defect.image_url}`

              return (
                <div
                  key={defect.id}
                  onClick={() => {
                    setActiveDefect(defect)
                    setIsFalsePositive(false)
                    setCorrectedType('')
                    setInspectorNotes('')
                  }}
                  className="bg-surface-800 border border-surface-700 rounded-2xl overflow-hidden hover:transform hover:-translate-y-1 hover:shadow-2xl transition-all duration-200 cursor-pointer group flex flex-col justify-between"
                >
                  <div className="relative h-48 bg-black/50 flex items-center justify-center overflow-hidden">
                    <img
                      src={imgUrl}
                      alt={defect.defect_type}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    />
                    <div className="absolute top-3 right-3">
                      <span
                        className={`badge ${
                          defect.outcome === 'FAIL'
                            ? 'badge-fail'
                            : defect.outcome === 'REVIEW'
                            ? 'badge-review'
                            : 'badge-pass'
                        }`}
                      >
                        {defect.outcome}
                      </span>
                    </div>
                  </div>
                  <div className="p-5 space-y-3">
                    <div className="flex items-start justify-between">
                      <h3 className="font-semibold text-white text-base capitalize">
                        {defect.defect_type.replace(/_/g, ' ')}
                      </h3>
                      {defect.confidence && (
                        <span className="text-xs text-zinc-400 font-mono">
                          {(defect.confidence * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>
                    <div className="text-sm text-zinc-400 space-y-1">
                      <div className="flex justify-between">
                        <span>Seat:</span>
                        <span className="font-mono text-primary-400">{defect.seat_id}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Station:</span>
                        <span className="text-white">{defect.station_id.replace('STATION_', '')}</span>
                      </div>
                      {defect.delta !== null && defect.delta !== undefined && (
                        <div className="flex justify-between">
                          <span>Delta:</span>
                          <span className="font-mono text-warning-400">{defect.delta > 0 ? `+${defect.delta}` : defect.delta} {defect.unit}</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )
            })
          )}
        </div>
      )}

      {/* Defect Detail & Feedback Modal */}
      {activeDefect && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="card max-w-2xl w-full p-6 space-y-6 bg-surface-900 border-surface-700 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-surface-700 pb-4">
              <div>
                <h3 className="text-xl font-bold text-white capitalize">
                  {activeDefect.defect_type.replace(/_/g, ' ')}
                </h3>
                <p className="text-xs text-zinc-400 font-mono mt-1">Defect ID #{activeDefect.id} • Seat {activeDefect.seat_id}</p>
              </div>
              <button
                onClick={() => setActiveDefect(null)}
                className="p-2 text-zinc-400 hover:text-white rounded-lg bg-surface-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="rounded-xl overflow-hidden bg-black/60 h-64 flex items-center justify-center border border-surface-700">
                <img
                  src={activeDefect.image_url.startsWith('http') ? activeDefect.image_url : `${import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'}${activeDefect.image_url}`}
                  alt="Defect detail"
                  className="w-full h-full object-contain"
                />
              </div>

              <div className="space-y-3 text-sm text-zinc-300 bg-surface-800 p-4 rounded-xl border border-surface-700">
                <div className="flex justify-between">
                  <span>Station:</span>
                  <span className="font-semibold text-white">{activeDefect.station_id}</span>
                </div>
                <div className="flex justify-between">
                  <span>Outcome:</span>
                  <span className="font-semibold text-white">{activeDefect.outcome}</span>
                </div>
                {activeDefect.measured_value !== null && (
                  <div className="flex justify-between">
                    <span>Measured Value:</span>
                    <span className="font-mono text-primary-400">{activeDefect.measured_value} {activeDefect.unit}</span>
                  </div>
                )}
                {activeDefect.nominal_value !== null && (
                  <div className="flex justify-between">
                    <span>Nominal Value:</span>
                    <span className="font-mono text-success-400">{activeDefect.nominal_value} {activeDefect.unit}</span>
                  </div>
                )}
                {activeDefect.delta !== null && (
                  <div className="flex justify-between">
                    <span>Deviation:</span>
                    <span className="font-mono text-warning-400">{activeDefect.delta} {activeDefect.unit}</span>
                  </div>
                )}
                {activeDefect.confidence !== null && (
                  <div className="flex justify-between">
                    <span>Model Confidence:</span>
                    <span className="font-mono text-white">{(activeDefect.confidence * 100).toFixed(1)}%</span>
                  </div>
                )}
              </div>
            </div>

            {/* Feedback Form */}
            <form onSubmit={handleFeedbackSubmit} className="space-y-4 pt-4 border-t border-surface-700">
              <h4 className="font-semibold text-white text-sm">Submit Inspector Feedback (Active Learning)</h4>

              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  id="fp"
                  checked={isFalsePositive}
                  onChange={(e) => setIsFalsePositive(e.target.checked)}
                  className="w-4 h-4 rounded bg-surface-800 border-surface-700 text-primary-600 focus:ring-primary-500"
                />
                <label htmlFor="fp" className="text-sm text-zinc-300 font-medium">Mark as False Positive (Clean Part)</label>
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Corrected Defect Type (Optional)</label>
                <input
                  type="text"
                  value={correctedType}
                  onChange={(e) => setCorrectedType(e.target.value)}
                  placeholder="e.g. scratch, stain, cut"
                  className="w-full text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Inspector Notes</label>
                <textarea
                  value={inspectorNotes}
                  onChange={(e) => setInspectorNotes(e.target.value)}
                  placeholder="Add notes for dataset retraining..."
                  className="w-full text-sm h-20"
                />
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setActiveDefect(null)}
                  className="btn-ghost"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="btn-primary flex items-center gap-2"
                >
                  <ShieldCheck className="w-4 h-4" />
                  {submitting ? 'Saving...' : 'Submit Feedback'}
                </button>
              </div>

              {feedbackSuccess && (
                <div className="p-3 bg-success-900/30 border border-success-500 rounded-lg text-success-400 text-sm text-center">
                  ✓ Feedback recorded successfully for active learning!
                </div>
              )}
            </form>
          </div>
        </div>
      )}
    </section>
  )
}

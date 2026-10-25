import { useState, useEffect } from 'react'
import { apiClient, type ReviewItem } from '../lib/api'
import { audioAlerts } from '../lib/audioAlerts'
import {
  Wrench,
  Search,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Sparkles,
  Camera,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react'

interface ReworkBenchProps {
  initialSeatId?: string | null
}

export default function ReworkBench({ initialSeatId }: ReworkBenchProps) {
  const [reviews, setReviews] = useState<ReviewItem[]>([])
  const [selectedReview, setSelectedReview] = useState<ReviewItem | null>(null)
  const [selectedSeatDetails, setSelectedSeatDetails] = useState<any | null>(null)
  const [searchSeatId, setSearchSeatId] = useState(initialSeatId || '')
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [inspectorId, setInspectorId] = useState('TECH_INSP_09')
  const [reworkNotes, setReworkNotes] = useState('')
  const [successMsg, setSuccessMsg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Interactive SOP checklist states per defect
  const [checklist, setChecklist] = useState<Record<string, boolean>>({})

  const fetchPendingReviews = async () => {
    setLoading(true)
    try {
      const data = await apiClient.getPendingReviews()
      setReviews(data)
      if (data.length > 0 && !selectedReview) {
        setSelectedReview(data[0])
        loadSeatDetails(data[0].seat_id)
      }
    } catch (err: any) {
      console.warn('Failed to load pending reviews:', err)
    } finally {
      setLoading(false)
    }
  }

  const loadSeatDetails = async (seatId: string) => {
    try {
      const seat = (await apiClient.getSeat(seatId)) as any
      setSelectedSeatDetails(seat)
      const initialChecks: Record<string, boolean> = {}
      if (seat.defects) {
        seat.defects.forEach((_: any, idx: number) => {
          initialChecks[`defect_${idx}`] = false
        })
      }
      setChecklist(initialChecks)
    } catch (err: any) {
      console.warn('Could not load seat details:', err)
    }
  }

  useEffect(() => {
    fetchPendingReviews()
  }, [])

  useEffect(() => {
    if (initialSeatId) {
      setSearchSeatId(initialSeatId)
      loadSeatDetails(initialSeatId)
    }
  }, [initialSeatId])

  const handleSelectReview = (rev: ReviewItem) => {
    setSelectedReview(rev)
    setSearchSeatId(rev.seat_id)
    loadSeatDetails(rev.seat_id)
    setSuccessMsg(null)
    setError(null)
  }

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (!searchSeatId.trim()) return
    loadSeatDetails(searchSeatId.trim())
  }

  const handleResolve = async (decision: 'PASS' | 'REWORK' | 'SCRAP') => {
    if (!selectedReview && !selectedSeatDetails) return
    setActionLoading(true)
    setError(null)
    setSuccessMsg(null)

    try {
      const reviewId = selectedReview?.review_id || 1
      await apiClient.resolveReview(
        reviewId,
        decision,
        reworkNotes || `Rework bench operator disposition: ${decision}`,
        inspectorId
      )

      if (decision === 'PASS') {
        audioAlerts.playPassChime()
        setSuccessMsg(`Seat ${selectedSeatDetails?.seat_id || ''} approved and released to main line conveyor.`)
      } else if (decision === 'SCRAP') {
        audioAlerts.playFailAlarm()
        setSuccessMsg(`Seat marked SCRAP. Material disposal routing slip generated.`)
      } else {
        audioAlerts.playReviewTone()
        setSuccessMsg(`Seat tagged for secondary station rework.`)
      }

      fetchPendingReviews()
    } catch (err: any) {
      setError(err.message || 'Failed to record disposition decision')
    } finally {
      setActionLoading(false)
    }
  }

  const handleFalsePositive = async (defectId: number) => {
    try {
      await apiClient.recordDefectFeedback(defectId, {
        is_false_positive: true,
        inspector_id: inspectorId,
        inspector_notes: 'Marked as false positive at rework bench',
      })
      alert('AI False Positive recorded. Model fine-tuning dataset updated.')
    } catch (err: any) {
      alert('Failed to record feedback: ' + err.message)
    }
  }

  const getDefectSopGuidance = (defectType?: string) => {
    switch (defectType?.toLowerCase()) {
      case 'wrinkle':
      case 'crease':
        return 'Apply heat gun / hot air wand at 115°C for 20s, massage leather inward toward seam using teflon bone.'
      case 'loose_thread':
      case 'broken_stitch':
        return 'Trim loose thread to <1.5mm with ceramic snips; apply thermal lock to tail. Re-stitch if seam integrity compromised.'
      case 'shield_gap':
      case 'unseated_clip':
        return 'Inspect retention clips for bent tabs; align bezel and apply firm palm pressure until audible click is confirmed.'
      case 'scratch':
      case 'blemish':
        return 'Assess depth. Superficial: apply approved matte leather conditioner. Structural grain tear: replace cushion cover.'
      default:
        return 'Inspect against OEM cosmetic standard visual aid and execute manual rectification.'
    }
  }

  const activeImageUrl = selectedSeatDetails?.stations?.STATION_1?.annotated_image_path
    ? (selectedSeatDetails.stations.STATION_1.annotated_image_path.startsWith('http')
        ? selectedSeatDetails.stations.STATION_1.annotated_image_path
        : `${import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'}${selectedSeatDetails.stations.STATION_1.annotated_image_path}`)
    : selectedReview?.annotated_image_path
    ? `${import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'}${selectedReview.annotated_image_path}`
    : null

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="font-bold text-white text-3xl flex items-center gap-3">
            <Wrench className="w-8 h-8 text-primary-400" />
            Rework Bench & Reject Spur Interface
          </h2>
          <p className="text-sm text-zinc-400 mt-1">
            Offline repair workstation: defect verification, automotive SOP repair checklists, and line re-entry signoff
          </p>
        </div>

        <form onSubmit={handleSearch} className="flex items-center gap-2 bg-surface-800 p-1.5 rounded-xl border border-surface-700">
          <Search className="w-4 h-4 text-zinc-400 ml-2" />
          <input
            type="text"
            value={searchSeatId}
            onChange={(e) => setSearchSeatId(e.target.value)}
            placeholder="Scan / Enter Seat ID..."
            className="text-xs py-1.5 px-3 min-w-[200px]"
          />
          <button type="submit" className="btn-primary text-xs py-1.5 px-3">
            Load Seat
          </button>
        </form>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Queue of Diverted Rejected Seats */}
        <div className="card p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-surface-700 pb-3">
            <div className="text-sm font-semibold uppercase tracking-wider text-zinc-400 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-warning-400" />
              Reject Spur Queue ({reviews.length})
            </div>
            <button onClick={fetchPendingReviews} className="btn-ghost p-1.5" title="Refresh">
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {reviews.length === 0 ? (
            <div className="text-center py-12 text-zinc-500 text-xs">
              <CheckCircle className="w-8 h-8 text-success-500 mx-auto mb-2 opacity-60" />
              No seats currently in reject spur queue.
            </div>
          ) : (
            <div className="space-y-3 max-h-[540px] overflow-y-auto pr-1">
              {reviews.map((rev) => {
                const isSelected = selectedReview?.review_id === rev.review_id
                return (
                  <div
                    key={rev.review_id}
                    onClick={() => handleSelectReview(rev)}
                    className={`p-4 rounded-xl border cursor-pointer transition-all ${
                      isSelected
                        ? 'bg-surface-800 border-primary-500 shadow-md shadow-primary-500/10'
                        : 'bg-surface-900 border-surface-700 hover:border-surface-600'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono text-sm font-bold text-white">{rev.seat_id}</span>
                      <span className="badge-review px-2 py-0.5 text-[10px] font-bold">REWORK</span>
                    </div>
                    <div className="text-xs text-zinc-400">
                      Held at: <span className="font-semibold text-zinc-300">{rev.station_id}</span>
                    </div>
                    <div className="text-[10px] text-zinc-500 mt-1">
                      {new Date(rev.created_at).toLocaleTimeString()}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Center & Right Column: Defect Viewer + SOP Repair Checklist */}
        <div className="lg:col-span-2 space-y-6">
          <div className="card p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-surface-700 pb-3">
              <div className="text-sm font-semibold uppercase tracking-wider text-zinc-400 flex items-center gap-2">
                <Camera className="w-4 h-4 text-primary-400" />
                Defect Inspection View: {selectedSeatDetails?.seat_id || searchSeatId || 'No Seat Selected'}
              </div>

              {selectedSeatDetails && (
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-zinc-400">Variant:</span>
                  <span className="text-xs font-bold text-white font-mono bg-surface-900 px-2 py-0.5 rounded border border-surface-700">
                    {selectedSeatDetails.variant_id}
                  </span>
                </div>
              )}
            </div>

            <div className="relative h-64 bg-black/90 rounded-xl overflow-hidden flex items-center justify-center border border-surface-700">
              {activeImageUrl ? (
                <img src={activeImageUrl} alt="Defect Capture" className="w-full h-full object-contain" />
              ) : (
                <div className="text-center text-zinc-500 text-xs">
                  <Wrench className="w-8 h-8 text-zinc-600 mx-auto mb-2" />
                  Select a rejected seat to inspect defect photos and bounding boxes
                </div>
              )}
            </div>
          </div>

          <div className="card p-6 space-y-6">
            <div className="text-sm font-semibold uppercase tracking-wider text-zinc-400 flex items-center gap-2 border-b border-surface-700 pb-3">
              <ShieldCheck className="w-4 h-4 text-primary-400" />
              Automotive Standard Operating Procedure (SOP) Checklist
            </div>

            <div className="space-y-4">
              {selectedSeatDetails?.defects && selectedSeatDetails.defects.length > 0 ? (
                selectedSeatDetails.defects.map((def: any, idx: number) => {
                  const checkKey = `defect_${idx}`
                  const isChecked = checklist[checkKey] || false

                  return (
                    <div
                      key={idx}
                      className="p-4 bg-surface-900 rounded-xl border border-surface-700 space-y-3"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <label className="flex items-start gap-3 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={(e) =>
                              setChecklist({ ...checklist, [checkKey]: e.target.checked })
                            }
                            className="mt-1 rounded accent-primary-500 w-4 h-4"
                          />
                          <div>
                            <div className="text-sm font-bold text-white capitalize">
                              {def.defect_type?.replace(/_/g, ' ')}
                            </div>
                            <div className="text-xs text-zinc-400 mt-0.5">
                              {getDefectSopGuidance(def.defect_type)}
                            </div>
                          </div>
                        </label>

                        <button
                          type="button"
                          onClick={() => handleFalsePositive(def.id || idx)}
                          className="btn-ghost text-[10px] py-1 px-2 text-zinc-400 hover:text-primary-300 flex items-center gap-1 flex-shrink-0"
                          title="Report AI False Positive"
                        >
                          <Sparkles className="w-3 h-3 text-primary-400" />
                          False Positive
                        </button>
                      </div>
                    </div>
                  )
                })
              ) : (
                <div className="p-4 bg-surface-900 rounded-xl border border-surface-700 text-xs text-zinc-400">
                  <div className="font-semibold text-white mb-1">General Cosmetic Rectification Checklist:</div>
                  <ul className="space-y-1.5 list-disc list-inside">
                    <li>Confirm all seam lockstitches are intact without loose loops</li>
                    <li>Inspect leather bolsters for transport scratches or pressure marks</li>
                    <li>Verify plastic retention clips are fully engaged with audible click</li>
                  </ul>
                </div>
              )}
            </div>

            <div className="space-y-4 border-t border-surface-700 pt-5">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1">
                    Certified Rework Technician ID
                  </label>
                  <input
                    type="text"
                    value={inspectorId}
                    onChange={(e) => setInspectorId(e.target.value)}
                    className="w-full text-xs"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1">
                    Rework Action Notes
                  </label>
                  <input
                    type="text"
                    value={reworkNotes}
                    onChange={(e) => setReworkNotes(e.target.value)}
                    placeholder="Heated wrinkle, restitched seam tail..."
                    className="w-full text-xs"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4 pt-2">
                <button
                  type="button"
                  disabled={actionLoading || !selectedSeatDetails}
                  onClick={() => handleResolve('PASS')}
                  className="btn-primary py-3 bg-success-600 hover:bg-success-500 text-white font-bold text-xs flex items-center justify-center gap-1.5 shadow-lg shadow-success-600/30"
                >
                  <CheckCircle className="w-4 h-4" />
                  Release to Line (PASS)
                </button>

                <button
                  type="button"
                  disabled={actionLoading || !selectedSeatDetails}
                  onClick={() => handleResolve('REWORK')}
                  className="btn-ghost border-warning-500/50 text-warning-400 hover:bg-warning-900/20 py-3 font-bold text-xs flex items-center justify-center gap-1.5"
                >
                  <AlertTriangle className="w-4 h-4" />
                  Secondary Audit
                </button>

                <button
                  type="button"
                  disabled={actionLoading || !selectedSeatDetails}
                  onClick={() => handleResolve('SCRAP')}
                  className="btn-ghost border-danger-500/50 text-danger-400 hover:bg-danger-900/20 py-3 font-bold text-xs flex items-center justify-center gap-1.5"
                >
                  <XCircle className="w-4 h-4" />
                  Scrap Unit
                </button>
              </div>
            </div>

            {successMsg && (
              <div className="p-4 bg-success-900/20 border border-success-500 rounded-xl text-success-400 text-xs flex items-center gap-2">
                <CheckCircle className="w-4 h-4 flex-shrink-0" />
                {successMsg}
              </div>
            )}

            {error && (
              <div className="p-4 bg-danger-900/20 border border-danger-500 rounded-xl text-danger-400 text-xs flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                {error}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

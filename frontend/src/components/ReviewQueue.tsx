import { apiClient } from '../lib/api'
import { useEffect, useState } from 'react'
import type { ReviewItem } from '../lib/api'
import { AlertTriangle, CheckCircle, X } from 'lucide-react'

export default function ReviewQueue() {
  const [reviews, setReviews] = useState<ReviewItem[]>([])
  const [shadowMode, setShadowMode] = useState(false)
  const [loading, setLoading] = useState(true)
  const [resolving, setResolving] = useState<number | null>(null)
  const [successToast, setSuccessToast] = useState<string | null>(null)

  const fetchData = async () => {
    try {
      const [reviewData, settingsData] = await Promise.all([
        apiClient.getPendingReviews(),
        apiClient.getSystemSettings().catch(() => ({ shadow_mode: false })),
      ])
      setReviews(reviewData)
      setShadowMode((settingsData as any)?.shadow_mode || false)
    } catch (error) {
      console.error('Failed to fetch reviews:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 5000)
    return () => clearInterval(interval)
  }, [])

  const handleResolve = async (reviewId: number, seatId: string, decision: 'PASS' | 'REWORK' | 'SCRAP') => {
    setResolving(reviewId)
    try {
      await apiClient.resolveReview(reviewId, decision, `Resolved as ${decision} via dashboard`)
      setSuccessToast(`Seat ${seatId} successfully dispositioned as ${decision}`)
      setTimeout(() => setSuccessToast(null), 4000)
      await fetchData()
    } catch (error) {
      console.error('Failed to resolve review:', error)
      alert('Failed to resolve review. Please try again.')
    } finally {
      setResolving(null)
    }
  }

  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      if (reviews.length === 0) return
      const firstReview = reviews[0]
      if (e.key === '1') handleResolve(firstReview.review_id, firstReview.seat_id, 'PASS')
      else if (e.key === '2') handleResolve(firstReview.review_id, firstReview.seat_id, 'REWORK')
      else if (e.key === '3') handleResolve(firstReview.review_id, firstReview.seat_id, 'SCRAP')
    }
    window.addEventListener('keypress', handleKeyPress)
    return () => window.removeEventListener('keypress', handleKeyPress)
  }, [reviews])

  if (loading) {
    return <div className="text-center py-20 text-zinc-400">Loading review queue...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="font-bold text-white text-2xl flex items-center gap-3">
            <AlertTriangle className="w-7 h-7 text-warning-400" />
            Human Review Queue & Disposition
          </h2>
          <p className="text-sm text-zinc-400 mt-1">
            {shadowMode
              ? 'Shadow Mode active: Review queue items are for offline audit and escape tracking.'
              : 'Production Mode active: Review resolutions actively control factory pallet release.'}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {shadowMode ? (
            <span className="px-3 py-1 rounded-lg text-xs font-bold bg-amber-500/20 text-amber-400 border border-amber-500/40">
              SHADOW MODE (Audit)
            </span>
          ) : (
            <span className="px-3 py-1 rounded-lg text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/40">
              PRODUCTION MODE
            </span>
          )}
          <span className="badge-review px-4 py-1.5 rounded-full text-sm font-bold">{reviews.length} pending</span>
        </div>
      </div>

      {successToast && (
        <div className="p-4 bg-success-900/20 text-success-400 text-sm rounded-xl border border-success-500 flex items-center gap-2 animate-fade-in">
          <CheckCircle className="w-5 h-5 flex-shrink-0" />
          {successToast}
        </div>
      )}

      {reviews.length > 0 && (
        <div className="p-4 rounded-xl bg-primary-900/20 border border-primary-500/20 text-sm text-zinc-300 flex items-center justify-between">
          <div>
            💡 <strong>Keyboard Shortcuts:</strong> Press{' '}
            <code className="px-2 py-1 rounded bg-black/40 text-success-400 font-mono">[1]</code> PASS,{' '}
            <code className="px-2 py-1 rounded bg-black/40 text-warning-400 font-mono">[2]</code> REWORK,{' '}
            <code className="px-2 py-1 rounded bg-black/40 text-danger-400 font-mono">[3]</code> SCRAP.
          </div>
          <div className="text-primary-400 font-medium">Floor Mode Active</div>
        </div>
      )}

      <div className="space-y-4">
        {reviews.length === 0 ? (
          <div className="text-zinc-500 py-16 text-center card">
            <CheckCircle className="w-16 h-16 mx-auto mb-4 text-success-500 opacity-80" />
            <p className="text-lg font-semibold text-white">No pending reviews</p>
            <p className="text-sm mt-1 text-zinc-400">All seat inspection ambiguities have been cleared.</p>
          </div>
        ) : (
          reviews.map((review) => (
            <div key={review.review_id} className="card p-6">
              <div className="flex items-start gap-6">
                <div className="flex-shrink-0">
                  <AlertTriangle className="w-12 h-12 text-warning-400" />
                </div>
                <div className="flex-1">
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <h3 className="text-lg font-bold text-white mb-1">Seat ID: {review.seat_id}</h3>
                      <p className="text-sm text-zinc-400">
                        Station: {review.station_id ? review.station_id.replace('STATION_', 'Station ') : 'Station'} • Flagged at {review.created_at ? new Date(review.created_at).toLocaleTimeString() : 'N/A'}
                      </p>
                    </div>
                  </div>

                  {review.annotated_image_path && (
                    <div className="mb-4">
                      <img
                        src={`${import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'}/${review.annotated_image_path}`}
                        alt="Inspection"
                        className="w-full max-w-md rounded-lg border border-surface-700"
                      />
                    </div>
                  )}

                  <div className="flex gap-3 flex-wrap">
                    <button
                      onClick={() => handleResolve(review.review_id, review.seat_id, 'PASS')}
                      disabled={resolving === review.review_id}
                      className="btn-primary bg-emerald-600 hover:bg-emerald-500 flex items-center gap-2 shadow-lg shadow-emerald-600/20"
                    >
                      <CheckCircle className="w-4 h-4" />
                      {resolving === review.review_id ? 'Processing...' : 'PASS [1]'}
                    </button>
                    <button
                      onClick={() => handleResolve(review.review_id, review.seat_id, 'REWORK')}
                      disabled={resolving === review.review_id}
                      className="btn-primary bg-amber-600 hover:bg-amber-500 flex items-center gap-2 shadow-lg shadow-amber-600/20"
                    >
                      <AlertTriangle className="w-4 h-4" />
                      REWORK [2]
                    </button>
                    <button
                      onClick={() => handleResolve(review.review_id, review.seat_id, 'SCRAP')}
                      disabled={resolving === review.review_id}
                      className="btn-primary bg-rose-600 hover:bg-rose-500 flex items-center gap-2 shadow-lg shadow-rose-600/20"
                    >
                      <X className="w-4 h-4" />
                      SCRAP [3]
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

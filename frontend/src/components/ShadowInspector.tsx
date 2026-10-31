import { useEffect, useState, useRef } from 'react'
import { apiClient } from '../lib/api'
import {
  FlaskConical, CheckCircle, XCircle, AlertTriangle,
  ClipboardList, RefreshCw, Activity, Eye, X,
} from 'lucide-react'

interface SeatCard {
  seat_id: string
  variant_id: string
  outcome: string
  timestamp: string
  decided?: boolean
  human_decision?: 'PASS' | 'FAIL'
  annotated_image_path: string | null
  camera_image_paths: Record<string, string>
}

interface RecentDecision {
  seat_id: string
  inspector_id: string
  decision: 'PASS' | 'FAIL'
  notes: string
  timestamp: string
}

interface ShiftStats {
  total_inspected: number
  human_decisions_count: number
  compared_sample_size: number
  agreement_rate: number
  false_reject_rate: number
  escape_rate: number
}

export default function ShadowInspector() {
  const [shadowMode, setShadowMode] = useState<boolean | null>(null)
  const [inspectorId, setInspectorId] = useState(() => localStorage.getItem('sg_inspector_id') || '')
  const [submitting, setSubmitting] = useState<string | null>(null)
  const [successToast, setSuccessToast] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [seatCards, setSeatCards] = useState<SeatCard[]>([])

  const [recentDecisions, setRecentDecisions] = useState<RecentDecision[]>(() => {
    try {
      const saved = localStorage.getItem('sg_shadow_decisions')
      return saved ? JSON.parse(saved) : []
    } catch {
      return []
    }
  })

  const [stats, setStats] = useState<ShiftStats | null>(null)
  const [notesMap, setNotesMap] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)

  const [inspectSeatId, setInspectSeatId] = useState<string | null>(null)

  const decidedRef = useRef<Set<string>>(new Set())

  useEffect(() => {
    const sSet = new Set<string>()
    recentDecisions.forEach(d => sSet.add(d.seat_id))
    decidedRef.current = sSet
  }, [])

  useEffect(() => {
    try {
      localStorage.setItem('sg_shadow_decisions', JSON.stringify(recentDecisions))
    } catch (err) {
      console.error('Failed to save decisions to localStorage:', err)
    }
  }, [recentDecisions])

  const fetchAll = async () => {
    try {
      const [settingsData, liveData, statsResp] = await Promise.all([
        apiClient.getSystemSettings().catch(() => ({ shadow_mode: false })),
        apiClient.getLiveLine().catch(() => ({ recent_strip: [] })),
        apiClient.getShadowModeStats().catch(() => ({}) as any),
      ])
      const mode = !!(settingsData as any)?.shadow_mode
      setShadowMode(mode)

      const statsRespAny = statsResp as any
      setStats({
        total_inspected: statsRespAny?.total_inspected || 0,
        human_decisions_count: statsRespAny?.human_decisions_count || recentDecisions.length,
        compared_sample_size: statsRespAny?.compared_sample_size || 0,
        agreement_rate: statsRespAny?.agreement_rate || 0,
        false_reject_rate: statsRespAny?.false_reject_rate || 0,
        escape_rate: statsRespAny?.escape_rate || 0,
      })

      const strip: SeatCard[] = ((liveData as any)?.recent_strip || []).map((s: any) => {
        const isDecided = decidedRef.current.has(s.seat_id)
        const existingDecision = recentDecisions.find(d => d.seat_id === s.seat_id)
        return {
          seat_id: s.seat_id,
          variant_id: s.variant_id,
          outcome: s.outcome,
          timestamp: s.timestamp,
          decided: isDecided,
          human_decision: existingDecision?.decision,
          annotated_image_path: s.annotated_image_path || null,
          camera_image_paths: s.camera_image_paths || {},
        }
      })
      setSeatCards(strip)
    } catch (err) {
      console.error('ShadowInspector fetch error:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAll()
    const interval = setInterval(fetchAll, 8000)
    return () => clearInterval(interval)
  }, [])

  const handleDecide = async (seatId: string, decision: 'PASS' | 'FAIL') => {
    if (!inspectorId.trim()) {
      setErrorMsg('Please enter your Inspector ID before recording decisions.')
      return
    }
    setSubmitting(seatId)
    setErrorMsg(null)
    const notes = notesMap[seatId] || ''
    try {
      await apiClient.recordShadowDecision(seatId, inspectorId.trim(), decision, notes)
      localStorage.setItem('sg_inspector_id', inspectorId.trim())
      decidedRef.current.add(seatId)
      setSeatCards(prev => prev.map(c =>
        c.seat_id === seatId ? { ...c, decided: true, human_decision: decision } : c
      ))
      const entry: RecentDecision = {
        seat_id: seatId,
        inspector_id: inspectorId.trim(),
        decision,
        notes,
        timestamp: new Date().toLocaleTimeString(),
      }
      setRecentDecisions(prev => {
        const filtered = prev.filter(p => p.seat_id !== seatId)
        return [entry, ...filtered].slice(0, 50)
      })
      setSuccessToast(`Seat ${seatId} → ${decision} recorded`)
      setTimeout(() => setSuccessToast(null), 3500)

      apiClient.getShadowModeStats().then(s => {
        const statsRespAny = s as any
        setStats({
          total_inspected: statsRespAny?.total_inspected || 0,
          human_decisions_count: statsRespAny?.human_decisions_count || recentDecisions.length + 1,
          compared_sample_size: statsRespAny?.compared_sample_size || 0,
          agreement_rate: statsRespAny?.agreement_rate || 0,
          false_reject_rate: statsRespAny?.false_reject_rate || 0,
          escape_rate: statsRespAny?.escape_rate || 0,
        })
      }).catch(() => {})
    } catch (err) {
      setErrorMsg(`Failed to record: ${err}`)
    } finally {
      setSubmitting(null)
    }
  }

  if (loading) return <div className="text-center py-20 text-zinc-400">Loading Shadow Inspector...</div>

  const pendingCount = seatCards.filter(c => !c.decided).length

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="font-bold text-white text-3xl flex items-center gap-3">
            <FlaskConical className="w-8 h-8 text-primary-400" />
            Shadow Inspector
          </h2>
          <p className="text-sm text-zinc-400 mt-1">
            Review each seat inspected by the AI, view live capture frames, and record ground-truth decisions for shift agreement metrics.
          </p>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          {shadowMode ? (
            <span className="px-3 py-1.5 rounded-lg text-xs font-bold bg-amber-500/20 text-amber-400 border border-amber-500/40 animate-pulse">
              SHADOW MODE ACTIVE
            </span>
          ) : (
            <span className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/40">
              PRODUCTION MODE
            </span>
          )}
          <button onClick={fetchAll} className="btn-ghost p-2" title="Refresh">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {!shadowMode && (
        <div className="p-6 rounded-2xl bg-amber-500/10 border border-amber-500/40 flex items-start gap-4">
          <AlertTriangle className="w-7 h-7 text-amber-400 flex-shrink-0 mt-0.5" />
          <div>
            <div className="font-bold text-amber-300 text-base mb-1">Shadow Mode is not active</div>
            <p className="text-sm text-amber-200/70">
              This panel is only used during AI model validation. Enable Shadow Mode in Settings to start
              recording human ground-truth decisions for comparison against AI outcomes.
            </p>
          </div>
        </div>
      )}

      {/* Inspector ID + Live Mini-Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="card p-6 space-y-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-zinc-400">Your Inspector ID</div>
          <input
            type="text"
            value={inspectorId}
            onChange={e => setInspectorId(e.target.value)}
            placeholder="e.g. OP_ALPHA or your name"
            className="w-full text-sm"
          />
          <p className="text-xs text-zinc-500">Saved automatically when you record your first decision.</p>
        </div>

        <div className="stat-card">
          <div className="stat-label">Seats in AI Log</div>
          <div className="stat-value text-white">{seatCards.length}</div>
          <div className="text-xs text-zinc-500 mt-1">{pendingCount} awaiting your review</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Decisions Recorded (Persisted)</div>
          <div className="stat-value text-primary-400">{stats?.human_decisions_count ?? recentDecisions.length}</div>
          <div className="text-xs text-zinc-500 mt-1">
            Agreement: {stats?.agreement_rate !== undefined ? `${(stats.agreement_rate * 100).toFixed(1)}%` : 'N/A'}
          </div>
        </div>
      </div>

      {/* Shift analytics mini row */}
      {stats && (stats.compared_sample_size > 0) && (
        <div className="grid grid-cols-3 gap-4">
          <div className="p-4 rounded-xl bg-surface-800 border border-surface-700 text-center">
            <div className="text-xs text-zinc-400 mb-1">AI vs Human Compared</div>
            <div className="text-xl font-bold text-white">{stats.compared_sample_size}</div>
          </div>
          <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-center">
            <div className="text-xs text-zinc-400 mb-1">False Reject Rate</div>
            <div className="text-xl font-bold text-amber-400">{(stats.false_reject_rate * 100).toFixed(2)}%</div>
          </div>
          <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-center">
            <div className="text-xs text-zinc-400 mb-1">Escape Rate</div>
            <div className="text-xl font-bold text-rose-400">{(stats.escape_rate * 100).toFixed(2)}%</div>
          </div>
        </div>
      )}

      {errorMsg && (
        <div className="p-4 bg-danger-900/20 border border-danger-500/40 text-danger-400 text-sm rounded-xl flex items-center gap-2">
          <XCircle className="w-4 h-4 flex-shrink-0" />
          {errorMsg}
        </div>
      )}

      {successToast && (
        <div className="p-4 bg-success-900/20 text-success-400 text-sm rounded-xl border border-success-500 flex items-center gap-2">
          <CheckCircle className="w-5 h-5 flex-shrink-0" />
          {successToast}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
        {/* AI Shadow Log Feed */}
        <div className={`space-y-4 ${!shadowMode ? 'opacity-40 pointer-events-none' : ''}`}>
          <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-zinc-400">
            <Activity className="w-4 h-4 text-primary-400" />
            AI Shadow Log — Recent Seats
            {pendingCount > 0 && (
              <span className="ml-auto px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400 text-xs font-bold border border-amber-500/30">
                {pendingCount} pending
              </span>
            )}
          </div>

          {seatCards.length === 0 ? (
            <div className="card p-10 text-center text-zinc-500 text-sm">
              <Activity className="w-10 h-10 mx-auto mb-3 text-zinc-700" />
              No seats in AI log yet. Seats will appear here as the line runs.
            </div>
          ) : (
            <div className="space-y-3 max-h-[600px] overflow-y-auto pr-1">
              {seatCards.map(card => {
                const BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
                // Pick the best available image: annotated path from API, first camera path, or nothing
                const firstCamPath = Object.values(card.camera_image_paths)[0] || null
                const rawPath = card.annotated_image_path || firstCamPath
                const captureImgUrl = rawPath ? `${BASE}/${rawPath.replace(/^\/+/, '')}` : null

                return (
                  <div
                    key={card.seat_id}
                    className={`card p-5 transition-all space-y-4 ${
                      card.decided ? 'opacity-60 border-surface-600' : 'border-surface-600 hover:border-primary-500/50'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <div className="font-bold text-white font-mono text-sm">{card.seat_id}</div>
                        <div className="text-xs text-zinc-500 mt-0.5">
                          {card.variant_id} · {new Date(card.timestamp).toLocaleTimeString()}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <span className="text-xs text-zinc-400">AI:</span>
                        <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                          card.outcome === 'PASS'
                            ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                            : card.outcome === 'FAIL'
                            ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                            : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                        }`}>{card.outcome}</span>
                      </div>
                    </div>

                    {/* Inline Thumbnail Preview that opens modal on click */}
                    {captureImgUrl ? (
                    <div
                      onClick={() => setInspectSeatId(card.seat_id)}
                      className="relative rounded-xl overflow-hidden border border-surface-700 bg-surface-950 h-36 cursor-pointer group"
                    >
                      <img
                        src={captureImgUrl}
                        alt={`Seat ${card.seat_id}`}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      />
                      <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2 text-white font-semibold text-xs">
                        <Eye className="w-4 h-4" /> Click to Inspect High-Res Capture
                      </div>
                    </div>
                    ) : (
                      <div className="flex items-center justify-center h-20 rounded-xl bg-surface-950 border border-surface-700 text-zinc-600 text-xs gap-2">
                        <Eye className="w-4 h-4" /> No capture saved for this seat
                      </div>
                    )}

                    {card.decided ? (
                      <div className={`flex items-center gap-2 text-sm font-semibold ${
                        card.human_decision === 'PASS' ? 'text-emerald-400' : 'text-rose-400'
                      }`}>
                        <CheckCircle className="w-4 h-4" />
                        You recorded: {card.human_decision}
                      </div>
                    ) : (
                      <div className="space-y-2">
                        <input
                          type="text"
                          value={notesMap[card.seat_id] || ''}
                          onChange={e => setNotesMap(prev => ({ ...prev, [card.seat_id]: e.target.value }))}
                          placeholder="Optional notes..."
                          className="w-full text-xs py-1.5 px-3"
                        />
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleDecide(card.seat_id, 'PASS')}
                            disabled={submitting === card.seat_id}
                            className="flex-1 py-2 rounded-lg font-bold text-xs text-white bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 transition-colors flex items-center justify-center gap-1.5"
                          >
                            <CheckCircle className="w-3.5 h-3.5" />
                            {submitting === card.seat_id ? 'Saving...' : 'PASS'}
                          </button>
                          <button
                            onClick={() => handleDecide(card.seat_id, 'FAIL')}
                            disabled={submitting === card.seat_id}
                            className="flex-1 py-2 rounded-lg font-bold text-xs text-white bg-rose-600 hover:bg-rose-500 disabled:opacity-50 transition-colors flex items-center justify-center gap-1.5"
                          >
                            <XCircle className="w-3.5 h-3.5" />
                            {submitting === card.seat_id ? 'Saving...' : 'FAIL'}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Decisions Log */}
        <div className="card p-8 space-y-4">
          <div className="text-sm font-semibold uppercase tracking-wide text-zinc-400 border-b border-surface-700 pb-4 flex items-center gap-2">
            <ClipboardList className="w-4 h-4 text-primary-400" />
            Decisions Recorded (Persisted)
            <span className="ml-auto text-xs text-zinc-500 font-normal normal-case">
              feeds into Shift Report
            </span>
          </div>

          {recentDecisions.length === 0 ? (
            <div className="py-12 text-center text-zinc-500 text-sm">
              <ClipboardList className="w-10 h-10 mx-auto mb-3 text-zinc-700" />
              No decisions recorded yet this session.
              <br />
              Click PASS or FAIL on a seat in the AI log.
            </div>
          ) : (
            <div className="space-y-2 max-h-[560px] overflow-y-auto pr-1">
              {recentDecisions.map((d, i) => (
                <div key={i} className="flex items-center justify-between p-3 rounded-xl bg-surface-900 border border-surface-700">
                  <div>
                    <div className="text-sm font-semibold text-white font-mono flex items-center gap-2">
                      {d.seat_id}
                      <button
                        onClick={() => setInspectSeatId(d.seat_id)}
                        className="text-xs text-primary-400 hover:underline flex items-center gap-1 font-sans"
                      >
                        <Eye className="w-3 h-3" /> Image
                      </button>
                    </div>
                    <div className="text-xs text-zinc-500 mt-0.5">{d.inspector_id} · {d.timestamp}</div>
                    {d.notes && <div className="text-xs text-zinc-400 mt-0.5 italic">"{d.notes}"</div>}
                  </div>
                  <span className={`px-2.5 py-1 rounded text-xs font-bold flex-shrink-0 ${
                    d.decision === 'PASS'
                      ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                      : 'bg-rose-500/20 text-rose-400 border border-rose-500/40'
                  }`}>
                    {d.decision}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Image Inspection Modal */}
      {inspectSeatId && (() => {
        const BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
        const card = seatCards.find(c => c.seat_id === inspectSeatId)
        const firstCamPath = card ? Object.values(card.camera_image_paths)[0] || null : null
        const rawPath = card?.annotated_image_path || firstCamPath
        const modalImgUrl = rawPath ? `${BASE}/${rawPath.replace(/^\/+/, '')}` : null
        return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="card max-w-3xl w-full p-6 space-y-4 border border-primary-500/40 bg-surface-900 shadow-2xl relative">
            <div className="flex items-center justify-between border-b border-surface-700 pb-3">
              <div>
                <h3 className="text-lg font-bold text-white font-mono">Capture Inspection — {inspectSeatId}</h3>
                <p className="text-xs text-zinc-400">High-resolution multi-station inspection frame capture</p>
              </div>
              <button
                onClick={() => setInspectSeatId(null)}
                className="p-2 text-zinc-400 hover:text-white rounded-lg bg-surface-800 hover:bg-surface-700"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex flex-col items-center justify-center p-4 bg-surface-950 rounded-xl border border-surface-800">
              {modalImgUrl ? (
                <img
                  src={modalImgUrl}
                  alt={`Seat ${inspectSeatId}`}
                  className="max-h-[480px] object-contain rounded-lg border border-surface-700 shadow-lg"
                />
              ) : (
                <div className="flex flex-col items-center justify-center h-48 text-zinc-500 text-sm gap-2">
                  <Eye className="w-10 h-10 text-zinc-700" />
                  No capture image available for this seat
                </div>
              )}
              <div className="text-xs text-zinc-400 mt-3 font-mono">
                Showing inspection capture frame for {inspectSeatId}
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => setInspectSeatId(null)}
                className="btn-primary px-5 py-2 text-xs"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
        )
      })()}
    </div>
  )
}
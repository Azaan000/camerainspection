import { useEffect, useState } from 'react'
import { apiClient } from '../lib/api'
import { FlaskConical, CheckCircle, XCircle, AlertTriangle, ClipboardList } from 'lucide-react'

interface RecentDecision {
  seat_id: string
  inspector_id: string
  decision: string
  notes: string
  timestamp: string
}

export default function ShadowInspector() {
  const [shadowMode, setShadowMode] = useState<boolean | null>(null)
  const [seatId, setSeatId] = useState('')
  const [inspectorId, setInspectorId] = useState(() => localStorage.getItem('sg_inspector_id') || '')
  const [notes, setNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [successToast, setSuccessToast] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [recentDecisions, setRecentDecisions] = useState<RecentDecision[]>([])

  useEffect(() => {
    apiClient.getSystemSettings()
      .then((s: any) => setShadowMode(!!s?.shadow_mode))
      .catch(() => setShadowMode(false))
  }, [])

  const handleSubmit = async (decision: 'PASS' | 'FAIL') => {
    if (!seatId.trim() || !inspectorId.trim()) {
      setErrorMsg('Seat ID and Inspector ID are required.')
      return
    }
    setSubmitting(true)
    setErrorMsg(null)
    try {
      await apiClient.recordShadowDecision(seatId.trim(), inspectorId.trim(), decision, notes.trim())
      localStorage.setItem('sg_inspector_id', inspectorId.trim())
      const entry: RecentDecision = {
        seat_id: seatId.trim(),
        inspector_id: inspectorId.trim(),
        decision,
        notes: notes.trim(),
        timestamp: new Date().toLocaleTimeString(),
      }
      setRecentDecisions(prev => [entry, ...prev.slice(0, 19)])
      setSuccessToast(`Recorded: Seat ${seatId.trim()} → ${decision} by ${inspectorId.trim()}`)
      setTimeout(() => setSuccessToast(null), 4000)
      setSeatId('')
      setNotes('')
    } catch (err) {
      setErrorMsg(`Failed to record decision: ${err}`)
    } finally {
      setSubmitting(false)
    }
  }

  if (shadowMode === null) {
    return <div className="text-center py-20 text-zinc-400">Loading system status...</div>
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="font-bold text-white text-3xl flex items-center gap-3">
            <FlaskConical className="w-8 h-8 text-primary-400" />
            Shadow Inspector
          </h2>
          <p className="text-sm text-zinc-400 mt-1">
            Record human ground-truth decisions during AI model validation. These decisions are compared against AI outcomes to calculate false reject and escape rates in the Shift Report.
          </p>
        </div>
        {shadowMode ? (
          <span className="px-3 py-1.5 rounded-lg text-xs font-bold bg-amber-500/20 text-amber-400 border border-amber-500/40 flex-shrink-0">
            SHADOW MODE ACTIVE
          </span>
        ) : (
          <span className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 flex-shrink-0">
            PRODUCTION MODE
          </span>
        )}
      </div>

      {!shadowMode && (
        <div className="p-6 rounded-2xl bg-amber-500/10 border border-amber-500/40 flex items-start gap-4">
          <AlertTriangle className="w-7 h-7 text-amber-400 flex-shrink-0 mt-0.5" />
          <div>
            <div className="font-bold text-amber-300 text-base mb-1">Shadow Mode is not active</div>
            <p className="text-sm text-amber-200/70">
              This panel is only used during AI model validation. Enable Shadow Mode in Settings to start recording human ground-truth inspection decisions for comparison against AI outcomes.
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Decision Form */}
        <div className={`card p-8 space-y-6 ${!shadowMode ? 'opacity-50 pointer-events-none' : ''}`}>
          <div className="text-sm font-semibold uppercase tracking-wide text-zinc-400 border-b border-surface-700 pb-4">
            Record Human Inspection Decision
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-zinc-400 mb-2">Seat ID <span className="text-danger-400">*</span></label>
              <input
                type="text"
                value={seatId}
                onChange={e => setSeatId(e.target.value)}
                placeholder="e.g. SEAT_2026_1031_0089"
                className="w-full font-mono text-sm"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-zinc-400 mb-2">Inspector ID <span className="text-danger-400">*</span></label>
              <input
                type="text"
                value={inspectorId}
                onChange={e => setInspectorId(e.target.value)}
                placeholder="e.g. OP_ALPHA or your name"
                className="w-full text-sm"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-zinc-400 mb-2">Notes <span className="text-zinc-600">(optional)</span></label>
              <textarea
                value={notes}
                onChange={e => setNotes(e.target.value)}
                rows={3}
                placeholder="Describe what you physically observed on the seat..."
                className="w-full text-sm resize-none"
              />
            </div>
          </div>

          {errorMsg && (
            <div className="p-3 bg-danger-900/20 border border-danger-500/40 text-danger-400 text-sm rounded-xl flex items-center gap-2">
              <XCircle className="w-4 h-4 flex-shrink-0" />
              {errorMsg}
            </div>
          )}

          <div className="flex gap-3 pt-2">
            <button
              onClick={() => handleSubmit('PASS')}
              disabled={submitting}
              className="flex-1 py-3 rounded-xl font-bold text-sm text-white bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 transition-colors flex items-center justify-center gap-2 shadow-lg shadow-emerald-600/20"
            >
              <CheckCircle className="w-5 h-5" />
              {submitting ? 'Recording...' : 'PASS — Seat is Good'}
            </button>
            <button
              onClick={() => handleSubmit('FAIL')}
              disabled={submitting}
              className="flex-1 py-3 rounded-xl font-bold text-sm text-white bg-rose-600 hover:bg-rose-500 disabled:opacity-50 transition-colors flex items-center justify-center gap-2 shadow-lg shadow-rose-600/20"
            >
              <XCircle className="w-5 h-5" />
              {submitting ? 'Recording...' : 'FAIL — Seat has Defect'}
            </button>
          </div>

          <div className="pt-2 text-xs text-zinc-500 border-t border-surface-700">
            Each decision is stored and compared against the AI's logged decision for this seat. Results feed into the Shift Report Agreement Rate, False Reject Rate, and Escape Rate metrics.
          </div>
        </div>

        {/* Recent Decisions Log */}
        <div className="card p-8 space-y-4">
          <div className="text-sm font-semibold uppercase tracking-wide text-zinc-400 border-b border-surface-700 pb-4 flex items-center gap-2">
            <ClipboardList className="w-4 h-4 text-primary-400" />
            Decisions Recorded This Session
          </div>

          {successToast && (
            <div className="p-3 bg-success-900/20 text-success-400 text-xs rounded-xl border border-success-500 flex items-center gap-2">
              <CheckCircle className="w-4 h-4 flex-shrink-0" />
              {successToast}
            </div>
          )}

          {recentDecisions.length === 0 ? (
            <div className="py-12 text-center text-zinc-500 text-sm">
              <ClipboardList className="w-10 h-10 mx-auto mb-3 text-zinc-700" />
              No decisions recorded this session yet.
              <br />
              Use the form to log your human inspection verdicts.
            </div>
          ) : (
            <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
              {recentDecisions.map((d, i) => (
                <div key={i} className="flex items-center justify-between p-3 rounded-xl bg-surface-900 border border-surface-700">
                  <div>
                    <div className="text-sm font-semibold text-white font-mono">{d.seat_id}</div>
                    <div className="text-xs text-zinc-500 mt-0.5">{d.inspector_id} · {d.timestamp}</div>
                    {d.notes && <div className="text-xs text-zinc-400 mt-0.5 italic">"{d.notes}"</div>}
                  </div>
                  <span className={`px-2.5 py-1 rounded text-xs font-bold ${
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
    </div>
  )
}

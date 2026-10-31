import { useEffect, useState } from 'react'
import { apiClient } from '../lib/api'
import { FileText, Shield, AlertTriangle, CheckCircle, RefreshCw, Download } from 'lucide-react'

export default function ShiftReport() {
  const [report, setReport] = useState<any>(null)
  const [shadowMode, setShadowMode] = useState(false)
  const [loading, setLoading] = useState(true)
  const [threshold, setThreshold] = useState(3.0)

  const fetchReport = async () => {
    setLoading(true)
    try {
      const [data, settings] = await Promise.all([
        apiClient.getShiftReport(threshold),
        apiClient.getSystemSettings().catch(() => ({ shadow_mode: false })),
      ])
      setReport(data)
      setShadowMode(!!(settings as any)?.shadow_mode)
    } catch (error) {
      console.error('Failed to fetch shift report:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchReport()
  }, [threshold])

  const handleDownloadPDF = () => {
    window.print()
  }

  return (
    <div className="space-y-8 print:space-y-4 print:text-black">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 print:hidden">
        <div>
          <h2 className="font-bold text-white text-2xl flex items-center gap-2">
            <FileText className="w-6 h-6 text-primary-400" />
            Shift Report & Shadow Mode Analytics
          </h2>
          <p className="text-sm text-zinc-400 mt-1">Comprehensive quality summary, false-reject tracking, and AI vs human agreement</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="text-xs text-zinc-400 font-medium">False Reject Threshold (%):</label>
          <input
            type="number"
            step="0.5"
            min="0.5"
            max="20"
            value={threshold}
            onChange={(e) => setThreshold(Number(e.target.value))}
            className="w-24 text-xs py-1.5 px-3"
          />
          <button onClick={fetchReport} className="btn-ghost p-2" title="Refresh">
            <RefreshCw className="w-4 h-4" />
          </button>
          <button onClick={handleDownloadPDF} className="btn-primary flex items-center gap-2 text-xs">
            <Download className="w-4 h-4" />
            Download PDF Report
          </button>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-20 text-zinc-400">Generating shift report...</div>
      ) : !report ? (
        <div className="text-center py-20 text-zinc-400">Failed to load shift report</div>
      ) : (
        <>
          {/* Summary KPI Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="stat-card">
              <div className="stat-label">Total Inspected</div>
              <div className="stat-value text-white">{report.total_inspected ?? 0}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">AI Pass Rate</div>
              <div className="stat-value text-success-400">
                {report.total_inspected > 0
                  ? ((report.camera_pass_count / report.total_inspected) * 100).toFixed(1)
                  : '0.0'}%
              </div>
            </div>
            <div className="stat-card border-warning-900/50">
              <div className="stat-label">False Reject Rate</div>
              <div className="stat-value text-warning-400">
                {((report.false_reject_rate ?? 0) * 100).toFixed(2)}%
              </div>
            </div>
            <div className="stat-card border-danger-900/50">
              <div className="stat-label">Escape Rate</div>
              <div className="stat-value text-danger-400">
                {((report.escape_rate ?? 0) * 100).toFixed(2)}%
              </div>
            </div>
          </div>

          {/* Shadow Mode & Agreement Details */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div className="card p-6 space-y-4">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-zinc-400 flex items-center gap-2">
                <Shield className="w-4 h-4 text-primary-400" />
                Shadow Mode & Agreement
              </h3>
              <div className="space-y-3 text-sm text-zinc-300 bg-surface-900 p-4 rounded-xl border border-surface-700">
                <div className="flex justify-between items-center">
                  <span>Shadow Mode Status:</span>
                  {shadowMode ? (
                    <span className="px-2.5 py-1 rounded text-xs font-bold bg-amber-500/20 text-amber-400 border border-amber-500/40">
                      ACTIVE (Simulation)
                    </span>
                  ) : (
                    <span className="px-2.5 py-1 rounded text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/40">
                      INACTIVE (Production)
                    </span>
                  )}
                </div>
                <div className="flex justify-between">
                  <span>Agreement Rate:</span>
                  <span className="font-mono text-success-400">
                    {report.agreement_rate !== undefined
                      ? `${(report.agreement_rate * 100).toFixed(1)}%`
                      : 'N/A'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Human Decisions Recorded:</span>
                  <span className="font-mono text-white">{report.human_decisions_count ?? 0}</span>
                </div>
                <div className="flex justify-between">
                  <span>Compared Sample Size:</span>
                  <span className="font-mono text-white">{report.compared_sample_size ?? 0}</span>
                </div>
                {report.human_decisions_count === 0 && (
                  <div className="pt-2 text-xs text-amber-400 border-t border-surface-700 flex items-start gap-2">
                    <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                    No human decisions recorded yet. Use the Shadow Inspector module to log ground-truth decisions for AI comparison.
                  </div>
                )}
              </div>
            </div>

            <div className="card p-6 space-y-4">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-zinc-400 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-warning-400" />
                Quality Recommendations
              </h3>
              <div className="space-y-2 text-sm text-zinc-300">
                {report.flagged_false_reject_warning && (
                  <div className="p-3 bg-danger-900/20 rounded-lg border border-danger-500/40 flex items-start gap-2 text-danger-300">
                    <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5 text-danger-400" />
                    <span>False-reject rate exceeds {report.threshold_pct?.toFixed(1)}% threshold. Retune station tolerances or inspect camera lighting.</span>
                  </div>
                )}
                {report.recommendations && report.recommendations.length > 0 ? (
                  report.recommendations.map((rec: string, idx: number) => (
                    <div key={idx} className="p-3 bg-surface-900 rounded-lg border border-surface-700 flex items-start gap-2">
                      <span className="text-primary-400 font-bold">•</span>
                      <span>{rec}</span>
                    </div>
                  ))
                ) : (
                  <div className="p-4 bg-surface-900 rounded-lg border border-surface-700 text-zinc-400 flex items-center gap-2">
                    <CheckCircle className="w-5 h-5 text-success-400" />
                    <span>No process anomalies or threshold violations detected. Line operating within nominal limits.</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}


import { useState } from 'react'
import { Tag, Plus, Trash2, CheckCircle } from 'lucide-react'

export default function DefectTaxonomy() {
  const [defects, setDefects] = useState([
    { id: 1, code: 'loose_stitch', name: 'Loose Stitch / Thread Tail', severity: 'MAJOR', threshold: 0.65, active: true },
    { id: 2, code: 'leather_wrinkle', name: 'Leather Surface Wrinkle', severity: 'MINOR', threshold: 0.50, active: true },
    { id: 3, code: 'scratch_mark', name: 'Plastic Shield Scuff / Scratch', severity: 'MINOR', threshold: 0.55, active: true },
    { id: 4, code: 'missing_clip', name: 'Missing Retaining Clip', severity: 'CRITICAL', threshold: 0.75, active: true },
  ])
  const [newCode, setNewCode] = useState('')
  const [newName, setNewName] = useState('')
  const [newSeverity, setNewSeverity] = useState('MAJOR')
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const handleAdd = (e: React.FormEvent) => {
    e.preventDefault()
    if (!newCode || !newName) return
    const newItem = {
      id: Date.now(),
      code: newCode.toLowerCase().replace(/\s+/g, '_'),
      name: newName,
      severity: newSeverity,
      threshold: 0.60,
      active: true,
    }
    setDefects([...defects, newItem])
    setNewCode('')
    setNewName('')
    setSuccessMsg('New defect category added successfully.')
    setTimeout(() => setSuccessMsg(null), 3000)
  }

  const handleDelete = (id: number) => {
    setDefects(defects.filter(d => d.id !== id))
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="font-bold text-white text-3xl flex items-center gap-3">
            <Tag className="w-8 h-8 text-primary-400" />
            Dynamic Defect Taxonomy & Severity Editor
          </h2>
          <p className="text-sm text-zinc-400 mt-1">Manage inspection classification rules, defect categories, and severity thresholds</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Add New Defect Form */}
        <div className="card p-6 space-y-6">
          <div className="text-sm font-semibold uppercase tracking-wide text-zinc-400 flex items-center gap-2">
            <Plus className="w-4 h-4 text-primary-400" />
            Add Defect Category
          </div>

          <form onSubmit={handleAdd} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">Defect Code (Slug)</label>
              <input
                type="text"
                value={newCode}
                onChange={(e) => setNewCode(e.target.value)}
                placeholder="e.g. leather_tear"
                className="w-full text-xs font-mono"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">Display Name</label>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="e.g. Leather Tear / Puncture"
                className="w-full text-xs"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">Severity Level</label>
              <select
                value={newSeverity}
                onChange={(e) => setNewSeverity(e.target.value)}
                className="w-full text-xs"
              >
                <option value="MINOR">MINOR (Warning)</option>
                <option value="MAJOR">MAJOR (Rework)</option>
                <option value="CRITICAL">CRITICAL (Scrap / Stop)</option>
              </select>
            </div>

            {successMsg && (
              <div className="p-3 bg-success-900/20 text-success-400 text-xs rounded-xl border border-success-500 flex items-center gap-2">
                <CheckCircle className="w-4 h-4 flex-shrink-0" />
                {successMsg}
              </div>
            )}

            <button type="submit" className="w-full btn-primary py-2.5 text-xs font-semibold flex items-center justify-center gap-2">
              <Plus className="w-4 h-4" />
              Add Taxonomy Item
            </button>
          </form>
        </div>

        {/* Taxonomy List Table */}
        <div className="lg:col-span-2 card p-6 space-y-4">
          <div className="text-sm font-semibold uppercase tracking-wider text-zinc-400 border-b border-surface-700 pb-4">
            Active Defect Taxonomy Rules ({defects.length})
          </div>

          <div className="space-y-3 max-h-[440px] overflow-y-auto pr-2">
            {defects.map((def) => (
              <div key={def.id} className="bg-surface-900 p-4 rounded-xl border border-surface-700 flex items-center justify-between">
                <div className="space-y-1">
                  <div className="flex items-center gap-3">
                    <span className="font-bold text-white text-sm">{def.name}</span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      def.severity === 'CRITICAL' ? 'bg-danger-900/40 text-danger-400 border border-danger-500/30' :
                      def.severity === 'MAJOR' ? 'bg-warning-900/40 text-warning-400 border border-warning-500/30' :
                      'bg-surface-800 text-zinc-300'
                    }`}>
                      {def.severity}
                    </span>
                  </div>
                  <div className="text-xs font-mono text-zinc-400">Code: {def.code} • Threshold: {def.threshold}</div>
                </div>
                <div className="flex items-center gap-3">
                  <button onClick={() => handleDelete(def.id)} className="p-2 text-zinc-500 hover:text-danger-400 transition-colors" title="Delete Rule">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

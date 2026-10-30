import { useState, useEffect } from 'react'
import { apiClient } from '../lib/api'
import { Sliders, Save, RefreshCw, CheckCircle, AlertCircle, Shield, Cpu, Layers, Code, FormInput } from 'lucide-react'
import { audioAlerts } from '../lib/audioAlerts'

export default function ConfigManagement() {
  const [activeTab, setActiveTab] = useState<'STATION_1' | 'STATION_2' | 'STATION_3' | 'STATION_4' | 'LIMITS'>('STATION_2')
  const [stationsData, setStationsData] = useState<Record<string, any>>({})
  const [limitsData, setLimitsData] = useState<Record<string, any>>({})
  const [currentConfig, setCurrentConfig] = useState<any>(null)
  const [viewMode, setViewMode] = useState<'form' | 'json'>('form')
  const [jsonText, setJsonText] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const loadData = async () => {
    setLoading(true)
    setErrorMsg(null)
    try {
      const stRes = await apiClient.getConfigStations()
      const stations = (stRes.stations as Record<string, unknown>) || stRes
      setStationsData(stations)

      const limRes = await apiClient.getLimitsConfig()
      setLimitsData(limRes)

      if (activeTab === 'LIMITS') {
        setCurrentConfig(JSON.parse(JSON.stringify(limRes)))
        setJsonText(JSON.stringify(limRes, null, 2))
      } else if (stations[activeTab]) {
        setCurrentConfig(JSON.parse(JSON.stringify(stations[activeTab])))
        setJsonText(JSON.stringify(stations[activeTab], null, 2))
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to load configuration')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  useEffect(() => {
    if (activeTab === 'LIMITS') {
      setCurrentConfig(JSON.parse(JSON.stringify(limitsData)))
      setJsonText(JSON.stringify(limitsData, null, 2))
    } else if (stationsData[activeTab]) {
      setCurrentConfig(JSON.parse(JSON.stringify(stationsData[activeTab])))
      setJsonText(JSON.stringify(stationsData[activeTab], null, 2))
    }
    setErrorMsg(null)
    setSuccessMsg(null)
  }, [activeTab, stationsData, limitsData])

  const handleFieldChange = (path: Array<string | number>, value: any) => {
    const updated = JSON.parse(JSON.stringify(currentConfig))
    let curr = updated
    for (let i = 0; i < path.length - 1; i++) {
      if (!curr[path[i]]) curr[path[i]] = {}
      curr = curr[path[i]]
    }
    curr[path[path.length - 1]] = value
    setCurrentConfig(updated)
    setJsonText(JSON.stringify(updated, null, 2))
  }

  const handleSave = async () => {
    setSaving(true)
    setErrorMsg(null)
    setSuccessMsg(null)
    try {
      const payload = viewMode === 'json' ? JSON.parse(jsonText) : currentConfig
      if (activeTab === 'LIMITS') {
        const res = await apiClient.updateLimitsConfig(payload)
        setLimitsData(res.limits || payload)
        setSuccessMsg('Global limits configuration updated successfully and recorded in audit log.')
      } else {
        const res = await apiClient.updateStationConfig(activeTab, payload)
        setStationsData(prev => ({ ...prev, [activeTab]: res.config || payload }))
        setSuccessMsg(`${activeTab} configuration updated successfully and recorded in audit log. (Restart required for live camera updates)`)
      }
      audioAlerts.playPassChime()
    } catch (err: unknown) {
      if (err instanceof SyntaxError) {
        setErrorMsg('Invalid JSON syntax in text editor mode. Please fix formatting.')
      } else {
        setErrorMsg(err instanceof Error ? err.message : 'Failed to save configuration')
      }
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <div className="text-center py-20 text-zinc-400">Loading Configuration Manager...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-bold text-white text-2xl flex items-center gap-3">
            <Sliders className="w-7 h-7 text-primary-400" />
            Configuration & Threshold Manager
          </h2>
          <p className="text-zinc-400 text-sm mt-1">
            Tune station inspection parameters, AI model confidence, IoU thresholds, ROIs, and OEM engineering limits with runtime validation and audit logging.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex bg-surface-800 p-1 rounded-xl border border-surface-700">
            <button
              onClick={() => setViewMode('form')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                viewMode === 'form' ? 'bg-primary-600 text-white' : 'text-zinc-400 hover:text-white'
              }`}
            >
              <FormInput className="w-3.5 h-3.5" />
              Structured Form
            </button>
            <button
              onClick={() => {
                if (currentConfig) setJsonText(JSON.stringify(currentConfig, null, 2))
                setViewMode('json')
              }}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                viewMode === 'json' ? 'bg-primary-600 text-white' : 'text-zinc-400 hover:text-white'
              }`}
            >
              <Code className="w-3.5 h-3.5" />
              Raw JSON
            </button>
          </div>
          <button
            onClick={loadData}
            className="flex items-center gap-2 px-4 py-2 bg-surface-800 hover:bg-surface-700 text-zinc-200 rounded-xl border border-surface-700 transition"
          >
            <RefreshCw className="w-4 h-4" />
            Reload
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap gap-2 border-b border-surface-700 pb-4">
        {[
          { id: 'STATION_1', label: 'Station 1 (Leather)', icon: Shield },
          { id: 'STATION_2', label: 'Station 2 (Stitch)', icon: Layers },
          { id: 'STATION_3', label: 'Station 3 (Plastic)', icon: Cpu },
          { id: 'STATION_4', label: 'Station 4 (Complete)', icon: CheckCircle },
          { id: 'LIMITS', label: 'Global Limits & Tolerances', icon: Sliders },
        ].map(tab => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition ${
                isActive
                  ? 'bg-primary-600 text-white shadow-lg shadow-primary-600/30'
                  : 'bg-surface-800 text-zinc-400 hover:bg-surface-700 hover:text-white border border-surface-700'
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          )
        })}
      </div>

      {successMsg && (
        <div className="p-4 rounded-xl bg-success-500/10 border border-success-500/30 text-success-300 flex items-center gap-3">
          <CheckCircle className="w-5 h-5 flex-shrink-0 text-success-400" />
          <span>{successMsg}</span>
        </div>
      )}

      {errorMsg && (
        <div className="p-4 rounded-xl bg-danger-500/10 border border-danger-500/30 text-danger-300 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 flex-shrink-0 text-danger-400" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Main Content Card */}
      <div className="card">
        <div className="card-header flex items-center justify-between">
          <span className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
            {activeTab === 'LIMITS' ? 'Global Engineering Limits (default_limits.yaml)' : `${activeTab} Structured Parameters`}
          </span>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-5 py-2.5 bg-primary-600 hover:bg-primary-500 disabled:bg-surface-700 text-white font-semibold rounded-xl transition shadow-lg shadow-primary-600/30"
          >
            <Save className="w-4 h-4" />
            {saving ? 'Validating & Saving...' : 'Save & Log Audit'}
          </button>
        </div>

        <div className="p-6">
          {viewMode === 'json' ? (
            <div>
              <textarea
                value={jsonText}
                onChange={e => setJsonText(e.target.value)}
                rows={22}
                className="w-full font-mono text-sm bg-surface-950 text-zinc-200 p-4 rounded-xl border border-surface-700 focus:outline-none focus:border-primary-500 leading-relaxed"
                spellCheck={false}
              />
              <div className="flex items-center justify-between mt-4 text-xs text-zinc-500">
                <span>Changes are validated against backend Pydantic models before persistence.</span>
                <span>Immutable audit log entry is recorded automatically upon success.</span>
              </div>
            </div>
          ) : currentConfig ? (
            <div className="space-y-8">
              {/* Station Basic Info */}
              {activeTab !== 'LIMITS' && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 bg-surface-950 p-6 rounded-2xl border border-surface-700">
                  <div>
                    <label className="block text-xs font-semibold text-zinc-400 uppercase mb-2">Station Name</label>
                    <input
                      type="text"
                      value={currentConfig.name || ''}
                      onChange={e => handleFieldChange(['name'], e.target.value)}
                      className="w-full bg-surface-900 border border-surface-700 rounded-xl px-4 py-2.5 text-white text-sm focus:outline-none focus:border-primary-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-zinc-400 uppercase mb-2">Enabled Status</label>
                    <div className="flex items-center gap-3 pt-2">
                      <input
                        type="checkbox"
                        checked={!!currentConfig.enabled}
                        onChange={e => handleFieldChange(['enabled'], e.target.checked)}
                        className="w-5 h-5 accent-primary-600 rounded bg-surface-900 border-surface-700"
                      />
                      <span className="text-sm text-zinc-200">{currentConfig.enabled ? 'Station Active' : 'Station Disabled'}</span>
                    </div>
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-xs font-semibold text-zinc-400 uppercase mb-2">Description</label>
                    <input
                      type="text"
                      value={currentConfig.description || ''}
                      onChange={e => handleFieldChange(['description'], e.target.value)}
                      className="w-full bg-surface-900 border border-surface-700 rounded-xl px-4 py-2.5 text-white text-sm focus:outline-none focus:border-primary-500"
                    />
                  </div>
                </div>
              )}

              {/* AI Model Thresholds */}
              {activeTab !== 'LIMITS' && currentConfig.model && (
                <div className="bg-surface-950 p-6 rounded-2xl border border-surface-700 space-y-6">
                  <h3 className="text-base font-bold text-white flex items-center gap-2">
                    <Cpu className="w-5 h-5 text-primary-400" />
                    AI Model & Inference Thresholds
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div>
                      <label className="block text-xs font-semibold text-zinc-400 uppercase mb-2">
                        Confidence Threshold: {currentConfig.model.confidence_threshold ?? currentConfig.model.threshold ?? 0.5}
                      </label>
                      <input
                        type="range"
                        min="0.1"
                        max="0.95"
                        step="0.05"
                        value={currentConfig.model.confidence_threshold ?? currentConfig.model.threshold ?? 0.5}
                        onChange={e => {
                          const val = parseFloat(e.target.value)
                          handleFieldChange(['model', 'confidence_threshold'], val)
                          handleFieldChange(['model', 'threshold'], val)
                        }}
                        className="w-full accent-primary-600"
                      />
                      <div className="flex justify-between text-[10px] text-zinc-500 mt-1">
                        <span>0.1 (Permissive)</span>
                        <span>0.5 (Default)</span>
                        <span>0.95 (Strict)</span>
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-zinc-400 uppercase mb-2">
                        IoU Threshold: {currentConfig.model.iou_threshold ?? 0.35}
                      </label>
                      <input
                        type="range"
                        min="0.1"
                        max="0.8"
                        step="0.05"
                        value={currentConfig.model.iou_threshold ?? 0.35}
                        onChange={e => handleFieldChange(['model', 'iou_threshold'], parseFloat(e.target.value))}
                        className="w-full accent-primary-600"
                      />
                      <div className="flex justify-between text-[10px] text-zinc-500 mt-1">
                        <span>0.1</span>
                        <span>0.35</span>
                        <span>0.8</span>
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-zinc-400 uppercase mb-2">Backend</label>
                      <select
                        value={currentConfig.model.backend || 'onnx'}
                        onChange={e => handleFieldChange(['model', 'backend'], e.target.value)}
                        className="w-full bg-surface-900 border border-surface-700 rounded-xl px-4 py-2.5 text-white text-sm focus:outline-none focus:border-primary-500"
                      >
                        <option value="onnx">ONNX Runtime</option>
                        <option value="mock">Mock Inference</option>
                        <option value="patchcore">PatchCore (Anomaly)</option>
                      </select>
                    </div>
                  </div>
                </div>
              )}

              {/* Regions of Interest (ROIs) */}
              {activeTab !== 'LIMITS' && currentConfig.regions_of_interest && (
                <div className="bg-surface-950 p-6 rounded-2xl border border-surface-700 space-y-6">
                  <h3 className="text-base font-bold text-white flex items-center gap-2">
                    <Sliders className="w-5 h-5 text-primary-400" />
                    Regions of Interest (ROIs)
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {Object.entries(currentConfig.regions_of_interest).map(([roiName, roiVal]: [string, any]) => (
                      <div key={roiName} className="bg-surface-900 p-4 rounded-xl border border-surface-700 space-y-3">
                        <div className="font-semibold text-sm text-primary-300">{roiName}</div>
                        <div className="grid grid-cols-4 gap-3">
                          {['x', 'y', 'w', 'h'].map(coord => (
                            <div key={coord}>
                              <label className="block text-[10px] font-semibold text-zinc-400 uppercase mb-1">{coord}</label>
                              <input
                                type="number"
                                value={String(roiVal[coord] ?? roiVal[coord === 'w' ? 'width' : coord === 'h' ? 'height' : coord] ?? 0)}
                                onChange={e => handleFieldChange(['regions_of_interest', roiName, coord], parseInt(e.target.value) || 0)}
                                className="w-full bg-surface-950 border border-surface-700 rounded-lg px-3 py-1.5 text-white text-xs text-center focus:outline-none focus:border-primary-500"
                              />
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Camera Configurations */}
              {activeTab !== 'LIMITS' && currentConfig.cameras && currentConfig.cameras.length > 0 && (
                <div className="bg-surface-950 p-6 rounded-2xl border border-surface-700 space-y-6">
                  <h3 className="text-base font-bold text-white flex items-center gap-2">
                    <Shield className="w-5 h-5 text-primary-400" />
                    Camera Adapters & Exposure Settings
                  </h3>
                  <div className="space-y-4">
                    {currentConfig.cameras.map((cam: any, idx: number) => (
                      <div key={cam.name || idx} className="bg-surface-900 p-4 rounded-xl border border-surface-700 grid grid-cols-1 md:grid-cols-4 gap-4 items-center">
                        <div>
                          <div className="font-semibold text-white text-sm">{cam.name}</div>
                          <div className="text-xs text-zinc-500">View: {cam.view}</div>
                        </div>
                        <div>
                          <label className="block text-[10px] font-semibold text-zinc-400 uppercase mb-1">Adapter</label>
                          <select
                            value={String(cam.adapter || 'replay')}
                            onChange={e => handleFieldChange(['cameras', idx, 'adapter'], e.target.value as any)}
                            className="w-full bg-surface-950 border border-surface-700 rounded-lg px-3 py-1.5 text-white text-xs focus:outline-none focus:border-primary-500"
                          >
                            <option value="replay">Replay (Folder)</option>
                            <option value="synthetic">Synthetic</option>
                            <option value="webcam">Webcam USB</option>
                            <option value="basler">Basler Industrial</option>
                            <option value="hikrobot">Hikrobot Industrial</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-[10px] font-semibold text-zinc-400 uppercase mb-1">Exposure (µs)</label>
                          <input
                            type="number"
                            value={String(cam.exposure_us || 15000)}
                            onChange={e => handleFieldChange(['cameras', idx, 'exposure_us'], (parseInt(e.target.value) || 15000) as any)}
                            className="w-full bg-surface-950 border border-surface-700 rounded-lg px-3 py-1.5 text-white text-xs focus:outline-none focus:border-primary-500"
                          />
                        </div>
                        <div>
                          <label className="block text-[10px] font-semibold text-zinc-400 uppercase mb-1">Pixel Size (mm)</label>
                          <input
                            type="number"
                            step="0.005"
                            value={String(cam.pixel_size_mm || 0.08)}
                            onChange={e => handleFieldChange(['cameras', idx, 'pixel_size_mm'], (parseFloat(e.target.value) || 0.08) as any)}
                            className="w-full bg-surface-950 border border-surface-700 rounded-lg px-3 py-1.5 text-white text-xs focus:outline-none focus:border-primary-500"
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Limits Structured Editor */}
              {activeTab === 'LIMITS' && currentConfig.limits && (
                <div className="space-y-6">
                  {Object.entries(currentConfig.limits).map(([category, catObj]: [string, any]) => (
                    <div key={category} className="bg-surface-950 p-6 rounded-2xl border border-surface-700 space-y-4">
                      <h3 className="text-base font-bold text-white uppercase tracking-wider text-primary-300">
                        {category} Inspection Limits
                      </h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {Object.entries(catObj).map(([paramName, paramVal]: [string, any]) => (
                          <div key={paramName} className="bg-surface-900 p-4 rounded-xl border border-surface-700 space-y-3">
                            <div className="font-semibold text-sm text-white">{paramName}</div>
                            {typeof paramVal === 'object' && paramVal !== null ? (
                              <div className="grid grid-cols-2 gap-3">
                                {Object.entries(paramVal).map(([subKey, subVal]: [string, any]) => (
                                  typeof subVal === 'number' || typeof subVal === 'string' ? (
                                    <div key={subKey}>
                                      <label className="block text-[10px] font-semibold text-zinc-400 uppercase mb-1">{subKey}</label>
                                      <input
                                        type="number"
                                        step="any"
                                        value={String(subVal)}
                                        onChange={e => handleFieldChange(['limits', category, paramName, subKey], parseFloat(e.target.value) || 0)}
                                        className="w-full bg-surface-950 border border-surface-700 rounded-lg px-3 py-1.5 text-white text-xs focus:outline-none focus:border-primary-500"
                                      />
                                    </div>
                                  ) : typeof subVal === 'boolean' ? (
                                    <div key={subKey} className="flex items-center gap-2 pt-2">
                                      <input
                                        type="checkbox"
                                        checked={subVal}
                                        onChange={e => handleFieldChange(['limits', category, paramName, subKey], e.target.checked)}
                                        className="w-4 h-4 accent-primary-600 rounded bg-surface-950"
                                      />
                                      <span className="text-xs text-zinc-300">{subKey}</span>
                                    </div>
                                  ) : null
                                ))}
                              </div>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-12 text-zinc-500">No configuration loaded</div>
          )}
        </div>
      </div>
    </div>
  )
}

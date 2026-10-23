import { apiClient } from '../lib/api'
import { useEffect, useState } from 'react'
import { Save, TestTube, RefreshCw, Camera, Trash2, CheckCircle, XCircle } from 'lucide-react'

interface SystemSettings {
  save_images: boolean
  shadow_mode: boolean
  storage?: {
    total_mb: number
    used_mb: number
    free_mb: number
  }
}

export default function Settings() {
  const [apiUrl, setApiUrl] = useState('http://127.0.0.1:8000')
  const [apiKey, setApiKey] = useState('')
  const [refreshInterval, setRefreshInterval] = useState('5')
  const [settings, setSettings] = useState<SystemSettings | null>(null)
  const [testResult, setTestResult] = useState('')
  const [saveResult, setSaveResult] = useState('')
  const [cameras, setCameras] = useState<any[]>([])
  const [detecting, setDetecting] = useState(false)
  const [testingCameraId, setTestingCameraId] = useState<string | null>(null)
  const [cameraTestResult, setCameraTestResult] = useState<any>(null)
  const [cleanupResult, setCleanupResult] = useState<any>(null)
  const [cleaningUp, setCleaningUp] = useState(false)

  useEffect(() => {
    const savedUrl = localStorage.getItem('sg_api_url')
    const savedKey = localStorage.getItem('sg_api_key')
    const savedInterval = localStorage.getItem('sg_refresh_s')

    if (savedUrl) setApiUrl(savedUrl)
    if (savedKey) {
      setApiKey(savedKey)
      apiClient.setApiKey(savedKey)
    }
    if (savedInterval) setRefreshInterval(savedInterval)

    fetchSystemSettings()
    fetchCamerasStatus()
  }, [])

  const fetchSystemSettings = async () => {
    try {
      const result = await apiClient.getSystemSettings()
      setSettings(result as SystemSettings)
    } catch (error) {
      console.error('Failed to fetch system settings:', error)
    }
  }

  const fetchCamerasStatus = async () => {
    try {
      const res = (await apiClient.getAllCamerasStatus()) as any
      setCameras(res?.cameras || [])
    } catch (err) {
      console.error('Failed to fetch camera status:', err)
    }
  }

  const handleSave = () => {
    localStorage.setItem('sg_api_url', apiUrl)
    localStorage.setItem('sg_api_key', apiKey)
    localStorage.setItem('sg_refresh_s', refreshInterval)
    apiClient.setApiKey(apiKey)
    setSaveResult('✓ Configuration saved successfully')
    setTimeout(() => setSaveResult(''), 3000)
  }

  const handleTest = async () => {
    try {
      const result = await apiClient.health()
      setTestResult(`✓ Connected: ${result?.service || 'API'} v${result?.version || '0.1.0'}`)
    } catch (error) {
      setTestResult(`✗ Connection failed: ${error}`)
    }
    setTimeout(() => setTestResult(''), 5000)
  }

  const toggleSaveImages = async () => {
    if (!settings) return
    try {
      await apiClient.setSaveImages(!settings.save_images)
      await fetchSystemSettings()
    } catch (error) {
      console.error('Failed to toggle save images:', error)
    }
  }

  const toggleShadowMode = async () => {
    if (!settings) return
    try {
      await apiClient.setShadowMode(!settings.shadow_mode)
      await fetchSystemSettings()
    } catch (error) {
      console.error('Failed to toggle shadow mode:', error)
    }
  }

  const handleDetectCameras = async () => {
    setDetecting(true)
    try {
      const res = (await apiClient.detectCameras()) as any
      setCameras(res?.cameras || [])
      alert(`Detected ${res?.count || 0} cameras successfully.`)
    } catch (err) {
      console.error('Camera detection failed:', err)
      alert('Camera detection failed')
    } finally {
      setDetecting(false)
    }
  }

  const handleTestCamera = async (adapter: string, cameraId: string) => {
    setTestingCameraId(cameraId)
    setCameraTestResult(null)
    try {
      const res = await apiClient.testCamera(adapter, String(cameraId))
      setCameraTestResult(res)
    } catch (err) {
      console.error('Camera test failed:', err)
      setCameraTestResult({ connected: false, error: String(err) })
    } finally {
      setTestingCameraId(null)
    }
  }

  const handleCleanup = async (dryRun: boolean) => {
    setCleaningUp(true)
    try {
      const res = (await apiClient.cleanupImages(dryRun)) as any
      setCleanupResult(res)
    } catch (err) {
      console.error('Cleanup failed:', err)
      alert('Image cleanup failed')
    } finally {
      setCleaningUp(false)
    }
  }

  return (
    <div className="space-y-8">
      <h2 className="font-bold text-white text-2xl">Settings & Hardware Management</h2>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* API Configuration */}
        <div className="card p-8 space-y-6">
          <div className="text-sm font-semibold uppercase tracking-wide text-zinc-400">API Configuration</div>
          <div>
            <label className="block text-sm font-medium text-zinc-400 mb-2">Base URL</label>
            <input type="text" value={apiUrl} onChange={(e) => setApiUrl(e.target.value)} className="w-full" />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-400 mb-2">X-API-Key</label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Enter Token"
              className="w-full"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-400 mb-2">Refresh Interval (sec)</label>
            <input
              type="text"
              value={refreshInterval}
              onChange={(e) => setRefreshInterval(e.target.value)}
              className="w-full"
            />
          </div>
          <div className="flex gap-4 pt-4">
            <button onClick={handleSave} className="btn-primary flex items-center gap-2">
              <Save className="w-4 h-4" />
              Save Configuration
            </button>
            <button onClick={handleTest} className="btn-ghost flex items-center gap-2">
              <TestTube className="w-4 h-4" />
              Test Connect
            </button>
          </div>
          {saveResult && <div className="text-sm font-medium text-success-400">{saveResult}</div>}
          {testResult && <div className="text-sm font-medium">{testResult}</div>}
        </div>

        {/* Runtime Settings & Storage Cleanup */}
        <div className="card p-8 space-y-6">
          <div className="text-sm font-semibold uppercase tracking-wide text-zinc-400">Runtime & Storage</div>

          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 rounded-xl bg-surface-900 border border-surface-700">
              <div>
                <div className="font-semibold text-white">Save Images</div>
                <div className="text-xs text-zinc-500">Store captured inspection images</div>
              </div>
              <button
                onClick={toggleSaveImages}
                className={`relative w-11 h-6 rounded-full transition-colors duration-200 ${
                  settings?.save_images ? 'bg-primary-600' : 'bg-zinc-700'
                }`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 ${
                    settings?.save_images ? 'translate-x-5' : ''
                  }`}
                />
              </button>
            </div>

            <div className="flex items-center justify-between p-4 rounded-xl bg-surface-900 border border-surface-700">
              <div>
                <div className="font-semibold text-white">Shadow Mode</div>
                <div className="text-xs text-zinc-500">Compare AI vs Human decisions</div>
              </div>
              <button
                onClick={toggleShadowMode}
                className={`relative w-11 h-6 rounded-full transition-colors duration-200 ${
                  settings?.shadow_mode ? 'bg-primary-600' : 'bg-zinc-700'
                }`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 ${
                    settings?.shadow_mode ? 'translate-x-5' : ''
                  }`}
                />
              </button>
            </div>
          </div>

          {settings?.storage && (
            <div className="pt-4 border-t border-surface-700 space-y-3">
              <div className="flex justify-between text-sm">
                <span className="font-medium text-zinc-400">Storage Usage</span>
                <span className="text-white">
                  {(settings.storage.used_mb ?? 0).toFixed(0)} MB / {(settings.storage.total_mb ?? 1).toFixed(0)} MB
                </span>
              </div>
              <div className="progress-bar">
                <div
                  className="progress-fill bg-primary-500"
                  style={{
                    width: `${Math.min(
                      100,
                      ((settings.storage.used_mb ?? 0) / (settings.storage.total_mb ?? 1)) * 100
                    )}%`,
                  }}
                />
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  onClick={() => handleCleanup(true)}
                  disabled={cleaningUp}
                  className="btn-ghost text-xs flex items-center gap-1.5"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  Dry Run Cleanup (30d)
                </button>
                <button
                  onClick={() => handleCleanup(false)}
                  disabled={cleaningUp}
                  className="btn-primary text-xs bg-danger-600 hover:bg-danger-700 flex items-center gap-1.5"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  Execute Cleanup
                </button>
              </div>
              {cleanupResult && (
                <div className="text-xs text-zinc-300 bg-surface-900 p-3 rounded-lg border border-surface-700 font-mono">
                  Deleted: {cleanupResult.deleted_folders ?? 0} folders | Freed: {cleanupResult.freed_mb ?? 0} MB ({cleanupResult.dry_run ? 'Dry Run' : 'Executed'})
                </div>
              )}
            </div>
          )}
        </div>

        {/* Camera Management & Testing */}
        <div className="card p-8 space-y-6 lg:col-span-2">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold uppercase tracking-wide text-zinc-400 flex items-center gap-2">
              <Camera className="w-4 h-4 text-primary-400" />
              Camera Management & Testing
            </div>
            <button
              onClick={handleDetectCameras}
              disabled={detecting}
              className="btn-primary text-xs flex items-center gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${detecting ? 'animate-spin' : ''}`} />
              {detecting ? 'Scanning...' : 'Detect Cameras'}
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {!cameras || cameras.length === 0 ? (
              <div className="col-span-full text-center py-8 text-zinc-500 bg-surface-900 rounded-xl border border-surface-700">
                No active camera configurations or none detected. Click "Detect Cameras" to scan.
              </div>
            ) : (
              cameras.map((cam, idx) => (
                <div key={idx} className="bg-surface-900 p-4 rounded-xl border border-surface-700 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-white text-sm">{cam?.camera_name || cam?.name || `Camera ${idx}`}</span>
                    <span className="badge-pass">{cam?.adapter || cam?.type || 'webcam'}</span>
                  </div>
                  <div className="text-xs text-zinc-400 space-y-1 font-mono">
                    <div>Station: {cam?.station_id ? cam.station_id.replace('STATION_', 'Station ') : 'General'}</div>
                    <div>ID / Index: {String(cam?.camera_id ?? idx)}</div>
                    {cam?.resolution && <div>Resolution: {cam.resolution.join('x')}</div>}
                  </div>
                  <button
                    onClick={() => handleTestCamera(cam?.adapter || 'webcam', String(cam?.camera_id ?? idx))}
                    disabled={testingCameraId === String(cam?.camera_id ?? idx)}
                    className="w-full btn-ghost text-xs py-1.5 flex items-center justify-center gap-2"
                  >
                    <TestTube className="w-3.5 h-3.5" />
                    {testingCameraId === String(cam?.camera_id ?? idx) ? 'Testing...' : 'Test Connection'}
                  </button>
                </div>
              ))
            )}
          </div>

          {cameraTestResult && (
            <div className={`p-4 rounded-xl border text-sm flex items-center gap-3 ${
              cameraTestResult.connected ? 'bg-success-900/20 border-success-500 text-success-400' : 'bg-danger-900/20 border-danger-500 text-danger-400'
            }`}>
              {cameraTestResult.connected ? <CheckCircle className="w-5 h-5 flex-shrink-0" /> : <XCircle className="w-5 h-5 flex-shrink-0" />}
              <div>
                <div className="font-semibold">Camera Test Result: {cameraTestResult.connected ? 'Connected Successfully' : 'Failed'}</div>
                {cameraTestResult.resolution && <div className="text-xs font-mono mt-0.5">Resolution: {cameraTestResult.resolution.join('x')}</div>}
                {cameraTestResult.error && <div className="text-xs font-mono mt-0.5">{cameraTestResult.error}</div>}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

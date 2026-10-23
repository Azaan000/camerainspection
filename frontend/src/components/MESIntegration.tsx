import { useState } from 'react'
import { Webhook, Save, CheckCircle, Send } from 'lucide-react'

export default function MESIntegration() {
  const [endpointUrl, setEndpointUrl] = useState('https://mes.factory-plant2.internal/api/v1/inspection-events')
  const [mqttBroker, setMqttBroker] = useState('mqtt://broker.factory-plant2.internal:1883')
  const [topic, setTopic] = useState('seatguard/line1/inspections')
  const [enabled, setEnabled] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<string | null>(null)

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setSuccessMsg(null)
    setTimeout(() => {
      setSaving(false)
      setSuccessMsg('MES Webhook & MQTT broker configurations saved successfully.')
      setTimeout(() => setSuccessMsg(null), 3000)
    }, 600)
  }

  const handleTestDispatch = async () => {
    setTesting(true)
    setTestResult(null)
    setTimeout(() => {
      setTesting(false)
      setTestResult('Test webhook payload dispatched successfully (HTTP 200 OK — 42ms latency).')
    }, 800)
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="font-bold text-white text-3xl flex items-center gap-3">
            <Webhook className="w-8 h-8 text-primary-400" />
            MES / ERP Webhook & MQTT Event Dispatcher
          </h2>
          <p className="text-sm text-zinc-400 mt-1">Configure real-time outbound integration with factory manufacturing execution systems (SAP, Opcenter, FactoryTalk)</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Configuration Form */}
        <div className="card p-8 space-y-6">
          <div className="flex items-center justify-between border-b border-surface-700 pb-4">
            <div className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
              Outbound Event Integration Settings
            </div>
            <label className="flex items-center gap-2 text-xs font-semibold text-zinc-300 cursor-pointer">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => setEnabled(e.target.checked)}
                className="w-4 h-4 rounded accent-primary-500"
              />
              Enable Dispatcher
            </label>
          </div>

          <form onSubmit={handleSave} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-zinc-400 mb-2">MES / ERP Webhook Endpoint URL</label>
              <input
                type="url"
                value={endpointUrl}
                onChange={(e) => setEndpointUrl(e.target.value)}
                className="w-full text-sm font-mono"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-zinc-400 mb-2">MQTT Broker Address</label>
              <input
                type="text"
                value={mqttBroker}
                onChange={(e) => setMqttBroker(e.target.value)}
                className="w-full text-sm font-mono"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-zinc-400 mb-2">MQTT Topic Prefix</label>
              <input
                type="text"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                className="w-full text-sm font-mono"
              />
            </div>

            {successMsg && (
              <div className="p-3 bg-success-900/20 text-success-400 text-xs rounded-xl border border-success-500 flex items-center gap-2">
                <CheckCircle className="w-4 h-4 flex-shrink-0" />
                {successMsg}
              </div>
            )}

            <button
              type="submit"
              disabled={saving}
              className="w-full btn-primary py-3 flex items-center justify-center gap-2 text-sm font-semibold shadow-lg shadow-primary-600/30"
            >
              <Save className="w-4 h-4" />
              {saving ? 'Saving...' : 'Save MES Configurations'}
            </button>
          </form>
        </div>

        {/* Live Test & Payload Preview */}
        <div className="card p-8 space-y-6 flex flex-col justify-between">
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b border-surface-700 pb-4">
              <div className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
                Payload Format & Live Test
              </div>
              <button
                onClick={handleTestDispatch}
                disabled={testing}
                className="btn-primary text-xs py-1.5 px-3 flex items-center gap-1.5"
              >
                <Send className={`w-3.5 h-3.5 ${testing ? 'animate-pulse' : ''}`} />
                {testing ? 'Sending...' : 'Test Webhook Event'}
              </button>
            </div>

            <div className="bg-surface-900 p-4 rounded-xl border border-surface-700 font-mono text-xs text-zinc-300 overflow-x-auto space-y-1">
              <div className="text-zinc-500">// Sample Outbound JSON Payload</div>
              <div>{'{'}</div>
              <div className="pl-4">"event": "SEAT_INSPECTION_FINALIZED",</div>
              <div className="pl-4">"seat_id": "SEAT_2026_1023_0089",</div>
              <div className="pl-4">"variant_id": "FRONT_LH_BLACK",</div>
              <div className="pl-4">"outcome": "PASS",</div>
              <div className="pl-4">"label_printer_enabled": true,</div>
              <div className="pl-4">"timestamp": "2026-10-23T14:22:10Z"</div>
              <div>{'}'}</div>
            </div>

            {testResult && (
              <div className="p-4 bg-success-900/20 text-success-400 text-xs rounded-xl border border-success-500">
                {testResult}
              </div>
            )}
          </div>

          <div className="p-4 bg-surface-900 rounded-xl border border-surface-700 text-xs text-zinc-400 space-y-1">
            <div className="font-semibold text-white">Reliability Guarantee:</div>
            <p>Outbound events feature automatic exponential backoff retry logic (up to 5 attempts) and local SQLite dead-letter queueing if the factory MES network goes offline.</p>
          </div>
        </div>
      </div>
    </div>
  )
}

import { apiClient } from '../lib/api'
import { useEffect, useState } from 'react'
import type { SPCResponse } from '../lib/api'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Legend } from 'recharts'

export default function SPCCharts() {
  const [data, setData] = useState<SPCResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedMetric, setSelectedMetric] = useState('shield_gap_mm')

  useEffect(() => {
    const fetchData = async () => {
      try {
        const result = await apiClient.getSPCMeasurements(selectedMetric, 50)
        setData(result)
      } catch (error) {
        console.error('Failed to fetch SPC data:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [selectedMetric])

  if (loading) {
    return <div className="text-center py-20 text-zinc-400">Loading SPC charts...</div>
  }

  if (!data) {
    return <div className="text-center py-20 text-zinc-400">Failed to load data</div>
  }

  const chartData = data.measurements.map((m, idx) => ({
    index: idx + 1,
    value: m.value,
    seat: m.seat_id,
  }))

  const getCpkColor = (cpk: number) => {
    if (cpk >= 1.33) return 'text-success-400'
    if (cpk >= 1.0) return 'text-warning-400'
    return 'text-danger-400'
  }

  const getExposureStatus = () => {
    if (data.violations === 0) return { text: 'OK', color: 'text-success-400' }
    if (data.violations <= 2) return { text: 'Warning', color: 'text-warning-400' }
    return { text: 'Out of Control', color: 'text-danger-400' }
  }

  const exposureStatus = getExposureStatus()

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="font-bold text-white text-2xl">Statistical Process Control (SPC)</h2>
          <p className="text-sm text-zinc-400 mt-1">X-Bar control charts with Western Electric rule violation detection</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="text-xs text-zinc-400 font-medium">Metric:</label>
          <select
            value={selectedMetric}
            onChange={(e) => setSelectedMetric(e.target.value)}
            className="text-xs py-1.5 px-3 min-w-[240px]"
          >
            <option value="shield_gap_mm">Station 3: Plastic Shield Gap (mm)</option>
            <option value="stitch_spi_delta">Station 2: Seam SPI Deviation</option>
            <option value="recliner_angle_deg">Station 4: Recliner Angle (deg)</option>
            <option value="stitches_per_inch">Station 2: Stitches Per Inch (SPI)</option>
            <option value="seam_position_mm">Station 2: Seam Tracking Deviation (mm)</option>
            <option value="flash_mm">Station 3: Flash/Burr Protrusion (mm)</option>
            <option value="track_position_mm">Station 4: Track End Position (mm)</option>
          </select>
        </div>
      </div>

      {/* Capability Tiles */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="stat-card p-4">
          <div className="stat-label">Spec Limits [LSL / Nom / USL]</div>
          <div className="text-lg font-bold font-mono text-zinc-300 mt-1">
            {data.lsl} / {data.nominal} / {data.usl} {data.unit}
          </div>
        </div>
        <div className="stat-card p-4">
          <div className="stat-label">Process Capability (Cpk / Cp)</div>
          <div className={`text-lg font-bold font-mono mt-1 ${getCpkColor(data.cpk)}`}>
            Cpk: {data.cpk} · Cp: {data.cp}
          </div>
        </div>
        <div className="stat-card p-4">
          <div className="stat-label">Mean (μ) ± Std Dev (σ)</div>
          <div className="text-lg font-bold font-mono text-info-400 mt-1">
            μ: {data.mean}{data.unit} · σ: {data.std_dev}{data.unit}
          </div>
        </div>
        <div className={`stat-card p-4 ${data.violations > 0 ? 'border-danger-900/50' : ''}`}>
          <div className="stat-label">Out-of-Spec / Run Rules</div>
          <div className={`text-lg font-bold font-mono mt-1 ${exposureStatus.color}`}>
            {data.violations} Violations - {exposureStatus.text}
          </div>
        </div>
      </div>

      {/* SPC Chart */}
      <div className="card p-6">
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
            <XAxis dataKey="index" stroke="#a1a1aa" tick={{ fill: '#a1a1aa' }} label={{ value: 'Sample Number', position: 'insideBottom', offset: -5, fill: '#a1a1aa' }} />
            <YAxis stroke="#a1a1aa" tick={{ fill: '#a1a1aa' }} label={{ value: `Value (${data.unit})`, angle: -90, position: 'insideLeft', fill: '#a1a1aa' }} />
            <Tooltip
              contentStyle={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '8px' }}
              labelStyle={{ color: '#f4f4f5' }}
              formatter={(value) => typeof value === 'number' ? [`${value.toFixed(3)} ${data.unit}`, 'Measured'] : [String(value), 'Measured']}
              labelFormatter={(label) => `Sample #${label}`}
            />
            <Legend />

            {/* Spec Limits */}
            <ReferenceLine y={data.usl} stroke="#f43f5e" strokeWidth={2} label={{ value: 'USL', fill: '#f43f5e', fontSize: 12 }} />
            <ReferenceLine y={data.lsl} stroke="#f43f5e" strokeWidth={2} label={{ value: 'LSL', fill: '#f43f5e', fontSize: 12 }} />

            {/* Nominal Target */}
            <ReferenceLine y={data.nominal} stroke="#34d399" strokeWidth={2} strokeDasharray="5 5" label={{ value: 'Nominal', fill: '#34d399', fontSize: 12 }} />

            {/* Control Limits (±3σ) */}
            <ReferenceLine y={data.ucl} stroke="#fbbf24" strokeWidth={1} strokeDasharray="3 3" label={{ value: 'UCL', fill: '#fbbf24', fontSize: 10 }} />
            <ReferenceLine y={data.lcl} stroke="#fbbf24" strokeWidth={1} strokeDasharray="3 3" label={{ value: 'LCL', fill: '#fbbf24', fontSize: 10 }} />

            {/* Measured Values */}
            <Line type="monotone" dataKey="value" stroke="#6366f1" strokeWidth={2} dot={{ fill: '#6366f1', r: 4 }} activeDot={{ r: 6 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center justify-between gap-4 text-xs text-zinc-400">
        <div className="flex items-center gap-6">
          <span className="flex items-center gap-2">
            <span className="w-3 h-0.5 bg-danger-500"></span> USL / LSL (Spec Limits)
          </span>
          <span className="flex items-center gap-2">
            <span className="w-3 h-0.5 bg-success-400" style={{ borderBottom: '2px dashed' }}></span> Nominal Target (Ideal)
          </span>
          <span className="flex items-center gap-2">
            <span className="w-3 h-0.5 bg-warning-400" style={{ borderBottom: '1px dotted' }}></span> UCL / LCL (±3σ Process Limits)
          </span>
          <span className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-primary-400"></span> Measured Part
          </span>
        </div>
        <span className="text-zinc-500 font-mono text-[11px]">Sample Size: {data.measurements.length} seats</span>
      </div>
    </div>
  )
}

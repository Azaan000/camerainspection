import { apiClient } from '../lib/api'
import { useEffect, useState } from 'react'
import type { QualityTrendsResponse } from '../lib/api'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts'

const COLORS = {
  pass: '#34d399',
  review: '#fbbf24',
  fail: '#fb7185',
}

export default function QualityTrends() {
  const [data, setData] = useState<QualityTrendsResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const result = await apiClient.getQualityTrends()
        setData(result)
      } catch (error) {
        console.error('Failed to fetch quality trends:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 5000)
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return <div className="text-center py-20 text-zinc-400">Loading quality trends...</div>
  }

  if (!data) {
    return <div className="text-center py-20 text-zinc-400">Failed to load data</div>
  }

  const outcomeData = [
    { name: 'Pass', value: data.pass_rate * 100, color: COLORS.pass },
    { name: 'Review', value: data.review_rate * 100, color: COLORS.review },
    { name: 'Fail', value: data.fail_rate * 100, color: COLORS.fail },
  ]

  const paretoData = Object.entries(data.pareto_defects)
    .slice(0, 10)
    .map(([name, count]) => ({
      name: name.replace(/_/g, ' ').replace(/\./g, ': '),
      count,
    }))

  return (
    <div className="space-y-8">
      <h2 className="font-bold text-white text-2xl">Quality Trends</h2>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="stat-card">
          <div className="stat-label">Pass Rate (Trend)</div>
          <div className="stat-value text-success-400">{(data.pass_rate * 100).toFixed(1)}%</div>
          <div className="progress-bar">
            <div className="progress-fill bg-success-400" style={{ width: `${data.pass_rate * 100}%` }} />
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Review Rate</div>
          <div className="stat-value text-warning-400">{(data.review_rate * 100).toFixed(1)}%</div>
          <div className="progress-bar">
            <div className="progress-fill bg-warning-400" style={{ width: `${data.review_rate * 100}%` }} />
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Fail Rate</div>
          <div className="stat-value text-danger-400">{(data.fail_rate * 100).toFixed(1)}%</div>
          <div className="progress-bar">
            <div className="progress-fill bg-danger-400" style={{ width: `${data.fail_rate * 100}%` }} />
          </div>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Outcome Distribution */}
        <div className="card p-6">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-zinc-400 mb-6">Outcome Distribution</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={outcomeData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, value }) => `${name}: ${value.toFixed(1)}%`}
                outerRadius={100}
                fill="#8884d8"
                dataKey="value"
              >
                {outcomeData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip formatter={(value) => typeof value === 'number' ? `${value.toFixed(1)}%` : String(value)} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Defect Pareto */}
        <div className="card p-6">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-zinc-400 mb-6">Defect Pareto (Top 10)</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={paretoData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis dataKey="name" angle={-45} textAnchor="end" height={100} stroke="#a1a1aa" tick={{ fill: '#a1a1aa', fontSize: 11 }} />
              <YAxis stroke="#a1a1aa" tick={{ fill: '#a1a1aa' }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '8px' }}
                labelStyle={{ color: '#f4f4f5' }}
              />
              <Bar dataKey="count" fill="#6366f1" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="text-sm text-zinc-500">
        Sample Size: {data.sample_size} seats inspected
      </div>
    </div>
  )
}

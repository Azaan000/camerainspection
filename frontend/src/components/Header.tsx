import { useState, useEffect } from 'react'
import { Menu, X, Activity, BarChart3, Image, Settings, Wrench, ClipboardList, Target, AlertCircle, FileText, FlaskConical, Camera, ShieldCheck, Cpu, Webhook, Tag } from 'lucide-react'

interface HeaderProps {
  currentSection: string
  onSectionChange: (section: string) => void
}

export default function Header({ currentSection, onSectionChange }: HeaderProps) {
  const [time, setTime] = useState(new Date())
  const [apiStatus, setApiStatus] = useState<'online' | 'offline'>('offline')
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await fetch('/health')
        if (response.ok) {
          setApiStatus('online')
        } else {
          setApiStatus('offline')
        }
      } catch (error) {
        console.error('Health check failed:', error)
        setApiStatus('offline')
      }
    }
    checkHealth()
    const interval = setInterval(checkHealth, 5000)
    return () => clearInterval(interval)
  }, [])

  const navItems = [
    { id: 'live', label: 'Live Line', icon: Activity },
    { id: 'camerastreams', label: 'Live Cameras', icon: Camera },
    { id: 'plc', label: 'PLC Telemetry', icon: Cpu },
    { id: 'mes', label: 'MES Webhooks', icon: Webhook },
    { id: 'taxonomy', label: 'Taxonomy', icon: Tag },
    { id: 'roi', label: 'ROI Editor', icon: Target },
    { id: 'qualityauditor', label: 'Auditor', icon: ShieldCheck },
    { id: 'quality', label: 'Quality', icon: BarChart3 },
    { id: 'gallery', label: 'Gallery', icon: Image },
    { id: 'health', label: 'Health', icon: Wrench },
    { id: 'review', label: 'Review', icon: AlertCircle },
    { id: 'spc', label: 'SPC', icon: Target },
    { id: 'audit', label: 'Audit', icon: ClipboardList },
    { id: 'report', label: 'Shift Report', icon: FileText },
    { id: 'tester', label: 'Station Tester', icon: FlaskConical },
    { id: 'settings', label: 'Settings', icon: Settings },
  ]

  return (
    <header className="border-b border-surface-700 bg-surface-900/90 backdrop-blur-md px-8 py-5 flex items-center justify-between sticky top-0 z-40 shadow-lg">
      {/* Logo */}
      <div className="flex items-center gap-4">
        <div className="w-10 h-10 rounded-xl bg-primary-600 flex items-center justify-center shadow-lg shadow-primary-500/20">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
          </svg>
        </div>
        <div>
          <div className="font-bold text-lg text-white tracking-tight leading-none">SeatGuard</div>
          <div className="text-xs text-zinc-400 mt-1 font-medium">Inspection Intelligence</div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="hidden lg:flex items-center gap-1 bg-surface-800 p-1.5 rounded-xl border border-surface-700 overflow-x-auto">
        {navItems.map((item) => {
          const Icon = item.icon
          return (
            <button
              key={item.id}
              onClick={() => onSectionChange(item.id)}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold transition-all whitespace-nowrap ${
                currentSection === item.id
                  ? 'bg-surface-600 text-white shadow-sm'
                  : 'text-zinc-400 hover:text-white hover:bg-surface-700'
              }`}
            >
              <Icon className="w-4 h-4" />
              {item.label}
            </button>
          )
        })}
      </nav>

      {/* Mobile Menu Button */}
      <button onClick={() => setMobileMenuOpen(!mobileMenuOpen)} className="lg:hidden p-2 text-zinc-400 hover:text-white">
        {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
      </button>

      {/* Status & Clock */}
      <div className="hidden md:flex items-center gap-4">
        <div className="flex items-center gap-2 text-sm">
          <span className={`w-2.5 h-2.5 rounded-full ${
            apiStatus === 'online' ? 'bg-success-400' : 'bg-danger-500'
          } animate-pulse`} />
          <span className={`font-semibold ${apiStatus === 'online' ? 'text-success-400' : 'text-danger-400'}`}>
            {apiStatus === 'online' ? 'Online' : 'Offline'}
          </span>
        </div>
        <div className="text-sm text-zinc-400 font-mono bg-surface-800 px-3 py-1.5 rounded-lg border border-surface-700">
          {time.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
          })}
        </div>
      </div>

      {/* Mobile Menu */}
      {mobileMenuOpen && (
        <div className="lg:hidden absolute top-full left-0 right-0 bg-surface-900 border-b border-surface-700 p-4 space-y-2 max-h-[80vh] overflow-y-auto z-50">
          {navItems.map((item) => {
            const Icon = item.icon
            return (
              <button
                key={item.id}
                onClick={() => {
                  onSectionChange(item.id)
                  setMobileMenuOpen(false)
                }}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                  currentSection === item.id
                    ? 'bg-surface-600 text-white'
                    : 'text-zinc-400 hover:text-white hover:bg-surface-700'
                }`}
              >
                <Icon className="w-5 h-5" />
                {item.label}
              </button>
            )
          })}
        </div>
      )}
    </header>
  )
}

import { useState, useEffect, useRef } from 'react'
import {
  Menu,
  X,
  Activity,
  BarChart3,
  Image,
  Settings,
  Wrench,
  ClipboardList,
  Target,
  AlertCircle,
  FileText,
  FlaskConical,
  Camera,
  ShieldCheck,
  Cpu,
  Webhook,
  Tag,
  Tv,
  Split,
  Crosshair,
  Volume2,
  VolumeX,
  ScanLine,
  ChevronDown,
  Sliders,
} from 'lucide-react'
import { audioAlerts } from '../lib/audioAlerts'
import { apiClient } from '../lib/api'

interface HeaderProps {
  currentSection: string
  onSectionChange: (section: string) => void
  onBarcodeScan?: (seatId: string) => void
}

export default function Header({ currentSection, onSectionChange, onBarcodeScan }: HeaderProps) {
  const [time, setTime] = useState(new Date())
  const [apiStatus, setApiStatus] = useState<'online' | 'offline'>('offline')
  const [systemSettings, setSystemSettings] = useState<{ save_images: boolean; shadow_mode: boolean } | null>(null)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [moreDropdownOpen, setMoreDropdownOpen] = useState(false)
  const [isMuted, setIsMuted] = useState(() => audioAlerts.isMuted())
  const [barcodeInput, setBarcodeInput] = useState('')
  const barcodeInputRef = useRef<HTMLInputElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

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
        setApiStatus('offline')
      }
    }
    const fetchSettings = async () => {
      try {
        const res = await apiClient.getSystemSettings()
        setSystemSettings(res as any)
      } catch (err) {
        // ignore
      }
    }
    checkHealth()
    fetchSettings()
    const interval = setInterval(() => {
      checkHealth()
      fetchSettings()
    }, 5000)
    return () => clearInterval(interval)
  }, [])

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setMoreDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Global keyboard shortcut: press '/' to focus barcode scanner
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === '/' && document.activeElement?.tagName !== 'INPUT' && document.activeElement?.tagName !== 'TEXTAREA') {
        e.preventDefault()
        barcodeInputRef.current?.focus()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  const handleBarcodeSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = barcodeInput.trim()
    if (!trimmed) return

    audioAlerts.playPassChime()
    if (onBarcodeScan) {
      onBarcodeScan(trimmed)
    } else {
      onSectionChange('rework')
    }
    setBarcodeInput('')
  }

  const toggleSound = () => {
    const muted = audioAlerts.toggleMuted()
    setIsMuted(muted)
  }

  // Primary core tabs always visible
  const primaryNav = [
    { id: 'live', label: 'Live Line', icon: Activity },
    { id: 'andon', label: 'Andon Board', icon: Tv },
    { id: 'camerastreams', label: 'Live Cameras', icon: Camera },
    { id: 'rework', label: 'Rework Bench', icon: Wrench },
    { id: 'tester', label: 'Station Tester', icon: FlaskConical },
    { id: 'golden', label: 'Golden Sample', icon: Split },
    { id: 'calibration', label: 'Calibration', icon: Crosshair },
  ]

  // Secondary modules inside the "More" dropdown
  const secondaryNav = [
    { id: 'config', label: 'Config Manager', icon: Sliders },
    { id: 'roi', label: 'ROI Editor', icon: Target },
    { id: 'plc', label: 'PLC Telemetry', icon: Cpu },
    { id: 'mes', label: 'MES Webhooks', icon: Webhook },
    { id: 'taxonomy', label: 'Taxonomy', icon: Tag },
    { id: 'qualityauditor', label: 'Auditor', icon: ShieldCheck },
    { id: 'quality', label: 'Quality Trends', icon: BarChart3 },
    { id: 'gallery', label: 'Defect Gallery', icon: Image },
    { id: 'review', label: 'Review Queue', icon: AlertCircle },
    { id: 'spc', label: 'SPC Charts', icon: Target },
    { id: 'audit', label: 'Audit Log', icon: ClipboardList },
    { id: 'report', label: 'Shift Report', icon: FileText },
    { id: 'health', label: 'System Health', icon: Wrench },
    { id: 'settings', label: 'Settings', icon: Settings },
  ]

  const isSecondaryActive = secondaryNav.some((item) => item.id === currentSection)
  const activeSecondaryItem = secondaryNav.find((item) => item.id === currentSection)

  return (
    <header className="border-b border-surface-700 bg-surface-900 px-6 lg:px-8 py-3.5 flex items-center justify-between sticky top-0 z-40 shadow-md gap-4">
      {/* Logo + Mode Badge */}
      <div className="flex items-center gap-4 flex-shrink-0">
        <div className="flex items-center gap-3 cursor-pointer" onClick={() => onSectionChange('live')}>
          <div className="w-9 h-9 rounded-xl bg-primary-600 flex items-center justify-center shadow-lg shadow-primary-500/20">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
            </svg>
          </div>
          <div>
            <div className="font-bold text-base text-white tracking-tight leading-none">SeatGuard</div>
            <div className="text-[10px] text-zinc-400 mt-1 font-medium">Vision Intelligence</div>
          </div>
        </div>

        {systemSettings?.shadow_mode ? (
          <div className="hidden sm:flex items-center gap-1.5 px-3 py-1 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-bold animate-pulse">
            <span className="w-2 h-2 rounded-full bg-amber-400"></span>
            SHADOW MODE (Simulation)
          </div>
        ) : (
          <div className="hidden sm:flex items-center gap-1.5 px-3 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-semibold">
            <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
            PRODUCTION MODE
          </div>
        )}
      </div>

      {/* Barcode Quick-Scan Field */}
      <form onSubmit={handleBarcodeSubmit} className="hidden xl:flex items-center gap-1.5 bg-surface-800 px-3 py-1.5 rounded-xl border border-surface-700 flex-shrink-0">
        <ScanLine className="w-3.5 h-3.5 text-primary-400" />
        <input
          ref={barcodeInputRef}
          type="text"
          value={barcodeInput}
          onChange={(e) => setBarcodeInput(e.target.value)}
          placeholder="Scan Barcode [/]..."
          className="bg-transparent text-xs text-white placeholder-zinc-500 focus:outline-none w-32 focus:w-48 transition-all"
        />
      </form>

      {/* Primary Navigation Tabs + More Dropdown */}
      <nav className="hidden lg:flex items-center gap-1.5">
        <div className="flex items-center gap-1 bg-surface-800 p-1 rounded-xl border border-surface-700">
          {primaryNav.map((item) => {
            const Icon = item.icon
            const isActive = currentSection === item.id
            return (
              <button
                key={item.id}
                onClick={() => onSectionChange(item.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all whitespace-nowrap ${
                  isActive
                    ? 'bg-primary-600 text-white shadow-sm'
                    : 'text-zinc-400 hover:text-white hover:bg-surface-700'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {item.label}
              </button>
            )
          })}
        </div>

        {/* More Dropdown */}
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setMoreDropdownOpen(!moreDropdownOpen)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold transition-all border ${
              isSecondaryActive
                ? 'bg-primary-600 text-white border-primary-500 shadow-sm'
                : 'bg-surface-800 text-zinc-300 border-surface-700 hover:text-white hover:bg-surface-700'
            }`}
          >
            {activeSecondaryItem ? (
              <>
                <activeSecondaryItem.icon className="w-3.5 h-3.5" />
                <span>{activeSecondaryItem.label}</span>
              </>
            ) : (
              <span>More Modules</span>
            )}
            <ChevronDown className={`w-3.5 h-3.5 transition-transform ${moreDropdownOpen ? 'rotate-180' : ''}`} />
          </button>

          {moreDropdownOpen && (
            <div className="absolute right-0 mt-2 w-56 bg-surface-900 border border-surface-700 rounded-2xl shadow-2xl py-2 z-50 grid grid-cols-1 gap-0.5">
              <div className="px-3 py-1 text-[10px] font-bold text-zinc-500 uppercase tracking-wider">
                Advanced Tools & Reports
              </div>
              {secondaryNav.map((item) => {
                const Icon = item.icon
                const isActive = currentSection === item.id
                return (
                  <button
                    key={item.id}
                    onClick={() => {
                      onSectionChange(item.id)
                      setMoreDropdownOpen(false)
                    }}
                    className={`flex items-center gap-2.5 px-4 py-2 text-xs font-medium transition-all text-left ${
                      isActive
                        ? 'bg-primary-600/20 text-primary-400 font-semibold border-l-2 border-primary-500'
                        : 'text-zinc-300 hover:bg-surface-800 hover:text-white'
                    }`}
                  >
                    <Icon className="w-4 h-4 text-zinc-400" />
                    <span>{item.label}</span>
                  </button>
                )
              })}
            </div>
          )}
        </div>
      </nav>

      {/* Right Controls: Sound, Status, Clock & Mobile Menu */}
      <div className="flex items-center gap-3 flex-shrink-0">
        {/* Sound Toggle */}
        <button
          onClick={toggleSound}
          className={`p-2 rounded-xl border transition-all ${
            isMuted
              ? 'bg-surface-800 text-zinc-500 border-surface-700'
              : 'bg-primary-900/30 text-primary-400 border-primary-500/40 hover:bg-primary-900/50'
          }`}
          title={isMuted ? 'Unmute Audio Chimes' : 'Mute Audio Chimes'}
        >
          {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
        </button>

        {/* API Health Pill */}
        <div className="hidden md:flex items-center gap-2 text-xs bg-surface-800 px-3 py-1.5 rounded-lg border border-surface-700">
          <span className={`w-2 h-2 rounded-full ${
            apiStatus === 'online' ? 'bg-success-400' : 'bg-danger-500'
          } animate-pulse`} />
          <span className={`font-semibold ${apiStatus === 'online' ? 'text-success-400' : 'text-danger-400'}`}>
            {apiStatus === 'online' ? 'Online' : 'Offline'}
          </span>
        </div>

        {/* System Status Badges: Shadow Mode & Save Images */}
        {systemSettings && (
          <div className="hidden xl:flex items-center gap-1.5">
            <div className={`flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-lg border font-medium ${
              systemSettings.shadow_mode
                ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                : 'bg-surface-800 text-zinc-400 border-surface-700'
            }`} title="Shadow Mode: Runs inspection without blocking line on failure">
              <span className={`w-1.5 h-1.5 rounded-full ${systemSettings.shadow_mode ? 'bg-amber-400 animate-pulse' : 'bg-zinc-500'}`} />
              Shadow: {systemSettings.shadow_mode ? 'ON' : 'OFF'}
            </div>
            <div className={`flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-lg border font-medium ${
              systemSettings.save_images
                ? 'bg-primary-500/10 text-primary-400 border-primary-500/30'
                : 'bg-surface-800 text-zinc-400 border-surface-700'
            }`} title="Save Images: Persists raw and annotated capture frames">
              <span className={`w-1.5 h-1.5 rounded-full ${systemSettings.save_images ? 'bg-primary-400' : 'bg-zinc-500'}`} />
              Images: {systemSettings.save_images ? 'ON' : 'OFF'}
            </div>
          </div>
        )}

        {/* Clock */}
        <div className="hidden sm:block text-xs text-zinc-400 font-mono bg-surface-800 px-3 py-1.5 rounded-lg border border-surface-700">
          {time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </div>

        {/* Mobile Menu Button */}
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="lg:hidden p-2 text-zinc-400 hover:text-white"
        >
          {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
      </div>

      {/* Mobile Dropdown Menu */}
      {mobileMenuOpen && (
        <div className="lg:hidden absolute top-full left-0 right-0 bg-surface-900 border-b border-surface-700 p-4 space-y-2 max-h-[80vh] overflow-y-auto z-50 shadow-2xl">
          <form onSubmit={handleBarcodeSubmit} className="flex items-center gap-2 bg-surface-800 p-2 rounded-lg border border-surface-700 mb-3">
            <ScanLine className="w-4 h-4 text-primary-400" />
            <input
              type="text"
              value={barcodeInput}
              onChange={(e) => setBarcodeInput(e.target.value)}
              placeholder="Scan Barcode..."
              className="bg-transparent text-xs text-white focus:outline-none w-full"
            />
            <button type="submit" className="btn-primary text-xs py-1 px-2.5">
              Go
            </button>
          </form>

          <div className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider px-2">Primary Views</div>
          {primaryNav.map((item) => {
            const Icon = item.icon
            return (
              <button
                key={item.id}
                onClick={() => {
                  onSectionChange(item.id)
                  setMobileMenuOpen(false)
                }}
                className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all ${
                  currentSection === item.id
                    ? 'bg-primary-600 text-white'
                    : 'text-zinc-400 hover:text-white hover:bg-surface-800'
                }`}
              >
                <Icon className="w-4 h-4" />
                {item.label}
              </button>
            )
          })}

          <div className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider px-2 pt-3">Advanced Modules</div>
          {secondaryNav.map((item) => {
            const Icon = item.icon
            return (
              <button
                key={item.id}
                onClick={() => {
                  onSectionChange(item.id)
                  setMobileMenuOpen(false)
                }}
                className={`w-full flex items-center gap-3 px-4 py-2 rounded-xl text-xs font-medium transition-all ${
                  currentSection === item.id
                    ? 'bg-primary-600 text-white font-semibold'
                    : 'text-zinc-400 hover:text-white hover:bg-surface-800'
                }`}
              >
                <Icon className="w-4 h-4" />
                {item.label}
              </button>
            )
          })}
        </div>
      )}
    </header>
  )
}

import { useState } from 'react'
import Header from './components/Header'
import LiveLine from './components/LiveLine'
import DefectGallery from './components/DefectGallery'
import QualityTrends from './components/QualityTrends'
import SystemHealth from './components/SystemHealth'
import ReviewQueue from './components/ReviewQueue'
import Settings from './components/Settings'
import AuditLog from './components/AuditLog'
import SPCCharts from './components/SPCCharts'
import ShiftReport from './components/ShiftReport'
import StationTester from './components/StationTester'
import LiveCameraStreams from './components/LiveCameraStreams'
import ROIEditor from './components/ROIEditor'
import QualityAuditor from './components/QualityAuditor'
import PLCSimulator from './components/PLCSimulator'
import MESIntegration from './components/MESIntegration'
import DefectTaxonomy from './components/DefectTaxonomy'

function App() {
  const [currentSection, setCurrentSection] = useState('live')

  return (
    <div className="min-h-screen flex flex-col bg-surface-900">
      <Header currentSection={currentSection} onSectionChange={setCurrentSection} />

      <main className="px-6 md:px-10 py-10 max-w-screen-2xl mx-auto w-full space-y-10">
        {currentSection === 'live' && <LiveLine />}
        {currentSection === 'camerastreams' && <LiveCameraStreams />}
        {currentSection === 'plc' && <PLCSimulator />}
        {currentSection === 'mes' && <MESIntegration />}
        {currentSection === 'taxonomy' && <DefectTaxonomy />}
        {currentSection === 'roi' && <ROIEditor />}
        {currentSection === 'qualityauditor' && <QualityAuditor />}
        {currentSection === 'quality' && <QualityTrends />}
        {currentSection === 'gallery' && <DefectGallery />}
        {currentSection === 'health' && <SystemHealth />}
        {currentSection === 'review' && <ReviewQueue />}
        {currentSection === 'spc' && <SPCCharts />}
        {currentSection === 'audit' && <AuditLog />}
        {currentSection === 'report' && <ShiftReport />}
        {currentSection === 'tester' && <StationTester />}
        {currentSection === 'settings' && <Settings />}
      </main>
    </div>
  )
}

export default App

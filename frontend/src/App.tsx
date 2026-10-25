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
import AndonBoard from './components/AndonBoard'
import CameraCalibration from './components/CameraCalibration'
import GoldenSampleComparator from './components/GoldenSampleComparator'
import ReworkBench from './components/ReworkBench'

function App() {
  const [currentSection, setCurrentSection] = useState('live')
  const [scannedSeatId, setScannedSeatId] = useState<string | null>(null)

  const handleBarcodeScan = (seatId: string) => {
    setScannedSeatId(seatId)
    setCurrentSection('rework')
  }

  return (
    <div className="min-h-screen flex flex-col bg-surface-900">
      <Header
        currentSection={currentSection}
        onSectionChange={setCurrentSection}
        onBarcodeScan={handleBarcodeScan}
      />

      <main className={`w-full mx-auto space-y-10 ${
        currentSection === 'andon'
          ? 'px-4 md:px-8 py-6 max-w-[1920px]'
          : 'px-6 md:px-10 py-10 max-w-screen-2xl'
      }`}>
        {currentSection === 'live' && <LiveLine />}
        {currentSection === 'andon' && <AndonBoard />}
        {currentSection === 'camerastreams' && <LiveCameraStreams />}
        {currentSection === 'rework' && <ReworkBench initialSeatId={scannedSeatId} />}
        {currentSection === 'tester' && <StationTester />}
        {currentSection === 'golden' && <GoldenSampleComparator />}
        {currentSection === 'calibration' && <CameraCalibration />}
        {currentSection === 'roi' && <ROIEditor />}
        {currentSection === 'plc' && <PLCSimulator />}
        {currentSection === 'mes' && <MESIntegration />}
        {currentSection === 'taxonomy' && <DefectTaxonomy />}
        {currentSection === 'qualityauditor' && <QualityAuditor />}
        {currentSection === 'quality' && <QualityTrends />}
        {currentSection === 'gallery' && <DefectGallery />}
        {currentSection === 'health' && <SystemHealth />}
        {currentSection === 'review' && <ReviewQueue />}
        {currentSection === 'spc' && <SPCCharts />}
        {currentSection === 'audit' && <AuditLog />}
        {currentSection === 'report' && <ShiftReport />}
        {currentSection === 'settings' && <Settings />}
      </main>
    </div>
  )
}

export default App

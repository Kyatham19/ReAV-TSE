import React, { useState, useEffect } from 'react';
import { Sparkles, Layers, ArrowLeft, Cpu, ExternalLink, HelpCircle } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

import UploadZone from './components/UploadZone';
import VideoPreview from './components/VideoPreview';
import SpeakerGrid from './components/SpeakerGrid';
import ProcessingTimeline from './components/ProcessingTimeline';
import ResultPanel from './components/ResultPanel';

export default function App() {
  // Navigation & Workflow Stage: 'upload' | 'selection' | 'processing' | 'results'
  const [currentStage, setCurrentStage] = useState('upload');
  const [jobId, setJobId] = useState(null);
  const [videoUrl, setVideoUrl] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [speakersData, setSpeakersData] = useState({ persons: [], tracks: [] });
  const [selectedPerson, setSelectedPerson] = useState(null);
  const [extractionResult, setExtractionResult] = useState(null);
  const [isLoadingDemo, setIsLoadingDemo] = useState(false);
  const [showHowItWorks, setShowHowItWorks] = useState(false);

  useEffect(() => {
    // Restore latest active analyzed job if present
    fetch('/api/jobs/latest')
      .then((res) => (res.ok ? res.json() : null))
      .then(async (data) => {
        if (data?.job_id) {
          console.log(`[Frontend] Found latest job_id: ${data.job_id}`);
          setJobId(data.job_id);
          setVideoUrl(data.video_url);

          // Fetch fresh speakers directly from /api/jobs/{CURRENT_JOB_ID}/speakers
          console.log(`[Frontend] Fetching /api/jobs/${data.job_id}/speakers`);
          const spRes = await fetch(`/api/jobs/${data.job_id}/speakers?t=${Date.now()}`);
          if (spRes.ok) {
            const spData = await spRes.json();
            console.log(`[Frontend] /api/jobs/${data.job_id}/speakers response:`, spData);
            console.log(`[Frontend] Loaded ${spData.persons?.length || 0} persons, ${spData.tracks?.length || 0} raw tracks`);
            setSpeakersData({
              persons: spData.persons || [],
              tracks: spData.tracks || []
            });
            if (spData.persons?.length > 0) {
              setSelectedPerson(spData.persons[0]);
            }
            setCurrentStage('selection');
          }
        }
      })
      .catch((err) => console.error("[Frontend] Initial job load error:", err));
  }, []);

  const handleVideoSelected = async (fileOrSample) => {
    // 1. Immediately clear old speaker state and cache
    setSpeakersData({ persons: [], tracks: [] });
    setSelectedPerson(null);
    setExtractionResult(null);
    setIsAnalyzing(true);
    setCurrentStage('selection');

    try {
      let uploadRes;
      if (fileOrSample === 'sample') {
        setIsLoadingDemo(true);
        const res = await fetch('/api/upload?use_sample=true', { method: 'POST' });
        uploadRes = await res.json();
        setIsLoadingDemo(false);
      } else {
        const formData = new FormData();
        formData.append('file', fileOrSample);
        const res = await fetch('/api/upload', {
          method: 'POST',
          body: formData,
        });
        uploadRes = await res.json();
      }

      const newJobId = uploadRes.job_id;
      console.log(`[Frontend] Upload succeeded! Current job_id: ${newJobId}`);
      setJobId(newJobId);
      setVideoUrl(uploadRes.video_url);

      // 2. Trigger fresh video analysis for this specific job
      console.log(`[Frontend] Triggering /api/analyze for job: ${newJobId}`);
      const analyzeRes = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: newJobId }),
      });
      const analyzeData = await analyzeRes.json();
      console.log(`[Frontend] /api/analyze completed:`, analyzeData);

      // 3. Fetch verified speaker grouping specifically for this CURRENT_JOB_ID
      console.log(`[Frontend] Fetching: /api/jobs/${newJobId}/speakers`);
      const speakersRes = await fetch(`/api/jobs/${newJobId}/speakers?t=${Date.now()}`);
      const speakersDataResponse = await speakersRes.json();
      console.log(`[Frontend] /api/jobs/${newJobId}/speakers returned:`, speakersDataResponse);
      console.log(`[Frontend] Clustered persons count: ${speakersDataResponse.persons?.length || 0}`);
      console.log(`[Frontend] Raw tracks count: ${speakersDataResponse.tracks?.length || 0}`);

      setSpeakersData({
        persons: speakersDataResponse.persons || [],
        tracks: speakersDataResponse.tracks || [],
      });

      if (speakersDataResponse.persons && speakersDataResponse.persons.length > 0) {
        setSelectedPerson(speakersDataResponse.persons[0]);
      }
    } catch (err) {
      console.error("[Frontend] Video processing error:", err);
      alert("Failed to analyze video: " + err.message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleStartExtraction = () => {
    if (!selectedPerson || !jobId) return;
    setCurrentStage('processing');
    setExtractionResult(null);

    // Trigger backend extraction API specifically for this job and selected person
    fetch('/api/extract', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        job_id: jobId,
        target: selectedPerson.id,
        mode: 'person'
      }),
    })
      .then(async (res) => {
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Extraction failed (${res.status})`);
        }
        return res.json();
      })
      .then((data) => {
        setExtractionResult(data);
        setCurrentStage('results');
      })
      .catch((err) => {
        console.error("Extraction error:", err);
        alert("Extraction failed: " + err.message);
        setCurrentStage('selection');
      });
  };

  const handleProcessingComplete = () => {
    setCurrentStage('results');
  };

  const handleReset = () => {
    setCurrentStage('selection');
  };

  return (
    <div className="min-h-screen bg-background text-neutral-200 flex flex-col font-sans selection:bg-accent/30 selection:text-white">
      {/* Top Header Navigation */}
      <header className="sticky top-0 z-50 w-full glass-panel border-b border-surface-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          {/* Logo & App Identity */}
          <div 
            onClick={() => setCurrentStage('upload')}
            className="flex items-center gap-3 cursor-pointer group"
          >
            <div className="w-8 h-8 rounded-lg bg-surface-elevated border border-surface-border group-hover:border-accent/50 flex items-center justify-center text-accent shadow-sm transition-all">
              <Sparkles className="w-4 h-4 text-accent group-hover:scale-110 transition-transform" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold font-display tracking-tight text-white text-base">ReAV-TSE</span>
                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-accent-muted text-lavender-300 border border-accent/20">
                  {jobId ? jobId.slice(0, 14) : "Multi-Job AI"}
                </span>
              </div>
              <p className="text-[11px] text-neutral-400 -mt-0.5 hidden sm:block">
                Audio-Visual Target Speaker Extraction
              </p>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="flex items-center gap-6 text-xs text-neutral-400">
            <button
              onClick={() => setCurrentStage('selection')}
              className={`transition-colors hover:text-white ${currentStage !== 'upload' ? 'text-white font-medium' : ''}`}
            >
              Workspace
            </button>
            <button
              onClick={() => setShowHowItWorks(true)}
              className="transition-colors hover:text-white flex items-center gap-1"
            >
              <span>How it works</span>
              <HelpCircle className="w-3 h-3 text-neutral-500" />
            </button>
            <a
              href="https://github.com/alibaba/ClearerVoice-Studio"
              target="_blank"
              rel="noreferrer"
              className="hidden md:flex items-center gap-1.5 text-neutral-400 hover:text-white transition-colors"
            >
              <Cpu className="w-3.5 h-3.5 text-accent" />
              <span>AV-MossFormer2</span>
              <ExternalLink className="w-3 h-3 text-neutral-600" />
            </a>
          </nav>
        </div>
      </header>

      {/* Main Content Area with Seamless Transitions */}
      <main className="flex-1 flex flex-col justify-center">
        <AnimatePresence mode="wait">
          {/* PAGE 1: Upload / Landing */}
          {currentStage === 'upload' && (
            <motion.div
              key="upload"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              transition={{ duration: 0.3 }}
              className="py-12"
            >
              <UploadZone
                onVideoSelected={handleVideoSelected}
                isLoadingDemo={isLoadingDemo}
              />
            </motion.div>
          )}

          {/* PAGE 2: Speaker Selection */}
          {currentStage === 'selection' && (
            <motion.div
              key="selection"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              transition={{ duration: 0.3 }}
              className="max-w-7xl mx-auto w-full px-4 sm:px-6 py-6"
            >
              {/* Back to Upload button */}
              <div className="mb-4 flex items-center justify-between">
                <button
                  onClick={() => setCurrentStage('upload')}
                  className="inline-flex items-center gap-1.5 text-xs text-neutral-400 hover:text-white transition-colors py-1 px-2 -ml-2 rounded-lg hover:bg-surface-elevated"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  <span>Upload different video</span>
                </button>

                {jobId && (
                  <span className="font-mono text-[11px] text-neutral-500">
                    Session: {jobId}
                  </span>
                )}
              </div>

              {/* Two-Column Workspace Layout */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
                {/* Left Column: Large Video Preview */}
                <div className="lg:col-span-6 space-y-4">
                  {videoUrl ? (
                    <VideoPreview
                      videoUrl={videoUrl}
                      title={`Active Video (${jobId ? jobId.slice(0, 10) : 'Loaded'})`}
                    />
                  ) : (
                    <div className="aspect-video rounded-2xl glass-panel flex items-center justify-center text-neutral-500 text-xs">
                      Loading video player...
                    </div>
                  )}
                  <div className="p-3.5 rounded-xl glass-panel border border-surface-border text-xs text-neutral-400 flex items-center justify-between">
                    <span className="flex items-center gap-1.5 text-neutral-300">
                      <Cpu className="w-3.5 h-3.5 text-accent" />
                      YuNet Face Detector & AV-MossFormer2
                    </span>
                    <span className="font-mono text-neutral-500">
                      {isAnalyzing ? "Processing..." : `${speakersData.tracks?.length || 0} tracks active`}
                    </span>
                  </div>
                </div>

                {/* Right Column: Speaker Selection Panel */}
                <div className="lg:col-span-6 glass-panel rounded-2xl p-6 border border-surface-border shadow-xl">
                  <SpeakerGrid
                    persons={speakersData.persons}
                    tracks={speakersData.tracks}
                    selectedPerson={selectedPerson}
                    onSelectPerson={setSelectedPerson}
                    onExtract={handleStartExtraction}
                    isExtracting={currentStage === 'processing'}
                    isAnalyzing={isAnalyzing}
                  />
                </div>
              </div>
            </motion.div>
          )}

          {/* PAGE 3: Processing Screen */}
          {currentStage === 'processing' && (
            <motion.div
              key="processing"
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 1.02 }}
              transition={{ duration: 0.3 }}
              className="py-12 flex-1 flex items-center justify-center"
            >
              <ProcessingTimeline
                jobId={jobId}
                selectedPerson={selectedPerson}
                isComplete={!!extractionResult}
                onComplete={handleProcessingComplete}
              />
            </motion.div>
          )}

          {/* PAGE 4: Results Workspace */}
          {currentStage === 'results' && (
            <motion.div
              key="results"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              transition={{ duration: 0.3 }}
              className="py-4"
            >
              <ResultPanel
                jobId={jobId}
                selectedPerson={selectedPerson}
                extractionData={extractionResult}
                onReset={handleReset}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* Footer */}
      <footer className="w-full border-t border-surface-border py-4 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-neutral-500 font-mono">
          <span>ReAV-TSE · Powered by ClearVoice AV-MossFormer2 & YuNet</span>
          <span className="text-neutral-400">Multi-Job Dynamic Audio-Visual Separation</span>
        </div>
      </footer>

      {/* How it works modal */}
      {showHowItWorks && (
        <div 
          onClick={() => setShowHowItWorks(false)}
          className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-200"
        >
          <div 
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-lg glass-panel-elevated rounded-2xl p-6 border border-surface-border shadow-2xl space-y-4"
          >
            <div className="flex items-center justify-between pb-3 border-b border-surface-border">
              <h3 className="text-lg font-bold font-display text-white">How ReAV-TSE Works</h3>
              <button 
                onClick={() => setShowHowItWorks(false)}
                className="text-neutral-400 hover:text-white text-xs px-2 py-1 rounded bg-surface border border-surface-border"
              >
                Close
              </button>
            </div>
            
            <div className="space-y-3 text-xs text-neutral-300 leading-relaxed">
              <div className="p-3 rounded-xl bg-surface border border-surface-border">
                <strong className="text-white block mb-1">1. Isolated Job Workspaces</strong>
                Every uploaded video generates a unique job ID and directory, ensuring zero stale data leakage between videos.
              </div>
              <div className="p-3 rounded-xl bg-surface border border-surface-border">
                <strong className="text-white block mb-1">2. Visual Lip-Sync Tracking</strong>
                YuNet and S3FD track face and mouth ROI across multi-speaker video shots at 25 fps.
              </div>
              <div className="p-3 rounded-xl bg-surface border border-surface-border">
                <strong className="text-white block mb-1">3. Target Speaker Extraction (TSE)</strong>
                AV-MossFormer2 uses mouth movements as visual conditioning cues to isolate the target speaker's vocal harmonics from the audio mix.
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

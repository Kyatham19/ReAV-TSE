import React from 'react';
import { Download, RotateCcw, CheckCircle2, Sparkles, Layers, Clock, Volume2 } from 'lucide-react';
import { motion } from 'framer-motion';
import WaveformPlayer from './WaveformPlayer';
import AudioComparison from './AudioComparison';

export default function ResultPanel({
  jobId,
  selectedPerson,
  extractionData,
  onReset
}) {
  const targetClean = (selectedPerson?.id || "person1").toLowerCase();
  const audioUrl = extractionData?.audioUrl || (jobId ? `/api/jobs/${jobId}/audio/target?person=${targetClean}` : "/api/audio/target");
  const downloadUrl = extractionData?.downloadUrl || (jobId ? `/api/jobs/${jobId}/audio/download?person=${targetClean}` : "/api/audio/download");
  const originalAudioUrl = jobId ? `/api/jobs/${jobId}/audio/original` : "/api/audio/original";
  const report = extractionData?.report;

  const handleDownload = () => {
    window.location.href = downloadUrl;
  };

  return (
    <div className="w-full max-w-5xl mx-auto py-8 px-4">
      {/* Top Breadcrumb & Actions */}
      <div className="flex items-center justify-between mb-8 pb-4 border-b border-surface-border">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center justify-center">
            <CheckCircle2 className="w-5 h-5 stroke-[2.2]" />
          </div>
          <div>
            <h1 className="text-2xl font-bold font-display text-white tracking-tight">
              Target speaker extracted
            </h1>
            <p className="text-xs text-neutral-400">
              AV-MossFormer2 Audio-Visual Neural Extraction Complete
            </p>
          </div>
        </div>

        <button
          onClick={onReset}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-surface hover:bg-surface-elevated text-neutral-300 hover:text-white border border-surface-border text-xs font-medium transition-all"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          <span>Extract another speaker</span>
        </button>
      </div>

      {/* Main Speaker Card Header */}
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="glass-panel-elevated rounded-2xl p-6 border border-surface-border mb-8 shadow-xl flex flex-col md:flex-row items-center justify-between gap-6"
      >
        <div className="flex items-center gap-5 w-full md:w-auto">
          {/* Large Avatar */}
          <div className="relative w-20 h-20 rounded-2xl overflow-hidden border-2 border-accent p-0.5 bg-neutral-900 shadow-[0_0_25px_rgba(139,92,246,0.35)] shrink-0">
            <img
              src={selectedPerson?.thumbnailUrl}
              alt={selectedPerson?.title}
              className="w-full h-full object-cover rounded-xl"
            />
          </div>

          <div className="space-y-1">
            <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-accent-muted border border-accent/20 text-lavender-300 text-[10px] font-mono tracking-wide uppercase">
              <Sparkles className="w-3 h-3 text-accent" />
              <span>Target Speaker</span>
            </div>
            <h2 className="text-2xl font-bold font-display text-white tracking-tight">
              {selectedPerson?.title}
            </h2>
            <p className="text-xs text-neutral-400">
              {selectedPerson?.role || "Extracted from multi-speaker video"}
            </p>
          </div>
        </div>

        {/* Stats Chips */}
        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto justify-start md:justify-end">
          <div className="px-3.5 py-2 rounded-xl bg-surface border border-surface-border text-center">
            <div className="text-[10px] uppercase font-mono text-neutral-400">Active Speech</div>
            <div className="text-base font-semibold text-white font-mono">
              {report?.active_speech_duration_sec || selectedPerson?.detectedDuration}s
            </div>
          </div>

          <div className="px-3.5 py-2 rounded-xl bg-surface border border-surface-border text-center">
            <div className="text-[10px] uppercase font-mono text-neutral-400">Segments</div>
            <div className="text-base font-semibold text-lavender-300 font-mono">
              {report?.num_segments_combined || selectedPerson?.tracksCount}
            </div>
          </div>

          <div className="px-3.5 py-2 rounded-xl bg-surface border border-surface-border text-center">
            <div className="text-[10px] uppercase font-mono text-neutral-400">Total Timeline</div>
            <div className="text-base font-semibold text-neutral-300 font-mono">
              {report?.total_timeline_duration_sec || 22.73}s
            </div>
          </div>

          <button
            onClick={handleDownload}
            className="flex items-center gap-2 px-5 py-3 rounded-xl bg-accent hover:bg-accent-hover text-white text-sm font-semibold shadow-[0_0_25px_rgba(139,92,246,0.35)] transition-all transform hover:scale-105 active:scale-95 cursor-pointer ml-auto md:ml-2"
          >
            <Download className="w-4 h-4 stroke-[2.2]" />
            <span>Download WAV</span>
          </button>
        </div>
      </motion.div>

      {/* Primary Waveform Player */}
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1 }}
        className="mb-8"
      >
        <WaveformPlayer
          audioUrl={audioUrl}
          title={`Isolated Vocal Track: ${selectedPerson?.title}`}
          subtitle="Continuous 22.7s timeline with non-target speech muted"
          onDownload={handleDownload}
        />
      </motion.div>

      {/* A/B Audio Comparison Section */}
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.2 }}
      >
        <AudioComparison
          originalAudioUrl={originalAudioUrl}
          targetAudioUrl={audioUrl}
          speakerName={selectedPerson?.title}
        />
      </motion.div>

      {/* Reconstructed Segment Breakdown */}
      {report?.segments && report.segments.length > 0 && (
        <div className="mt-8 glass-panel rounded-2xl p-6 border border-surface-border">
          <div className="flex items-center gap-2 text-xs font-mono text-neutral-400 uppercase tracking-wider mb-4">
            <Layers className="w-3.5 h-3.5 text-accent" />
            <span>Combined Speech Timeline Segments</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
            {report.segments.map((seg, i) => (
              <div key={i} className="p-3 rounded-xl bg-surface border border-surface-border text-xs space-y-1">
                <div className="flex items-center justify-between font-mono">
                  <span className="font-semibold text-white">Segment #{i + 1} (Track {seg.track_id})</span>
                  <span className="text-accent">{seg.duration_sec}s</span>
                </div>
                <p className="text-[11px] text-neutral-400 font-mono">
                  Frames {seg.start_frame} – {seg.end_frame}
                </p>
                <p className="text-[10px] text-neutral-500 font-mono">
                  Time: {seg.start_time_sec}s – {seg.end_time_sec}s
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

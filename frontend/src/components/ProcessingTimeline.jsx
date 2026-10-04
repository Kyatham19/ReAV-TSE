import React, { useState, useEffect } from 'react';
import { Check, Circle, Loader2, Sparkles } from 'lucide-react';
import { motion } from 'framer-motion';

const PIPELINE_STAGES = [
  { id: 'uploading', title: 'Video uploaded', desc: 'Raw video stream decoded into audio & video frames' },
  { id: 'detecting_faces', title: 'Detecting faces', desc: 'YuNet neural face detector processing visual frames' },
  { id: 'tracking_speakers', title: 'Tracking speakers', desc: 'Linking mouth and face bounding boxes across shots' },
  { id: 'speakers_detected', title: 'Speakers detected', desc: 'Deep visual embeddings clustered into distinct individuals' },
  { id: 'target_selected', title: 'Target selected', desc: 'Visual lip-sync conditioning reference locked' },
  { id: 'extracting_speech', title: 'Extracting speech', desc: 'AV-MossFormer2 isolating vocal harmonics for target' },
  { id: 'combining_segments', title: 'Combining speech segments', desc: 'Reconstructing timeline and inserting natural silence gaps' },
  { id: 'completed', title: 'Complete', desc: 'Clean target vocal track ready for evaluation' },
];

export default function ProcessingTimeline({ jobId, selectedPerson, isComplete, onComplete }) {
  const [currentStageId, setCurrentStageId] = useState('extracting_speech');
  const [statusMessage, setStatusMessage] = useState('AV-MossFormer2 isolating vocal harmonics for target...');
  const [progress, setProgress] = useState(0.4);

  useEffect(() => {
    if (!jobId) return;

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/jobs/${jobId}/status`);
        if (res.ok) {
          const data = await res.json();
          if (data.stage) {
            setCurrentStageId(data.stage);
            setStatusMessage(data.message || '');
            setProgress(data.progress || 0.5);

            if (data.stage === 'completed' || isComplete) {
              clearInterval(interval);
              setTimeout(() => {
                if (onComplete) onComplete();
              }, 600);
            }
          }
        }
      } catch (err) {
        console.error("Status poll error:", err);
      }
    }, 400);

    return () => clearInterval(interval);
  }, [jobId, isComplete, onComplete]);

  // Determine active step index
  const activeIndex = Math.max(
    5, // Extraction stage starts at index 5 ('extracting_speech')
    PIPELINE_STAGES.findIndex((s) => s.id === currentStageId)
  );

  return (
    <div className="w-full max-w-2xl mx-auto py-12 px-6 flex flex-col items-center">
      {/* Target Avatar with Pulsing Halo */}
      <div className="relative mb-8">
        <motion.div
          animate={{ scale: [1, 1.08, 1], opacity: [0.4, 0.8, 0.4] }}
          transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
          className="absolute -inset-4 rounded-full bg-accent/25 blur-xl -z-10"
        />
        <div className="w-24 h-24 rounded-full overflow-hidden border-2 border-accent shadow-[0_0_35px_rgba(139,92,246,0.5)] p-0.5 bg-surface-elevated">
          <img
            src={selectedPerson?.thumbnailUrl}
            alt={selectedPerson?.title}
            className="w-full h-full object-cover rounded-full"
          />
        </div>
        <div className="absolute -bottom-2 -right-1 px-2.5 py-0.5 rounded-full bg-accent text-[11px] font-mono text-white font-medium border border-white/20 shadow-md">
          {selectedPerson?.title}
        </div>
      </div>

      {/* Main Title */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-accent-muted border border-accent/20 text-lavender-300 text-xs font-mono tracking-wide mb-3">
          <Sparkles className="w-3.5 h-3.5 text-accent animate-spin" style={{ animationDuration: '4s' }} />
          <span>AUDIO + VISUAL NEURAL EXTRACTION</span>
        </div>
        <h2 className="text-3xl font-bold font-display text-white tracking-tight">
          Extracting target speaker
        </h2>
        <p className="text-xs text-neutral-400 mt-1 max-w-md font-mono">
          {statusMessage}
        </p>
      </div>

      {/* Live Sound Wave Animation */}
      <div className="w-full max-w-md h-16 glass-panel rounded-xl p-3 flex items-center justify-center gap-1.5 mb-8 border border-surface-border">
        {Array.from({ length: 32 }).map((_, i) => (
          <motion.div
            key={i}
            animate={{
              height: [
                `${Math.max(10, Math.sin(i * 0.4) * 36 + 18)}px`,
                `${Math.max(10, Math.cos(i * 0.3) * 44 + 20)}px`,
                `${Math.max(10, Math.sin(i * 0.5) * 32 + 16)}px`
              ]
            }}
            transition={{
              duration: 0.7 + (i % 5) * 0.12,
              repeat: Infinity,
              ease: "easeInOut"
            }}
            className="w-1.5 rounded-full bg-gradient-to-t from-accent/50 to-lavender-300"
          />
        ))}
      </div>

      {/* Steps Timeline Connected to Real Backend Pipeline */}
      <div className="w-full max-w-md space-y-2.5">
        {PIPELINE_STAGES.map((step, idx) => {
          const isDone = idx < activeIndex || currentStageId === 'completed';
          const isActive = idx === activeIndex && currentStageId !== 'completed';

          return (
            <div
              key={step.id}
              className={`flex items-center justify-between p-3 rounded-xl border transition-all ${
                isActive
                  ? 'bg-surface-elevated border-accent/60 shadow-[0_0_18px_rgba(139,92,246,0.18)]'
                  : isDone
                  ? 'bg-surface/50 border-white/[0.04]'
                  : 'bg-surface/20 border-transparent opacity-35'
              }`}
            >
              <div className="flex items-center gap-3">
                <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${
                  isDone
                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                    : isActive
                    ? 'bg-accent/20 text-accent border border-accent/40'
                    : 'bg-neutral-800 text-neutral-500'
                }`}>
                  {isDone ? (
                    <Check className="w-3.5 h-3.5 stroke-[2.5]" />
                  ) : isActive ? (
                    <span className="w-2 h-2 rounded-full bg-accent animate-ping" />
                  ) : (
                    <Circle className="w-3 h-3 fill-neutral-700 stroke-none" />
                  )}
                </div>

                <div>
                  <p className={`text-xs font-medium ${isActive ? 'text-white font-semibold' : isDone ? 'text-neutral-200' : 'text-neutral-500'}`}>
                    {step.title}
                  </p>
                  <p className="text-[10px] text-neutral-400">
                    {step.desc}
                  </p>
                </div>
              </div>

              {isActive && (
                <div className="flex items-center gap-1.5 text-accent text-[11px] font-mono">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  <span>Running</span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

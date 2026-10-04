import React, { useState } from 'react';
import { Volume2, Sparkles, SlidersHorizontal } from 'lucide-react';
import WaveformPlayer from './WaveformPlayer';

export default function AudioComparison({
  originalAudioUrl,
  targetAudioUrl,
  speakerName = "Selected Target"
}) {
  const [activeTab, setActiveTab] = useState('sideBySide'); // 'sideBySide' or 'target' or 'original'

  return (
    <div className="w-full glass-panel rounded-2xl p-6 border border-surface-border mt-8">
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono text-lavender-400 uppercase tracking-wider mb-1">
            <SlidersHorizontal className="w-3.5 h-3.5" />
            <span>A/B Audio Evaluation</span>
          </div>
          <h3 className="text-xl font-bold font-display text-white tracking-tight">
            Original Mix vs Isolated Target Speech
          </h3>
          <p className="text-xs text-neutral-400 mt-0.5">
            Compare the multi-speaker overlapping original soundtrack against the isolated target voice.
          </p>
        </div>

        {/* Tab Selector */}
        <div className="flex items-center p-1 rounded-xl bg-surface-elevated border border-surface-border text-xs self-start sm:self-auto">
          <button
            onClick={() => setActiveTab('sideBySide')}
            className={`px-3 py-1.5 rounded-lg transition-all ${
              activeTab === 'sideBySide'
                ? 'bg-accent/20 text-white font-medium border border-accent/30 shadow-sm'
                : 'text-neutral-400 hover:text-neutral-200'
            }`}
          >
            Stacked View
          </button>
          <button
            onClick={() => setActiveTab('target')}
            className={`px-3 py-1.5 rounded-lg transition-all ${
              activeTab === 'target'
                ? 'bg-accent/20 text-white font-medium border border-accent/30 shadow-sm'
                : 'text-neutral-400 hover:text-neutral-200'
            }`}
          >
            Isolated Only
          </button>
          <button
            onClick={() => setActiveTab('original')}
            className={`px-3 py-1.5 rounded-lg transition-all ${
              activeTab === 'original'
                ? 'bg-accent/20 text-white font-medium border border-accent/30 shadow-sm'
                : 'text-neutral-400 hover:text-neutral-200'
            }`}
          >
            Original Only
          </button>
        </div>
      </div>

      {/* Players */}
      <div className="space-y-6">
        {(activeTab === 'sideBySide' || activeTab === 'target') && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs px-1">
              <span className="font-semibold text-lavender-300 flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-accent" />
                EXTRACTED TARGET SPEECH ({speakerName})
              </span>
              <span className="text-emerald-400 font-mono text-[11px] bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                Interfering speakers suppressed
              </span>
            </div>
            <WaveformPlayer
              audioUrl={targetAudioUrl}
              title={`Clean Target Voice: ${speakerName}`}
              subtitle="Reconstructed speech timeline with silent gaps preserved"
              accentColor="violet"
            />
          </div>
        )}

        {(activeTab === 'sideBySide' || activeTab === 'original') && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs px-1">
              <span className="font-semibold text-neutral-400 flex items-center gap-1.5">
                <Volume2 className="w-3.5 h-3.5 text-neutral-500" />
                ORIGINAL VIDEO AUDIO (FULL MIX)
              </span>
              <span className="text-neutral-400 font-mono text-[11px] bg-white/[0.04] px-2 py-0.5 rounded border border-white/[0.08]">
                All voices + background chatter
              </span>
            </div>
            <WaveformPlayer
              audioUrl={originalAudioUrl}
              title="Original 16kHz Mixed Audio"
              subtitle="Raw soundtrack extracted from input video"
              accentColor="neutral"
            />
          </div>
        )}
      </div>
    </div>
  );
}

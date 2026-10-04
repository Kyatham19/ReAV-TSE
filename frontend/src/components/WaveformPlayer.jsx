import React, { useRef, useState, useEffect } from 'react';
import { Play, Pause, RotateCcw, Volume2, VolumeX, Download, Sparkles } from 'lucide-react';

export default function WaveformPlayer({
  audioUrl,
  title = "Extracted Audio",
  subtitle = "AV-MossFormer2 Reconstructed Timeline",
  accentColor = "violet", // "violet" or "emerald" or "neutral"
  onDownload,
  downloadFilename = "extracted_speaker.wav"
}) {
  const audioRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);

  // Generate realistic pseudo-waveform bars
  const [bars] = useState(() => {
    return Array.from({ length: 64 }, (_, i) => {
      // Natural speech envelope shape
      const v = Math.abs(Math.sin(i * 0.2) * Math.cos(i * 0.08) * 0.7 + 0.3);
      return Math.max(0.15, Math.min(0.95, v * (0.6 + (i % 7) * 0.06)));
    });
  });

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const onTimeUpdate = () => setCurrentTime(audio.currentTime);
    const onLoadedMetadata = () => setDuration(audio.duration || 22.73);
    const onEnded = () => setIsPlaying(false);

    audio.addEventListener('timeupdate', onTimeUpdate);
    audio.addEventListener('loadedmetadata', onLoadedMetadata);
    audio.addEventListener('ended', onEnded);

    return () => {
      audio.removeEventListener('timeupdate', onTimeUpdate);
      audio.removeEventListener('loadedmetadata', onLoadedMetadata);
      audio.removeEventListener('ended', onEnded);
    };
  }, [audioUrl]);

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play();
      setIsPlaying(true);
    }
  };

  const handleSeek = (percentage) => {
    if (!audioRef.current || !duration) return;
    const target = percentage * duration;
    audioRef.current.currentTime = target;
    setCurrentTime(target);
  };

  const toggleMute = () => {
    if (!audioRef.current) return;
    audioRef.current.muted = !isMuted;
    setIsMuted(!isMuted);
  };

  const handleVolumeChange = (e) => {
    const v = parseFloat(e.target.value);
    setVolume(v);
    if (audioRef.current) {
      audioRef.current.volume = v;
      setIsMuted(v === 0);
    }
  };

  const formatTime = (secs) => {
    if (isNaN(secs)) return "00:00";
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  const progress = duration > 0 ? (currentTime / duration) : 0;

  return (
    <div className="w-full glass-panel-elevated rounded-2xl p-5 sm:p-6 border border-surface-border shadow-xl">
      <audio ref={audioRef} src={audioUrl} preload="auto" />

      {/* Header Info */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h3 className="text-base font-semibold text-white tracking-tight flex items-center gap-2">
            <span>{title}</span>
            <span className="px-2 py-0.5 rounded-full bg-accent-muted border border-accent/20 text-lavender-300 text-[10px] font-mono uppercase">
              16kHz Mono WAV
            </span>
          </h3>
          <p className="text-xs text-neutral-400 mt-0.5">{subtitle}</p>
        </div>

        {onDownload && (
          <button
            onClick={onDownload}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface hover:bg-accent/20 text-neutral-300 hover:text-white border border-surface-border hover:border-accent/40 text-xs font-medium transition-all"
            title="Download WAV File"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download WAV</span>
          </button>
        )}
      </div>

      {/* Interactive Waveform Visualization */}
      <div 
        onClick={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const clickX = e.clientX - rect.left;
          handleSeek(clickX / rect.width);
        }}
        className="relative w-full h-20 sm:h-24 bg-surface rounded-xl p-3 flex items-center justify-between gap-1 cursor-pointer border border-surface-border group hover:border-surface-border-hover transition-colors overflow-hidden"
      >
        {/* Progress Fill Background Layer */}
        <div 
          className="absolute inset-y-0 left-0 bg-accent/[0.08] pointer-events-none transition-all duration-75 border-r border-accent/40"
          style={{ width: `${progress * 100}%` }}
        />

        {/* Waveform Bars */}
        {bars.map((barH, idx) => {
          const barProgress = idx / bars.length;
          const isPassed = barProgress <= progress;

          return (
            <div
              key={idx}
              className="flex-1 flex items-center justify-center h-full pointer-events-none"
            >
              <div
                className={`w-full max-w-[4px] rounded-full transition-all duration-150 ${
                  isPassed
                    ? 'bg-accent shadow-[0_0_8px_rgba(139,92,246,0.6)]'
                    : 'bg-neutral-700/60 group-hover:bg-neutral-600/70'
                }`}
                style={{ height: `${barH * 100}%` }}
              />
            </div>
          );
        })}
      </div>

      {/* Controls & Timecode */}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
        {/* Left: Playback controls */}
        <div className="flex items-center gap-3">
          <button
            onClick={togglePlay}
            className="w-11 h-11 rounded-full bg-accent hover:bg-accent-hover text-white flex items-center justify-center shadow-[0_0_20px_rgba(139,92,246,0.35)] transition-all cursor-pointer transform hover:scale-105 active:scale-95"
          >
            {isPlaying ? (
              <Pause className="w-5 h-5 fill-current" />
            ) : (
              <Play className="w-5 h-5 fill-current translate-x-0.5" />
            )}
          </button>

          <button
            onClick={() => {
              if (audioRef.current) {
                audioRef.current.currentTime = 0;
                audioRef.current.play();
                setIsPlaying(true);
              }
            }}
            className="w-8 h-8 rounded-lg bg-surface hover:bg-surface-elevated text-neutral-400 hover:text-white flex items-center justify-center border border-surface-border transition-colors"
            title="Replay from start"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>

          <div className="font-mono text-xs text-neutral-300">
            <span className="font-medium text-white">{formatTime(currentTime)}</span>
            <span className="text-neutral-500"> / </span>
            <span className="text-neutral-400">{formatTime(duration)}</span>
          </div>
        </div>

        {/* Right: Volume slider */}
        <div className="flex items-center gap-2 text-neutral-400">
          <button onClick={toggleMute} className="hover:text-white transition-colors">
            {isMuted || volume === 0 ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
          </button>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={isMuted ? 0 : volume}
            onChange={handleVolumeChange}
            className="w-20 h-1 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-accent"
          />
        </div>
      </div>
    </div>
  );
}

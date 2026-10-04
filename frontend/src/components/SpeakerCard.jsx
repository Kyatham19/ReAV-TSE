import React from 'react';
import { Check, Clock, Film } from 'lucide-react';
import { motion } from 'framer-motion';

export default function SpeakerCard({ person, isSelected, onSelect }) {
  return (
    <motion.div
      whileHover={{ y: -3, scale: 1.01 }}
      whileTap={{ scale: 0.99 }}
      transition={{ duration: 0.2 }}
      onClick={() => onSelect(person)}
      className={`relative group cursor-pointer rounded-2xl p-3.5 transition-all duration-300 border flex flex-col justify-between ${
        isSelected
          ? 'bg-surface-elevated border-accent shadow-[0_0_25px_rgba(139,92,246,0.3)] ring-1 ring-accent'
          : 'bg-surface/80 hover:bg-surface-elevated border-surface-border hover:border-surface-border-hover'
      }`}
    >
      {/* Selected Indicator Badge */}
      {isSelected && (
        <div className="absolute top-2.5 right-2.5 z-10 w-6 h-6 rounded-full bg-accent text-white flex items-center justify-center shadow-md animate-in fade-in zoom-in duration-200">
          <Check className="w-3.5 h-3.5 stroke-[2.5]" />
        </div>
      )}

      {/* Face Image Frame */}
      <div className="relative aspect-square w-full rounded-xl overflow-hidden bg-neutral-900 mb-3 border border-white/[0.06] group-hover:border-accent/40 transition-colors">
        <img
          src={person.thumbnailUrl}
          alt={person.title}
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
          loading="lazy"
        />

        {/* Duration Chip on Image */}
        <div className="absolute bottom-2 left-2 px-2 py-0.5 rounded-md bg-black/70 backdrop-blur-md border border-white/10 text-[11px] font-mono font-medium text-white flex items-center gap-1">
          <Clock className="w-3 h-3 text-lavender-400" />
          <span>{person.detectedDuration}s speech</span>
        </div>

        {/* Gradient shadow overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-60" />
      </div>

      {/* Details */}
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-white text-sm group-hover:text-lavender-200 transition-colors">
            {person.title}
          </h3>
          <span className="text-[11px] font-mono text-neutral-500">
            {person.tracksCount} {person.tracksCount === 1 ? 'segment' : 'segments'}
          </span>
        </div>

        {person.role && (
          <p className="text-xs text-neutral-400 font-light truncate">
            {person.role}
          </p>
        )}

        <div className="pt-2 flex items-center gap-2 text-[11px] text-neutral-500 font-mono">
          <Film className="w-3 h-3 text-neutral-400" />
          <span>Span: {person.timeSpan}</span>
        </div>
      </div>

      {/* Micro indicator */}
      <div className="mt-3 pt-2 border-t border-white/[0.04] flex items-center justify-between text-[11px]">
        <span className={isSelected ? 'text-accent font-medium' : 'text-neutral-500 group-hover:text-neutral-400'}>
          {isSelected ? 'Target Selected' : 'Click to select'}
        </span>
        <span className="font-mono text-[10px] text-neutral-600 uppercase">
          Tracks {person.trackIds.join(', ')}
        </span>
      </div>
    </motion.div>
  );
}

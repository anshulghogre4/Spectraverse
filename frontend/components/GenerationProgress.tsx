'use client';

import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

type Stage = { label: string; duration: number };

const IMAGE_STAGES: Stage[] = [
  { label: 'Analysing image', duration: 3000 },
  { label: 'Mapping to sound', duration: 8000 },
  { label: 'Synthesising audio', duration: 6000 },
  { label: 'Finalising', duration: 400 },
];

const AUDIO_STAGES: Stage[] = [
  { label: 'Analysing audio', duration: 1000 },
  { label: 'Mapping to visuals', duration: 800 },
  { label: 'Building particle scene', duration: 1800 },
  { label: 'Finalising', duration: 400 },
];

type Props = {
  type: 'image' | 'audio';
  done: boolean;
};

export default function GenerationProgress({ type, done }: Props) {
  const stages = type === 'image' ? IMAGE_STAGES : AUDIO_STAGES;
  const [current, setCurrent] = useState(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (done) {
      setCurrent(stages.length); // mark all complete
      return;
    }
    setCurrent(0);

    let idx = 0;
    const advance = () => {
      // Stall at 90% (second-to-last stage) until done=true
      if (idx >= stages.length - 1) return;
      idx += 1;
      setCurrent(idx);
      if (idx < stages.length - 1) {
        timerRef.current = setTimeout(advance, stages[idx].duration);
      }
    };

    timerRef.current = setTimeout(advance, stages[0].duration);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [done, type]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-gray-900/60 border border-gray-700/60 rounded-2xl px-5 py-4 space-y-3"
    >
      <p className="text-xs font-semibold text-gray-400 uppercase tracking-widest">
        {done ? 'Complete' : 'Generating…'}
      </p>
      <div className="space-y-2">
        {stages.map((stage, i) => {
          const isComplete = i < current || done;
          const isActive = i === current && !done;
          return (
            <div key={stage.label} className="flex items-center gap-3">
              {/* Icon */}
              <div className="w-5 h-5 flex-shrink-0 flex items-center justify-center">
                <AnimatePresence mode="wait">
                  {isComplete ? (
                    <motion.span
                      key="check"
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      className="text-green-400 text-base leading-none"
                    >
                      ✓
                    </motion.span>
                  ) : isActive ? (
                    <motion.span
                      key="spin"
                      animate={{ rotate: 360 }}
                      transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}
                      className="block w-3.5 h-3.5 border-2 border-blue-400 border-t-transparent rounded-full"
                    />
                  ) : (
                    <span key="dot" className="block w-2 h-2 rounded-full bg-gray-700" />
                  )}
                </AnimatePresence>
              </div>

              {/* Label */}
              <span
                className={`text-sm transition-colors duration-300 ${
                  isComplete
                    ? 'text-green-400'
                    : isActive
                    ? 'text-white font-medium'
                    : 'text-gray-600'
                }`}
              >
                {stage.label}
              </span>
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}

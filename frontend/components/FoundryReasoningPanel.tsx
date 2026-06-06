'use client';

import { motion } from 'framer-motion';
import type { FoundryCitation, FoundryReasoningStep } from '../lib/api';

type Props = {
  description: string;
  citations: FoundryCitation[];
  reasoningSteps: FoundryReasoningStep[];
  isFullyLive: boolean;
  isMock: boolean;
};

export default function FoundryReasoningPanel({
  description,
  citations,
  reasoningSteps,
  isFullyLive,
  isMock,
}: Props) {
  const stageColor: Record<string, string> = {
    vision:    'text-blue-300 border-blue-500/30 bg-blue-500/10',
    retrieval: 'text-purple-300 border-purple-500/30 bg-purple-500/10',
    mapping:   'text-emerald-300 border-emerald-500/30 bg-emerald-500/10',
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-gradient-to-b from-slate-900/80 to-slate-950/90 border border-slate-700/60 rounded-2xl overflow-hidden"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-5 pt-4 pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <span className="text-lg">🧠</span>
          <span className="text-sm font-semibold text-slate-200 uppercase tracking-widest">
            Agent reasoning
          </span>
          {isFullyLive ? (
            <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
              🔮 Foundry live
            </span>
          ) : isMock ? (
            <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30">
              ⚠ mock fallback
            </span>
          ) : null}
        </div>
      </div>

      {/* Vision description */}
      {description && (
        <div className="px-5 py-3 border-b border-slate-800">
          <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">
            What the AI saw
          </p>
          <p className="text-sm text-slate-200 italic leading-relaxed">
            “{description}”
          </p>
        </div>
      )}

      {/* Reasoning steps */}
      {reasoningSteps.length > 0 && (
        <div className="px-5 py-3 border-b border-slate-800 space-y-2">
          <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">
            Chain of thought
          </p>
          {reasoningSteps.map((step, i) => (
            <div
              key={i}
              className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-sm ${stageColor[step.stage] ?? 'border-slate-700 text-slate-300'}`}
            >
              <span className="text-xs font-bold uppercase tracking-widest opacity-70 mt-0.5 w-20 flex-shrink-0">
                {step.stage}
              </span>
              <div className="flex-1 min-w-0">
                <p className="leading-snug">{step.description}</p>
                {(step.tokens_used || step.is_mock) && (
                  <div className="flex gap-3 text-xs opacity-60 mt-0.5">
                    {step.tokens_used ? <span>{step.tokens_used} tokens</span> : null}
                    {step.is_mock ? <span>(mock)</span> : null}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Citations */}
      {citations.length > 0 && (
        <div className="px-5 py-3">
          <p className="text-xs text-slate-500 uppercase tracking-wide mb-2">
            Sources cited <span className="text-slate-600">({citations.length})</span>
          </p>
          <ol className="space-y-2">
            {citations.map((c) => (
              <li
                key={c.ref_id}
                className="bg-slate-900/60 border border-slate-800 rounded-lg p-3"
              >
                <div className="flex items-start gap-2">
                  <span className="text-xs font-bold text-emerald-400 mt-0.5">
                    [{c.ref_id}]
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-slate-200 truncate">
                      {c.title}
                    </p>
                    <p className="text-xs text-slate-500 truncate">
                      {c.doc_key}
                    </p>
                    <p className="text-xs text-slate-400 mt-1 leading-relaxed line-clamp-3">
                      {c.content_snippet}
                    </p>
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}
    </motion.div>
  );
}

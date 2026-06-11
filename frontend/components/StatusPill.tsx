'use client';

type Props = {
  mode: 'live' | 'heuristic' | 'mock';
  provider?: string;
};

const DOT_COLORS = {
  live: 'bg-green-400',
  heuristic: 'bg-yellow-400',
  mock: 'bg-amber-500',
} as const;

const PILL_STYLES = {
  live: 'bg-green-500/10 border-green-500/30 text-green-300',
  heuristic: 'bg-yellow-500/10 border-yellow-500/30 text-yellow-300',
  mock: 'bg-amber-500/10 border-amber-500/30 text-amber-300',
} as const;

const LABELS = {
  live: 'Live',
  heuristic: 'Heuristic',
  mock: 'Mock',
} as const;

export default function StatusPill({ mode, provider }: Props) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border text-xs font-medium ${PILL_STYLES[mode]}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${DOT_COLORS[mode]}`} />
      <span>{LABELS[mode]}</span>
      {mode === 'live' && provider && (
        <span className="opacity-70">&middot; {provider}</span>
      )}
    </span>
  );
}

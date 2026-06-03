'use client';

import { useState, useRef } from 'react';
import { motion } from 'framer-motion';
import {
  analyzeImage,
  analyzeAudio,
  type ImageFeatures,
  type AudioFeatures,
} from '../lib/api';

type Props = {
  type: 'image' | 'audio';
  mode: 'classic' | 'creative';
  style: string;
};

export default function UploadZone({ type, mode, style }: Props) {
  const [isDragging, setIsDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ImageFeatures | AudioFeatures | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const acceptedTypes =
    type === 'image'
      ? 'image/png,image/jpeg,image/webp'
      : 'audio/mpeg,audio/wav,audio/x-wav,audio/ogg';

  const clear = () => {
    setFile(null);
    setPreview(null);
    setResult(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleDragOver = (e: React.DragEvent) => { e.preventDefault(); setIsDragging(true); };
  const handleDragLeave = () => setIsDragging(false);
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
  };
  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) handleFile(e.target.files[0]);
  };

  const handleFile = (f: File) => {
    if (f.size > 10 * 1024 * 1024) { setError('File too large (max 10MB)'); return; }
    setFile(f);
    setResult(null);
    setError(null);
    if (type === 'image') {
      const reader = new FileReader();
      reader.onload = (e) => setPreview(e.target?.result as string);
      reader.readAsDataURL(f);
    } else {
      setPreview('audio');
    }
  };

  const handleTransform = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const res = type === 'image' ? await analyzeImage(file) : await analyzeAudio(file);
      if (res.status !== 'analysis_complete') {
        setError(res.message || 'Analysis unavailable — check backend dependencies');
        return;
      }
      setResult(res.features);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Analysis failed — is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  const accentBorder = type === 'image' ? 'hover:border-blue-400' : 'hover:border-purple-400';
  const accentBg = type === 'image' ? 'border-blue-400 bg-blue-500/10' : 'border-purple-400 bg-purple-500/10';
  const btnColor =
    type === 'image'
      ? 'bg-blue-600 hover:bg-blue-500 disabled:opacity-50'
      : 'bg-purple-600 hover:bg-purple-500 disabled:opacity-50';

  return (
    <div className="space-y-3">
      {/* Drop zone */}
      <motion.div
        className={`border-2 border-dashed rounded-xl p-8 transition-colors min-h-[180px] flex items-center justify-center ${
          isDragging ? accentBg : file ? 'border-green-600/50 bg-green-500/5' : `border-gray-600 ${accentBorder}`
        } ${!file ? 'cursor-pointer' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !file && fileInputRef.current?.click()}
        whileHover={!file ? { scale: 1.01 } : {}}
      >
        <input ref={fileInputRef} type="file" hidden accept={acceptedTypes} onChange={handleFileInput} />

        {file ? (
          <div className="text-center w-full">
            {type === 'image' && preview ? (
              <img src={preview} alt="preview" className="w-24 h-24 mx-auto rounded-lg object-cover mb-3" />
            ) : (
              <div className="text-5xl mb-3">🎵</div>
            )}
            <p className="font-semibold text-sm text-gray-200 truncate max-w-xs mx-auto">{file.name}</p>
            <p className="text-xs text-gray-500 mt-1">{(file.size / 1024).toFixed(0)} KB</p>
            <button
              onClick={(e) => { e.stopPropagation(); clear(); }}
              className="mt-2 text-xs text-gray-600 hover:text-red-400 transition underline"
            >
              Remove
            </button>
          </div>
        ) : (
          <div className="text-center">
            <p className="text-4xl mb-2">{type === 'image' ? '📸' : '🎵'}</p>
            <p className="text-base font-semibold text-gray-200">
              {type === 'image' ? 'Drag image here' : 'Drag audio here'}
            </p>
            <p className="text-sm text-gray-500 mt-1">or click to browse</p>
            <p className="text-xs text-gray-600 mt-2">
              {type === 'image' ? 'PNG, JPEG, WEBP' : 'MP3, WAV, OGG'} · Max 10MB
            </p>
          </div>
        )}
      </motion.div>

      {/* Transform button */}
      {file && !result && (
        <motion.button
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          onClick={handleTransform}
          disabled={loading}
          className={`w-full py-3 rounded-xl font-semibold transition flex items-center justify-center gap-2 text-white ${btnColor}`}
        >
          {loading ? (
            <>
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Analyzing…
            </>
          ) : (
            <>
              {type === 'image' ? '🎶 Analyze Image' : '🖼 Analyze Audio'}
              {mode === 'creative' && style && (
                <span className="text-xs opacity-70">({style})</span>
              )}
            </>
          )}
        </motion.button>
      )}

      {/* Error */}
      {error && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="bg-red-900/30 border border-red-500/40 rounded-lg p-3 text-sm text-red-300"
        >
          {error}
        </motion.div>
      )}

      {/* Results */}
      {result && <ResultPanel features={result} onReset={clear} />}
    </div>
  );
}

function ResultPanel({
  features,
  onReset,
}: {
  features: ImageFeatures | AudioFeatures;
  onReset: () => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-gray-900/60 border border-gray-700 rounded-xl p-5"
    >
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs font-semibold text-green-400 uppercase tracking-widest">
          ✓ Analysis complete
        </span>
        <button onClick={onReset} className="text-xs text-gray-500 hover:text-gray-300 transition">
          Try another
        </button>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {Object.entries(features).map(([key, value]) => (
          <FeatureTile key={key} label={key} value={value} />
        ))}
      </div>
    </motion.div>
  );
}

function FeatureTile({ label, value }: { label: string; value: unknown }) {
  let display: string;
  if (value !== null && typeof value === 'object') {
    display = Object.entries(value as Record<string, unknown>)
      .map(([k, v]) => {
        const n = Number(v);
        return `${k}:${isNaN(n) ? v : Math.round(n)}`;
      })
      .join(' ');
  } else if (typeof value === 'number') {
    display = value > 1 ? String(Math.round(value)) : value.toFixed(4);
  } else {
    display = String(value);
  }

  return (
    <div className="bg-gray-800/60 rounded-lg p-3">
      <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">
        {label.replace(/_/g, ' ')}
      </p>
      <p className="text-sm font-semibold text-gray-100 truncate">{display}</p>
    </div>
  );
}

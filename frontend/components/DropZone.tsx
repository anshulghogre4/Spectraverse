'use client';

import { motion } from 'framer-motion';

export type DropZoneProps = {
  isDragging: boolean;
  file: File | null;
  preview: string | null;
  type: 'image' | 'audio' | 'spectrogram';
  accept: string;
  fileInputRef: React.RefObject<HTMLInputElement>;
  onDragOver: (e: React.DragEvent) => void;
  onDragLeave: () => void;
  onDrop: (e: React.DragEvent) => void;
  onFileInput: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onClear: () => void;
  /** Whether to show the Remove button (default: true) */
  showRemove?: boolean;
};

const ACCENT_CONFIG = {
  image: {
    border: 'hover:border-blue-400',
    bg: 'border-blue-400 bg-blue-500/10',
    icon: '\u{1F4F8}', // camera emoji
    dragText: 'Drag image here',
    formats: 'PNG, JPEG, WEBP',
  },
  audio: {
    border: 'hover:border-purple-400',
    bg: 'border-purple-400 bg-purple-500/10',
    icon: '\u{1F3B5}', // music note emoji
    dragText: 'Drag audio here',
    formats: 'MP3, WAV, OGG',
  },
  spectrogram: {
    border: 'hover:border-teal-400',
    bg: 'border-teal-400 bg-teal-500/10',
    icon: '\u{1F52C}', // microscope emoji
    dragText: 'Drag spectrogram here',
    formats: 'PNG, JPEG, WEBP',
  },
};

export default function DropZone({
  isDragging,
  file,
  preview,
  type,
  accept,
  fileInputRef,
  onDragOver,
  onDragLeave,
  onDrop,
  onFileInput,
  onClear,
  showRemove = true,
}: DropZoneProps) {
  const accent = ACCENT_CONFIG[type];

  return (
    <motion.div
      className={`border-2 border-dashed rounded-xl p-6 transition-colors min-h-[160px] flex items-center justify-center ${
        isDragging ? accent.bg
        : file ? 'border-green-600/50 bg-green-500/5'
        : `border-gray-600 ${accent.border}`
      } ${!file ? 'cursor-pointer' : ''}`}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      onClick={() => !file && fileInputRef.current?.click()}
      whileHover={!file ? { scale: 1.01 } : {}}
    >
      <input ref={fileInputRef} type="file" hidden accept={accept} onChange={onFileInput} />

      {file ? (
        <div className="text-center w-full">
          {type === 'image' && preview ? (
            <img src={preview} alt="preview" className="w-20 h-20 mx-auto rounded-lg object-cover mb-2" />
          ) : type === 'spectrogram' && preview ? (
            <img src={preview} alt="preview" className="w-full max-h-36 mx-auto rounded-lg object-contain mb-2" />
          ) : (
            <div className="text-4xl mb-2">{'\u{1F3B5}'}</div>
          )}
          <p className="font-semibold text-sm text-gray-200 truncate max-w-xs mx-auto">{file.name}</p>
          <p className="text-xs text-gray-500 mt-1">{(file.size / 1024).toFixed(0)} KB</p>
          {showRemove && (
            <button
              onClick={(e) => { e.stopPropagation(); onClear(); }}
              className="mt-1.5 text-xs text-gray-600 hover:text-red-400 transition underline"
            >
              Remove
            </button>
          )}
        </div>
      ) : (
        <div className="text-center">
          <p className="text-4xl mb-2">{accent.icon}</p>
          <p className="text-base font-semibold text-gray-200">{accent.dragText}</p>
          <p className="text-sm text-gray-500 mt-1">or click to browse</p>
          <p className="text-xs text-gray-600 mt-2">{accent.formats} &middot; Max 10MB</p>
        </div>
      )}
    </motion.div>
  );
}

'use client';

import { useState, useRef, useCallback } from 'react';

export type UseFileUploadOptions = {
  maxSizeMB?: number;       // default 10
  accept?: string[];        // mime types
  generatePreview?: boolean; // default true for images
};

export type UseFileUploadReturn = {
  file: File | null;
  preview: string | null;
  error: string | null;
  isDragging: boolean;
  fileInputRef: React.RefObject<HTMLInputElement>;
  handleDragOver: (e: React.DragEvent) => void;
  handleDragLeave: () => void;
  handleDrop: (e: React.DragEvent) => void;
  handleFileInput: (e: React.ChangeEvent<HTMLInputElement>) => void;
  clear: () => void;
};

export function useFileUpload(options: UseFileUploadOptions = {}): UseFileUploadReturn {
  const { maxSizeMB = 10, accept, generatePreview = true } = options;

  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const processFile = useCallback((f: File) => {
    if (f.size > maxSizeMB * 1024 * 1024) {
      setError(`File too large (max ${maxSizeMB}MB)`);
      return;
    }
    setFile(f);
    setError(null);

    // Generate preview
    if (generatePreview && f.type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = (e) => setPreview(e.target?.result as string);
      reader.readAsDataURL(f);
    } else if (f.type.startsWith('audio/')) {
      setPreview('audio');
    } else {
      setPreview(null);
    }
  }, [maxSizeMB, generatePreview]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files[0]) processFile(e.dataTransfer.files[0]);
  }, [processFile]);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) processFile(e.target.files[0]);
  }, [processFile]);

  const clear = useCallback(() => {
    setFile(null);
    setPreview(null);
    setError(null);
    setIsDragging(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, []);

  return {
    file,
    preview,
    error,
    isDragging,
    fileInputRef,
    handleDragOver,
    handleDragLeave,
    handleDrop,
    handleFileInput,
    clear,
  };
}

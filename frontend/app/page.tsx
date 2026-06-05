"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import UploadZone from "../components/UploadZone";
import SpectrogramUploadZone from "../components/SpectrogramUploadZone";

export default function Home() {
  const [mode, setMode] = useState<"classic" | "creative">("classic");
  const [style, setStyle] = useState<string>("");

  const styles = {
    creative: [
      "Funny",
      "Horror",
      "Emotional",
      "Bassy",
      "Electrifying",
      "Spiritual",
      "Experimental",
    ],
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-black text-white p-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="max-w-6xl mx-auto mb-12"
      >
        <h1 className="text-6xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent mb-2">
          SpectraVerse
        </h1>
        <p className="text-xl text-gray-300">Hear images. Visualize music. Decode spectrograms.</p>
      </motion.div>

      {/* Mode & Style Selector */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2 }}
        className="max-w-6xl mx-auto mb-12"
      >
        <div className="flex flex-wrap gap-4 mb-6">
          <button
            onClick={() => setMode("classic")}
            className={`px-6 py-3 rounded-lg font-semibold transition transform hover:scale-105 ${
              mode === "classic"
                ? "bg-blue-500 text-white shadow-lg shadow-blue-500/50"
                : "bg-gray-700 text-gray-300 hover:bg-gray-600"
            }`}
          >
            Classic Mode
          </button>
          <button
            onClick={() => setMode("creative")}
            className={`px-6 py-3 rounded-lg font-semibold transition transform hover:scale-105 ${
              mode === "creative"
                ? "bg-purple-500 text-white shadow-lg shadow-purple-500/50"
                : "bg-gray-700 text-gray-300 hover:bg-gray-600"
            }`}
          >
            Creative Mode
          </button>
        </div>

        {mode === "creative" && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            className="flex flex-wrap gap-2"
          >
            {styles.creative.map((s) => (
              <button
                key={s}
                onClick={() => setStyle(s)}
                className={`px-4 py-2 rounded-full text-sm font-semibold transition ${
                  style === s
                    ? "bg-gradient-to-r from-pink-500 to-purple-500 text-white"
                    : "bg-gray-700 text-gray-300 hover:bg-gray-600"
                }`}
              >
                {s}
              </button>
            ))}
          </motion.div>
        )}
      </motion.div>

      {/* Section 1 & 2: Image↔Audio transforms */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.4 }}
        className="max-w-6xl mx-auto grid md:grid-cols-2 gap-8 mb-12"
      >
        <div>
          <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
            <span>🎨</span> Image to Audio
          </h2>
          <UploadZone type="image" mode={mode} style={style} />
        </div>

        <div>
          <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
            <span>🎵</span> Audio to Visual
          </h2>
          <UploadZone type="audio" mode={mode} style={style} />
        </div>
      </motion.div>

      {/* Section 3: Spectrogram → Audio (teal theme) */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.6 }}
        className="max-w-6xl mx-auto"
      >
        {/* Divider */}
        <div className="flex items-center gap-4 mb-8">
          <div className="h-px flex-1 bg-gradient-to-r from-transparent via-teal-500/40 to-transparent" />
          <span className="text-xs font-semibold text-teal-500 uppercase tracking-widest px-3">
            Spectrogram Inversion
          </span>
          <div className="h-px flex-1 bg-gradient-to-r from-transparent via-teal-500/40 to-transparent" />
        </div>

        <div className="max-w-2xl mx-auto">
          <div className="mb-4">
            <h2 className="text-2xl font-bold flex items-center gap-2 text-teal-300">
              <span>🔬</span> Spectrogram → Audio
            </h2>
            <p className="text-sm text-gray-400 mt-1">
              Upload any mel or STFT spectrogram image — a screenshot, export, or photo —
              and hear the audio reconstructed from it using Griffin-Lim inversion.
            </p>
          </div>
          <SpectrogramUploadZone />
        </div>
      </motion.div>

      {/* Footer */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.8 }}
        className="max-w-6xl mx-auto mt-16 text-center text-gray-400"
      >
        <p>✨ AI-powered multimodal transformation · Spectrogram inversion via Griffin-Lim</p>
      </motion.div>
    </main>
  );
}

"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import UploadZone from "../components/UploadZone";
import SpectrogramUploadZone from "../components/SpectrogramUploadZone";

type Tab = "image" | "audio" | "spectrogram";

const TABS: { id: Tab; icon: string; label: string }[] = [
  { id: "spectrogram", icon: "🔬", label: "Spectrogram Lab" },
  { id: "audio",       icon: "🎵", label: "Audio → Visual" },
  { id: "image",       icon: "🎨", label: "Image → Audio" },
];

export default function Home() {
  const [activeTab, setActiveTab] = useState<Tab>("spectrogram");

  return (
    <main className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-black text-white">
      {/* ── Header ───────────────────────────────────────────────── */}
      <div className="px-8 pt-10 pb-6 max-w-3xl mx-auto">
        <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="text-5xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent mb-1">
            SpectraVerse
          </h1>
          <p className="text-lg text-gray-400">Hear images. Visualize music. Decode spectrograms.</p>
        </motion.div>
      </div>

      {/* ── Tab bar ──────────────────────────────────────────────── */}
      <div className="sticky top-0 z-30 bg-gradient-to-b from-indigo-950/90 to-purple-950/80 backdrop-blur-md border-b border-white/10">
        <div className="max-w-3xl mx-auto px-8 flex gap-1 py-2">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all ${
                activeTab === t.id
                  ? "bg-white/10 text-white shadow-sm"
                  : "text-gray-400 hover:text-gray-200 hover:bg-white/5"
              }`}
            >
              <span>{t.icon}</span>
              <span>{t.label}</span>
            </button>
          ))}
        </div>
        {/* sliding underline */}
        <div className="max-w-3xl mx-auto px-8 relative h-0.5">
          {TABS.map((t) => (
            activeTab === t.id && (
              <motion.div
                key={t.id}
                layoutId="tab-underline"
                className={`absolute h-0.5 rounded-full ${
                  t.id === "image" ? "bg-blue-400" :
                  t.id === "audio" ? "bg-purple-400" : "bg-teal-400"
                }`}
                style={{
                  width: "calc(33.33% - 0.5rem)",
                  left: `calc(${TABS.findIndex(x => x.id === t.id)} * 33.33%)`,
                }}
              />
            )
          ))}
        </div>
      </div>

      {/* ── Tab content ──────────────────────────────────────────── */}
      <div className="max-w-3xl mx-auto px-8 py-8">
        <AnimatePresence mode="wait">
          {activeTab === "spectrogram" && (
            <TabPane key="spectrogram">
              <TabHeader
                icon="🔬"
                title="Spectrogram Lab"
                subtitle="Convert audio to spectrograms, or reconstruct audio from spectrogram images via Griffin-Lim inversion."
                accentClass="text-teal-300"
              />
              <SpectrogramUploadZone />
            </TabPane>
          )}

          {activeTab === "image" && (
            <TabPane key="image">
              <TabHeader
                icon="🎨"
                title="Image to Audio"
                subtitle="Upload an image and let Foundry IQ compose music grounded in colour theory and music science."
                accentClass="text-blue-300"
              />
              <UploadZone type="image" mode="classic" style="" />
            </TabPane>
          )}

          {activeTab === "audio" && (
            <TabPane key="audio">
              <TabHeader
                icon="🎵"
                title="Audio to Visual"
                subtitle="Upload audio and watch Foundry IQ turn timbres, BPM, and vibe into a cited generative visual."
                accentClass="text-purple-300"
              />
              <UploadZone type="audio" mode="classic" style="" />
            </TabPane>
          )}
        </AnimatePresence>
      </div>

      {/* ── Footer ───────────────────────────────────────────────── */}
      <div className="max-w-3xl mx-auto px-8 pb-12 text-center text-gray-500 text-sm">
        AI-powered multimodal transformation · Foundry IQ cited reasoning · Griffin-Lim spectrogram inversion
      </div>
    </main>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function TabPane({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      transition={{ duration: 0.18 }}
      className="space-y-6"
    >
      {children}
    </motion.div>
  );
}

function TabHeader({
  icon, title, subtitle, accentClass,
}: {
  icon: string;
  title: string;
  subtitle: string;
  accentClass: string;
}) {
  return (
    <div className="mb-2">
      <h2 className={`text-2xl font-bold flex items-center gap-2 ${accentClass}`}>
        <span>{icon}</span> {title}
      </h2>
      <p className="text-sm text-gray-400 mt-1">{subtitle}</p>
    </div>
  );
}


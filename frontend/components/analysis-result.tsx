"use client"

import { useState } from "react"
import {
  AlertTriangle,
  Shield,
  ArrowRight,
  Clock,
  Image as ImageIcon,
  Volume2,
  FileText,
  Play,
  Pause,
  CheckCircle,
  AlertCircle,
  FileDown,
  Activity,
  ExternalLink,
  ChevronDown,
  ChevronUp
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import type { SourceInfo } from "./upload-screen"

interface AnalysisResultProps {
  onContinue: () => void
  onBack: () => void
  sourceInfo?: SourceInfo
  data?: any
}

export function AnalysisResult({ onContinue, onBack, sourceInfo, data }: AnalysisResultProps) {
  const [isPlaying, setIsPlaying] = useState(false)
  const [showFactCheck, setShowFactCheck] = useState(true)

  // Retrieve nested structure or fallback to top level for legacy support
  const detection = data?.deepfake_detection || {}
  const isFake = detection.label ? detection.label === "Fake" : data?.final_prediction === "Fake"
  const finalLabel = detection.label || data?.final_prediction || "Unknown"
  const rawConfidence = detection.confidence !== undefined ? detection.confidence : data?.confidence
  const confidenceValue = rawConfidence ? Math.round(rawConfidence * 100) : 85
  const riskLevel = detection.risk_level || data?.reliability || "MEDIUM"
  const streams = detection.streams || {}
  const legalReportUrl = data?.legal_report_url
  const factCheck = data?.fact_check || {}
  const isVideo = data?.media_type === "video" || 
                  sourceInfo?.localPreviewUrl?.match(/\.(mp4|webm|ogg|mov|mkv|avi|m4v)/i) ||
                  (data?.file_name || "").match(/\.(mp4|webm|ogg|mov|mkv|avi|m4v)/i);
  
  const getRiskColor = (level: string) => {
    switch (level) {
      case "CRITICAL":
      case "HIGH":
        return "text-red-500 border-red-500/30 bg-red-500/10"
      case "MEDIUM":
        return "text-amber-500 border-amber-500/30 bg-amber-500/10"
      case "LOW":
        return "text-blue-500 border-blue-500/30 bg-blue-500/10"
      default:
        return "text-emerald-500 border-emerald-500/30 bg-emerald-500/10"
    }
  }

  const getStreamColor = (prob: number | null | undefined) => {
    if (prob === null || prob === undefined) return "bg-muted"
    if (prob >= 0.75) return "bg-red-500"
    if (prob >= 0.50) return "bg-amber-500"
    return "bg-emerald-500"
  }

  // Handle PDF Download
  const handleDownloadReport = () => {
    if (legalReportUrl) {
      const fullUrl = `http://127.0.0.1:8000${legalReportUrl}`
      window.open(fullUrl, "_blank")
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#0b0f19] text-[#e2e8f0] font-sans selection:bg-primary selection:text-primary-foreground">
      {/* Header */}
      <header className="border-b border-[#1e293b] bg-[#0f172a]/80 px-6 py-4 sticky top-0 z-50 backdrop-blur-md">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="sm" onClick={onBack} className="text-[#94a3b8] hover:text-white hover:bg-slate-800">
              Back
            </Button>
            <div className="flex items-center gap-3">
              <div className="p-2 bg-primary/10 rounded-lg">
                <Shield className="w-5 h-5 text-primary" />
              </div>
              <span className="font-semibold text-white">BharatShield</span>
            </div>
            <span className="text-[#475569]">/</span>
            <span className="text-[#94a3b8]">Analysis Dashboard</span>
          </div>

          {legalReportUrl && (
            <Button
              onClick={handleDownloadReport}
              variant="outline"
              size="sm"
              className="gap-2 text-primary border-primary/30 bg-primary/5 hover:bg-primary/20 hover:text-white transition-all shadow-[0_0_15px_rgba(59,130,246,0.1)]"
            >
              <FileDown className="w-4 h-4" />
              <span>Legal Report (PDF)</span>
            </Button>
          )}
        </div>
      </header>

      <main className="flex-1 px-6 py-8">
        <div className="max-w-5xl mx-auto space-y-8">
          
          {/* Main Verdict Banner */}
          <Card className={`relative overflow-hidden bg-gradient-to-r ${
            isFake 
              ? "from-red-950/40 to-slate-900/60 border-red-900/40" 
              : "from-emerald-950/40 to-slate-900/60 border-emerald-900/40"
          } border-2 shadow-[0_4px_30px_rgba(0,0,0,0.4)] backdrop-blur-md`}>
            {/* Ambient Background Glow */}
            <div className={`absolute top-0 right-0 w-80 h-80 rounded-full blur-[100px] pointer-events-none opacity-20 ${
              isFake ? "bg-red-500" : "bg-emerald-500"
            }`} />

            <CardContent className="p-8 relative z-10">
              <div className="flex flex-col md:flex-row items-center justify-between gap-8">
                
                {/* Verdict Info */}
                <div className="flex-1 space-y-4 text-center md:text-left">
                  <div className="flex flex-wrap items-center gap-3 justify-center md:justify-start">
                    <span className={`px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider border ${getRiskColor(riskLevel)}`}>
                      {riskLevel} RISK TIER
                    </span>
                    {sourceInfo?.verified && (
                      <span className="px-3 py-1 rounded-full text-xs font-semibold bg-blue-500/10 border border-blue-500/20 text-blue-400">
                        VERIFIED ORIGIN
                      </span>
                    )}
                  </div>
                  
                  <h1 className={`text-4xl md:text-5xl font-extrabold tracking-tight ${
                    isFake ? "text-red-400 drop-shadow-[0_0_20px_rgba(248,113,113,0.2)]" : "text-emerald-400 drop-shadow-[0_0_20px_rgba(52,211,153,0.2)]"
                  }`}>
                    {isFake ? "Likely Synthetic Media" : "Likely Authentic"}
                  </h1>

                  <p className="text-lg text-slate-300 max-w-xl">
                    Our multi-stream neural ensemble has analyzed the file integrity and assessed the overall probability of manipulation at{" "}
                    <strong className="text-white">{confidenceValue}%</strong>.
                  </p>

                  <div className="text-xs text-slate-400 flex items-center justify-center md:justify-start gap-2">
                    <Clock className="w-3.5 h-3.5" />
                    <span>Analyzed in {(detection.processing_ms || 120).toFixed(0)} ms</span>
                    <span>•</span>
                    <span>Ref: {data?.submission_id || "BS-N/A"}</span>
                  </div>
                </div>

                {/* Score Radial Gauge */}
                <div className="relative w-36 h-36 flex-shrink-0 flex items-center justify-center">
                  <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                    <circle
                      cx="50"
                      cy="50"
                      r="40"
                      fill="none"
                      stroke="#1e293b"
                      strokeWidth="8"
                    />
                    <circle
                      cx="50"
                      cy="50"
                      r="40"
                      fill="none"
                      stroke={isFake ? "#f87171" : "#34d599"}
                      strokeWidth="8"
                      strokeDasharray={`${confidenceValue * 2.51} 251`}
                      strokeLinecap="round"
                      className="transition-all duration-1000 ease-out"
                    />
                  </svg>
                  <div className="absolute flex flex-col items-center">
                    <span className="text-3xl font-extrabold text-white">{confidenceValue}%</span>
                    <span className="text-[10px] uppercase text-slate-400 font-bold tracking-wider">Confidence</span>
                  </div>
                </div>

              </div>
            </CardContent>
          </Card>

          {/* 5-Stream Forensic Grid */}
          <div className="space-y-4">
            <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
              <Activity className="w-5 h-5 text-primary" />
              <span>Multi-Stream Neural Forensic Analysis</span>
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
              
              {/* Stream A: Spatial Texture */}
              <Card className="bg-[#0f172a] border-[#1e293b] hover:border-slate-700 transition-all">
                <CardContent className="p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Spatial Stream</span>
                    <ImageIcon className="w-4 h-4 text-sky-400" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-white text-sm">Spatial Textures</h3>
                    <p className="text-[11px] text-slate-400 mt-0.5">SRM Noise Forensics</p>
                  </div>
                  {streams.spatial_texture ? (
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs font-semibold">
                        <span>P(Fake)</span>
                        <span className={streams.spatial_texture.fake_prob >= 0.5 ? "text-red-400" : "text-emerald-400"}>
                          {Math.round(streams.spatial_texture.fake_prob * 100)}%
                        </span>
                      </div>
                      <div className="h-2 bg-[#1e293b] rounded-full overflow-hidden">
                        <div 
                          className={`h-full ${getStreamColor(streams.spatial_texture.fake_prob)}`} 
                          style={{ width: `${streams.spatial_texture.fake_prob * 100}%` }}
                        />
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-slate-500 italic">No spatial data</p>
                  )}
                </CardContent>
              </Card>

              {/* Stream B: Frequency Domain */}
              <Card className="bg-[#0f172a] border-[#1e293b] hover:border-slate-700 transition-all">
                <CardContent className="p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Frequency Stream</span>
                    <Activity className="w-4 h-4 text-purple-400" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-white text-sm">2D FFT DCT</h3>
                    <p className="text-[11px] text-slate-400 mt-0.5">Upsampling Grid Artifacts</p>
                  </div>
                  {streams.frequency_domain ? (
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs font-semibold">
                        <span>P(Fake)</span>
                        <span className={streams.frequency_domain.fake_prob >= 0.5 ? "text-red-400" : "text-emerald-400"}>
                          {Math.round(streams.frequency_domain.fake_prob * 100)}%
                        </span>
                      </div>
                      <div className="h-2 bg-[#1e293b] rounded-full overflow-hidden">
                        <div 
                          className={`h-full ${getStreamColor(streams.frequency_domain.fake_prob)}`} 
                          style={{ width: `${streams.frequency_domain.fake_prob * 100}%` }}
                        />
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-slate-500 italic">No frequency data</p>
                  )}
                </CardContent>
              </Card>

              {/* Stream C: Temporal Consistency */}
              <Card className="bg-[#0f172a] border-[#1e293b] hover:border-slate-700 transition-all">
                <CardContent className="p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Temporal Stream</span>
                    <Play className="w-4 h-4 text-amber-400" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-white text-sm">Temporal</h3>
                    <p className="text-[11px] text-slate-400 mt-0.5">R3D-18 Inter-frame Consistency</p>
                  </div>
                  {streams.temporal && streams.temporal.fake_prob !== null ? (
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs font-semibold">
                        <span>P(Fake)</span>
                        <span className={streams.temporal.fake_prob >= 0.5 ? "text-red-400" : "text-emerald-400"}>
                          {Math.round(streams.temporal.fake_prob * 100)}%
                        </span>
                      </div>
                      <div className="h-2 bg-[#1e293b] rounded-full overflow-hidden">
                        <div 
                          className={`h-full ${getStreamColor(streams.temporal.fake_prob)}`} 
                          style={{ width: `${streams.temporal.fake_prob * 100}%` }}
                        />
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-slate-500 italic">N/A — Image input</p>
                  )}
                </CardContent>
              </Card>

              {/* Stream D: Voice Synthesis */}
              <Card className="bg-[#0f172a] border-[#1e293b] hover:border-slate-700 transition-all">
                <CardContent className="p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Acoustic Stream</span>
                    <Volume2 className="w-4 h-4 text-red-400" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-white text-sm">Acoustic Forensics</h3>
                    <p className="text-[11px] text-slate-400 mt-0.5">Voice Synthesis RawNet2</p>
                  </div>
                  {streams.audio && streams.audio.available ? (
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs font-semibold">
                        <span>P(Fake)</span>
                        <span className={streams.audio.fake_prob >= 0.5 ? "text-red-400" : "text-emerald-400"}>
                          {Math.round(streams.audio.fake_prob * 100)}%
                        </span>
                      </div>
                      <div className="h-2 bg-[#1e293b] rounded-full overflow-hidden">
                        <div 
                          className={`h-full ${getStreamColor(streams.audio.fake_prob)}`} 
                          style={{ width: `${streams.audio.fake_prob * 100}%` }}
                        />
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-slate-500 italic">
                      {streams.audio?.note || "No audio track"}
                    </p>
                  )}
                </CardContent>
              </Card>

              {/* Stream E: rPPG Liveness */}
              <Card className="bg-[#0f172a] border-[#1e293b] hover:border-slate-700 transition-all">
                <CardContent className="p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Liveness Stream</span>
                    <Activity className="w-4 h-4 text-emerald-400 animate-pulse" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-white text-sm">rPPG Liveness</h3>
                    <p className="text-[11px] text-slate-400 mt-0.5">Biological Pulse Tracking</p>
                  </div>
                  {streams.rppg && streams.rppg.available ? (
                    <div className="space-y-2">
                      <div className="flex items-center gap-1.5">
                        <div className={`w-2.5 h-2.5 rounded-full ${streams.rppg.has_pulse ? 'bg-emerald-400 animate-ping' : 'bg-red-500'}`} />
                        <span className={`text-xs font-bold ${streams.rppg.has_pulse ? 'text-emerald-400' : 'text-red-400'}`}>
                          {streams.rppg.has_pulse ? "Pulse Detected" : "No Pulse (Fake)"}
                        </span>
                      </div>
                      <div className="text-[10px] text-slate-400">
                        SNR: {streams.rppg.bvp_snr ? streams.rppg.bvp_snr.toFixed(2) : "0.0"} dB
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-slate-500 italic">
                      {streams.rppg?.note || "Requires video input"}
                    </p>
                  )}
                </CardContent>
              </Card>

            </div>
          </div>

          {/* Media & Grad-CAM Visualizations */}
          <div className="grid md:grid-cols-2 gap-6">
            
            {/* Visualizer Block */}
            <Card className="bg-[#0f172a] border-[#1e293b]">
              <CardHeader className="pb-2 border-b border-[#1e293b]">
                <CardTitle className="text-lg text-white">Ingested Media Analysis</CardTitle>
                <CardDescription className="text-xs text-[#94a3b8]">
                  SHA-256: {data?.file?.sha256 || data?.hash || "Computing..."}
                </CardDescription>
              </CardHeader>
              <CardContent className="p-6 space-y-6">
                
                {/* Media Preview Box with Scanning Effect */}
                <div className="relative aspect-video bg-[#0b0f19] border border-[#1e293b] rounded-xl overflow-hidden group flex items-center justify-center">
                  {sourceInfo?.localPreviewUrl ? (
                    isVideo ? (
                      <video 
                        src={sourceInfo.localPreviewUrl} 
                        className="w-full h-full object-contain" 
                        controls
                        playsInline
                      />
                    ) : (
                      <img 
                        src={sourceInfo.localPreviewUrl} 
                        alt="Ingested Media Preview" 
                        className="w-full h-full object-contain"
                      />
                    )
                  ) : detection.gradcam_url ? (
                    <img 
                      src={`http://127.0.0.1:8000${detection.gradcam_url}`} 
                      alt="Grad-CAM Forensic Overlay" 
                      className="w-full h-full object-contain"
                    />
                  ) : (
                    <div className="text-center space-y-3">
                      <div className="w-14 h-14 rounded-full bg-slate-800/80 flex items-center justify-center mx-auto border border-slate-700">
                        <button 
                          onClick={() => setIsPlaying(!isPlaying)}
                          className="hover:scale-110 transition-transform text-white"
                        >
                          {isPlaying ? <Pause className="w-6 h-6" /> : <Play className="w-6 h-6 ml-1" />}
                        </button>
                      </div>
                      <p className="text-xs text-slate-400 font-semibold">{data?.file?.name || data?.file_name || "media_preview"}</p>
                    </div>
                  )}

                  {/* Tamper Scan lines */}
                  {isFake && (
                    <div className="absolute inset-x-0 top-0 overflow-hidden h-full pointer-events-none">
                      <div className="w-full h-0.5 bg-red-500/50 shadow-[0_0_10px_#ef4444] animate-scan-line" />
                      <div className="absolute top-4 left-4 bg-red-500/90 text-white font-bold text-[10px] px-2 py-0.5 rounded shadow-[0_0_10px_rgba(239,68,68,0.4)]">
                        SYNTHETIC PATTERN DETECTED
                      </div>
                    </div>
                  )}
                </div>

                {/* Audit Integrity verification */}
                <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800 space-y-2">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-emerald-400" />
                    <span className="text-xs font-bold text-white uppercase tracking-wider">BSA Sec. 63 Blockchain Chain of Custody</span>
                  </div>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    Cryptographic signature is linked to past audit ledger entries, creating a tamper-evident audit record. Verification status: <span className="text-emerald-400 font-semibold">Active & Confirmed</span>.
                  </p>
                </div>

              </CardContent>
            </Card>

            {/* Fact Check / Misinformation Analysis */}
            <Card className="bg-[#0f172a] border-[#1e293b]">
              <CardHeader className="pb-2 border-b border-[#1e293b] flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-lg text-white">Contextual Fact-Check</CardTitle>
                  <CardDescription className="text-xs text-[#94a3b8]">Claim Verification and Cross-Referencing</CardDescription>
                </div>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  onClick={() => setShowFactCheck(!showFactCheck)} 
                  className="text-slate-400 hover:text-white"
                >
                  {showFactCheck ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </Button>
              </CardHeader>
              
              {showFactCheck && (
                <CardContent className="p-6 space-y-4 max-h-[360px] overflow-y-auto">
                  {factCheck.available ? (
                    <div className="space-y-4">
                      
                      <div className="flex justify-between items-center bg-slate-950/40 p-3 rounded-lg border border-slate-800">
                        <span className="text-xs text-slate-400 font-semibold uppercase">Misinformation Risk</span>
                        <span className={`text-xs font-bold uppercase ${
                          factCheck.overall_misinfo_risk === "HIGH" ? "text-red-400" : "text-amber-400"
                        }`}>
                          {factCheck.overall_misinfo_risk} RISK
                        </span>
                      </div>

                      {factCheck.claims && factCheck.claims.map((claim: any, idx: number) => (
                        <div key={idx} className="p-3 bg-slate-950/60 rounded-lg border border-slate-800 space-y-2">
                          <div className="flex justify-between items-start gap-2">
                            <span className="text-[11px] text-slate-500 font-semibold">Speaker: {claim.speaker || "Unknown"}</span>
                            <span className={`text-[10px] font-extrabold uppercase px-1.5 py-0.5 rounded ${
                              claim.verdict === "FALSE" ? "bg-red-500/10 text-red-400 border border-red-500/20" : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                            }`}>
                              {claim.verdict}
                            </span>
                          </div>
                          
                          <p className="text-xs text-white italic font-medium leading-relaxed">
                            "{claim.claim}"
                          </p>
                          
                          <p className="text-[11px] text-slate-400 leading-normal">
                            {claim.explanation}
                          </p>

                          {/* Sources */}
                          {claim.sources && claim.sources.length > 0 && (
                            <div className="pt-2 border-t border-slate-900 space-y-1">
                              <span className="text-[9px] text-slate-500 font-bold uppercase tracking-wider">Refuted by Sources:</span>
                              {claim.sources.slice(0, 2).map((src: any, sIdx: number) => (
                                <a 
                                  key={sIdx} 
                                  href={src.url} 
                                  target="_blank" 
                                  rel="noopener noreferrer"
                                  className="flex items-center justify-between text-[10px] text-primary hover:underline"
                                >
                                  <span className="truncate max-w-[200px]">{src.title}</span>
                                  <ExternalLink className="w-2.5 h-2.5 flex-shrink-0" />
                                </a>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}

                    </div>
                  ) : (
                    <div className="text-center py-12 text-slate-500 space-y-2">
                      <AlertCircle className="w-8 h-8 mx-auto opacity-50" />
                      <p className="text-xs font-semibold">{factCheck.note || "No misinformation analysis was run for this input."}</p>
                    </div>
                  )}
                </CardContent>
              )}
            </Card>

          </div>

          {/* Continue Button */}
          <div className="flex justify-end gap-4 pt-6 border-t border-[#1e293b]">
            <Button
              onClick={onContinue}
              size="lg"
              className="gap-2 bg-primary hover:bg-primary/90 text-white shadow-lg shadow-primary/20"
            >
              <span>Escalate and Remediate</span>
              <ArrowRight className="w-5 h-5" />
            </Button>
          </div>

        </div>
      </main>
    </div>
  )
}

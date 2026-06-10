"use client"

import { useRef, useState } from "react"
import { AlertTriangle, Shield, ArrowRight, Video, CheckCircle, AlertCircle, BarChart, Clock, LayoutGrid, Info, Image as ImageIcon, PlayCircle, Download } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { SourceInfo } from "./upload-screen"

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8001";

interface VideoAnalysisResultProps {
  onContinue: () => void
  onBack: () => void
  sourceInfo?: SourceInfo
  data?: any
}

export function VideoAnalysisResult({ onContinue, onBack, sourceInfo, data }: VideoAnalysisResultProps) {
  const confidenceValue = data?.final_score ? Math.round(data.final_score * 100) : 0;
  const isFake = data?.final_decision === "FAKE";
  const reliability = data?.final_reliability || "LOW";

  const videoRef = useRef<HTMLVideoElement>(null);
  const [selectedFrame, setSelectedFrame] = useState<number | null>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [isSeekingEvidence, setIsSeekingEvidence] = useState<boolean>(false);
  const [evidenceViewMode, setEvidenceViewMode] = useState<"original" | "face" | "gradcam">("original");
  const [isExporting, setIsExporting] = useState<boolean>(false);

  const handleExportReport = async () => {
    try {
      setIsExporting(true);
      if (!data?.report_url) {
        throw new Error("Report URL not found in analysis data.");
      }
      
      const fullUrl = `${API_BASE_URL}${data.report_url}`;
      
      const a = document.createElement('a');
      a.href = fullUrl;
      a.download = "BharatShield_Forensic_Report.pdf";
      a.target = "_blank";
      // We must append to body for Firefox support
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      
    } catch (e) {
      console.error(e);
      alert("Failed to download PDF report.");
    } finally {
      setIsExporting(false);
    }
  };

  const verdictData = (() => {
    if (isFake) {
      return { verdict: "Likely Deepfake", confidence: confidenceValue, status: "fake" as const };
    }
    if (data?.final_decision === "REAL") {
      if (reliability === "HIGH") {
        return { verdict: "Likely Authentic", confidence: confidenceValue, status: "real" as const };
      }
      return { verdict: "Uncertain / Needs Review", confidence: confidenceValue, status: "uncertain" as const };
    }
    return { verdict: "Unknown", confidence: confidenceValue, status: "uncertain" as const };
  })();

  const getVerdictColor = (status: "fake" | "real" | "uncertain") => {
    switch (status) {
      case "fake": return "text-verdict-fake"
      case "real": return "text-verdict-real"
      case "uncertain": return "text-verdict-uncertain"
    }
  }

  const getVerdictBg = (status: "fake" | "real" | "uncertain") => {
    switch (status) {
      case "fake": return "bg-verdict-fake"
      case "real": return "bg-verdict-real"
      case "uncertain": return "bg-verdict-uncertain"
    }
  }

  const handleSeek = (timestampSec: number, frameIndex: number) => {
    setIsSeekingEvidence(true);
    setSelectedFrame(frameIndex);
    if (videoRef.current) {
      videoRef.current.currentTime = timestampSec;
      videoRef.current.pause();
    }
  };

  const getEvidenceTypeStyle = (type: string) => {
    switch (type) {
      case "Strong Multi-Model Agreement":
        return "bg-red-500/10 text-red-500 border-red-500/20";
      case "Temporal Consistency Anomaly":
        return "bg-orange-500/10 text-orange-500 border-orange-500/20";
      case "Frequency Artifact Detected":
        return "bg-purple-500/10 text-purple-500 border-purple-500/20";
      case "Visual Face Anomaly":
        return "bg-blue-500/10 text-blue-500 border-blue-500/20";
      case "Low Quality Evidence":
      default:
        return "bg-gray-500/10 text-gray-500 border-gray-500/20";
    }
  };

  const getDisplayEvidenceType = (type: string) => {
    switch (type) {
      case "Strong Multi-Model Agreement":
        return "High Confidence Multi-Model Detection";
      case "Frequency Artifact Detected":
        return "Frequency Pattern Anomaly";
      default:
        return type;
    }
  };

  const getEvidenceSummary = (score: number, type: string) => {
    const pct = Math.round(score * 100);
    let confidence = "Low";
    if (pct >= 95) confidence = "Very High";
    else if (pct >= 90) confidence = "High";
    else if (pct >= 75) confidence = "Moderate";

    const displayType = getDisplayEvidenceType(type || "");
    let signals: string[] = [];
    let assessment = "";

    switch (displayType) {
      case "High Confidence Multi-Model Detection":
        signals = ["CNN Detector", "Frequency Detector"];
        assessment = "Multiple independent detection methods identified suspicious patterns in this frame.";
        break;
      case "Frequency Pattern Anomaly":
        signals = ["Frequency Detector"];
        assessment = "The frequency-domain detector identified unusual patterns commonly associated with manipulated media.";
        break;
      case "Visual Face Anomaly":
        signals = ["CNN Detector"];
        assessment = "The spatial detector identified unusual facial characteristics.";
        break;
      case "Temporal Consistency Anomaly":
        signals = ["Temporal Consistency"];
        assessment = "Suspicious patterns persisted across multiple neighboring frames.";
        break;
      default:
        signals = ["Weak Supporting Signal"];
        assessment = "The frame was flagged, but supporting evidence is limited.";
        break;
    }

    return { confidence, signals, assessment };
  };

  const SourceBadge = () => {
    if (!sourceInfo) return null

    if (sourceInfo.verified && sourceInfo.type === "url") {
      return (
        <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-verdict-real/10 border border-verdict-real/30 rounded-full text-sm">
          <CheckCircle className="w-4 h-4 text-verdict-real" />
          <span className="text-verdict-real">
            Source: {sourceInfo.username ? `@${sourceInfo.username}` : "Direct link"} on {sourceInfo.platform}
          </span>
          <span className="text-verdict-real font-medium">Verified</span>
        </div>
      )
    }

    return (
      <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-verdict-uncertain/10 border border-verdict-uncertain/30 rounded-full text-sm">
        <AlertCircle className="w-4 h-4 text-verdict-uncertain" />
        <span className="text-verdict-uncertain">
          Source: Not verified (uploaded media)
          {sourceInfo.platform && ` — claimed from ${sourceInfo.platform}`}
        </span>
      </div>
    )
  }

  const metrics = data?.metrics || {}
  const suspiciousFrames = data?.top_suspicious_frames || data?.top_5_frames || []
  const frameScores = data?.frame_scores || []

  const maxIndex = frameScores.length > 0 ? Math.max(...frameScores.map((f: any) => f.frame_index)) : 100;

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-border px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={onBack}>
            Back
          </Button>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-primary/10 rounded-lg">
              <Shield className="w-5 h-5 text-primary" />
            </div>
            <span className="font-semibold">BharatShield</span>
          </div>
          <span className="text-muted-foreground">/</span>
          <span className="text-muted-foreground">Video Analysis Results</span>
          <div className="ml-auto">
            <Button 
              variant="default"
              size="sm"
              onClick={handleExportReport}
              disabled={isExporting}
            >
              <Download className="w-4 h-4 mr-2" />
              {isExporting ? "Exporting..." : "Export PDF Report"}
            </Button>
          </div>
        </div>
      </header>

      <main className="flex-1 px-6 py-8">
        <div className="max-w-5xl mx-auto space-y-8">
          
          {/* Multimodal Verdict Card */}
          {data?.fusion && (
            <Card className={`bg-card border-2 ${data.fusion.final_decision === "FAKE" ? "border-verdict-fake/50" : data.fusion.final_decision === "REAL" ? "border-verdict-real/50" : "border-verdict-uncertain/50"}`}>
              <CardContent className="p-8">
                <div className="flex flex-col md:flex-row items-center gap-8">
                  <div className={`p-6 rounded-2xl ${data.fusion.final_decision === "FAKE" ? "bg-verdict-fake/10" : data.fusion.final_decision === "REAL" ? "bg-verdict-real/10" : "bg-verdict-uncertain/10"}`}>
                    <Shield className={`w-16 h-16 ${data.fusion.final_decision === "FAKE" ? "text-verdict-fake" : data.fusion.final_decision === "REAL" ? "text-verdict-real" : "text-verdict-uncertain"}`} />
                  </div>

                  <div className="flex-1 text-center md:text-left space-y-3">
                    <p className="text-sm font-semibold tracking-wider text-muted-foreground uppercase">Multimodal Verdict</p>
                    <h1 className={`text-3xl md:text-4xl font-bold ${data.fusion.final_decision === "FAKE" ? "text-verdict-fake" : data.fusion.final_decision === "REAL" ? "text-verdict-real" : "text-verdict-uncertain"}`}>
                      {data.fusion.final_decision === "FAKE" ? "Likely Deepfake" : data.fusion.final_decision === "REAL" ? "Likely Authentic" : "Inconclusive"}
                    </h1>
                    
                    <div className="flex flex-wrap gap-2 items-center justify-center md:justify-start pt-1">
                      <div className={`inline-flex items-center gap-1.5 px-3 py-1.5 border rounded-full text-sm shadow-sm backdrop-blur-sm ${data.fusion.confidence === 'HIGH' ? 'bg-verdict-real/10 border-verdict-real/20 text-verdict-real' : data.fusion.confidence === 'MEDIUM' ? 'bg-amber-500/10 border-amber-500/20 text-amber-500' : 'bg-verdict-fake/10 border-verdict-fake/20 text-verdict-fake'}`}>
                        {data.fusion.confidence === 'HIGH' ? <CheckCircle className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
                        <span className="font-medium">Confidence: {data.fusion.confidence}</span>
                      </div>
                      
                      <div className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-secondary/50 border border-border rounded-full text-sm shadow-sm backdrop-blur-sm">
                        <span className="font-medium">Source: {data.fusion.decision_source}</span>
                      </div>

                      {data.fusion.conflict_level && data.fusion.conflict_level !== "NONE" && (
                        <div className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-red-500/10 border border-red-500/20 rounded-full text-sm shadow-sm backdrop-blur-sm text-red-500">
                          <AlertCircle className="w-4 h-4" />
                          <span className="font-medium">Conflict: {data.fusion.conflict_level}</span>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="w-32 h-32 relative">
                    <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                      <circle cx="50" cy="50" r="40" fill="none" stroke="currentColor" strokeWidth="8" className="text-secondary" />
                      <circle cx="50" cy="50" r="40" fill="none" stroke="currentColor" strokeWidth="8" strokeDasharray={`${Math.round(data.fusion.final_score * 100) * 2.51} 251`} strokeLinecap="round" className={data.fusion.final_decision === "FAKE" ? "text-verdict-fake" : data.fusion.final_decision === "REAL" ? "text-verdict-real" : "text-verdict-uncertain"} />
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className={`text-2xl font-bold ${data.fusion.final_decision === "FAKE" ? "text-verdict-fake" : data.fusion.final_decision === "REAL" ? "text-verdict-real" : "text-verdict-uncertain"}`}>
                        {Math.round(data.fusion.final_score * 100)}%
                      </span>
                    </div>
                  </div>
                </div>

                <div className="mt-8 pt-6 border-t border-border grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <h4 className="text-sm font-semibold mb-3">Modality Contributions</h4>
                    <div className="space-y-4">
                      <div>
                        <div className="flex justify-between text-sm mb-1">
                          <span className="text-muted-foreground">Video Analysis ({data.fusion.video_quality})</span>
                          <span className="font-medium">
                            {data.fusion.decision_source?.includes("VIDEO_PRIMARY") ? "Dominant" : `${Math.round((data.fusion.modality_contributions?.video || 0) * 100)}%`}
                          </span>
                        </div>
                        <div className="w-full h-2 bg-secondary rounded-full overflow-hidden">
                          <div className="h-full bg-primary" style={{ width: data.fusion.decision_source?.includes("VIDEO_PRIMARY") ? "100%" : `${(data.fusion.modality_contributions?.video || 0) * 100}%` }}></div>
                        </div>
                      </div>
                      <div>
                        <div className="flex justify-between text-sm mb-1">
                          <span className="text-muted-foreground">Audio Analysis ({data.fusion.audio_quality})</span>
                          <span className="font-medium">
                            {data.fusion.decision_source?.includes("VIDEO_PRIMARY") ? "Supporting" : `${Math.round((data.fusion.modality_contributions?.audio || 0) * 100)}%`}
                          </span>
                        </div>
                        <div className="w-full h-2 bg-secondary rounded-full overflow-hidden">
                          <div className="h-full bg-primary" style={{ width: data.fusion.decision_source?.includes("VIDEO_PRIMARY") ? "20%" : `${(data.fusion.modality_contributions?.audio || 0) * 100}%` }}></div>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold mb-3">Explanation</h4>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      {data.fusion.explanation}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
          
          {/* Verdict Card */}
          <Card className={`bg-card border-2 ${verdictData.status === "fake" ? "border-verdict-fake/50" : "border-verdict-real/50"}`}>
            <CardContent className="p-8">
              <div className="flex flex-col md:flex-row items-center gap-8">
                <div className={`p-6 rounded-2xl ${getVerdictBg(verdictData.status)}/10`}>
                  <Video className={`w-16 h-16 ${getVerdictColor(verdictData.status)}`} />
                </div>

                <div className="flex-1 text-center md:text-left space-y-3">
                  <h1 className={`text-3xl md:text-4xl font-bold ${getVerdictColor(verdictData.status)}`}>
                    {verdictData.verdict}
                  </h1>
                  <p className="text-xl text-muted-foreground">
                    Final Aggregated Score: {confidenceValue}%
                  </p>
                  
                  <div className="flex flex-col gap-2 items-center md:items-start pt-1">
                    <SourceBadge />
                    
                    <div className={`inline-flex items-center gap-1.5 px-3 py-1.5 ${reliability === 'HIGH' ? 'bg-verdict-real/10 border-verdict-real/20 text-verdict-real' : reliability === 'MEDIUM' ? 'bg-amber-500/10 border-amber-500/20 text-amber-500' : 'bg-verdict-fake/10 border-verdict-fake/20 text-verdict-fake'} border rounded-full text-sm shadow-sm backdrop-blur-sm`}>
                      {reliability === 'HIGH' ? <CheckCircle className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
                      <span className="font-medium">Reliability: {reliability}</span>
                    </div>
                  </div>
                </div>

                <div className="w-32 h-32 relative">
                  <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                    <circle cx="50" cy="50" r="40" fill="none" stroke="currentColor" strokeWidth="8" className="text-secondary" />
                    <circle cx="50" cy="50" r="40" fill="none" stroke="currentColor" strokeWidth="8" strokeDasharray={`${verdictData.confidence * 2.51} 251`} strokeLinecap="round" className={getVerdictColor(verdictData.status)} />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className={`text-2xl font-bold ${getVerdictColor(verdictData.status)}`}>
                      {verdictData.confidence}%
                    </span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Video Preview and Timeline */}
          {sourceInfo?.url && (
            <Card className="bg-card border-border overflow-hidden">
              <CardContent className="p-0">
                <div className="relative bg-black w-full flex flex-col items-center justify-center">
                  <div className="relative inline-block overflow-hidden">
                    <video 
                      ref={videoRef}
                      src={sourceInfo.url} 
                      controls 
                      className="max-h-[400px] w-auto block"
                      onPlay={() => setIsPlaying(true)}
                      onPause={() => setIsPlaying(false)}
                      onSeeked={() => setIsSeekingEvidence(false)}
                    />
                    {isSeekingEvidence && selectedFrame !== null && (
                      <div className="absolute inset-0 z-30 flex items-center justify-center bg-black/20 backdrop-blur-[1px]">
                        <div className="bg-black/80 text-white text-xs font-medium px-3 py-1.5 rounded-full flex items-center shadow-lg">
                          <div className="w-3 h-3 border-2 border-white/20 border-t-white rounded-full animate-spin mr-2"></div>
                          Loading evidence frame...
                        </div>
                      </div>
                    )}
                    {!isPlaying && !isSeekingEvidence && selectedFrame !== null && suspiciousFrames.find((f: any) => f.frame_index === selectedFrame)?.face_bbox && (
                      <>
                        <div className="absolute top-3 left-3 z-20 bg-black/70 backdrop-blur-sm text-white text-[10px] uppercase font-bold tracking-wider px-2.5 py-1 rounded border border-white/20 flex items-center shadow-lg">
                          <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse mr-1.5"></span>
                          Evidence Inspection Mode
                        </div>
                        <div 
                          className="absolute border-2 border-red-500 shadow-[0_0_10px_rgba(239,68,68,0.5)] bg-red-500/10 transition-all duration-300 pointer-events-none z-10"
                          style={{
                            left: `${suspiciousFrames.find((f: any) => f.frame_index === selectedFrame).face_bbox.left_percent}%`,
                            top: `${suspiciousFrames.find((f: any) => f.frame_index === selectedFrame).face_bbox.top_percent}%`,
                            width: `${suspiciousFrames.find((f: any) => f.frame_index === selectedFrame).face_bbox.width_percent}%`,
                            height: `${suspiciousFrames.find((f: any) => f.frame_index === selectedFrame).face_bbox.height_percent}%`
                          }}
                        >
                          <span className="absolute -top-5 left-0 bg-red-500 text-white text-[9px] font-bold px-1.5 py-0.5 rounded shadow-sm whitespace-nowrap">
                            Detected Face Region
                          </span>
                        </div>
                      </>
                    )}
                  </div>
                </div>
                <div className="p-4 border-t border-border bg-secondary/10">
                  <h4 className="text-sm font-medium mb-2">Suspicious Moments Timeline</h4>
                  <div className="relative w-full h-12 bg-secondary rounded mt-2 mb-4">
                    <div className="absolute top-0 w-full h-2 bg-secondary rounded" />
                    {suspiciousFrames.map((f: any, i: number) => {
                      const left = `${((f.frame_index || 0) / maxIndex) * 100}%`;
                      return (
                        <div 
                          key={i} 
                          className="absolute flex flex-col items-center cursor-pointer group" 
                          style={{ left, transform: 'translateX(-50%)', top: '-4px' }}
                          title={`Score: ${Math.round(f.score * 100)}%`}
                          onClick={() => handleSeek(f.timestamp_sec || 0, f.frame_index)}
                        >
                          <div className={`w-3 h-4 rounded-sm shadow transition-transform group-hover:scale-125 ${selectedFrame === f.frame_index ? 'bg-primary ring-2 ring-primary ring-offset-1 ring-offset-background scale-110' : 'bg-verdict-fake'}`} />
                          <div className="mt-1 text-[10px] font-medium leading-tight text-center opacity-80">
                            <div>{f.timestamp_label || "00:00.0"}</div>
                            <div className={f.score > 0.5 ? 'text-verdict-fake' : 'text-verdict-real'}>{Math.round(f.score * 100)}%</div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                  {/* Selected Evidence Panel */}
                  {selectedFrame !== null && suspiciousFrames.find((f: any) => f.frame_index === selectedFrame) && (() => {
                    const f = suspiciousFrames.find((f: any) => f.frame_index === selectedFrame);
                    return (
                      <div className="mt-6 p-4 border border-border bg-secondary/20 rounded-lg animate-in fade-in duration-200">
                        <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-4 gap-2">
                          <h4 className="font-semibold text-lg flex items-center gap-2">
                            <LayoutGrid className="w-5 h-5 text-primary" /> Selected Evidence
                          </h4>
                          {f.face_bbox && (
                            <span className="text-xs text-muted-foreground bg-primary/5 px-2 py-1 rounded border border-primary/10 flex items-center">
                              <Info className="w-3.5 h-3.5 mr-1 flex-shrink-0" />
                              This shows the face region analyzed by the model, not the exact manipulated artifact.
                            </span>
                          )}
                        </div>
                        <div className="flex flex-col md:flex-row gap-6 items-start">
                          <div className="flex flex-col gap-3 flex-shrink-0">
                            <div className="flex bg-secondary/80 rounded-md p-1 self-start w-full border border-border/50">
                              <button 
                                onClick={() => setEvidenceViewMode("original")}
                                className={`flex-1 px-2 py-1 text-[10px] font-medium rounded-sm transition-colors ${evidenceViewMode === "original" ? 'bg-background shadow text-foreground' : 'text-muted-foreground hover:text-foreground'}`}
                              >
                                Original
                              </button>
                              <button 
                                onClick={() => setEvidenceViewMode("face")}
                                className={`flex-1 px-2 py-1 text-[10px] font-medium rounded-sm transition-colors ${evidenceViewMode === "face" ? 'bg-background shadow text-foreground' : 'text-muted-foreground hover:text-foreground'}`}
                              >
                                Face
                              </button>
                              <button 
                                onClick={() => setEvidenceViewMode("gradcam")}
                                className={`flex-1 px-2 py-1 text-[10px] font-medium rounded-sm transition-colors ${evidenceViewMode === "gradcam" ? 'bg-background shadow text-foreground' : 'text-muted-foreground hover:text-foreground'}`}
                              >
                                Attention
                              </button>
                            </div>
                            <div className="w-48 bg-black rounded-lg overflow-hidden relative border border-border">
                              {f.image_url ? (
                                <div className="relative w-full">
                                  <img 
                                    src={`${API_BASE_URL}${evidenceViewMode === 'original' ? f.image_url : evidenceViewMode === 'face' ? (f.face_crop_url || f.image_url) : (f.gradcam_url || f.image_url)}`} 
                                    alt="evidence" 
                                    className="w-full h-auto block"
                                    onError={(e) => {
                                      e.currentTarget.style.display = 'none';
                                      if (e.currentTarget.nextElementSibling && e.currentTarget.nextElementSibling.nextElementSibling) {
                                        e.currentTarget.nextElementSibling.nextElementSibling.classList.remove('hidden');
                                        e.currentTarget.nextElementSibling.nextElementSibling.classList.add('flex');
                                      }
                                    }}
                                  />
                                  <div className="hidden absolute inset-0 items-center justify-center bg-muted">
                                    <ImageIcon className="w-8 h-8 text-muted-foreground" />
                                  </div>
                                </div>
                              ) : (
                                <div className="w-full h-32 flex items-center justify-center">
                                  <ImageIcon className="w-8 h-8 text-muted-foreground" />
                                </div>
                              )}
                            </div>
                          </div>
                          <div className="flex flex-col space-y-3 w-full">
                            <div className="grid grid-cols-3 gap-4">
                              <div className="flex flex-col">
                                <span className="text-sm text-muted-foreground">Timestamp</span>
                                <span className="font-bold text-lg">{f.timestamp_label}</span>
                              </div>
                              <div className="flex flex-col">
                                <span className="text-sm text-muted-foreground">Suspicion Score</span>
                                <span className={`font-bold text-lg ${f.score > 0.5 ? 'text-verdict-fake' : 'text-verdict-real'}`}>
                                  {Math.round(f.score * 100)}%
                               </span>
                              </div>
                              <div className="flex flex-col">
                                <span className="text-sm text-muted-foreground mb-1">Evidence Type</span>
                                <div className={`inline-flex w-fit items-center px-2 py-1 border rounded-md text-xs font-semibold ${getEvidenceTypeStyle(f.evidence_type || 'Low Quality Evidence')}`}>
                                  {getDisplayEvidenceType(f.evidence_type || "Low Quality Evidence")}
                                </div>
                                <span className="text-[10px] text-muted-foreground/70 mt-1.5 leading-tight italic max-w-xs">
                                  This explanation is derived from AI model signals and should be considered supporting evidence rather than manual human verification.
                                </span>
                              </div>
                            </div>
                            <div className="mt-2 text-sm text-foreground bg-secondary/50 p-3 rounded border border-border/50">
                              {f.evidence_explanation || "The model detected suspicious behavior but evidence quality is lower due to limited visual information."}
                            </div>
                            {evidenceViewMode === 'gradcam' && (
                              <div className="mt-3 p-3 bg-blue-500/10 border border-blue-500/20 rounded-md animate-in fade-in slide-in-from-top-1">
                                <h5 className="font-semibold text-sm text-blue-400 mb-1 flex items-center">
                                  <Info className="w-4 h-4 mr-1.5" />
                                  Model Attention Map
                                </h5>
                                <p className="text-xs text-muted-foreground mb-2">
                                  Highlighted regions contributed most strongly to the CNN detector’s prediction.
                                </p>
                                <div className="flex items-center gap-4 text-[10px] font-medium mb-2">
                                  <div className="flex items-center">
                                    <span className="w-3 h-3 rounded-sm bg-gradient-to-r from-red-500 to-yellow-400 mr-1.5 shadow-sm"></span>
                                    <span>Higher influence</span>
                                  </div>
                                  <div className="flex items-center">
                                    <span className="w-3 h-3 rounded-sm bg-blue-500 mr-1.5 shadow-sm"></span>
                                    <span>Lower influence</span>
                                  </div>
                                </div>
                                <p className="text-[10px] text-muted-foreground/80 italic leading-tight">
                                  <strong>Important note:</strong> This heatmap does not prove that a specific region is fake. It shows which regions influenced the AI model’s decision.
                                </p>
                              </div>
                            )}

                            {(() => {
                              const summary = getEvidenceSummary(f.score, f.evidence_type);
                              return (
                                <div className="mt-4 p-4 border border-border/60 bg-background/50 rounded-lg">
                                  <h5 className="font-semibold text-sm mb-3 text-foreground flex items-center">
                                    <Shield className="w-4 h-4 mr-1.5 text-primary" />
                                    Evidence Summary
                                  </h5>
                                  <div className="space-y-3">
                                    <div className="flex justify-between items-center text-xs">
                                      <span className="text-muted-foreground">Confidence:</span>
                                      <span className="font-bold text-foreground">{summary.confidence}</span>
                                    </div>
                                    <div>
                                      <span className="text-xs text-muted-foreground block mb-1.5">Signals:</span>
                                      <div className="flex flex-col gap-1">
                                        {summary.signals.map((sig, idx) => (
                                          <div key={idx} className="flex items-center text-xs text-foreground">
                                            <CheckCircle className="w-3.5 h-3.5 mr-1.5 text-green-500" />
                                            {sig}
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                    <div>
                                      <span className="text-xs text-muted-foreground block mb-1">Assessment:</span>
                                      <p className="text-xs text-foreground/90">{summary.assessment}</p>
                                    </div>
                                  </div>
                                </div>
                              );
                            })()}
                            <div className="flex items-center justify-between mt-2 pt-2 border-t border-border/30">
                              <div className="text-xs text-muted-foreground font-mono">
                                Frame ID: {f.frame} (Traceability / Authority Review)
                              </div>
                              {f.image_url && (
                                <Button 
                                  variant="outline" 
                                  size="sm" 
                                  className="h-8 text-xs"
                                  onClick={() => window.open(`${API_BASE_URL}${f.image_url}`, '_blank')}
                                >
                                  <Download className="w-3.5 h-3.5 mr-1.5" />
                                  Download Evidence Frame
                                </Button>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })()}
                </div>
              </CardContent>
            </Card>
          )}



          {/* Audio Analysis Block */}
          <Card className="bg-card border-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg flex items-center gap-2">
                <AlertCircle className={`w-5 h-5 ${data?.audio?.available ? 'text-primary' : 'text-muted-foreground'}`} />
                Audio Analysis
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4">
              <div className="flex flex-col gap-4">
                <div className="flex items-start gap-4 p-4 rounded-lg bg-secondary/50 border border-border">
                  <div className="flex-1 space-y-2">
                    {!data?.audio?.available ? (
                      <>
                        <h4 className="font-medium text-muted-foreground">Status: {data?.audio?.extraction_status === "NO_AUDIO" ? "Audio track not detected" : (data?.audio?.extraction_status === "FAILED" ? "Extraction Failed" : "Not enabled yet")}</h4>
                        <p className="text-sm text-muted-foreground">
                          {data?.audio?.explanation || "Audio deepfake analysis is not enabled yet."}
                        </p>
                      </>
                    ) : (
                      <>
                        <div className="flex justify-between items-start">
                          <div>
                            <h4 className="font-medium flex items-center gap-2">
                              Status: Extracted Successfully
                              {data.audio.decision === "UNRELIABLE" && (
                                <span className="inline-flex items-center px-2 py-0.5 rounded-full border text-amber-500 border-amber-500/50 bg-amber-500/10 text-[10px] font-semibold">
                                  <AlertCircle className="w-3 h-3 mr-1" />
                                  UNRELIABLE AUDIO
                                </span>
                              )}
                            </h4>
                            <p className="text-sm text-muted-foreground mt-1">
                              {data.audio.explanation}
                            </p>
                            {data.audio.model_name && (
                              <p className="text-xs text-muted-foreground mt-2 flex items-center gap-1.5 font-mono bg-secondary/50 inline-flex px-2 py-0.5 rounded border border-border/50">
                                <Shield className="w-3 h-3" />
                                {data.audio.model_name} {data.audio.model_version !== "Error" && `(${data.audio.model_version})`} • {data.audio.checkpoint_name}
                              </p>
                            )}
                          </div>
                          {data.audio.decision && data.audio.decision !== "NOT_ANALYZED" && data.audio.decision !== "UNRELIABLE" && (
                            <div className="text-right flex flex-col items-end">
                              <p className="text-sm font-medium text-muted-foreground mb-1">Audio Supporting Signal</p>
                              <span className={`inline-flex items-center justify-center rounded-md text-sm font-semibold text-lg py-1 px-3 ${data.audio.decision.includes("SUSPICION") || data.audio.decision.includes("SUSPICIOUS") ? "bg-destructive text-destructive-foreground hover:bg-destructive/90" : data.audio.decision === "NO_STRONG_ACOUSTIC_ANOMALY" ? "bg-secondary text-secondary-foreground" : "bg-muted text-muted-foreground"}`}>
                                {data.audio.decision.replace(/_/g, " ")}
                              </span>
                              <div className="flex flex-col items-end gap-1 mt-1.5">
                                <div className="flex items-center gap-2">
                                  <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${data.audio.confidence === 'HIGH' ? 'bg-green-500/20 text-green-500' : 'bg-amber-500/20 text-amber-500'}`}>
                                    {data.audio.confidence === 'LOW' && (data.audio.calibrated_fake_score || 0) >= 0.65 ? 'MODERATE AUDIO CONFIDENCE' : `${data.audio.confidence} CONFIDENCE`}
                                  </span>
                                  <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${data.audio.reliability_level === 'HIGH' ? 'bg-green-500/20 text-green-500' : data.audio.reliability_level === 'MEDIUM' ? 'bg-amber-500/20 text-amber-500' : 'bg-red-500/20 text-red-500'}`}>
                                    SIGNAL QUALITY: {data.audio.audio_reliability || 'LOW'}/100
                                  </span>
                                </div>
                                <div className="text-xs font-semibold">
                                  <span className="text-muted-foreground mr-1">Raw:</span>
                                  <span className="line-through text-muted-foreground opacity-70">{((data.audio.raw_fake_score || 0) * 100).toFixed(1)}%</span>
                                  <span className="text-muted-foreground ml-2 mr-1">Calibrated:</span>
                                  <span>{((data.audio.calibrated_fake_score || 0) * 100).toFixed(1)}%</span>
                                </div>
                                {data.audio.audio_reliability < 50 && (
                                  <div className="text-[10px] text-amber-500 mt-1 max-w-[200px] text-right">
                                    <AlertTriangle className="inline w-3 h-3 mr-1" />
                                    Audio down-weighted in fusion due to low reliability.
                                  </div>
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                        
                        {data.audio.audio_quality_report && (
                          <div className="grid grid-cols-2 md:grid-cols-6 gap-4 mt-4 pt-4 border-t border-border">
                            <div>
                              <p className="text-xs text-muted-foreground">Quality Score</p>
                              <p className={`font-semibold text-sm ${data.audio.audio_quality_report.quality_score < 0.5 ? 'text-amber-500' : 'text-green-500'}`}>
                                {Math.round((data.audio.audio_quality_report.quality_score || 0) * 100)}/100
                              </p>
                            </div>
                            <div>
                              <p className="text-xs text-muted-foreground">Duration</p>
                              <p className="font-semibold text-sm">{(data.audio.audio_quality_report.duration_sec || 0).toFixed(2)}s</p>
                            </div>
                            <div>
                              <p className="text-xs text-muted-foreground">Sample Rate</p>
                              <p className="font-semibold text-sm">{data.audio.audio_quality_report.sample_rate || 0} Hz</p>
                            </div>
                            <div>
                              <p className="text-xs text-muted-foreground">Silence Ratio</p>
                              <p className={`font-semibold text-sm ${data.audio.audio_quality_report.silence_ratio > 0.5 ? 'text-amber-500' : ''}`}>
                                {((data.audio.audio_quality_report.silence_ratio || 0) * 100).toFixed(1)}%
                              </p>
                            </div>
                            <div>
                              <p className="text-xs text-muted-foreground">SNR Estimate</p>
                              <p className="font-semibold text-sm">{(data.audio.audio_quality_report.snr_estimate || 0).toFixed(1)} dB</p>
                            </div>
                            <div>
                              <p className="text-xs text-muted-foreground">Clipping</p>
                              <p className={`font-semibold text-sm ${data.audio.audio_quality_report.clipping_detected ? 'text-red-500' : 'text-green-500'}`}>
                                {data.audio.audio_quality_report.clipping_detected ? 'Yes' : 'No'}
                              </p>
                            </div>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </div>

                {data?.audio?.available && data?.audio?.decision !== "NOT_ANALYZED" && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Spectrogram Image */}
                    {data.audio.evidence_images && data.audio.evidence_images.length > 0 && (
                      <div className="p-4 rounded-lg bg-secondary/30 border border-border">
                        <p className="text-sm font-medium mb-3">Spectrogram Analysis</p>
                        <div className="relative aspect-[5/2] w-full rounded overflow-hidden border border-border/50">
                          <img 
                            src={`${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'}${data.audio.evidence_images[0]}`} 
                            alt="Audio Spectrogram"
                            className="object-cover w-full h-full"
                          />
                        </div>
                      </div>
                    )}
                    
                    {/* Suspicious Segments */}
                    {data.audio.suspicious_segments && data.audio.suspicious_segments.length > 0 && (
                      <div className="p-4 rounded-lg bg-secondary/30 border border-border">
                        <p className="text-sm font-medium mb-3">Top Suspicious Segments</p>
                        <div className="space-y-2">
                          {data.audio.suspicious_segments.map((seg: any, idx: number) => (
                            <div key={idx} className="flex justify-between items-center p-2 rounded bg-background/50 border border-border/50">
                              <span className="text-sm font-mono">{(seg.start_sec || 0).toFixed(1)}s - {(seg.end_sec || 0).toFixed(1)}s</span>
                              <span className={`text-sm font-semibold ${seg.score > 0.6 ? 'text-red-500' : 'text-green-500'}`}>
                                {((seg.score || 0) * 100).toFixed(1)}%
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Detailed Metrics */}
          <Card className="bg-card border-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg flex items-center gap-2">
                <BarChart className="w-5 h-5 text-primary" />
                Temporal Metrics
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4 space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 rounded-lg bg-secondary/50 border border-border">
                  <p className="text-sm text-muted-foreground mb-1">Frames Processed</p>
                  <p className="text-2xl font-bold">{metrics.frames_processed || 0}</p>
                </div>
                <div className="p-4 rounded-lg bg-secondary/50 border border-border">
                  <p className="text-sm text-muted-foreground mb-1">Fake/Real Ratio</p>
                  <p className="text-2xl font-bold">
                    {Math.round((metrics.fake_frame_ratio || 0) * 100)}% / {Math.round((metrics.real_frame_ratio || 0) * 100)}%
                  </p>
                </div>
                <div className="p-4 rounded-lg bg-secondary/50 border border-border">
                  <p className="text-sm text-muted-foreground mb-1 flex items-center gap-1">
                     Temporal Diff
                  </p>
                  <p className="text-2xl font-bold">{(metrics.mean_diff || 0).toFixed(3)}</p>
                </div>
                <div className="p-4 rounded-lg bg-secondary/50 border border-border">
                  <p className="text-sm text-muted-foreground mb-1">Variance</p>
                  <p className="text-2xl font-bold">{(metrics.variance || 0).toFixed(3)}</p>
                </div>
              </div>
              
              <div className="mt-4 p-4 rounded-lg border border-primary/20 bg-primary/5 flex items-start gap-3">
                <Info className="w-5 h-5 text-primary mt-0.5" />
                <div>
                  <h4 className="font-medium text-sm">Smoothing Applied</h4>
                  <p className="text-xs text-muted-foreground mt-1">
                    A {data?.smoothing?.replace(/_/g, " ") || "temporal filter"} was applied to stabilize spatial predictions and suppress transient frame drops.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="flex justify-end">
            <Button size="lg" onClick={onContinue} className="gap-2 bg-primary hover:bg-primary/90">
              Continue to Action
              <ArrowRight className="w-5 h-5" />
            </Button>
          </div>
          
        </div>
      </main>
    </div>
  )
}

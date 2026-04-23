"use client"

import { AlertTriangle, Shield, ArrowRight, Clock, Image, Volume2, FileText, Play, Pause, CheckCircle, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useState } from "react"
import type { SourceInfo } from "./upload-screen"

interface AnalysisResultProps {
  onContinue: () => void
  onBack: () => void
  sourceInfo?: SourceInfo
}

export function AnalysisResult({ onContinue, onBack, sourceInfo }: AnalysisResultProps) {
  const [isPlaying, setIsPlaying] = useState(false)

  const verdictData = {
    verdict: "Likely Deepfake",
    confidence: 87,
    status: "fake" as "fake" | "real" | "uncertain",
    timestamp: "0:12 - 0:18",
  }

  const detectedIssues = [
    {
      icon: Image,
      title: "Face inconsistency detected",
      description: "Facial features show unnatural movements and blending artifacts",
      severity: "high",
    },
    {
      icon: Volume2,
      title: "Audio-video mismatch",
      description: "Lip movements do not synchronize with speech patterns",
      severity: "high",
    },
    {
      icon: FileText,
      title: "Metadata anomaly",
      description: "File metadata indicates multiple editing sessions",
      severity: "medium",
    },
  ]

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

  // Source verification badge component
  const SourceBadge = () => {
    if (!sourceInfo) {
      return null
    }

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

    // Uploaded file - not verified
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

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
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
          <span className="text-muted-foreground">Analysis Results</span>
        </div>
      </header>

      <main className="flex-1 px-6 py-8">
        <div className="max-w-5xl mx-auto space-y-8">
          {/* Verdict Card */}
          <Card className={`bg-card border-2 ${verdictData.status === "fake" ? "border-verdict-fake/50" : "border-verdict-real/50"}`}>
            <CardContent className="p-8">
              <div className="flex flex-col md:flex-row items-center gap-8">
                {/* Warning Icon */}
                <div className={`p-6 rounded-2xl ${getVerdictBg(verdictData.status)}/10`}>
                  <AlertTriangle className={`w-16 h-16 ${getVerdictColor(verdictData.status)}`} />
                </div>

                {/* Verdict Info */}
                <div className="flex-1 text-center md:text-left space-y-3">
                  <h1 className={`text-3xl md:text-4xl font-bold ${getVerdictColor(verdictData.status)}`}>
                    {verdictData.verdict}
                  </h1>
                  <p className="text-xl text-muted-foreground">
                    {verdictData.confidence}% Confidence
                  </p>
                  
                  <div className="flex flex-col gap-2 items-center md:items-start pt-1">
                    {/* Source Badge - positioned near verdict */}
                    <SourceBadge />
                    
                    {/* Public Impact Indicator */}
                    {verdictData.status === "real" ? (
                      <div className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-verdict-real/10 border border-verdict-real/20 rounded-full text-sm shadow-sm backdrop-blur-sm">
                        <CheckCircle className="w-4 h-4 text-verdict-real" />
                        <span className="text-verdict-real font-medium">Low Risk Content</span>
                      </div>
                    ) : (
                      <div className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-verdict-fake/10 border border-verdict-fake/20 rounded-full text-sm shadow-sm backdrop-blur-sm">
                        <AlertTriangle className="w-4 h-4 text-verdict-fake animate-pulse" />
                        <span className="text-verdict-fake font-medium">Potential Public Impact: High</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Confidence Meter */}
                <div className="w-32 h-32 relative">
                  <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                    <circle
                      cx="50"
                      cy="50"
                      r="40"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="8"
                      className="text-secondary"
                    />
                    <circle
                      cx="50"
                      cy="50"
                      r="40"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="8"
                      strokeDasharray={`${verdictData.confidence * 2.51} 251`}
                      strokeLinecap="round"
                      className={getVerdictColor(verdictData.status)}
                    />
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

          {/* Media Preview with Detection Overlay */}
          <div className="grid md:grid-cols-2 gap-6">
            <Card className="bg-card border-border overflow-hidden">
              <CardHeader className="pb-2">
                <CardTitle className="text-lg">Media Preview</CardTitle>
              </CardHeader>
              <CardContent className="p-4">
                <div className="relative aspect-video bg-secondary rounded-lg overflow-hidden">
                  {/* Placeholder video area */}
                  <div className="absolute inset-0 bg-gradient-to-br from-secondary to-muted flex items-center justify-center">
                    <div className="text-center space-y-3">
                      <div className="w-16 h-16 rounded-full bg-background/50 flex items-center justify-center mx-auto">
                        <button 
                          onClick={() => setIsPlaying(!isPlaying)}
                          className="hover:scale-110 transition-transform"
                        >
                          {isPlaying ? (
                            <Pause className="w-8 h-8 text-foreground" />
                          ) : (
                            <Play className="w-8 h-8 text-foreground ml-1" />
                          )}
                        </button>
                      </div>
                      <p className="text-sm text-muted-foreground">sample_video.mp4</p>
                    </div>
                  </div>
                  
                  {/* Detection Overlay Box */}
                  <div className="absolute top-1/4 left-1/4 w-1/2 h-1/2 border-2 border-verdict-fake rounded-lg animate-pulse">
                    <div className="absolute -top-6 left-0 bg-verdict-fake text-verdict-fake-foreground text-xs px-2 py-1 rounded">
                      Face Region
                    </div>
                    {/* Scanning line effect */}
                    <div className="absolute inset-0 overflow-hidden rounded-lg">
                      <div className="w-full h-0.5 bg-verdict-fake/50 animate-scan-line" />
                    </div>
                  </div>
                </div>

                {/* Timeline */}
                <div className="mt-4 space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Issue detected at:</span>
                    <span className="flex items-center gap-2 text-verdict-fake">
                      <Clock className="w-4 h-4" />
                      {verdictData.timestamp}
                    </span>
                  </div>
                  <div className="h-2 bg-secondary rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-gradient-to-r from-verdict-real via-verdict-fake to-verdict-real"
                      style={{
                        background: `linear-gradient(to right, 
                          var(--verdict-real) 0%, 
                          var(--verdict-real) 20%, 
                          var(--verdict-fake) 20%, 
                          var(--verdict-fake) 30%, 
                          var(--verdict-real) 30%, 
                          var(--verdict-real) 100%
                        )`
                      }}
                    />
                  </div>
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>0:00</span>
                    <span>0:45</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Detected Issues */}
            <Card className="bg-card border-border">
              <CardHeader className="pb-2">
                <CardTitle className="text-lg">Why This Was Flagged</CardTitle>
              </CardHeader>
              <CardContent className="p-4 space-y-4">
                {detectedIssues.map((issue, index) => (
                  <div 
                    key={index}
                    className={`p-4 rounded-lg border transition-all hover:border-primary/50 ${
                      issue.severity === "high" 
                        ? "bg-verdict-fake/5 border-verdict-fake/30" 
                        : "bg-verdict-uncertain/5 border-verdict-uncertain/30"
                    }`}
                  >
                    <div className="flex items-start gap-4">
                      <div className={`p-2 rounded-lg ${
                        issue.severity === "high" 
                          ? "bg-verdict-fake/10" 
                          : "bg-verdict-uncertain/10"
                      }`}>
                        <issue.icon className={`w-5 h-5 ${
                          issue.severity === "high" 
                            ? "text-verdict-fake" 
                            : "text-verdict-uncertain"
                        }`} />
                      </div>
                      <div>
                        <h3 className="font-medium">{issue.title}</h3>
                        <p className="text-sm text-muted-foreground mt-1">
                          {issue.description}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}

                <div className="pt-2">
                  <p className="text-xs text-muted-foreground text-center">
                    Analysis powered by multi-modal verification system
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Continue Button */}
          <div className="flex justify-end">
            <Button 
              size="lg" 
              onClick={onContinue}
              className="gap-2 bg-primary hover:bg-primary/90"
            >
              Continue to Action
              <ArrowRight className="w-5 h-5" />
            </Button>
          </div>
        </div>
      </main>
    </div>
  )
}

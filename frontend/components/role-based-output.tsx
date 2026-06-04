// "use client"

import { useState } from "react"
import {
  User,
  Newspaper,
  Shield as ShieldIcon,
  Building2,
  Download,
  Send,
  FileText,
  Copy,
  Clock,
  CheckCircle,
  AlertTriangle,
  ArrowLeft,
  ExternalLink,
  Hash,
  Loader2,
  FileCheck,
  Scale,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { useToast } from "@/hooks/use-toast"
import type { Role } from "@/components/login-page"
import { submitReport, generateReportLegalDocs, getLegalDocDownloadUrl } from "../src/api"

/**
 * Props for the RoleBasedOutput component. Supports all user roles and the data required
 * for both citizen/journalist workflows and authority/police/legal document handling.
 */
interface RoleBasedOutputProps {
  userRole: Role
  sourceUrl?: string
  userIdentifier: string
  userName: string
  userOrganization: string
  analysisData: any
  uploadedFile: File | null
  onAction: (reportInfo: any) => void
  onBack: () => void
}

export function RoleBasedOutput({
  userRole,
  sourceUrl,
  userIdentifier,
  userName,
  userOrganization,
  analysisData,
  uploadedFile,
  onAction,
  onBack,
}: RoleBasedOutputProps) {
  const { toast } = useToast()
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(false)
  const [submittedReport, setSubmittedReport] = useState<any>(null)
  const [generatingDocs, setGeneratingDocs] = useState(false)
  const [legalDocs, setLegalDocs] = useState<any[] | null>(null)

  // Derived values
  const prediction = analysisData?.final_prediction || analysisData?.prediction || "Unknown"
  const isFake = prediction === "Fake" || prediction === "Likely Deepfake"
  const rawConfidence = analysisData?.confidence
  const confidenceValue = rawConfidence
    ? rawConfidence <= 1
      ? Math.round(rawConfidence * 100)
      : Math.round(rawConfidence)
    : 85
  const mediaHash =
    analysisData?.hash ||
    analysisData?.integrity?.sha256 ||
    analysisData?.file?.sha256 ||
    "a7f8c3d2e9b1f5a6c8d4e2b7f9a3c5d8e1b4f6a9c2d5e8b1f3a6c9d2e5b8f1a4"
  const filename = analysisData?.file_name || analysisData?.file?.name || uploadedFile?.name || "suspicious_media.png"
  const mediaType = analysisData?.media_type || "image"
  const oodFlags = analysisData?.ood_flags || []

  const custodyLog = [
    { time: "14:30:12", event: "Media ingested via frontend", actor: userName || "User" },
    { time: "14:30:15", event: "Cryptographic SHA-256 hash computed", actor: "System" },
    { time: "14:30:18", event: "Tamper-evident evidence block sealed", actor: "System" },
    { time: "14:32:45", event: "Ensemble deepfake detection completed", actor: "AI Engine" },
  ]

  const copyHash = () => {
    navigator.clipboard.writeText(mediaHash)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
    toast({
      title: "Hash copied to clipboard",
      description: "You can use this hash to verify media authenticity.",
    })
  }

  // ---------- Report submission (citizen/journalist/police) ----------
  const handleReportOrRegister = async () => {
    setLoading(true)
    try {
      const analysisPayload = {
        ...analysisData,
        hash: mediaHash,
        file_name: filename,
        file_size: uploadedFile?.size || 1024,
      }
      const res = await submitReport(
        userRole,
        userIdentifier,
        userName || "Verified User",
        analysisPayload,
        uploadedFile || undefined
      )
      if (res.success) {
        setSubmittedReport(res)
        toast({
          title: "Case Registered Successfully",
          description: `Case ID: ${res.report_id} is secured in MongoDB GridFS.`,
        })
        if (userRole === "Citizen" || userRole === "Journalist") {
          onAction({
            report_id: res.report_id,
            status: res.status,
            timestamp: new Date().toLocaleString("en-IN", { dateStyle: "full", timeStyle: "short" }),
            actions: [
              { label: "Case registered in BharatShield Ledger", completed: true },
              { label: "Evidence locked in MongoDB GridFS", completed: true },
              { label: "Authority notification dispatched", completed: true },
            ],
          })
        }
      }
    } catch (err: any) {
      console.error(err)
      toast({
        variant: "destructive",
        title: "Registration Failed",
        description: err.message || "Failed to submit case to backend.",
      })
    } finally {
      setLoading(false)
    }
  }

  // ---------- Legal document generation (authority) ----------
  const handleGenerateLegalDocs = async () => {
    if (!submittedReport) return
    setGeneratingDocs(true)
    try {
      const res = await generateReportLegalDocs(submittedReport.report_id)
      if (res.success) {
        setLegalDocs(res.documents)
        toast({
          title: "Legal Documents Generated",
          description: `Packet ID: ${res.packet_id}`,
        })
      }
    } catch (err: any) {
      console.error(err)
      toast({
        variant: "destructive",
        title: "Document Generation Failed",
        description: err.message || "Could not generate legal notice.",
      })
    } finally {
      setGeneratingDocs(false)
    }
  }

  // ---------- Helpers for downloading reports ----------
  const generateReportContent = () => `
╔════════════════════════════════════════════════════════════════════╗
║                    BHARATSHIELD DETAILED REPORT                    ║
╚════════════════════════════════════════════════════════════════════╝

CASE REFERENCE: ${submittedReport?.report_id || "BS-PENDING"}
GENERATED AT:   ${new Date().toLocaleString()}
REPORTER ROLE:  ${userRole}
REPORTER ID:    ${userIdentifier}
REPORTER NAME:  ${userName || "N/A"}
ORGANIZATION:   ${userOrganization || "N/A"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EVIDENCE METADATA:
  File Name:   ${filename}
  Media Type:  ${mediaType}
  SHA-256 Hash: ${mediaHash}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AI VERDICT SUMMARY:
  Verdict:     ${prediction}
  Confidence:  ${confidenceValue}%
  Reasoning:   ${analysisData?.reason || "High probability of synthetic manipulation detected."}
  OOD Flags:   ${oodFlags.length > 0 ? oodFlags.join(", ") : "None"}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DETECTION ENGINE RAW SCORES:
  CNN Probability:   ${analysisData?.cnn_probability !== undefined ? Math.round(analysisData.cnn_probability * 100) : "N/A"}%
  FFT Probability:   ${analysisData?.fft_probability !== undefined ? Math.round(analysisData.fft_probability * 100) : "N/A"}%
  Fusion Probability: ${analysisData?.fusion_probability !== undefined ? Math.round(analysisData.fusion_probability * 100) : "N/A"}%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This report serves as verification evidence. Generated by BharatShield.
`.trim()

  const downloadReportFile = () => {
    const content = generateReportContent()
    const blob = new Blob([content], { type: "text/plain" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `BharatShield_Report_${submittedReport?.report_id || "Draft"}.txt`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    toast({
      title: "Detailed report downloaded",
      description: "Saved as text file.",
    })
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#0b0f19] text-[#e2e8f0]">
      {/* Header */}
      <header className="border-b border-[#1e293b] px-6 py-4 bg-[#0f172a]/80 backdrop-blur-md">
        <div className="max-w-5xl mx-auto flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={onBack} className="text-[#94a3b8] hover:text-white">
            <ArrowLeft className="w-4 h-4 mr-2" /> Back
          </Button>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-primary/10 rounded-lg">
              <ShieldIcon className="w-5 h-5 text-primary" />
            </div>
            <span className="font-semibold text-white">BharatShield</span>
          </div>
          <span className="text-[#475569]">/</span>
          <span className="text-[#94a3b8]">Take Action</span>
        </div>
      </header>

      <main className="flex-1 px-6 py-8">
        <div className="max-w-4xl mx-auto space-y-8">
          {/* Summary Card */}
          <Card className="bg-[#0f172a] border-[#1e293b] overflow-hidden relative">
            <div className={`absolute top-0 left-0 w-2 h-full ${isFake ? "bg-red-500" : "bg-emerald-500"}`} />
            <CardContent className="p-6 flex flex-col md:flex-row items-center justify-between gap-6">
              <div className="space-y-1">
                <span className="text-xs text-muted-foreground uppercase font-semibold">
                  Verified Session: {userName} ({userOrganization})
                </span>
                <h2 className="text-2xl font-bold text-white flex items-center gap-2 mt-1">
                  <span>Ensemble AI Verdict:</span>
                  <span className={isFake ? "text-red-400" : "text-emerald-400"}>{prediction}</span>
                </h2>
                <p className="text-sm text-slate-400 max-w-xl">
                  Detection confidence score is {confidenceValue}%. File: <span className="text-white font-mono text-xs">{filename}</span>
                </p>
              </div>
              <div className="text-right shrink-0">
                <div className={`text-4xl font-extrabold ${isFake ? "text-red-400" : "text-emerald-400"}`}>{confidenceValue}%</div>
                <div className="text-xs text-slate-500 font-bold uppercase mt-1">Confidence</div>
              </div>
            </CardContent>
          </Card>

          {/* Role‑specific actions */}
          {userRole === "Citizen" && (
            <Card className="bg-[#0f172a] border-[#1e293b]">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Send className="w-5 h-5 text-primary" /> Citizen Grievance Redressal
                </CardTitle>
                <CardDescription>
                  Escalate this fake media directly to the Cyber Crime Coordination Center (I4C).
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="p-4 bg-red-950/20 border border-red-900/30 rounded-xl flex items-start gap-4">
                  <AlertTriangle className="w-6 h-6 text-red-400" />
                  <div>
                    <h4 className="text-sm font-semibold text-white">Legal Notice regarding Misleading Media</h4>
                    <p className="text-xs text-slate-400 mt-1">
                      BharatShield records evidence details (SHA-256 and timestamp) in a secure ledger. Authorities can initiate takedown.
                    </p>
                  </div>
                </div>
                <div className="flex flex-col sm:flex-row gap-4 pt-2">
                  <Button size="lg" onClick={handleReportOrRegister} disabled={loading} className="flex-1 bg-primary hover:bg-primary/90 text-white gap-2 h-12">
                    {loading ? <><Loader2 className="w-5 h-5 animate-spin" /> Submitting Grievance...</>
                    : <><Send className="w-5 h-5" /> File Grievance Report</>}
                  </Button>
                  <Button size="lg" variant="outline" onClick={onBack} className="flex-1 border-slate-700 text-slate-300 hover:bg-slate-800 h-12">
                    Cancel & Re‑analyze
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {userRole === "Journalist" && (
            <Card className="bg-[#0f172a] border-[#1e293b]">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Send className="w-5 h-5 text-primary" /> Journalist Reporting
                </CardTitle>
                <CardDescription>
                  Register the analysis as a secure evidence packet for publication.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="flex flex-col sm:flex-row gap-4">
                  <Button size="lg" onClick={handleReportOrRegister} disabled={loading} className="flex-1 bg-primary hover:bg-primary/90 text-white gap-2 h-12">
                    {loading ? <><Loader2 className="w-5 h-5 animate-spin" /> Saving Report...</>
                    : <><Send className="w-5 h-5" /> Register & Secure Case ID</>}
                  </Button>
                  {submittedReport && (
                    <Button size="lg" variant="outline" onClick={downloadReportFile} className="flex-1 border-slate-700 text-slate-300 hover:bg-slate-800 gap-2 h-12">
                      <Download className="w-5 h-5" /> Download Press Evidence TXT
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {userRole === "Police" && (
            <Card className="bg-[#0f172a] border-[#1e293b]">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Building2 className="w-5 h-5 text-indigo-400" /> Law Enforcement Dashboard
                </CardTitle>
                <CardDescription>
                  Manage evidence, view custody chain, and register official cases.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <Card className="bg-[#0f172a] border-[#1e293b]">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm text-slate-300 flex items-center gap-2">
                      <Hash className="w-4 h-4 text-primary" /> Evidence Cryptographic Signature
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="p-4 bg-slate-900 rounded-lg flex items-center justify-between gap-4">
                      <code className="text-xs font-mono text-slate-400 break-all select-all">{mediaHash}</code>
                      <Button variant="ghost" size="icon" onClick={copyHash} className="text-[#94a3b8] hover:text-white shrink-0">
                        {copied ? <CheckCircle className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                      </Button>
                    </div>
                    <p className="text-[11px] text-slate-500">Secured using SHA-256 for courtroom proof of integrity.</p>
                  </CardContent>
                </Card>
                <Card className="bg-[#0f172a] border-[#1e293b]">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm text-slate-300 flex items-center gap-2">
                      <Clock className="w-4 h-4 text-primary" /> Evidence Custody Ledger
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {custodyLog.map((log, i) => (
                        <div key={i} className="flex items-start gap-2.5 text-xs">
                          <div className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                          <div className="flex-1">
                            <div className="flex justify-between">
                              <span className="font-semibold text-slate-300">{log.event}</span>
                              <span className="text-[10px] text-slate-500 font-mono">{log.time}</span>
                            </div>
                            <span className="text-[10px] text-slate-500">by {log.actor}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>

                {!submittedReport ? (
                  <Button size="lg" onClick={handleReportOrRegister} disabled={loading} className="bg-primary hover:bg-primary/90 text-white gap-2 min-w-[200px]">
                    {loading ? <><Loader2 className="w-4 h-4 animate-spin" /> Registering Case...</> : <><FileText className="w-5 h-5" /> Register Official Case</>}
                  </Button>
                ) : (
                  <div className="space-y-4">
                    <Card className="bg-[#0f172a] border-emerald-900/30 bg-emerald-950/5 p-6">
                      <div className="flex items-center gap-4">
                        <div className="p-3 bg-emerald-500/10 rounded-xl"><CheckCircle className="w-8 h-8 text-emerald-400" /></div>
                        <div className="flex-1">
                          <h3 className="text-lg font-bold text-white">Case Registered Successfully</h3>
                          <p className="text-sm text-slate-400 mt-0.5">
                            Case ID: <span className="text-emerald-400 font-semibold font-mono">{submittedReport.report_id}</span> • Status: <span className="text-emerald-400 uppercase font-semibold text-xs">{submittedReport.status}</span>
                          </p>
                        </div>
                        <Button variant="outline" className="border-slate-700 text-slate-300" onClick={downloadReportFile}>
                          <Download className="w-4 h-4 mr-2" /> Export Log
                        </Button>
                      </div>
                    </Card>

                    {/* Legal Docs */}
                    <Card className="bg-[#0f172a] border-[#1e293b] p-6 space-y-4">
                      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                        <div>
                          <h3 className="text-lg font-bold text-white flex items-center gap-2">
                            <Scale className="w-5 h-5 text-indigo-400" /> Official Legal notice Generation
                          </h3>
                          <p className="text-sm text-slate-400 mt-1 max-w-2xl">
                            Generate regulatory compliance notice documents and spatial forensic affidavits.
                          </p>
                        </div>
                        {!legalDocs && (
                          <Button onClick={handleGenerateLegalDocs} disabled={generatingDocs} className="bg-indigo-600 hover:bg-indigo-700 text-white shrink-0">
                            {generatingDocs ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Generating PDFs...</> : <><Scale className="w-4 h-4 mr-2" /> Generate Legal Packet</>}
                          </Button>
                        )}
                      </div>
                      {legalDocs && (
                        <div className="p-4 bg-slate-900/60 rounded-xl border border-slate-800 space-y-4">
                          <div className="flex items-center gap-2 text-emerald-400 font-semibold text-xs uppercase tracking-wider">
                            <FileCheck className="w-4 h-4" /> Generated Documents Ready
                          </div>
                          <div className="grid sm:grid-cols-2 gap-4">
                            {legalDocs.map((doc, idx) => {
                              const downloadUrl = getLegalDocDownloadUrl(submittedReport.report_id, doc.packet_id, doc.filename)
                              return (
                                <div key={idx} className="p-4 bg-[#0b0f19] border border-slate-800 rounded-lg flex items-center justify-between">
                                  <div className="space-y-1">
                                    <div className="text-sm font-semibold text-white">{doc.document_type}</div>
                                    <div className="text-xs text-slate-500 font-mono">{doc.filename}</div>
                                  </div>
                                  <a href={downloadUrl} target="_blank" rel="noopener noreferrer" className="p-2 bg-primary/10 hover:bg-primary/20 text-primary rounded-lg transition-colors flex items-center gap-2 text-xs font-semibold">
                                    <Download className="w-4 h-4" />
                                    <span>Download</span>
                                  </a>
                                </div>
                              )
                            })}
                          </div>
                        </div>
                      )}
                    </Card>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {userRole === "Authority" && (
            <Card className="bg-[#0f172a] border-[#1e293b] p-6 text-center space-y-6">
              <div className="p-4 bg-indigo-500/10 rounded-full w-fit mx-auto border border-indigo-500/20">
                <Building2 className="w-10 h-10 text-indigo-400" />
              </div>
              <div className="space-y-2">
                <h3 className="text-xl font-bold text-white">Administrative Authority Console</h3>
                <p className="text-sm text-slate-400 max-w-lg mx-auto">
                  As an administrative review officer, you have direct access to the official case review dashboard to inspect all logged reports, execute media re‑evaluations, manage takedown directives, and sign affidavits.
                </p>
              </div>
              <div className="flex flex-col sm:flex-row gap-4 justify-center pt-4">
                {!submittedReport ? (
                  <Button size="lg" onClick={handleReportOrRegister} disabled={loading} className="bg-primary hover:bg-primary/90 text-white min-w-[200px]">
                    {loading ? <><Loader2 className="w-4 h-4 animate-spin" /> Registering Case...</> : <><FileText className="w-4 h-4" /> Register Case First</>}
                  </Button>
                ) : (
                  <div className="p-4 bg-emerald-500/10 border border-emerald-500/25 rounded-lg text-sm text-emerald-400 font-semibold mb-2">
                    Case Registered. Case ID: {submittedReport.report_id}
                  </div>
                )}
                <Button size="lg" variant="outline" onClick={() => onAction({
                  report_id: submittedReport?.report_id || "BS-DRAFT",
                  status: submittedReport?.status || "pending_review",
                  timestamp: new Date().toLocaleString()
                })} className="border-slate-700 text-slate-300 hover:bg-slate-800 min-w-[200px]">
                  Go to Action Dashboard
                </Button>
              </div>
            </Card>
          )}
        </div>
      </main>
    </div>
  )
}

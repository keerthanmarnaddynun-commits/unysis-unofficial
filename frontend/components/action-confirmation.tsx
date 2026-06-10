"use client"

import { useState } from "react"
import { 
  CheckCircle, 
  Shield, 
  Copy, 
  Home, 
  FileText, 
  ExternalLink,
  RefreshCw,
  X,
  Loader2,
  Clock,
  ArrowLeft,
  Download
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { useToast } from "@/hooks/use-toast"
import { getReport, type Report, getLegalDocDownloadUrl, generateReportLegalDocs } from "../src/api"

interface ActionConfirmationProps {
  userRole: string
  reportInfo?: {
    report_id: string
    status: string
    actions?: Array<{ label: string; completed: boolean }>
    timestamp?: string
  } | null
  onStartOver: () => void
}

export function ActionConfirmation({ userRole, reportInfo, onStartOver }: ActionConfirmationProps) {
  const { toast } = useToast()
  const [copied, setCopied] = useState(false)
  
  // Tracking states
  const [showTracking, setShowTracking] = useState(false)
  const [loadingTracking, setLoadingTracking] = useState(false)
  const [trackingReport, setTrackingReport] = useState<Report | null>(null)

  const isSensitiveDoc = (docType: string) => {
    const sensitiveTypes = ["complete_legal_evidence_packet", "bsa_section_63_part_b", "cyber_crime_fir_bns"]
    return sensitiveTypes.includes(docType.toLowerCase())
  }

  const visibleDocs = trackingReport?.legal_documents?.filter(doc => {
    const isAuth = userRole === "Police" || userRole === "Authority"
    if (isAuth) return true
    return !isSensitiveDoc(doc.document_type)
  }) || []

  const trackingId = reportInfo?.report_id || "BS-10234"
  const actions = reportInfo?.actions || [
    { label: "Case registered in BharatShield Ledger", completed: true },
    { label: "Evidence locked in MongoDB GridFS", completed: true },
    { label: "Authority notification dispatched", completed: true },
  ]
  const timestamp = reportInfo?.timestamp || new Date().toLocaleString("en-IN", {
    dateStyle: "full",
    timeStyle: "short",
  })

  const copyTrackingId = () => {
    navigator.clipboard.writeText(trackingId)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
    toast({
      title: "Tracking ID copied",
      description: "You can use this ID to check case updates later.",
    })
  }

  // Fetch live status from database
  const handleTrackStatus = async () => {
    setLoadingTracking(true)
    setShowTracking(true)
    try {
      const res = await getReport(trackingId)
      setTrackingReport(res.report)
      toast({
        title: "Status Refreshed",
        description: `Current status: ${res.report.status.replace("_", " ")}`,
      })
    } catch (err: any) {
      console.error(err)
      toast({
        variant: "destructive",
        title: "Tracking Failed",
        description: "Failed to connect to database ledger. Showing cached offline data.",
      })
    } finally {
      setLoadingTracking(false)
    }
  }

  // Compile and download legal PDF notices dynamically
  const handleDownloadReceipt = async () => {
    setLoadingTracking(true)
    try {
      // 1. Fetch latest report
      const res = await getReport(trackingId)
      let currentReport = res.report
      
      // 2. If no legal documents are generated yet, generate them now!
      if (!currentReport.legal_documents || currentReport.legal_documents.length === 0) {
        toast({
          title: "Compiling Legal Notice",
          description: "Generating official compliance documents from server...",
        })
        const genRes = await generateReportLegalDocs(trackingId)
        if (genRes.success) {
          // Re-fetch report
          const fresh = await getReport(trackingId)
          currentReport = fresh.report
        }
      }
      
      // 3. Determine visible documents based on role
      const docs = currentReport.legal_documents || []
      const visible = docs.filter(doc => {
        const isAuth = userRole === "Police" || userRole === "Authority"
        if (isAuth) return true
        return !isSensitiveDoc(doc.document_type)
      })
      
      if (visible.length === 0) {
        throw new Error("No visible documents available for your role.")
      }
      
      // 4. Download/open each visible document!
      toast({
        title: "Downloading Documents",
        description: `Downloading ${visible.length} generated legal document(s).`,
      })
      
      visible.forEach(doc => {
        const downloadUrl = getLegalDocDownloadUrl(trackingId, doc.packet_id, doc.filename)
        window.open(downloadUrl, "_blank")
      })
    } catch (err: any) {
      console.error(err)
      toast({
        variant: "destructive",
        title: "Download Failed",
        description: err.message || "Failed to compile or retrieve legal documents.",
      })
    } finally {
      setLoadingTracking(false)
    }
  }

  const getStatusBadgeColor = (status: string) => {
    switch (status) {
      case "pending_review":
        return "bg-amber-500/10 border-amber-500/20 text-amber-400"
      case "under_investigation":
        return "bg-blue-500/10 border-blue-500/20 text-blue-400"
      case "resolved":
        return "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
      case "dismissed":
        return "bg-slate-500/10 border-slate-500/20 text-slate-400"
      default:
        return "bg-slate-500/10 border-slate-500/20 text-slate-400"
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#0b0f19] text-[#e2e8f0]">
      {/* Header */}
      <header className="border-b border-[#1e293b] px-6 py-4 bg-[#0f172a]/80 backdrop-blur-md">
        <div className="max-w-4xl mx-auto flex items-center gap-3">
          <div className="p-2 bg-primary/10 rounded-lg">
            <Shield className="w-5 h-5 text-primary" />
          </div>
          <span className="font-semibold text-white">BharatShield</span>
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-lg">
          <Card className="bg-[#0f172a] border-[#1e293b] overflow-hidden shadow-2xl">
            
            {/* Success Banner */}
            <div className="bg-emerald-500/10 p-8 text-center border-b border-emerald-500/20 relative">
              <div className="w-20 h-20 rounded-full bg-emerald-500/20 flex items-center justify-center mx-auto mb-4 border border-emerald-500/30 shadow-[0_0_15px_rgba(16,185,129,0.15)] animate-pulse">
                <CheckCircle className="w-10 h-10 text-emerald-400" />
              </div>
              <h1 className="text-2xl font-bold text-white">
                Action Completed Successfully
              </h1>
              <p className="text-slate-400 mt-2 text-sm">
                Your report has been submitted and locked in the secure database
              </p>
            </div>

            <CardContent className="p-6 space-y-6">
              
              {/* Conditional Tracking Timeline View */}
              {showTracking ? (
                <div className="space-y-4 animate-in fade-in duration-300">
                  <div className="flex items-center justify-between border-b border-[#1e293b] pb-2">
                    <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Live Case Tracker</span>
                    <div className="flex gap-2">
                      <Button variant="ghost" size="icon" onClick={handleTrackStatus} disabled={loadingTracking} className="h-7 w-7 text-slate-400 hover:text-white">
                        <RefreshCw className={`w-3.5 h-3.5 ${loadingTracking ? "animate-spin" : ""}`} />
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => setShowTracking(false)} className="h-7 w-7 text-slate-400 hover:text-destructive">
                        <X className="w-3.5 h-3.5" />
                      </Button>
                    </div>
                  </div>

                  {loadingTracking && !trackingReport ? (
                    <div className="py-12 text-center text-slate-500 space-y-2">
                      <Loader2 className="w-6 h-6 animate-spin mx-auto text-primary" />
                      <p className="text-xs">Connecting to secure ledger...</p>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {/* Live status badge */}
                      <div className="flex justify-between items-center bg-[#0b0f19] p-3 rounded-lg border border-slate-800 text-xs">
                        <span className="text-slate-400 font-semibold uppercase">Current Status:</span>
                        <span className={`px-2 py-0.5 rounded font-bold uppercase ${getStatusBadgeColor(trackingReport?.status || "pending_review")}`}>
                          {(trackingReport?.status || "pending_review").replace("_", " ")}
                        </span>
                      </div>

                      {/* Log timeline */}
                      <div className="space-y-3 max-h-[180px] overflow-y-auto pr-1">
                        {(trackingReport?.custody_log || []).map((log, index) => (
                          <div key={index} className="flex gap-2.5 text-xs">
                            <div className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                            <div className="flex-1">
                              <div className="flex justify-between font-semibold text-slate-300">
                                <span>{log.event}</span>
                                <span className="text-[10px] text-slate-500 font-mono">
                                  {log.time ? new Date(log.time).toLocaleTimeString() : ""}
                                </span>
                              </div>
                              <p className="text-[10px] text-slate-500">by {log.actor}</p>
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* Legal notice package if available */}
                      {visibleDocs.length > 0 && (
                        <div className="p-3 bg-indigo-950/10 border border-indigo-900/30 rounded-lg space-y-2">
                          <div className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider flex items-center gap-1">
                            <FileText className="w-3.5 h-3.5" />
                            <span>Generated Legal Notices Ready</span>
                          </div>
                          <div className="space-y-1.5">
                            {visibleDocs.map((doc, idx) => {
                              const downloadUrl = getLegalDocDownloadUrl(trackingId, doc.packet_id, doc.filename)
                              return (
                                <a 
                                  key={idx}
                                  href={downloadUrl}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="flex items-center justify-between text-xs text-primary hover:underline bg-[#0b0f19] p-2 rounded border border-slate-800"
                                >
                                  <span className="truncate max-w-[280px]">{doc.document_type}</span>
                                  <Download className="w-3.5 h-3.5 shrink-0" />
                                </a>
                              )
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ) : (
                /* Completed Actions Checklist */
                <div className="space-y-3">
                  {actions.map((action, index) => (
                    <div 
                      key={index}
                      className="flex items-center gap-3 p-3 bg-emerald-500/5 rounded-lg border border-emerald-500/10 shadow-[0_2px_8px_rgba(16,185,129,0.05)]"
                    >
                      <CheckCircle className="w-5 h-5 text-emerald-400 shrink-0" />
                      <span className="text-sm text-slate-200">{action.label}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Tracking ID card */}
              <div className="p-4 bg-[#0b0f19] border border-slate-850 rounded-xl">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-[10px] text-slate-500 uppercase tracking-wider font-bold">
                      BharatShield Case Reference
                    </div>
                    <div className="text-xl font-mono font-bold mt-1 text-white select-all">
                      {trackingId}
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={copyTrackingId}
                    className="shrink-0 border-slate-700 hover:bg-slate-800 text-slate-300"
                  >
                    {copied ? (
                      <CheckCircle className="w-4 h-4 text-emerald-400" />
                    ) : (
                      <Copy className="w-4 h-4" />
                    )}
                  </Button>
                </div>
                <p className="text-[11px] text-slate-500 mt-3 leading-relaxed">
                  Record this Case ID to track investigation progress, issue takedowns, or request compliance audits.
                </p>
              </div>

              {/* Timestamp */}
              <div className="text-center text-xs text-slate-500 flex items-center justify-center gap-1.5">
                <Clock className="w-3.5 h-3.5" />
                <span>Submitted on {timestamp}</span>
              </div>

              {/* Action Buttons */}
              <div className="flex flex-col gap-3 pt-2">
                <Button 
                  size="lg" 
                  onClick={onStartOver}
                  className="w-full bg-primary hover:bg-primary/90 text-white gap-2 h-11"
                >
                  <Home className="w-5 h-5" />
                  Start New Analysis
                </Button>
                <div className="grid grid-cols-2 gap-3">
                  <Button 
                    variant="outline" 
                    onClick={handleDownloadReceipt}
                    disabled={loadingTracking}
                    className="gap-2 border-slate-700 hover:bg-slate-800 text-slate-300 h-10 text-xs"
                  >
                    {loadingTracking ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <FileText className="w-4 h-4 text-primary" />
                    )}
                    Download Documents
                  </Button>
                  <Button 
                    variant="outline" 
                    onClick={handleTrackStatus}
                    className="gap-2 border-slate-700 hover:bg-slate-800 text-slate-300 h-10 text-xs"
                  >
                    <ExternalLink className="w-4 h-4 text-sky-400" />
                    Track Status
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Support Link */}
          <p className="text-center text-xs text-slate-500 mt-6">
            Need help? Contact{" "}
            <a href="#" className="text-primary hover:underline font-semibold">
              support@bharatshield.gov.in
            </a>
          </p>
        </div>
      </main>
    </div>
  )
}

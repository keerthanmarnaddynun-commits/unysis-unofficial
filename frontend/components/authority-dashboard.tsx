"use client"

import { useState, useEffect } from "react"
import { 
  ArrowLeft,
  Shield,
  Search,
  RefreshCw,
  FileText,
  CheckCircle,
  AlertTriangle,
  Download,
  User,
  Clock,
  Activity,
  FileCheck,
  ExternalLink,
  Layers,
  Settings,
  Scale,
  Calendar,
  AlertCircle,
  ListFilter
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useToast } from "@/hooks/use-toast"
import { 
  listReports, 
  getReport, 
  updateReportStatus, 
  reanalyzeReport, 
  generateReportLegalDocs, 
  getLegalDocDownloadUrl,
  type Report 
} from "../src/api"

interface AuthorityDashboardProps {
  userRole: string
  userIdentifier: string
  userName: string
  userOrganization: string
  onBack: () => void
}

export function AuthorityDashboard({ 
  userRole, 
  userIdentifier, 
  userName, 
  userOrganization, 
  onBack 
}: AuthorityDashboardProps) {
  const { toast } = useToast()
  
  // State for reports
  const [reports, setReports] = useState<Report[]>([])
  const [selectedReport, setSelectedReport] = useState<Report | null>(null)
  
  // Loading & Filter states
  const [loadingList, setLoadingList] = useState(true)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [reanalyzing, setReanalyzing] = useState(false)
  const [generatingDocs, setGeneratingDocs] = useState(false)
  const [updatingStatus, setUpdatingStatus] = useState(false)
  
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [searchQuery, setSearchQuery] = useState("")
  
  // Status editing states
  const [adminNotes, setAdminNotes] = useState("")
  const [newStatus, setNewStatus] = useState("")

  // Fetch reports on mount/filter
  const fetchReports = async () => {
    setLoadingList(true)
    try {
      const res = await listReports({
        role: userRole,
        identifier: userIdentifier,
        status: statusFilter !== "all" ? statusFilter : undefined
      })
      setReports(res.reports)
      
      // Update selected report if it exists in the list to get fresh data
      if (selectedReport) {
        const updated = res.reports.find(r => r.report_id === selectedReport.report_id)
        if (updated) setSelectedReport(updated)
      }
    } catch (err: any) {
      console.error(err)
      toast({
        variant: "destructive",
        title: "Failed to load reports",
        description: err.message || "Database connection error.",
      })
    } finally {
      setLoadingList(false)
    }
  }

  useEffect(() => {
    fetchReports()
  }, [statusFilter])

  // Select a report and fetch full details
  const handleSelectReport = async (reportId: string) => {
    setLoadingDetail(true)
    try {
      const res = await getReport(reportId)
      setSelectedReport(res.report)
      setNewStatus(res.report.status)
      setAdminNotes(res.report.admin_notes || "")
    } catch (err: any) {
      console.error(err)
      toast({
        variant: "destructive",
        title: "Failed to load report details",
        description: err.message || "Report could not be retrieved.",
      })
    } finally {
      setLoadingDetail(false)
    }
  }

  // Handle re-evaluation (reanalyze)
  const handleReevaluate = async () => {
    if (!selectedReport) return
    setReanalyzing(true)
    try {
      const res = await reanalyzeReport(selectedReport.report_id)
      if (res.success) {
        toast({
          title: "Re-evaluation Complete",
          description: `AI Re-analysis verdict: ${res.new_analysis.prediction} (Confidence: ${Math.round(res.new_analysis.confidence * 100)}%)`,
        })
        // Refresh detail view
        await handleSelectReport(selectedReport.report_id)
        // Refresh list
        fetchReports()
      }
    } catch (err: any) {
      console.error(err)
      toast({
        variant: "destructive",
        title: "Re-evaluation Failed",
        description: err.message || "Ensure detection models are fully loaded.",
      })
    } finally {
      setReanalyzing(false)
    }
  }

  // Handle legal documents generation
  const handleGenerateDocs = async () => {
    if (!selectedReport) return
    setGeneratingDocs(true)
    try {
      const res = await generateReportLegalDocs(selectedReport.report_id)
      if (res.success) {
        toast({
          title: "Legal Notice Packet Generated",
          description: `Notice, metadata, and affidavit documents are compiled.`,
        })
        // Refresh details
        await handleSelectReport(selectedReport.report_id)
        // Refresh list
        fetchReports()
      }
    } catch (err: any) {
      console.error(err)
      toast({
        variant: "destructive",
        title: "Generation Failed",
        description: err.message || "Failed to generate PDFs on server.",
      })
    } finally {
      setGeneratingDocs(false)
    }
  }

  // Handle status update
  const handleUpdateStatus = async () => {
    if (!selectedReport) return
    setUpdatingStatus(true)
    try {
      const res = await updateReportStatus(selectedReport.report_id, newStatus, adminNotes)
      if (res.success) {
        toast({
          title: "Status Updated",
          description: `Report status set to: ${newStatus}`,
        })
        // Refresh details
        await handleSelectReport(selectedReport.report_id)
        // Refresh list
        fetchReports()
      }
    } catch (err: any) {
      console.error(err)
      toast({
        variant: "destructive",
        title: "Status Update Failed",
        description: err.message || "Failed to save status in database.",
      })
    } finally {
      setUpdatingStatus(false)
    }
  }

  // Helper formatting values
  const getStatusBadge = (status: string) => {
    switch (status) {
      case "pending_review":
        return <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-500/10 border border-amber-500/20 text-amber-400">Pending Review</span>
      case "under_investigation":
        return <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-blue-500/10 border border-blue-500/20 text-blue-400">In Investigation</span>
      case "resolved":
        return <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">Resolved</span>
      case "dismissed":
        return <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-slate-500/10 border border-slate-500/20 text-slate-400">Dismissed</span>
      default:
        return <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-slate-500/10 border border-slate-500/20 text-slate-400">{status}</span>
    }
  }

  const formatConfidence = (val?: number) => {
    if (val === undefined) return 0;
    if (val <= 1) return Math.round(val * 100);
    return Math.round(val);
  }

  // Filter list by search query
  const filteredReports = reports.filter(r => 
    r.report_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (r.media_filename || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
    (r.reporter.name || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
    (r.reporter.identifier || "").toLowerCase().includes(searchQuery.toLowerCase())
  )

  return (
    <div className="min-h-screen flex flex-col bg-[#0b0f19] text-[#e2e8f0]">
      {/* Header */}
      <header className="border-b border-[#1e293b] px-6 py-4 bg-[#0f172a]/80 sticky top-0 z-50 backdrop-blur-md">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="sm" onClick={onBack} className="text-[#94a3b8] hover:text-white hover:bg-slate-800">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Home
            </Button>
            <div className="flex items-center gap-3">
              <div className="p-2 bg-primary/10 rounded-lg">
                <Shield className="w-5 h-5 text-primary" />
              </div>
              <span className="font-semibold text-white">BharatShield</span>
            </div>
            <span className="text-[#475569]">/</span>
            <span className="text-[#94a3b8]">Authority Case Ledger</span>
          </div>
          
          <div className="text-xs text-[#94a3b8] font-medium bg-slate-900 px-3 py-1.5 rounded-lg border border-slate-800">
            Officer: <span className="text-white font-semibold">{userName} ({userOrganization})</span>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* Left Column: Case Directory */}
        <div className="lg:col-span-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <Layers className="w-5 h-5 text-primary" />
              <span>Case Directory</span>
            </h2>
            <Button variant="ghost" size="icon" onClick={fetchReports} className="text-slate-400 hover:text-white hover:bg-slate-800">
              <RefreshCw className={`w-4 h-4 ${loadingList ? 'animate-spin' : ''}`} />
            </Button>
          </div>

          {/* Search and Filter */}
          <div className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <Input
                placeholder="Search case ID, media name..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 bg-[#0f172a] border-[#1e293b] text-white"
              />
            </div>
            <div className="w-36">
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="bg-[#0f172a] border-[#1e293b]">
                  <SelectValue placeholder="All Status" />
                </SelectTrigger>
                <SelectContent className="bg-[#0f172a] border-[#1e293b] text-white">
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="pending_review">Pending</SelectItem>
                  <SelectItem value="under_investigation">In Progress</SelectItem>
                  <SelectItem value="resolved">Resolved</SelectItem>
                  <SelectItem value="dismissed">Dismissed</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Directory List */}
          <Card className="bg-[#0f172a] border-[#1e293b] overflow-hidden min-h-[400px]">
            <CardContent className="p-0 max-h-[600px] overflow-y-auto">
              {loadingList ? (
                <div className="p-12 text-center text-slate-500 space-y-2">
                  <RefreshCw className="w-8 h-8 animate-spin mx-auto text-primary" />
                  <p className="text-xs">Connecting to secure ledger...</p>
                </div>
              ) : filteredReports.length === 0 ? (
                <div className="p-12 text-center text-slate-500 space-y-2">
                  <AlertCircle className="w-8 h-8 mx-auto opacity-40" />
                  <p className="text-sm">No cases match the query.</p>
                </div>
              ) : (
                <div className="divide-y divide-[#1e293b]">
                  {filteredReports.map((report) => {
                    const isSelected = selectedReport?.report_id === report.report_id
                    const predictionLabel = report.analysis?.final_prediction || report.analysis?.prediction || "Unknown"
                    const confidenceVal = formatConfidence(report.analysis?.confidence)
                    
                    return (
                      <div
                        key={report.report_id}
                        onClick={() => handleSelectReport(report.report_id)}
                        className={`p-4 cursor-pointer transition-all flex items-center justify-between gap-4 ${
                          isSelected ? "bg-slate-900 border-l-2 border-primary" : "hover:bg-slate-900/50"
                        }`}
                      >
                        <div className="space-y-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-mono font-bold text-white text-sm">{report.report_id}</span>
                            {getStatusBadge(report.status)}
                          </div>
                          <div className="text-xs text-slate-400 truncate max-w-[240px]">
                            File: {report.media_filename}
                          </div>
                          <div className="text-[10px] text-slate-500 flex items-center gap-1.5">
                            <User className="w-3 h-3" />
                            <span>{report.reporter.role} • {new Date(report.created_at).toLocaleDateString()}</span>
                          </div>
                        </div>
                        <div className="text-right shrink-0">
                          <span className={`text-xs font-semibold px-2 py-0.5 rounded ${
                            predictionLabel === "Fake" || predictionLabel === "Likely Deepfake"
                              ? "bg-red-500/10 text-red-400 border border-red-500/20"
                              : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          }`}>
                            {predictionLabel} ({confidenceVal}%)
                          </span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Case Details */}
        <div className="lg:col-span-7 space-y-6">
          {!selectedReport ? (
            <Card className="bg-[#0f172a] border-[#1e293b] border-dashed h-full flex flex-col items-center justify-center p-12 text-center text-slate-500">
              <Layers className="w-12 h-12 text-slate-700 mb-3" />
              <h3 className="text-lg font-bold text-slate-400">No Case Selected</h3>
              <p className="text-xs max-w-sm mt-1">
                Select an escalation ticket from the directory to review details, re-evaluate files, download notice PDFs, or issue resolutions.
              </p>
            </Card>
          ) : loadingDetail ? (
            <Card className="bg-[#0f172a] border-[#1e293b] h-full flex flex-col items-center justify-center p-12 text-center text-slate-500">
              <RefreshCw className="w-8 h-8 animate-spin text-primary mb-3" />
              <p className="text-sm">Fetching evidence block details...</p>
            </Card>
          ) : (
            <div className="space-y-6 animate-in fade-in slide-in-from-right-4 duration-300">
              
              {/* Header Title */}
              <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-[#1e293b] pb-4">
                <div>
                  <h2 className="text-2xl font-bold text-white flex items-center gap-3">
                    <span className="font-mono text-primary">{selectedReport.report_id}</span>
                    <span>Evidence Review</span>
                  </h2>
                  <p className="text-xs text-slate-400 mt-1">
                    Ingested on {new Date(selectedReport.created_at).toLocaleString()} • ID: {selectedReport._id}
                  </p>
                </div>
                
                {/* Re-evaluate Actions */}
                <div className="flex gap-2">
                  <Button 
                    variant="outline" 
                    size="sm" 
                    onClick={handleReevaluate}
                    disabled={reanalyzing}
                    className="border-slate-700 text-slate-300 hover:bg-slate-800 gap-1.5 h-9"
                  >
                    {reanalyzing ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        Analyzing...
                      </>
                    ) : (
                      <>
                        <RefreshCw className="w-3.5 h-3.5" />
                        Re-evaluate Media
                      </>
                    )}
                  </Button>
                  
                  {!selectedReport.legal_documents || selectedReport.legal_documents.length === 0 ? (
                    <Button 
                      size="sm" 
                      onClick={handleGenerateDocs}
                      disabled={generatingDocs}
                      className="bg-indigo-600 hover:bg-indigo-700 text-white gap-1.5 h-9"
                    >
                      {generatingDocs ? (
                        <>
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                          Compiling docs...
                        </>
                      ) : (
                        <>
                          <Scale className="w-3.5 h-3.5" />
                          Generate Legal Notice
                        </>
                      )}
                    </Button>
                  ) : null}
                </div>
              </div>

              {/* Case Details Cards */}
              <div className="grid md:grid-cols-2 gap-6">
                {/* Ingested File details */}
                <Card className="bg-[#0f172a] border-[#1e293b]">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-xs uppercase text-slate-400 tracking-wider">Ingested Media</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2 text-xs">
                    <div>
                      <span className="text-slate-500">File Name:</span>
                      <p className="text-white font-mono truncate mt-0.5">{selectedReport.media_filename}</p>
                    </div>
                    <div>
                      <span className="text-slate-500">SHA-256 Hash:</span>
                      <p className="text-white font-mono break-all mt-0.5">{selectedReport.media_hash}</p>
                    </div>
                    {selectedReport.media_file_id && (
                      <div>
                        <span className="text-slate-500">GridFS Media ID:</span>
                        <p className="text-slate-400 font-mono truncate mt-0.5">{selectedReport.media_file_id}</p>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Reporter information */}
                <Card className="bg-[#0f172a] border-[#1e293b]">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-xs uppercase text-slate-400 tracking-wider">Submitter Details</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2 text-xs">
                    <div>
                      <span className="text-slate-500">Role & Identifier:</span>
                      <p className="text-white mt-0.5">{selectedReport.reporter.role} ({selectedReport.reporter.identifier})</p>
                    </div>
                    <div>
                      <span className="text-slate-500">Full Name:</span>
                      <p className="text-white mt-0.5">{selectedReport.reporter.name || "N/A"}</p>
                    </div>
                    <div>
                      <span className="text-slate-500">Organization:</span>
                      <p className="text-white mt-0.5">{userOrganization || "Independent Submit"}</p>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Analysis Scores */}
              <Card className="bg-[#0f172a] border-[#1e293b]">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm text-slate-300">AI Neural Inferences</CardTitle>
                </CardHeader>
                <CardContent className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
                  <div className="p-3 bg-[#0b0f19] rounded-lg border border-slate-800">
                    <div className="text-lg font-bold text-white">
                      {selectedReport.analysis?.final_prediction || selectedReport.analysis?.prediction || "N/A"}
                    </div>
                    <div className="text-[10px] text-slate-500 font-bold uppercase mt-1">Ensemble Verdict</div>
                  </div>
                  <div className="p-3 bg-[#0b0f19] rounded-lg border border-slate-800">
                    <div className="text-lg font-bold text-white">
                      {formatConfidence(selectedReport.analysis?.confidence)}%
                    </div>
                    <div className="text-[10px] text-slate-500 font-bold uppercase mt-1">Confidence Score</div>
                  </div>
                  <div className="p-3 bg-[#0b0f19] rounded-lg border border-slate-800">
                    <div className="text-lg font-bold text-white">
                      {selectedReport.analysis?.cnn_probability !== undefined 
                        ? `${Math.round(selectedReport.analysis.cnn_probability * 100)}%` 
                        : "N/A"}
                    </div>
                    <div className="text-[10px] text-slate-500 font-bold uppercase mt-1">Spatial Texture</div>
                  </div>
                  <div className="p-3 bg-[#0b0f19] rounded-lg border border-slate-800">
                    <div className="text-lg font-bold text-white">
                      {selectedReport.analysis?.fft_probability !== undefined 
                        ? `${Math.round(selectedReport.analysis.fft_probability * 100)}%` 
                        : "N/A"}
                    </div>
                    <div className="text-[10px] text-slate-500 font-bold uppercase mt-1">FFT Frequency</div>
                  </div>
                </CardContent>
              </Card>

              {/* Re-analysis / Re-evaluation History */}
              {selectedReport.reanalysis_history && selectedReport.reanalysis_history.length > 0 && (
                <Card className="bg-[#0f172a] border-[#1e293b]">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm text-slate-300 flex items-center gap-2">
                      <Activity className="w-4 h-4 text-primary" />
                      <span>Re-evaluation History</span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {selectedReport.reanalysis_history.map((hist, idx) => {
                      const verdict = hist.analysis?.final_prediction || hist.analysis?.prediction || "Unknown"
                      const conf = formatConfidence(hist.analysis?.confidence)
                      return (
                        <div key={idx} className="flex justify-between items-center bg-[#0b0f19] p-3 rounded-lg border border-slate-850 text-xs">
                          <div className="space-y-0.5">
                            <div className="text-slate-400">
                              Verdict: <span className="font-semibold text-white">{verdict}</span> ({conf}% confidence)
                            </div>
                            <div className="text-[10px] text-slate-500">
                              Executed on {new Date(hist.performed_at).toLocaleString()}
                            </div>
                          </div>
                          <span className="text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded uppercase">
                            Verified Re-run
                          </span>
                        </div>
                      )
                    })}
                  </CardContent>
                </Card>
              )}

              {/* Generated Legal notice Packages */}
              {selectedReport.legal_documents && selectedReport.legal_documents.length > 0 && (
                <Card className="bg-[#0f172a] border-[#1e293b]">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm text-slate-300 flex items-center gap-2">
                      <FileCheck className="w-4 h-4 text-indigo-400" />
                      <span>Compliance Notice Packet (FastAPI Server-Side PDFs)</span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="grid sm:grid-cols-2 gap-4">
                    {selectedReport.legal_documents.map((doc, idx) => {
                      const downloadUrl = getLegalDocDownloadUrl(selectedReport.report_id, doc.packet_id, doc.filename)
                      return (
                        <div key={idx} className="p-3 bg-[#0b0f19] border border-slate-800 rounded-lg flex items-center justify-between text-xs">
                          <div className="space-y-0.5 min-w-0">
                            <div className="font-semibold text-white truncate">{doc.document_type}</div>
                            <div className="text-[10px] text-slate-500 font-mono truncate">{doc.filename}</div>
                          </div>
                          <a 
                            href={downloadUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-2 bg-primary/10 hover:bg-primary/20 text-primary rounded-lg transition-colors flex items-center gap-1.5 shrink-0"
                          >
                            <Download className="w-3.5 h-3.5" />
                          </a>
                        </div>
                      )
                    })}
                  </CardContent>
                </Card>
              )}

              {/* Custody Log */}
              <Card className="bg-[#0f172a] border-[#1e293b]">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm text-slate-300">Auditable Custody Log</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 max-h-[160px] overflow-y-auto">
                  {selectedReport.custody_log.map((log, idx) => (
                    <div key={idx} className="flex gap-3 text-xs leading-relaxed">
                      <div className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                      <div className="flex-1">
                        <div className="flex justify-between items-center">
                          <span className="font-semibold text-slate-300">{log.event}</span>
                          <span className="text-[10px] text-slate-500 font-mono">{new Date(log.time).toLocaleTimeString()}</span>
                        </div>
                        <p className="text-[10px] text-slate-500">by {log.actor}</p>
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>

              {/* Administrative Resolution Controls */}
              <Card className="bg-gradient-to-r from-slate-900 to-[#0f172a] border-[#1e293b] p-6 space-y-4">
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <Settings className="w-4 h-4 text-primary" />
                  <span>Administrative Resolution</span>
                </h3>
                
                <div className="grid sm:grid-cols-12 gap-4">
                  <div className="sm:col-span-4">
                    <label className="text-xs text-slate-400 font-semibold uppercase">Update Status</label>
                    <Select value={newStatus} onValueChange={setNewStatus}>
                      <SelectTrigger className="bg-[#0b0f19] border-[#1e293b] text-white mt-1 h-10">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-[#0f172a] border-[#1e293b] text-white">
                        <SelectItem value="pending_review">Pending Review</SelectItem>
                        <SelectItem value="under_investigation">Under Investigation</SelectItem>
                        <SelectItem value="resolved">Resolved</SelectItem>
                        <SelectItem value="dismissed">Dismissed</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="sm:col-span-8">
                    <label className="text-xs text-slate-400 font-semibold uppercase">Resolution Notes / Action log</label>
                    <Input
                      placeholder="Add compliance notes, directives, or takedown receipts..."
                      value={adminNotes}
                      onChange={(e) => setAdminNotes(e.target.value)}
                      className="bg-[#0b0f19] border-[#1e293b] text-white mt-1 h-10"
                    />
                  </div>
                </div>

                <div className="flex justify-end pt-2">
                  <Button 
                    onClick={handleUpdateStatus}
                    disabled={updatingStatus}
                    className="bg-primary hover:bg-primary/90 text-white min-w-[150px]"
                  >
                    {updatingStatus ? (
                      <>
                        <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                        Saving notes...
                      </>
                    ) : (
                      "Apply Resolution"
                    )}
                  </Button>
                </div>
              </Card>

            </div>
          )}
        </div>

      </main>
    </div>
  )
}

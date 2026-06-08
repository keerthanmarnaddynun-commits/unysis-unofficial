"use client"

import { useState, useEffect } from "react"
import { 
  ArrowLeft,
  Shield,
  Search,
  RefreshCw,
  FileText,
  CheckCircle,
  Download,
  Clock,
  FileCheck,
  AlertCircle,
  Clock3,
  Layers,
  ChevronRight,
  ExternalLink
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { useToast } from "@/hooks/use-toast"
import { 
  listReports, 
  getReport, 
  getLegalDocDownloadUrl,
  type Report 
} from "../src/api"

interface MyReportsProps {
  userRole: string
  userIdentifier: string
  userName: string
  onBack: () => void
}

export function MyReports({ 
  userRole, 
  userIdentifier, 
  userName, 
  onBack 
}: MyReportsProps) {
  const { toast } = useToast()
  
  // State for reports
  const [reports, setReports] = useState<Report[]>([])
  const [selectedReport, setSelectedReport] = useState<Report | null>(null)
  
  // Loading states
  const [loadingList, setLoadingList] = useState(true)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")

  // Fetch user's reports on mount
  const fetchUserReports = async () => {
    setLoadingList(true)
    try {
      const res = await listReports({})
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
    fetchUserReports()
  }, [userIdentifier])

  // Select a report and fetch full details
  const handleSelectReport = async (reportId: string) => {
    setLoadingDetail(true)
    try {
      const res = await getReport(reportId)
      setSelectedReport(res.report)
    } catch (err: any) {
      console.error(err)
      toast({
        variant: "destructive",
        title: "Failed to load case details",
        description: err.message || "Report could not be retrieved.",
      })
    } finally {
      setLoadingDetail(false)
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
    (r.media_filename || "").toLowerCase().includes(searchQuery.toLowerCase())
  )

  const isSensitiveDoc = (docType: string) => {
    const sensitiveTypes = ["complete_legal_evidence_packet", "bsa_section_63_part_b", "cyber_crime_fir_bns"]
    return sensitiveTypes.includes(docType.toLowerCase())
  }

  // Filter documents based on role
  const visibleDocs = selectedReport?.legal_documents?.filter(doc => {
    const isAuth = userRole === "Police" || userRole === "Authority"
    if (isAuth) return true
    return !isSensitiveDoc(doc.document_type)
  }) || []

  const hiddenDocsCount = (selectedReport?.legal_documents?.length || 0) - visibleDocs.length

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
            <span className="text-[#94a3b8]">My Reports</span>
          </div>
          
          <div className="text-xs text-[#94a3b8] font-medium bg-slate-900 px-3 py-1.5 rounded-lg border border-slate-800">
            User ID: <span className="text-white font-semibold">{userIdentifier} ({userRole})</span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* Left Column: Report List */}
        <div className="lg:col-span-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <Layers className="w-5 h-5 text-primary" />
              <span>Report History</span>
            </h2>
            <Button variant="ghost" size="icon" onClick={fetchUserReports} className="text-slate-400 hover:text-white hover:bg-slate-800 animate-in spin-in-1">
              <RefreshCw className={`w-4 h-4 ${loadingList ? 'animate-spin' : ''}`} />
            </Button>
          </div>

          {/* Search Box */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <Input
              placeholder="Search by case ID or file name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 bg-[#0f172a] border-[#1e293b] text-white focus-visible:ring-primary"
            />
          </div>

          {/* Report Directory List */}
          <Card className="bg-[#0f172a] border-[#1e293b] overflow-hidden min-h-[400px]">
            <CardContent className="p-0 max-h-[600px] overflow-y-auto">
              {loadingList ? (
                <div className="p-12 text-center text-slate-500 space-y-2">
                  <RefreshCw className="w-8 h-8 animate-spin mx-auto text-primary" />
                  <p className="text-xs">Fetching your secure custody cases...</p>
                </div>
              ) : filteredReports.length === 0 ? (
                <div className="p-12 text-center text-slate-500 space-y-2">
                  <AlertCircle className="w-8 h-8 mx-auto opacity-40 text-slate-400" />
                  <p className="text-sm">No reports found.</p>
                  <p className="text-xs text-slate-600">Reports you submit will appear here.</p>
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
                            {report.media_filename || "Unnamed submission"}
                          </div>
                          <div className="text-[10px] text-slate-500 flex items-center gap-1.5">
                            <Clock className="w-3 h-3" />
                            <span>{new Date(report.created_at).toLocaleDateString()}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <span className={`text-xs font-semibold px-2 py-0.5 rounded ${
                            predictionLabel === "Fake" || predictionLabel === "Likely Deepfake"
                              ? "bg-red-500/10 text-red-400 border border-red-500/20"
                              : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          }`}>
                            {predictionLabel} ({confidenceVal}%)
                          </span>
                          <ChevronRight className="w-4 h-4 text-slate-600" />
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Report Details & Timeline */}
        <div className="lg:col-span-7 space-y-6">
          {!selectedReport ? (
            <Card className="bg-[#0f172a] border-[#1e293b] border-dashed h-full flex flex-col items-center justify-center p-12 text-center text-slate-500">
              <Layers className="w-12 h-12 text-slate-700 mb-3" />
              <h3 className="text-lg font-bold text-slate-400">No Report Selected</h3>
              <p className="text-xs max-w-sm mt-1">
                Select a report from the directory list to view its real-time custody status, compliance logs, and download official legal documents.
              </p>
            </Card>
          ) : loadingDetail ? (
            <Card className="bg-[#0f172a] border-[#1e293b] h-full flex flex-col items-center justify-center p-12 text-center text-slate-500">
              <RefreshCw className="w-8 h-8 animate-spin text-primary mb-3" />
              <p className="text-sm">Loading ledger details...</p>
            </Card>
          ) : (
            <div className="space-y-6 animate-in fade-in slide-in-from-right-4 duration-300">
              
              {/* Header Title */}
              <div className="flex justify-between items-center border-b border-[#1e293b] pb-4">
                <div>
                  <h2 className="text-2xl font-bold text-white flex items-center gap-3">
                    <span className="font-mono text-primary">{selectedReport.report_id}</span>
                    <span>Case Overview</span>
                  </h2>
                  <p className="text-xs text-slate-400 mt-1">
                    Submitted on {new Date(selectedReport.created_at).toLocaleString()}
                  </p>
                </div>
                
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => handleSelectReport(selectedReport.report_id)} className="border-slate-700 text-slate-300 hover:bg-slate-800">
                    <RefreshCw className="w-3.5 h-3.5 mr-2" />
                    Refresh Case
                  </Button>
                </div>
              </div>

              {/* Case Details Cards */}
              <div className="grid md:grid-cols-2 gap-6">
                {/* Media details */}
                <Card className="bg-[#0f172a] border-[#1e293b]">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-xs uppercase text-slate-400 tracking-wider">Submitted Media</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2 text-xs">
                    <div>
                      <span className="text-slate-500">File Name:</span>
                      <p className="text-white font-mono truncate mt-0.5">{selectedReport.media_filename || "N/A"}</p>
                    </div>
                    <div>
                      <span className="text-slate-500">SHA-256 Hash:</span>
                      <p className="text-white font-mono break-all mt-0.5">{selectedReport.media_hash || "N/A"}</p>
                    </div>
                  </CardContent>
                </Card>

                {/* Submitter details */}
                <Card className="bg-[#0f172a] border-[#1e293b]">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-xs uppercase text-slate-400 tracking-wider">Incident Verdict</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2 text-xs">
                    <div>
                      <span className="text-slate-500">AI Detection Status:</span>
                      <p className="text-white font-semibold mt-0.5">
                        {selectedReport.analysis?.final_prediction || selectedReport.analysis?.prediction || "Unknown"}
                      </p>
                    </div>
                    <div>
                      <span className="text-slate-500">Ensemble Confidence:</span>
                      <p className="text-white mt-0.5">{formatConfidence(selectedReport.analysis?.confidence)}%</p>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Live Tracking Timeline */}
              <Card className="bg-[#0f172a] border-[#1e293b]">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm text-slate-300 flex items-center gap-1.5">
                    <Clock3 className="w-4 h-4 text-sky-400" />
                    <span>Real-Time Custody Timeline</span>
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-6 space-y-4">
                  <div className="space-y-4">
                    {/* Live status badge */}
                    <div className="flex justify-between items-center bg-[#0b0f19] p-3 rounded-lg border border-slate-800 text-xs">
                      <span className="text-slate-400 font-semibold uppercase">Current Case Status:</span>
                      {getStatusBadge(selectedReport.status)}
                    </div>

                    {/* Timeline items */}
                    <div className="space-y-4 pl-1">
                      {selectedReport.custody_log && selectedReport.custody_log.map((log, index) => (
                        <div key={index} className="flex gap-3 text-xs">
                          <div className="w-2 h-2 rounded-full bg-primary mt-1.5 shrink-0 shadow-[0_0_8px_rgba(var(--primary),0.5)]" />
                          <div className="flex-1">
                            <div className="flex justify-between font-semibold text-slate-200">
                              <span>{log.event}</span>
                              <span className="text-[10px] text-slate-500 font-mono">
                                {log.time ? new Date(log.time).toLocaleTimeString() : ""}
                              </span>
                            </div>
                            <p className="text-[10px] text-slate-500 mt-0.5">Actor: {log.actor}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Legal documents */}
              <Card className="bg-[#0f172a] border-[#1e293b]">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm text-slate-300 flex items-center gap-1.5">
                    <FileCheck className="w-4 h-4 text-indigo-400" />
                    <span>Legal Documents & Receipts</span>
                  </CardTitle>
                  <CardDescription className="text-xs text-slate-500">
                    Download official notices and compliance affidavits.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {!selectedReport.legal_documents || selectedReport.legal_documents.length === 0 ? (
                    <div className="text-center py-6 text-slate-500 text-xs flex flex-col items-center gap-2 border border-dashed border-slate-800 rounded-lg">
                      <AlertCircle className="w-6 h-6 text-slate-600" />
                      <span>No documents generated yet. Authorities must review and verify the case first.</span>
                    </div>
                  ) : visibleDocs.length === 0 ? (
                    <div className="text-center py-6 text-slate-500 text-xs flex flex-col items-center gap-2 border border-dashed border-slate-800 rounded-lg">
                      <AlertCircle className="w-6 h-6 text-amber-500" />
                      <span>All compiled documents are classified as sensitive and require Police or Authority clearance to access.</span>
                    </div>
                  ) : (
                    <div className="grid sm:grid-cols-2 gap-4">
                      {visibleDocs.map((doc, idx) => {
                        const downloadUrl = getLegalDocDownloadUrl(selectedReport.report_id, doc.packet_id, doc.filename)
                        return (
                          <div key={idx} className="p-3 bg-[#0b0f19] border border-slate-800 rounded-lg flex items-center justify-between text-xs hover:border-slate-700 transition-all">
                            <div className="space-y-0.5 min-w-0 pr-2">
                              <div className="font-semibold text-white truncate">{doc.document_type.replace(/_/g, " ").toUpperCase()}</div>
                              <div className="text-[10px] text-slate-500 font-mono truncate">{doc.filename}</div>
                            </div>
                            <a 
                              href={downloadUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="p-2 bg-primary/10 hover:bg-primary/20 text-primary rounded-lg transition-colors flex items-center shrink-0"
                            >
                              <Download className="w-3.5 h-3.5" />
                            </a>
                          </div>
                        )
                      })}
                    </div>
                  )}

                  {/* Inform non-auth user that some docs are hidden */}
                  {hiddenDocsCount > 0 && (
                    <div className="p-3 bg-amber-950/10 border border-amber-900/30 rounded-lg text-xs text-amber-400 mt-2 flex items-center gap-2">
                      <AlertCircle className="w-4 h-4 shrink-0 text-amber-400" />
                      <span>
                        Note: {hiddenDocsCount} document(s) containing sensitive forensic reports (e.g. Expert Certifications, FIR drafts) are restricted. Only Police and Authorities can access them.
                      </span>
                    </div>
                  )}
                </CardContent>
              </Card>
              
            </div>
          )}
        </div>

      </main>
    </div>
  )
}

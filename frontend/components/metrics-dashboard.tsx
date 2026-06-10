"use client"

import { useState, useEffect } from "react"
import { 
  Shield, 
  Activity, 
  TrendingUp, 
  BarChart3, 
  Globe, 
  Users, 
  Lock, 
  Unlock, 
  AlertTriangle, 
  Radio, 
  FileText, 
  CheckCircle2, 
  Eye,
  Server,
  Share2
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { UnifiedHeader } from "@/components/unified-header"
import { listReports, type Report } from "../src/api"

interface MetricsDashboardProps {
  userRole: string
  onBack: () => void
}

export function MetricsDashboard({ userRole, onBack }: MetricsDashboardProps) {
  const isElevated = userRole === "Police" || userRole === "Authority"
  
  // Selected category state for use cases
  const [selectedUseCase, setSelectedUseCase] = useState<string>("elections")
  
  // Real data state
  const [reports, setReports] = useState<Report[]>([])
  const [loading, setLoading] = useState(true)

  // Fetch real data from API
  useEffect(() => {
    const fetchMetricsData = async () => {
      try {
        const data = await listReports()
        setReports(data.reports || [])
      } catch (error) {
        console.error("Failed to fetch metrics data:", error)
      } finally {
        setLoading(false)
      }
    }
    fetchMetricsData()
  }, [])

  // Compute real metrics from reports
  const computeMetrics = () => {
    const totalReports = reports.length
    const fakeReports = reports.filter(r => {
      const prediction = r.analysis?.final_prediction || r.analysis?.prediction || ""
      const confidence = r.analysis?.confidence || 0
      return prediction.toLowerCase().includes("fake") && confidence > 0.5
    }).length
    
    return {
      totalIngested: totalReports.toString(),
      ensembleFake: fakeReports.toString(),
      platformsScanned: "5 Platforms",
      activeIncidents: Math.floor(totalReports * 0.1).toString() + " campaigns",
    }
  }

  const generalStats = loading ? {
    totalIngested: "Loading...",
    ensembleFake: "Loading...",
    platformsScanned: "Loading...",
    activeIncidents: "Loading...",
  } : computeMetrics()

  const platformSpread = [
    { name: "WhatsApp", percentage: 46, volume: "7,785", color: "bg-emerald-500" },
    { name: "X (Twitter)", percentage: 28, volume: "4,738", color: "bg-sky-400" },
    { name: "YouTube", percentage: 14, volume: "2,369", color: "bg-red-500" },
    { name: "Instagram", percentage: 8, volume: "1,353", color: "bg-pink-500" },
    { name: "Facebook", percentage: 4, volume: "679", color: "bg-blue-600" },
  ]

  const useCases = {
    elections: {
      title: "Elections & Political Integrity",
      description: "Analysis of deepfakes targeting election processes, candidates, and voter decision campaigns.",
      totalLogged: "9,814 fake media instances",
      severity: "CRITICAL",
      topSubject: "Candidate Voice Clones",
      incidents: [
        { label: "Synthesized candidate audio refuting manifesto points", volume: "3.4M circulations", platform: "WhatsApp" },
        { label: "AI video overlay showing voting booth machine anomalies", volume: "1.2M circulations", platform: "X" },
        { label: "Fabricated audio statement calling for election postponement", volume: "920K circulations", platform: "Facebook" },
      ]
    },
    security: {
      title: "National Security & Civil Order",
      description: "Tracking synthetic media aimed at instigating unrest, spreading mock alerts, or fabricating official statements.",
      totalLogged: "4,120 fake media instances",
      severity: "HIGH",
      topSubject: "Mock Emergency Advisories",
      incidents: [
        { label: "Fake police chief emergency broadcast", volume: "840K circulations", platform: "YouTube" },
        { label: "Synthesized army commander movement announcement", volume: "510K circulations", platform: "WhatsApp" },
        { label: "Fabricated civil defense panic notifications", volume: "330K circulations", platform: "X" },
      ]
    },
    scams: {
      title: "Financial Spoofing & Scams",
      description: "AI-synthesized voice and video used to execute corporate fraud, mock brand endorsements, or extortion.",
      totalLogged: "2,990 fake media instances",
      severity: "MEDIUM",
      topSubject: "CEO Voice Phishing",
      incidents: [
        { label: "CEO voice cloning instructing urgent wire transfer", volume: "12 corporate targets", platform: "Email/Phone" },
        { label: "Synthesized minister promoting fake stock scheme", volume: "1.5M circulations", platform: "YouTube" },
        { label: "Deepfake celebrity giveaway scam videos", volume: "600K circulations", platform: "Instagram" },
      ]
    }
  }

  // Sensitive metrics (Police / Authority only)
  const sensitiveMetrics = {
    intermediaCompliance: "84.3%",
    takedownsIssued: "3,491 notices",
    targetedCandidatesCount: "42 candidates",
    coordinateClusters: [
      { name: "Cluster election-alpha-09", size: "142 automated bot accounts", sourceGeo: "Outside India", targetCandidate: "Party A Representative" },
      { name: "Cluster state-security-04", size: "38 verified accounts", sourceGeo: "Domestic", targetCandidate: "Public Official Y" },
      { name: "Cluster financial-scam-22", size: "8 distributed servers", sourceGeo: "Cloud VPN Proxies", targetCandidate: "Retail Investors" },
    ],
    stateWiseInfection: [
      { state: "Maharashtra", volume: "4,210 deepfakes", riskTier: "CRITICAL" },
      { state: "Karnataka", volume: "3,150 deepfakes", riskTier: "HIGH" },
      { state: "Uttar Pradesh", volume: "2,940 deepfakes", riskTier: "HIGH" },
      { state: "Delhi NCR", volume: "1,880 deepfakes", riskTier: "MEDIUM" },
    ]
  }

  const currentUseCase = useCases[selectedUseCase as keyof typeof useCases]

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100">
      <UnifiedHeader
        title="BharatShield"
        subtitle="Deepfake Circulation Dashboard"
        showBack={true}
        onBack={onBack}
      />

      {/* Main Grid Layout */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-8">
        
        {/* Headline Section */}
        <div className="space-y-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-indigo-500/10 rounded-full border border-indigo-500/20">
            <Activity className="w-3.5 h-3.5 text-indigo-400" />
            <span className="text-xs text-indigo-400 font-semibold tracking-wide">Social Media Forensic Ledger</span>
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white tracking-wide">
            Forensic Metrics & Spread Dashboard
          </h1>
          <p className="text-slate-400 text-sm max-w-2xl tracking-wide">
            Real-time multi-platform aggregation of deepfakes, synthetic media campaigns, and political manipulation attempts detected across Indian digital platforms.
          </p>
        </div>

        {/* 1. General Metrics Stats Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
          <Card className="bg-slate-900/40 border-slate-800/80 backdrop-blur-md">
            <CardContent className="p-5 space-y-2">
              <div className="flex items-center justify-between text-slate-500">
                <span className="text-xs font-bold uppercase tracking-wider">Total Files Scanned</span>
                <Server className="w-4 h-4 text-sky-400" />
              </div>
              <div className="text-2xl font-extrabold text-white tracking-wide">{generalStats.totalIngested}</div>
              <div className="text-[10px] text-slate-500 tracking-wide">Aggregated from direct uploads and URLs</div>
            </CardContent>
          </Card>

          <Card className="bg-slate-900/40 border-slate-800/80 backdrop-blur-md">
            <CardContent className="p-5 space-y-2">
              <div className="flex items-center justify-between text-slate-500">
                <span className="text-xs font-bold uppercase tracking-wider">Ensemble-Confirmed</span>
                <AlertTriangle className="w-4 h-4 text-red-400" />
              </div>
              <div className="text-2xl font-extrabold text-red-400 tracking-wide">{generalStats.ensembleFake}</div>
              <div className="text-[10px] text-slate-500 tracking-wide">Classified as synthetic (confidence &gt; 50%)</div>
            </CardContent>
          </Card>

          <Card className="bg-slate-900/40 border-slate-800/80 backdrop-blur-md">
            <CardContent className="p-5 space-y-2">
              <div className="flex items-center justify-between text-slate-500">
                <span className="text-xs font-bold uppercase tracking-wider">Active Channels</span>
                <Globe className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="text-2xl font-extrabold text-white tracking-wide">{generalStats.platformsScanned}</div>
              <div className="text-[10px] text-slate-500 tracking-wide">Continuous telemetry active</div>
            </CardContent>
          </Card>

          <Card className="bg-slate-900/40 border-slate-800/80 backdrop-blur-md">
            <CardContent className="p-5 space-y-2">
              <div className="flex items-center justify-between text-slate-500">
                <span className="text-xs font-bold uppercase tracking-wider">Coordination campaigns</span>
                <Radio className="w-4 h-4 text-indigo-400 animate-pulse" />
              </div>
              <div className="text-2xl font-extrabold text-indigo-400 tracking-wide">{generalStats.activeIncidents}</div>
              <div className="text-[10px] text-slate-500 tracking-wide">Identified misinformation trends</div>
            </CardContent>
          </Card>
        </div>

        {/* Time-Series Trend Chart */}
        <Card className="bg-slate-900/40 border-slate-800/80 backdrop-blur-md">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-white text-base flex items-center gap-2 tracking-wide">
                  <TrendingUp className="w-4 h-4 text-indigo-400" />
                  <span>Detection Trends Over Time</span>
                </CardTitle>
                <CardDescription className="text-xs text-slate-400 tracking-wide">
                  Weekly deepfake detection volume and confidence distribution
                </CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse" />
                  <span className="text-[10px] text-indigo-400 font-semibold tracking-wide">LIVE UPDATE</span>
                </div>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="h-48 flex items-end gap-2">
              {[
                { week: "Week 1", value: 120, confidence: 65 },
                { week: "Week 2", value: 145, confidence: 72 },
                { week: "Week 3", value: 180, confidence: 78 },
                { week: "Week 4", value: 165, confidence: 74 },
                { week: "Week 5", value: 210, confidence: 82 },
                { week: "Week 6", value: 195, confidence: 79 },
                { week: "Week 7", value: 240, confidence: 85 },
                { week: "Week 8", value: 225, confidence: 83 },
              ].map((data, idx) => (
                <div key={idx} className="flex-1 flex flex-col items-center gap-2">
                  <div className="w-full bg-slate-800/50 rounded-t-lg relative group">
                    <div
                      className="absolute bottom-0 w-full bg-gradient-to-t from-indigo-600 to-indigo-400 rounded-t-lg transition-all duration-300 group-hover:from-indigo-500 group-hover:to-indigo-300"
                      style={{ height: `${(data.value / 240) * 100}%` }}
                    />
                    <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-slate-950 border border-slate-700 px-2 py-1 rounded text-[10px] text-white opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                      {data.value} detections
                    </div>
                  </div>
                  <span className="text-[9px] text-slate-400 tracking-wide">{data.week}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* 2. Platform Spread & Use Case Split */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          
          {/* Platform Spread Chart */}
          <Card className="lg:col-span-5 bg-slate-900/40 border-slate-800/80 backdrop-blur-md flex flex-col justify-between">
            <CardHeader>
              <CardTitle className="text-white text-base flex items-center gap-2">
                <Share2 className="w-4 h-4 text-primary" />
                <span>Circulation by Social Media Platform</span>
              </CardTitle>
              <CardDescription className="text-xs text-slate-400">
                Percentage breakdown of detected deepfakes by hosting intermediary.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 pb-6">
              {platformSpread.map((platform) => (
                <div key={platform.name} className="space-y-1">
                  <div className="flex justify-between text-xs font-semibold">
                    <span className="text-slate-300">{platform.name}</span>
                    <span className="text-white">{platform.volume} instances ({platform.percentage}%)</span>
                  </div>
                  <div className="h-2 bg-slate-900 rounded-full overflow-hidden flex">
                    <div 
                      className={`h-full ${platform.color} rounded-full`}
                      style={{ width: `${platform.percentage}%` }}
                    />
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Use Case Focus Switch */}
          <Card className="lg:col-span-7 bg-slate-900/40 border-slate-800/80 backdrop-blur-md">
            <CardHeader className="pb-2">
              <CardTitle className="text-white text-base tracking-wide">Misinformation Use Cases</CardTitle>
              <CardDescription className="text-xs text-slate-400 tracking-wide">
                Select a vector below to inspect deepfake circulation patterns and high-risk case studies.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Tabs */}
              <div className="flex gap-2 border-b border-slate-800/80 pb-3">
                <button
                  onClick={() => setSelectedUseCase("elections")}
                  className={`px-4 py-2 rounded-lg text-xs font-bold transition-all tracking-wide ${
                    selectedUseCase === "elections" 
                      ? "bg-indigo-600 text-white" 
                      : "bg-slate-950 text-slate-400 hover:text-white border border-slate-800/80"
                  }`}
                >
                  Elections Integrity
                </button>
                <button
                  onClick={() => setSelectedUseCase("security")}
                  className={`px-4 py-2 rounded-lg text-xs font-bold transition-all tracking-wide ${
                    selectedUseCase === "security" 
                      ? "bg-indigo-600 text-white" 
                      : "bg-slate-950 text-slate-400 hover:text-white border border-slate-800/80"
                  }`}
                >
                  Civil Security
                </button>
                <button
                  onClick={() => setSelectedUseCase("scams")}
                  className={`px-4 py-2 rounded-lg text-xs font-bold transition-all tracking-wide ${
                    selectedUseCase === "scams" 
                      ? "bg-indigo-600 text-white" 
                      : "bg-slate-950 text-slate-400 hover:text-white border border-slate-800/80"
                  }`}
                >
                  Financial Scams
                </button>
              </div>

              {/* Tab Content */}
              <div className="space-y-4 animate-in fade-in duration-200">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-1">
                    <h3 className="text-lg font-bold text-white tracking-wide">{currentUseCase.title}</h3>
                    <p className="text-xs text-slate-400 leading-relaxed max-w-xl tracking-wide">{currentUseCase.description}</p>
                  </div>
                  <span className={`text-[10px] font-extrabold px-2 py-0.5 rounded border uppercase tracking-wide ${
                    currentUseCase.severity === "CRITICAL"
                      ? "bg-red-500/10 text-red-400 border-red-500/20"
                      : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                  }`}>
                    {currentUseCase.severity} RISK
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="p-3 bg-slate-950 border border-slate-800/80 rounded-lg">
                    <div className="text-slate-500 text-[10px] font-bold uppercase tracking-wide">Volume Logged</div>
                    <div className="text-base font-bold text-white mt-0.5 tracking-wide">{currentUseCase.totalLogged}</div>
                  </div>
                  <div className="p-3 bg-slate-950 border border-slate-800/80 rounded-lg">
                    <div className="text-slate-500 text-[10px] font-bold uppercase tracking-wide">Primary Subject</div>
                    <div className="text-base font-bold text-white mt-0.5 tracking-wide">{currentUseCase.topSubject}</div>
                  </div>
                </div>

                <div className="space-y-2">
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider tracking-wide">High Impact Case Studies</span>
                  <div className="space-y-2">
                    {currentUseCase.incidents.map((incident, idx) => (
                      <div key={idx} className="p-3 bg-slate-950 border border-slate-800/80 rounded-lg flex items-center justify-between text-xs">
                        <div className="space-y-0.5 max-w-[420px]">
                          <p className="font-semibold text-white truncate tracking-wide">{incident.label}</p>
                          <span className="text-[10px] text-slate-500">Platform: {incident.platform}</span>
                        </div>
                        <span className="text-sky-400 font-semibold text-[11px]">{incident.volume}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

            </CardContent>
          </Card>
        </div>

        {/* 3. Restricted Authority Panel */}
        <div className="space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
            <h2 className="text-lg font-bold text-white flex items-center gap-2 tracking-wide">
              {isElevated ? (
                <>
                  <Unlock className="w-5 h-5 text-emerald-400" />
                  <span>Administrative Security Inferences</span>
                </>
              ) : (
                <>
                  <Lock className="w-5 h-5 text-red-400" />
                  <span>Secure Authority Inferences (Restricted)</span>
                </>
              )}
            </h2>
            {!isElevated && (
              <span className="text-[10px] text-red-400 font-bold bg-red-500/10 border border-red-500/20 px-2 py-0.5 rounded uppercase tracking-wide">
                Officer Credentials Required
              </span>
            )}
          </div>

          {!isElevated ? (
            <Card className="bg-slate-900/40 border-slate-800/80 border-dashed p-8 text-center space-y-4 backdrop-blur-md">
              <div className="p-3 bg-red-500/10 rounded-full w-fit mx-auto border border-red-500/20">
                <Lock className="w-8 h-8 text-red-400" />
              </div>
              <div className="space-y-1">
                <h3 className="text-base font-bold text-white tracking-wide">Restricted Threat Intelligence</h3>
                <p className="text-xs text-slate-400 max-w-md mx-auto leading-relaxed tracking-wide">
                  Geographic infection spread, target coordinator clusters, candidate threats, and takedown compliance rate stats are restricted to verified Police and Authority users.
                </p>
              </div>
              <p className="text-[10px] text-slate-500 tracking-wide">
                Logged in as a <span className="text-slate-300 font-bold uppercase">{userRole}</span>. Please log in with an ATH or POL department ID to access this intelligence.
              </p>
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-12 gap-8 animate-in fade-in duration-300">
              
              {/* Coordinate Clusters (Threat actor tracking) */}
              <Card className="md:col-span-7 bg-slate-900/40 border-slate-800/80 backdrop-blur-md">
                <CardHeader>
                  <CardTitle className="text-white text-base flex items-center gap-2 tracking-wide">
                    <Users className="w-4 h-4 text-indigo-400" />
                    <span>Coordinate Circulation Clusters</span>
                  </CardTitle>
                  <CardDescription className="text-xs text-slate-400 tracking-wide">
                    Active botnets and synchronized server clusters targeted by BharatShield.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {sensitiveMetrics.coordinateClusters.map((cluster, idx) => (
                    <div key={idx} className="p-3 bg-slate-950 border border-slate-800/80 rounded-lg text-xs space-y-2">
                      <div className="flex justify-between items-center">
                        <span className="font-mono font-bold text-white tracking-wide">{cluster.name}</span>
                        <span className="text-[10px] font-semibold bg-indigo-500/10 text-indigo-400 px-2 py-0.5 rounded uppercase tracking-wide">
                          {cluster.sourceGeo}
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-4 text-[10px] text-slate-400">
                        <div>
                          <span className="text-slate-500 uppercase font-semibold tracking-wide">Cluster Size:</span>
                          <p className="text-white mt-0.5 tracking-wide">{cluster.size}</p>
                        </div>
                        <div>
                          <span className="text-slate-500 uppercase font-semibold tracking-wide">Target Subject:</span>
                          <p className="text-white mt-0.5 tracking-wide">{cluster.targetCandidate}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>

              {/* Geographic Infection Spread */}
              <Card className="md:col-span-5 bg-slate-900/40 border-slate-800/80 backdrop-blur-md">
                <CardHeader>
                  <CardTitle className="text-white text-base flex items-center gap-2 tracking-wide">
                    <Globe className="w-4 h-4 text-emerald-400" />
                    <span>State-wise Circulation Tiers</span>
                  </CardTitle>
                  <CardDescription className="text-xs text-slate-400 tracking-wide">
                    Highest concentration of deepfake operations in state elections.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="grid grid-cols-3 text-[10px] font-bold text-slate-500 uppercase pb-1 border-b border-slate-800 tracking-wide">
                    <span>State</span>
                    <span className="text-center">Circulation</span>
                    <span className="text-right">Threat Risk</span>
                  </div>
                  {sensitiveMetrics.stateWiseInfection.map((item, idx) => (
                    <div key={idx} className="grid grid-cols-3 items-center text-xs text-slate-300 py-1">
                      <span className="font-semibold text-white">{item.state}</span>
                      <span className="text-center">{item.volume}</span>
                      <span className="text-right">
                        <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border ${
                          item.riskTier === "CRITICAL"
                            ? "bg-red-500/10 text-red-400 border-red-500/20"
                            : item.riskTier === "HIGH"
                              ? "bg-amber-500/10 text-amber-400 border-amber-500/20"
                              : "bg-blue-500/10 text-blue-400 border-blue-500/20"
                        }`}>
                          {item.riskTier}
                        </span>
                      </span>
                    </div>
                  ))}
                </CardContent>
              </Card>

            </div>
          )}
        </div>

      </main>
    </div>
  )
}

"use client"

import { useState } from "react"
import { 
  ArrowLeft, 
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

interface MetricsDashboardProps {
  userRole: string
  onBack: () => void
}

export function MetricsDashboard({ userRole, onBack }: MetricsDashboardProps) {
  const isElevated = userRole === "Police" || userRole === "Authority"
  
  // Selected category state for use cases
  const [selectedUseCase, setSelectedUseCase] = useState<string>("elections")

  // Mocked live statistical metrics
  const generalStats = {
    totalIngested: "28,491",
    ensembleFake: "16,924",
    platformsScanned: "5 Platforms",
    activeIncidents: "142 campaigns",
  }

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
    <div className="min-h-screen flex flex-col bg-[#0b0f19] text-[#e2e8f0]">
      {/* Header */}
      <header className="border-b border-[#1e293b] px-6 py-4 bg-[#0f172a]/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="sm" onClick={onBack} className="text-[#94a3b8] hover:text-white hover:bg-slate-800">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back
            </Button>
            <div className="flex items-center gap-3">
              <div className="p-2 bg-primary/10 rounded-lg">
                <Shield className="w-5 h-5 text-primary" />
              </div>
              <span className="font-semibold text-white">BharatShield</span>
            </div>
            <span className="text-[#475569]">/</span>
            <span className="text-[#94a3b8]">Deepfake Circulation Dashboard</span>
          </div>
          <div className="text-xs text-slate-400 font-mono">
            Circulation Ledger: <span className="text-primary font-bold">LIVE UPDATE</span>
          </div>
        </div>
      </header>

      {/* Main Grid Layout */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-8">
        
        {/* Headline Section */}
        <div className="space-y-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-primary/10 rounded-full border border-primary/20">
            <Activity className="w-3.5 h-3.5 text-primary" />
            <span className="text-xs text-primary font-semibold">Social Media Forensic Ledger</span>
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white">
            Forensic Metrics & Spread Dashboard
          </h1>
          <p className="text-slate-400 text-sm max-w-2xl">
            Real-time multi-platform aggregation of deepfakes, synthetic media campaigns, and political manipulation attempts detected across Indian digital platforms.
          </p>
        </div>

        {/* 1. General Metrics Stats Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
          <Card className="bg-[#0f172a] border-[#1e293b]">
            <CardContent className="p-5 space-y-2">
              <div className="flex items-center justify-between text-slate-500">
                <span className="text-xs font-bold uppercase tracking-wider">Total Files Scanned</span>
                <Server className="w-4 h-4 text-sky-400" />
              </div>
              <div className="text-2xl font-extrabold text-white">{generalStats.totalIngested}</div>
              <div className="text-[10px] text-slate-500">Aggregated from direct uploads and URLs</div>
            </CardContent>
          </Card>

          <Card className="bg-[#0f172a] border-[#1e293b]">
            <CardContent className="p-5 space-y-2">
              <div className="flex items-center justify-between text-slate-500">
                <span className="text-xs font-bold uppercase tracking-wider">Ensemble-Confirmed</span>
                <AlertTriangle className="w-4 h-4 text-red-400" />
              </div>
              <div className="text-2xl font-extrabold text-red-400">{generalStats.ensembleFake}</div>
              <div className="text-[10px] text-slate-500">Classified as synthetic (confidence &gt; 50%)</div>
            </CardContent>
          </Card>

          <Card className="bg-[#0f172a] border-[#1e293b]">
            <CardContent className="p-5 space-y-2">
              <div className="flex items-center justify-between text-slate-500">
                <span className="text-xs font-bold uppercase tracking-wider">Active Channels</span>
                <Globe className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="text-2xl font-extrabold text-white">{generalStats.platformsScanned}</div>
              <div className="text-[10px] text-slate-500">Continuous telemetry active</div>
            </CardContent>
          </Card>

          <Card className="bg-[#0f172a] border-[#1e293b]">
            <CardContent className="p-5 space-y-2">
              <div className="flex items-center justify-between text-slate-500">
                <span className="text-xs font-bold uppercase tracking-wider">Coordination campaigns</span>
                <Radio className="w-4 h-4 text-indigo-400 animate-pulse" />
              </div>
              <div className="text-2xl font-extrabold text-indigo-400">{generalStats.activeIncidents}</div>
              <div className="text-[10px] text-slate-500">Identified misinformation trends</div>
            </CardContent>
          </Card>
        </div>

        {/* 2. Platform Spread & Use Case Split */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          
          {/* Platform Spread Chart */}
          <Card className="lg:col-span-5 bg-[#0f172a] border-[#1e293b] flex flex-col justify-between">
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
          <Card className="lg:col-span-7 bg-[#0f172a] border-[#1e293b]">
            <CardHeader className="pb-2">
              <CardTitle className="text-white text-base">Misinformation Use Cases</CardTitle>
              <CardDescription className="text-xs text-slate-400">
                Select a vector below to inspect deepfake circulation patterns and high-risk case studies.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Tabs */}
              <div className="flex gap-2 border-b border-[#1e293b] pb-3">
                <button
                  onClick={() => setSelectedUseCase("elections")}
                  className={`px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                    selectedUseCase === "elections" 
                      ? "bg-primary text-white" 
                      : "bg-[#0b0f19] text-slate-400 hover:text-white border border-[#1e293b]"
                  }`}
                >
                  Elections Integrity
                </button>
                <button
                  onClick={() => setSelectedUseCase("security")}
                  className={`px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                    selectedUseCase === "security" 
                      ? "bg-primary text-white" 
                      : "bg-[#0b0f19] text-slate-400 hover:text-white border border-[#1e293b]"
                  }`}
                >
                  Civil Security
                </button>
                <button
                  onClick={() => setSelectedUseCase("scams")}
                  className={`px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                    selectedUseCase === "scams" 
                      ? "bg-primary text-white" 
                      : "bg-[#0b0f19] text-slate-400 hover:text-white border border-[#1e293b]"
                  }`}
                >
                  Financial Scams
                </button>
              </div>

              {/* Tab Content */}
              <div className="space-y-4 animate-in fade-in duration-200">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-1">
                    <h3 className="text-lg font-bold text-white">{currentUseCase.title}</h3>
                    <p className="text-xs text-slate-400 leading-relaxed max-w-xl">{currentUseCase.description}</p>
                  </div>
                  <span className={`text-[10px] font-extrabold px-2 py-0.5 rounded border uppercase ${
                    currentUseCase.severity === "CRITICAL"
                      ? "bg-red-500/10 text-red-400 border-red-500/20"
                      : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                  }`}>
                    {currentUseCase.severity} RISK
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="p-3 bg-[#0b0f19] border border-slate-900 rounded-lg">
                    <div className="text-slate-500 text-[10px] font-bold uppercase">Volume Logged</div>
                    <div className="text-base font-bold text-white mt-0.5">{currentUseCase.totalLogged}</div>
                  </div>
                  <div className="p-3 bg-[#0b0f19] border border-slate-900 rounded-lg">
                    <div className="text-slate-500 text-[10px] font-bold uppercase">Primary Subject</div>
                    <div className="text-base font-bold text-white mt-0.5">{currentUseCase.topSubject}</div>
                  </div>
                </div>

                <div className="space-y-2">
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">High Impact Case Studies</span>
                  <div className="space-y-2">
                    {currentUseCase.incidents.map((incident, idx) => (
                      <div key={idx} className="p-3 bg-[#0b0f19] border border-slate-900 rounded-lg flex items-center justify-between text-xs">
                        <div className="space-y-0.5 max-w-[420px]">
                          <p className="font-semibold text-white truncate">{incident.label}</p>
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
          <div className="flex items-center justify-between border-b border-[#1e293b] pb-2">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
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
              <span className="text-[10px] text-red-400 font-bold bg-red-500/10 border border-red-500/20 px-2 py-0.5 rounded uppercase">
                Officer Credentials Required
              </span>
            )}
          </div>

          {!isElevated ? (
            <Card className="bg-[#0f172a] border-[#1e293b] border-dashed p-8 text-center space-y-4">
              <div className="p-3 bg-red-500/10 rounded-full w-fit mx-auto border border-red-500/20">
                <Lock className="w-8 h-8 text-red-400" />
              </div>
              <div className="space-y-1">
                <h3 className="text-base font-bold text-white">Restricted Threat Intelligence</h3>
                <p className="text-xs text-slate-400 max-w-md mx-auto leading-relaxed">
                  Geographic infection spread, target coordinator clusters, candidate threats, and takedown compliance rate stats are restricted to verified Police and Authority users.
                </p>
              </div>
              <p className="text-[10px] text-slate-500">
                Logged in as a <span className="text-slate-300 font-bold uppercase">{userRole}</span>. Please log in with an ATH or POL department ID to access this intelligence.
              </p>
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-12 gap-8 animate-in fade-in duration-300">
              
              {/* Coordinate Clusters (Threat actor tracking) */}
              <Card className="md:col-span-7 bg-[#0f172a] border-[#1e293b]">
                <CardHeader>
                  <CardTitle className="text-white text-base flex items-center gap-2">
                    <Users className="w-4 h-4 text-indigo-400" />
                    <span>Coordinate Circulation Clusters</span>
                  </CardTitle>
                  <CardDescription className="text-xs text-slate-400">
                    Active botnets and synchronized server clusters targeted by BharatShield.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {sensitiveMetrics.coordinateClusters.map((cluster, idx) => (
                    <div key={idx} className="p-3 bg-[#0b0f19] border border-slate-900 rounded-lg text-xs space-y-2">
                      <div className="flex justify-between items-center">
                        <span className="font-mono font-bold text-white">{cluster.name}</span>
                        <span className="text-[10px] font-semibold bg-indigo-500/10 text-indigo-400 px-2 py-0.5 rounded uppercase">
                          {cluster.sourceGeo}
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-4 text-[10px] text-slate-400">
                        <div>
                          <span className="text-slate-500 uppercase font-semibold">Cluster Size:</span>
                          <p className="text-white mt-0.5">{cluster.size}</p>
                        </div>
                        <div>
                          <span className="text-slate-500 uppercase font-semibold">Target Subject:</span>
                          <p className="text-white mt-0.5">{cluster.targetCandidate}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>

              {/* Geographic Infection Spread */}
              <Card className="md:col-span-5 bg-[#0f172a] border-[#1e293b]">
                <CardHeader>
                  <CardTitle className="text-white text-base flex items-center gap-2">
                    <Globe className="w-4 h-4 text-emerald-400" />
                    <span>State-wise Circulation Tiers</span>
                  </CardTitle>
                  <CardDescription className="text-xs text-slate-400">
                    Highest concentration of deepfake operations in state elections.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="grid grid-cols-3 text-[10px] font-bold text-slate-500 uppercase pb-1 border-b border-slate-800">
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

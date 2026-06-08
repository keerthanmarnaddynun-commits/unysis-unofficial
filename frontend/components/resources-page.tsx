"use client"

import { Shield, Scale, AlertTriangle, ArrowLeft, FileText, Clock, Gavel, CheckCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"

interface ResourcesPageProps {
  onBack: () => void
}

export function ResourcesPage({ onBack }: ResourcesPageProps) {
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
            <span className="text-[#94a3b8]">Legal & Compliance Resources</span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-8">
        {/* Page Title */}
        <div className="space-y-2">
          <h1 className="text-3xl font-bold text-white">Statutory Compliance Knowledge Base</h1>
          <p className="text-[#94a3b8]">
            Official legal frameworks governing digital evidence integrity, AI-generated content regulation, and punitive measures for deepfake offenses in India.
          </p>
        </div>

        {/* Section A: Digital Evidence Integrity */}
        <Card className="bg-[#0f172a] border-[#1e293b]">
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="p-3 bg-emerald-500/10 rounded-lg">
                <FileText className="w-6 h-6 text-emerald-400" />
              </div>
              <div>
                <CardTitle className="text-white text-xl">Section A: Digital Evidence Integrity</CardTitle>
                <CardDescription className="text-[#94a3b8]">
                  Bharatiya Sakshya Adhiniyam, 2023 - Section 63
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="p-4 bg-[#0b0f19] rounded-lg border border-[#1e293b]">
              <h3 className="text-emerald-400 font-semibold mb-2 flex items-center gap-2">
                <CheckCircle className="w-4 h-4" />
                Automated Certificate Generation
              </h3>
              <p className="text-sm text-[#94a3b8]">
                BharatShield automatically generates Part A & Part B Certificates for court admissibility, ensuring compliance with electronic evidence standards under Section 63 of the Bharatiya Sakshya Adhiniyam, 2023.
              </p>
            </div>
            
            <div className="p-4 bg-[#0b0f19] rounded-lg border border-[#1e293b]">
              <h3 className="text-emerald-400 font-semibold mb-2 flex items-center gap-2">
                <CheckCircle className="w-4 h-4" />
                Cryptographic SHA-256 Media Hashing
              </h3>
              <p className="text-sm text-[#94a3b8]">
                All submitted media is cryptographically hashed using SHA-256 algorithms, providing immutable fingerprinting that meets forensic standards for digital evidence authentication.
              </p>
            </div>
            
            <div className="p-4 bg-[#0b0f19] rounded-lg border border-[#1e293b]">
              <h3 className="text-emerald-400 font-semibold mb-2 flex items-center gap-2">
                <CheckCircle className="w-4 h-4" />
                Append-Only Chain-of-Custody Ledgers
              </h3>
              <p className="text-sm text-[#94a3b8]">
                Our platform maintains tamper-evident, append-only custody logs that track every evidence transfer, analysis, and administrative action, establishing clear provenance chains for judicial proceedings.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Section B: Generative AI & Intermediary Liability */}
        <Card className="bg-[#0f172a] border-[#1e293b]">
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="p-3 bg-amber-500/10 rounded-lg">
                <Clock className="w-6 h-6 text-amber-400" />
              </div>
              <div>
                <CardTitle className="text-white text-xl">Section B: Generative AI & Intermediary Liability</CardTitle>
                <CardDescription className="text-[#94a3b8]">
                  IT Rules 2021 / 2026 Updates
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="p-4 bg-[#0b0f19] rounded-lg border border-[#1e293b]">
              <h3 className="text-amber-400 font-semibold mb-2 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4" />
                Automated Takedown Notice Dispatch Protocol
              </h3>
              <p className="text-sm text-[#94a3b8]">
                BharatShield implements statutory-compliant takedown notice generation and dispatch to intermediaries (social media platforms, content hosts) upon verified deepfake detection.
              </p>
            </div>
            
            <div className="p-4 bg-[#0b0f19] rounded-lg border border-[#1e293b]">
              <h3 className="text-amber-400 font-semibold mb-2 flex items-center gap-2">
                <Clock className="w-4 h-4" />
                Emergency Timeline: Non-Consensual Intimate Imagery (NCII)
              </h3>
              <p className="text-sm text-[#94a3b8]">
                For NCII cases, our system enforces the statutory <span className="text-amber-400 font-semibold">2-hour emergency takedown window</span> as mandated by IT Rules 2021 amendments, ensuring rapid content removal.
              </p>
            </div>
            
            <div className="p-4 bg-[#0b0f19] rounded-lg border border-[#1e293b]">
              <h3 className="text-amber-400 font-semibold mb-2 flex items-center gap-2">
                <Clock className="w-4 h-4" />
                Standard Timeline: General Deepfake Content
              </h3>
              <p className="text-sm text-[#94a3b8]">
                For non-emergency deepfake cases, our protocol follows the <span className="text-amber-400 font-semibold">3-hour standard removal window</span> established in the 2026 IT Rules updates for synthetic media.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Section C: Punitive Legal Frameworks */}
        <Card className="bg-[#0f172a] border-[#1e293b]">
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="p-3 bg-red-500/10 rounded-lg">
                <Gavel className="w-6 h-6 text-red-400" />
              </div>
              <div>
                <CardTitle className="text-white text-xl">Section C: Punitive Legal Frameworks</CardTitle>
                <CardDescription className="text-[#94a3b8]">
                  Bharatiya Nyaya Sanhita (BNS) & Electoral Laws
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="p-4 bg-[#0b0f19] rounded-lg border border-[#1e293b]">
              <h3 className="text-red-400 font-semibold mb-2 flex items-center gap-2">
                <Gavel className="w-4 h-4" />
                BNS 319: Cheating by Personation
              </h3>
              <p className="text-sm text-[#94a3b8]">
                Applicable when deepfakes are used to impersonate individuals for fraudulent purposes, carrying imprisonment up to 3 years and fines.
              </p>
            </div>
            
            <div className="p-4 bg-[#0b0f19] rounded-lg border border-[#1e293b]">
              <h3 className="text-red-400 font-semibold mb-2 flex items-center gap-2">
                <Gavel className="w-4 h-4" />
                BNS 356: Defamation
              </h3>
              <p className="text-sm text-[#94a3b8]">
                Covers creation and distribution of defamatory deepfakes that harm reputation, with penalties including imprisonment and substantial fines.
              </p>
            </div>
            
            <div className="p-4 bg-[#0b0f19] rounded-lg border border-[#1e293b]">
              <h3 className="text-red-400 font-semibold mb-2 flex items-center gap-2">
                <Scale className="w-4 h-4" />
                Representation of the People Act Section 123(4)
              </h3>
              <p className="text-sm text-[#94a3b8]">
                Specifically addresses electoral disinformation through synthetic media, with provisions for disqualification of candidates and criminal prosecution for deepfake election interference.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Footer Note */}
        <div className="p-6 bg-[#0f172a] border border-[#1e293b] rounded-lg">
          <div className="flex items-start gap-3">
            <Shield className="w-5 h-5 text-primary mt-0.5" />
            <div>
              <h4 className="text-white font-semibold mb-1">Legal Disclaimer</h4>
              <p className="text-sm text-[#94a3b8]">
                This knowledge base provides general information about applicable legal frameworks. For specific legal advice, consult qualified legal counsel. BharatShield maintains compliance with all applicable Indian laws and regulations.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

"use client"

import { useState, useEffect, Suspense } from "react"
import { useSearchParams } from "next/navigation"
import { LandingPage } from "@/components/landing-page"
import { UploadScreen } from "@/components/upload-screen"
import { AnalysisResult } from "@/components/analysis-result"
import { RoleBasedOutput } from "@/components/role-based-output"
import { ActionConfirmation } from "@/components/action-confirmation"
import { LoginPage, type Role } from "@/components/login-page"
import { AuthorityDashboard } from "@/components/authority-dashboard"
import { MetricsDashboard } from "@/components/metrics-dashboard"
import HowItWorksPage from "./how-it-works/page"
import { MyReports } from "@/components/my-reports"
import { ResourcesPage } from "@/components/resources-page"

type Screen = "landing" | "upload-file" | "upload-url" | "analysis" | "role-output" | "confirmation" | "how-it-works" | "authority-dashboard" | "metrics-dashboard" | "my-reports" | "resources"

function MainApp({ initialScreen, initialUrl: propInitialUrl }: { initialScreen?: Screen; initialUrl?: string }) {
  const searchParams = useSearchParams()
  const sourceUrl = searchParams.get("sourceUrl") || propInitialUrl

  const [currentScreen, setCurrentScreen] = useState<Screen>(initialScreen || "landing")
  const [userRole, setUserRole] = useState<Role | null>(null)
  const [userIdentifier, setUserIdentifier] = useState("")
  const [userName, setUserName] = useState("")
  const [userOrganization, setUserOrganization] = useState("")
  const [accessToken, setAccessToken] = useState("")
  const [uploadedFile, setUploadedFile] = useState<File | null>(null)
  const [initialUrl, setInitialUrl] = useState("")
  const [analysisData, setAnalysisData] = useState<any>(null)
  const [submittedReportInfo, setSubmittedReportInfo] = useState<any>(null)

  useEffect(() => {
    if (sourceUrl) {
      try {
        const decoded = decodeURIComponent(sourceUrl)
        setInitialUrl(decoded)
        setCurrentScreen("upload-url")
      } catch (e) {
        setInitialUrl(sourceUrl)
        setCurrentScreen("upload-url")
      }
    }
  }, [sourceUrl])

  const handleLogin = (role: Role, identifier: string, name: string, organization: string, token: string) => {
    setUserRole(role)
    setUserIdentifier(identifier)
    setUserName(name)
    setUserOrganization(organization)
    setAccessToken(token)
    // Store token in localStorage for persistence
    if (typeof window !== 'undefined') {
      localStorage.setItem('access_token', token)
    }
  }

  const navigateTo = (screen: Screen) => {
    setCurrentScreen(screen)
  }


  const handleLogout = () => {
    setUserRole(null)
    setUserIdentifier("")
    setUserName("")
    setUserOrganization("")
    setAccessToken("")
    setUploadedFile(null)
    setAnalysisData(null)
    setSubmittedReportInfo(null)
    setCurrentScreen("landing")
    // Clear token from localStorage
    if (typeof window !== 'undefined') {
      localStorage.removeItem('access_token')
    }
  }

  if (!userRole) {
    return <LoginPage onLogin={handleLogin} onResourcesClick={() => navigateTo("resources")} />
  }

  return (
    <div className="min-h-screen bg-background text-foreground relative">
      {currentScreen === "landing" && userRole && (
        <LandingPage
          userRole={userRole}
          onUploadClick={() => navigateTo("upload-file")}
          onUrlClick={() => navigateTo("upload-url")}
          onHowItWorksClick={() => navigateTo("how-it-works")}
          onResourcesClick={() => navigateTo("resources")}
          onViewDashboardClick={() => navigateTo("authority-dashboard")}
          onViewMetricsClick={() => navigateTo("metrics-dashboard")}
          onViewMyReportsClick={() => navigateTo("my-reports")}
          onLogout={handleLogout}
        />
      )}

      {currentScreen === "upload-file" && (
        <UploadScreen
          mode="file"
          onBack={() => navigateTo("landing")}
          onAnalyze={(result, file) => {
            setAnalysisData(result)
            setUploadedFile(file)
            navigateTo("analysis")
          }}
        />
      )}

      {currentScreen === "upload-url" && (
        <UploadScreen
          mode="url"
          initialUrl={initialUrl}
          onBack={() => navigateTo("landing")}
          onAnalyze={(result, file) => {
            setAnalysisData(result)
            setUploadedFile(file)
            navigateTo("analysis")
          }}
        />
      )}

      {currentScreen === "analysis" && (
          <AnalysisResult
            data={analysisData}
            sourceInfo={analysisData?.sourceInfo}
            onContinue={() => navigateTo("role-output")}
            onBack={() => navigateTo("landing")}
          />
      )}

      {currentScreen === "role-output" && userRole && (
        <RoleBasedOutput
          userRole={userRole}
          sourceUrl={initialUrl}
          userIdentifier={userIdentifier}
          userName={userName}
          userOrganization={userOrganization}
          analysisData={analysisData}
          uploadedFile={uploadedFile}
          onAction={(reportInfo) => {
            setSubmittedReportInfo(reportInfo)
            navigateTo("confirmation")
          }}
          onBack={() => navigateTo("analysis")}
        />
      )}

      {currentScreen === "confirmation" && (
        <ActionConfirmation
          userRole={userRole || "Citizen"}
          reportInfo={submittedReportInfo}
          onStartOver={() => navigateTo("landing")}
        />
      )}

      {currentScreen === "how-it-works" && (
        <HowItWorksPage onBack={() => navigateTo("landing")} />
      )}

      {currentScreen === "authority-dashboard" && (
        <AuthorityDashboard
          userRole={userRole}
          userIdentifier={userIdentifier}
          userName={userName}
          userOrganization={userOrganization}
          onBack={() => navigateTo("landing")}
        />
      )}

      {currentScreen === "metrics-dashboard" && (
        <MetricsDashboard
          userRole={userRole || "Citizen"}
          onBack={() => navigateTo("landing")}
        />
      )}

      {currentScreen === "my-reports" && userRole && (
        <MyReports
          userRole={userRole}
          userIdentifier={userIdentifier}
          userName={userName}
          onBack={() => navigateTo("landing")}
        />
      )}

      {currentScreen === "resources" && (
        <ResourcesPage onBack={() => navigateTo("landing")} />
      )}
    </div>
  )
}

export default function Home({ initialScreen, initialUrl }: { initialScreen?: any; initialUrl?: string }) {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-background text-foreground flex items-center justify-center">
        <div className="animate-pulse flex flex-col items-center gap-4">
          <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
        </div>
      </div>
    }>
      <MainApp initialScreen={initialScreen} initialUrl={initialUrl} />
    </Suspense>
  )
}

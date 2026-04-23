"use client"

import { useState } from "react"
import { LandingPage } from "@/components/landing-page"
import { UploadScreen } from "@/components/upload-screen"
import { AnalysisResult } from "@/components/analysis-result"
import { RoleBasedOutput } from "@/components/role-based-output"
import { ActionConfirmation } from "@/components/action-confirmation"
import { LoginPage, type Role } from "@/components/login-page"
import HowItWorksPage from "./how-it-works/page"

type Screen = "landing" | "upload-file" | "upload-url" | "analysis" | "role-output" | "confirmation" | "how-it-works"

export default function Home() {
  const [currentScreen, setCurrentScreen] = useState<Screen>("landing")
  const [userRole, setUserRole] = useState<Role | null>(null)

  const handleLogin = (role: Role) => {
    setUserRole(role)
  }

  const navigateTo = (screen: Screen) => {
    setCurrentScreen(screen)
  }

  const handleDemo = () => {
    // Skip to analysis screen for demo
    setCurrentScreen("analysis")
  }

  if (!userRole) {
    return <LoginPage onLogin={handleLogin} />
  }

  return (
    <div className="min-h-screen bg-background text-foreground relative">
      {currentScreen === "landing" && userRole && (
        <LandingPage
          userRole={userRole}
          onUploadClick={() => navigateTo("upload-file")}
          onUrlClick={() => navigateTo("upload-url")}
          onDemoClick={handleDemo}
          onHowItWorksClick={() => navigateTo("how-it-works")}
        />
      )}

      {currentScreen === "upload-file" && (
        <UploadScreen
          mode="file"
          onBack={() => navigateTo("landing")}
          onAnalyze={() => navigateTo("analysis")}
        />
      )}

      {currentScreen === "upload-url" && (
        <UploadScreen
          mode="url"
          onBack={() => navigateTo("landing")}
          onAnalyze={() => navigateTo("analysis")}
        />
      )}

      {currentScreen === "analysis" && (
        <AnalysisResult
          onContinue={() => navigateTo("role-output")}
          onBack={() => navigateTo("landing")}
        />
      )}

      {currentScreen === "role-output" && userRole && (
        <RoleBasedOutput
          userRole={userRole}
          onAction={() => navigateTo("confirmation")}
          onBack={() => navigateTo("analysis")}
        />
      )}

      {currentScreen === "confirmation" && (
        <ActionConfirmation
          onStartOver={() => navigateTo("landing")}
        />
      )}

      {currentScreen === "how-it-works" && (
        <HowItWorksPage onBack={() => navigateTo("landing")} />
      )}
    </div>
  )
}

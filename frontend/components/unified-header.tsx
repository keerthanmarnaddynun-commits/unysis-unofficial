"use client"

import { useRouter } from "next/navigation"
import { ArrowLeft, Shield as ShieldIcon } from "lucide-react"
import { Button } from "@/components/ui/button"

interface UnifiedHeaderProps {
  title: string
  subtitle?: string
  showBack?: boolean
  backPath?: string
  onBack?: () => void
}

export function UnifiedHeader({
  title,
  subtitle,
  showBack = true,
  backPath,
  onBack,
}: UnifiedHeaderProps) {
  const router = useRouter()

  const handleBack = () => {
    if (onBack) {
      onBack()
    } else if (backPath) {
      router.push(backPath)
    } else {
      router.back()
    }
  }

  return (
    <header className="border-b border-slate-800/80 px-6 py-4 bg-slate-900/40 backdrop-blur-md">
      <div className="max-w-7xl mx-auto flex items-center gap-4">
        {showBack && (
          <Button
            variant="ghost"
            size="sm"
            onClick={handleBack}
            className="text-slate-400 hover:text-white hover:bg-slate-800/50 transition-colors"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back
          </Button>
        )}
        <div className="flex items-center gap-3">
          <div className="p-2 bg-indigo-500/10 rounded-lg border border-indigo-500/20">
            <ShieldIcon className="w-5 h-5 text-indigo-400" />
          </div>
          <div className="flex flex-col">
            <span className="font-semibold text-white tracking-wide">{title}</span>
            {subtitle && <span className="text-xs text-slate-400 tracking-wide">{subtitle}</span>}
          </div>
        </div>
      </div>
    </header>
  )
}

// api.ts

// Define response type (VERY IMPORTANT for TS)
export interface AnalyzeResponse {
  // Legacy fields (kept for backward compatibility)
  file_name?: string;
  result?: string;
  confidence?: number;
  hash?: string;
  timestamp?: string;
  legal_notice?: string;

  // New fields
  submission_id?: string;
  timestamp_utc?: string;
  file?: {
    name: string;
    size_bytes: number;
    size_human: string;
    type?: string;
    media_type: string;
    sha256: string;
  };
  deepfake_detection?: {
    label: string;
    confidence: number;
    risk_level: string;
    is_deepfake: boolean;
    fake_probability: number;
    streams: {
      spatial_texture?: { fake_prob: number | null; label: string };
      frequency_domain?: { fake_prob: number | null; label: string };
      temporal?: { fake_prob: number | null; label: string };
      audio?: { fake_prob: number | null; label: string; available?: boolean; note?: string };
      rppg?: { has_pulse: boolean | null; bvp_snr: number | null; available?: boolean; note?: string };
    };
    metadata_flags?: string[];
    gradcam_url?: string | null;
    processing_ms: number;
  };
  fact_check?: {
    available: boolean;
    note?: string;
    overall_misinfo_risk?: string;
    claims?: Array<{
      claim: string;
      speaker: string;
      verdict: string;
      explanation: string;
      confidence: number;
      sources: Array<{
        title: string;
        url: string;
        snippet: string;
      }>;
    }>;
  };
  integrity?: {
    sha256: string;
    audit_entry: string;
  };
  legal_report_url?: string | null;
}

// Function to call backend API with timeout
export async function analyzeFile(file: File, timeoutMs: number = 300000): Promise<AnalyzeResponse> {
  const formData = new FormData();
  formData.append("file", file);

  // Create abort controller for timeout
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch("http://127.0.0.1:8000/analyze", {
      method: "POST",
      body: formData,
      signal: controller.signal,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ error: response.statusText }));
      throw new Error(errorData.error || `API error: ${response.status}`);
    }

    return response.json();
  } finally {
    clearTimeout(timeoutId);
  }
}
// api.ts

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8001";

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
export async function analyzeFile(file: File): Promise<AnalyzeResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const isVideo = file.type.startsWith("video/");
  const timeoutMs = isVideo ? 300000 : 60000;

  // Create abort controller for timeout
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${API_BASE_URL}/analyze`, {
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

export interface CustodyLogItem {
  time: string;
  event: string;
  actor: string;
  notes?: string;
}

export interface ReanalysisItem {
  analysis: any;
  performed_at: string;
  performed_by: string;
}

export interface LegalDocument {
  document_type: string;
  filename: string;
  packet_id: string;
}

export interface Report {
  _id: string;
  report_id: string;
  reporter: {
    role: string;
    identifier: string;
    name?: string | null;
  };
  analysis: any;
  media_file_id?: string | null;
  media_hash?: string | null;
  media_filename?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  custody_log: CustodyLogItem[];
  reanalysis_history?: ReanalysisItem[];
  legal_documents?: LegalDocument[];
  admin_notes?: string | null;
  takedown_status?: string | null;
  takedown_response?: {
    sent_at?: string;
    vibestream_response?: any;
    payload?: any;
    error?: string;
  } | null;
}

const BACKEND_BASE_URL = "http://127.0.0.1:8000";

// Helper to get auth headers
function getAuthHeaders(): HeadersInit {
  const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
  const headers: HeadersInit = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

export async function submitReport(
  analysis: any,
  file?: File
): Promise<{ success: boolean; report_id: string; status: string; message: string }> {
  const formData = new FormData();
  formData.append("analysis_json", JSON.stringify(analysis));
  if (file) {
    formData.append("file", file);
  }

  const response = await fetch(`${BACKEND_BASE_URL}/api/reports/submit`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(errorData.detail || `Failed to submit report: ${response.status}`);
  }

  return response.json();
}

export async function listReports(params: {
  status?: string;
  limit?: number;
} = {}): Promise<{ reports: Report[] }> {
  const query = new URLSearchParams();
  if (params.status) query.append("status", params.status);
  if (params.limit) query.append("limit", String(params.limit));

  const response = await fetch(`${BACKEND_BASE_URL}/api/reports?${query.toString()}`, {
    headers: getAuthHeaders(),
  });
  if (!response.ok) {
    throw new Error(`Failed to list reports: ${response.status}`);
  }
  return response.json();
}

export async function getReport(reportId: string): Promise<{ report: Report }> {
  const response = await fetch(`${BACKEND_BASE_URL}/api/reports/${reportId}`, {
    headers: getAuthHeaders(),
  });
  if (!response.ok) {
    throw new Error(`Failed to get report: ${response.status}`);
  }
  return response.json();
}

export async function updateReportStatus(
  reportId: string,
  status: string,
  adminNotes?: string
): Promise<{ success: boolean; report: Report }> {
  const response = await fetch(`${BACKEND_BASE_URL}/api/reports/${reportId}/status`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify({ status, admin_notes: adminNotes }),
  });

  if (!response.ok) {
    throw new Error(`Failed to update status: ${response.status}`);
  }
  return response.json();
}

export async function reanalyzeReport(
  reportId: string
): Promise<{ success: boolean; new_analysis: any; report: Report }> {
  const response = await fetch(`${BACKEND_BASE_URL}/api/reports/${reportId}/reanalyze`, {
    method: "POST",
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(errorData.detail || `Failed to re-evaluate media: ${response.status}`);
  }
  return response.json();
}

export async function generateReportLegalDocs(
  reportId: string
): Promise<{ success: boolean; documents: LegalDocument[]; packet_id: string }> {
  const response = await fetch(`${BACKEND_BASE_URL}/api/reports/${reportId}/generate-legal-docs`, {
    method: "POST",
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(errorData.detail || `Failed to generate legal docs: ${response.status}`);
  }
  return response.json();
}

export function getLegalDocDownloadUrl(reportId: string, packetId: string, filename: string): string {
  const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
  const url = `${BACKEND_BASE_URL}/api/reports/${reportId}/documents/${packetId}/${filename}`;
  if (token) {
    return `${url}?token=${token}`;
  }
  return url;
}

export async function sendTakedownNotice(
  reportId: string
): Promise<{ success: boolean; message: string; takedown_status: string; vibestream_response?: any; warning?: string }> {
  try {
    const response = await fetch(`${BACKEND_BASE_URL}/api/reports/${reportId}/send-takedown`, {
      method: "POST",
      headers: getAuthHeaders(),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(errorData.detail || `Failed to send takedown notice: ${response.status}`);
    }

    return response.json();
  } catch (error) {
    if (error instanceof TypeError && error.message === "Failed to fetch") {
      throw new Error("Unable to connect to BharatShield backend. Please ensure the backend server is running on http://127.0.0.1:8000");
    }
    throw error;
  }
}
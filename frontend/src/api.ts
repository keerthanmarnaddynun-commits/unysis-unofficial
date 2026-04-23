// api.ts

// Define response type (VERY IMPORTANT for TS)
export interface AnalyzeResponse {
  file_name: string;
  result: string;
  confidence: number;
  hash: string;
  timestamp: string;
  legal_notice: string;
}

// Function to call backend API with timeout
export async function analyzeFile(file: File, timeoutMs: number = 120000): Promise<AnalyzeResponse> {
  const formData = new FormData();
  formData.append("file", file);

  // Create abort controller for timeout
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch("http://127.0.0.1:5000/analyze", {
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
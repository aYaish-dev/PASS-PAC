export type ScanSession = {
  id: number;
  session_name: string;
  description: string | null;
  mode: string;
  status: string;
  environment: string;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
  updated_at: string;
};

export type DetectedCard = {
  id: number;
  session_id: number;
  technology: string;
  frequency: string;
  card_type: string;
  protocol: string;
  uid: string;
  risk_level: string;
  normalized_data_json: Record<string, unknown>;
  raw_output_json: Record<string, unknown>;
  created_at: string;
};

export type SessionCreatePayload = {
  session_name: string;
  description?: string | null;
  mode?: string;
  environment?: string;
};

export type SimulatedScanPayload = {
  technology?: string | null;
  card_type?: string | null;
};

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) {
        message = body.detail;
      }
    } catch {
      // Keep the generic request message when the backend does not return JSON.
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export function listSessions(): Promise<ScanSession[]> {
  return apiRequest<ScanSession[]>("/api/v1/sessions");
}

export function getSession(sessionId: number): Promise<ScanSession> {
  return apiRequest<ScanSession>(`/api/v1/sessions/${sessionId}`);
}

export function createSession(
  payload: SessionCreatePayload,
): Promise<ScanSession> {
  return apiRequest<ScanSession>("/api/v1/sessions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function startSession(sessionId: number): Promise<ScanSession> {
  return apiRequest<ScanSession>(`/api/v1/sessions/${sessionId}/start`, {
    method: "POST",
  });
}

export function stopSession(sessionId: number): Promise<ScanSession> {
  return apiRequest<ScanSession>(`/api/v1/sessions/${sessionId}/stop`, {
    method: "POST",
  });
}

export function simulateSessionScan(
  sessionId: number,
  payload: SimulatedScanPayload = {},
): Promise<DetectedCard> {
  return apiRequest<DetectedCard>(
    `/api/v1/sessions/${sessionId}/scan/simulate`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function listSessionCards(sessionId: number): Promise<DetectedCard[]> {
  return apiRequest<DetectedCard[]>(`/api/v1/sessions/${sessionId}/cards`);
}

export function deleteSession(sessionId: number): Promise<void> {
  return apiRequest<void>(`/api/v1/sessions/${sessionId}`, {
    method: "DELETE",
  });
}

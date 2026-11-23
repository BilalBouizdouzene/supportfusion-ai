export type Dashboard = {
  incidents: number;
  documents: number;
  images: number;
  logs: number;
  tickets: number;
  products: { name: string; count: number }[];
  frequent_errors: { name: string; count: number }[];
  recent_syncs: {
    id: number;
    source: string;
    status: string;
    items: number;
    created: number;
    started_at: string;
  }[];
  search_mode: string;
};

export type Incident = {
  id: number;
  title: string;
  description?: string;
  product?: string;
  repository?: string;
  status: string;
  source_url: string;
  error_codes?: string[];
  affected_component?: string;
  observed_at?: string;
};

export type SearchResult = {
  source_id: number;
  source_type: string;
  title: string;
  excerpt: string;
  source_url: string;
  score: number;
  rank: number;
  verification: string;
  metadata: {
    product?: string;
    status?: string;
    error_codes?: string[];
  };
};

export type SearchResponse = {
  query: string;
  results: SearchResult[];
  retrieval_method: string;
  dense_backend: string;
  reranker_status: string;
  latency_ms: number;
  model_status: string;
};

export type TicketAnalysis = {
  ticket_id: number;
  analysis_id: number;
  classification: string;
  hypotheses: {
    label: string;
    confidence: number;
    basis: string;
    source_id: number;
  }[];
  missing_information: string[];
  draft_response: string;
  evidence: SearchResult[];
  validation_required: boolean;
  evidence_bundle_id: number;
  retrieval_method: string;
  dense_backend: string;
  reranker_status: string;
  model_status: string;
  latency_ms: number;
};

export type DataSource = {
  id: number;
  name: string;
  source_type: string;
  uri: string;
  enabled: boolean;
  last_cursor: string | null;
  last_synced_at: string | null;
  syncs: {
    id: number;
    status: string;
    items_seen: number;
    items_created: number;
    started_at: string | null;
  }[];
};

export type SyncResult = {
  items_created: number;
  items_seen: number;
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    const body = await response.json();
    throw new Error(body.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

export const getDashboard = () => request<Dashboard>("/api/dashboard");

export const getIncidents = (query = "") =>
  request<Incident[]>(
    `/api/incidents?limit=60${query ? `&q=${encodeURIComponent(query)}` : ""}`,
  );

export const searchIncidents = (query: string) =>
  request<SearchResponse>(`/api/search?q=${encodeURIComponent(query)}`);

export const getSources = () => request<DataSource[]>("/api/sources");

export const syncGithub = (repository: string, limit: number) =>
  request<SyncResult>("/api/sync/github", {
    method: "POST",
    body: JSON.stringify({ repository, limit }),
  });

export const analyzeTicket = (
  title: string,
  description: string,
  priority: string,
) =>
  request<TicketAnalysis>("/api/tickets/analyze", {
    method: "POST",
    body: JSON.stringify({ title, description, priority }),
  });

import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  Archive,
  ArrowUpRight,
  BookOpen,
  Boxes,
  BrainCircuit,
  Database,
  FileSearch,
  GitBranch,
  Headphones,
  LayoutDashboard,
  MessageSquare,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  Ticket,
  Workflow,
} from "lucide-react";
import {
  analyzeTicket,
  getDashboard,
  getIncidents,
  getSources,
  searchIncidents,
  syncGithub,
  type Dashboard,
  type DataSource,
  type Incident,
  type SearchResponse,
  type TicketAnalysis,
} from "./api";

type View = "overview" | "copilot" | "knowledge" | "sources" | "search";

const navigation = [
  { id: "overview" as View, label: "Overview", icon: LayoutDashboard },
  { id: "copilot" as View, label: "Incident Copilot", icon: BrainCircuit },
  { id: "knowledge" as View, label: "Knowledge Base", icon: Database },
  { id: "search" as View, label: "Search Lab", icon: FileSearch },
  { id: "sources" as View, label: "Data Sources", icon: Workflow },
];

function MetricCard({
  label,
  value,
  accent,
  icon: Icon,
}: {
  label: string;
  value: number;
  accent: string;
  icon: typeof Activity;
}) {
  return (
    <div className="metric-card">
      <div className={`metric-icon ${accent}`}>
        <Icon size={18} />
      </div>
      <div>
        <p>{label}</p>
        <strong>{value.toLocaleString()}</strong>
      </div>
      <span className="metric-spark">↗</span>
    </div>
  );
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="empty-state">
      <div className="empty-orb">
        <Sparkles size={22} />
      </div>
      <h3>{title}</h3>
      <p>{body}</p>
    </div>
  );
}

function Overview({
  dashboard,
  onNavigate,
}: {
  dashboard: Dashboard | null;
  onNavigate: (view: View) => void;
}) {
  if (!dashboard) {
    return <EmptyState title="Loading workspace" body="Connecting to the local service…" />;
  }

  return (
    <div className="page-stack">
      <div className="hero">
        <div>
          <span className="eyebrow">
            OPERATIONS CENTER · {dashboard.search_mode} MODE
          </span>
          <h1>Technical support, with evidence attached.</h1>
          <p>
            Real public incidents and local tickets, organized into an
            auditable support workflow.
          </p>
        </div>
        <button className="primary-button" onClick={() => onNavigate("copilot")}>
          <Sparkles size={16} /> Analyze a ticket
        </button>
      </div>

      <div className="metrics">
        <MetricCard
          label="Incidents indexed"
          value={dashboard.incidents}
          accent="indigo"
          icon={Archive}
        />
        <MetricCard
          label="Documents parsed"
          value={dashboard.documents}
          accent="cyan"
          icon={BookOpen}
        />
        <MetricCard
          label="Media references"
          value={dashboard.images}
          accent="violet"
          icon={Boxes}
        />
        <MetricCard
          label="Tickets analyzed"
          value={dashboard.tickets}
          accent="green"
          icon={Ticket}
        />
      </div>

      <div className="grid-two">
        <section className="panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">SIGNALS</span>
              <h2>Frequent error signatures</h2>
            </div>
            <span className="badge muted">Observed data</span>
          </div>
          {dashboard.frequent_errors.length ? (
            dashboard.frequent_errors.map((error) => (
              <div className="signal-row" key={error.name}>
                <span className="code-pill">{error.name}</span>
                <div className="signal-bar">
                  <span
                    style={{ width: `${Math.min(100, error.count * 20)}%` }}
                  />
                </div>
                <b>{error.count}</b>
              </div>
            ))
          ) : (
            <EmptyState
              title="No error signatures yet"
              body="Collect a pilot repository to populate the signal layer."
            />
          )}
        </section>

        <section className="panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">CONNECTIVITY</span>
              <h2>Recent synchronizations</h2>
            </div>
            <button className="ghost-button" onClick={() => onNavigate("sources")}>
              View all <ArrowUpRight size={14} />
            </button>
          </div>
          {dashboard.recent_syncs.length ? (
            dashboard.recent_syncs.map((sync) => (
              <div className="sync-row" key={sync.id}>
                <div className="sync-icon">
                  <GitBranch size={16} />
                </div>
                <div>
                  <b>{sync.source}</b>
                  <small>
                    {sync.items} seen · {sync.created} new
                  </small>
                </div>
                <span className={`status-dot ${sync.status}`} />
              </div>
            ))
          ) : (
            <EmptyState
              title="No sync run yet"
              body="Connect GitHub to start building the knowledge base."
            />
          )}
        </section>
      </div>
    </div>
  );
}

function Copilot() {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("medium");
  const [result, setResult] = useState<TicketAnalysis | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      setResult(await analyzeTicket(title, description, priority));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page-stack">
      <div className="page-title">
        <div>
          <span className="eyebrow">SUPPORT WORKSPACE</span>
          <h1>Incident Copilot</h1>
          <p>
            Ground a technician response in retrieved evidence. Human validation
            remains required.
          </p>
        </div>
        <span className="mode-chip">
          <ShieldCheck size={15} />
          {result?.retrieval_method || "STANDARD retrieval ready"}
        </span>
      </div>

      <div className="copilot-layout">
        <section className="panel form-panel">
          <label>
            Ticket title
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="e.g. OAuth callback returns 401 after deployment"
            />
          </label>
          <label>
            What is happening?
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Describe the symptom, error code, product and version if known…"
              rows={9}
            />
          </label>
          <div className="form-row">
            <label>
              Priority
              <select
                value={priority}
                onChange={(event) => setPriority(event.target.value)}
              >
                <option>low</option>
                <option>medium</option>
                <option>high</option>
                <option>urgent</option>
              </select>
            </label>
            <button
              className="primary-button analyze-button"
              disabled={busy || !title || !description}
              onClick={submit}
            >
              {busy ? (
                <RefreshCw className="spin" size={16} />
              ) : (
                <Sparkles size={16} />
              )}
              {busy ? "Analyzing…" : "Run evidence search"}
            </button>
          </div>
          {error && <div className="error-banner">{error}</div>}
        </section>

        <section className="panel result-panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">ANALYSIS OUTPUT</span>
              <h2>{result?.classification || "Waiting for a ticket"}</h2>
            </div>
            {result && <span className="badge warning">Validation required</span>}
          </div>

          {result ? (
            <>
              <div className="retrieval-strip">
                <span>
                  <b>Method</b>
                  {result.retrieval_method}
                </span>
                <span>
                  <b>Dense backend</b>
                  {result.dense_backend}
                </span>
                <span>
                  <b>Reranker</b>
                  {result.reranker_status}
                </span>
                <span>
                  <b>Latency</b>
                  {result.latency_ms} ms
                </span>
              </div>

              <p className="draft-response">{result.draft_response}</p>
              <h3>Hypotheses</h3>
              {result.hypotheses.length ? (
                result.hypotheses.map((hypothesis) => (
                  <div className="hypothesis" key={hypothesis.label}>
                    <div>
                      <b>{hypothesis.label}</b>
                      <small>{hypothesis.basis}</small>
                    </div>
                    <span>{Math.round(hypothesis.confidence * 100)}%</span>
                  </div>
                ))
              ) : (
                <p className="muted-text">
                  No supported hypothesis. The system abstained.
                </p>
              )}

              <h3>Missing information</h3>
              <div className="tag-list">
                {result.missing_information.length ? (
                  result.missing_information.map((item) => (
                    <span className="tag" key={item}>
                      {item}
                    </span>
                  ))
                ) : (
                  <span className="muted-text">No obvious gaps detected.</span>
                )}
              </div>

              <h3>Evidence</h3>
              {result.evidence.length ? (
                result.evidence.map((item) => (
                  <a
                    className="evidence-card"
                    href={item.source_url}
                    target="_blank"
                    rel="noreferrer"
                    key={`${item.source_type}:${item.source_id}`}
                  >
                    <div>
                      <span className="rank">0{item.rank}</span>
                      <b>{item.title}</b>
                    </div>
                    <p>{item.excerpt}</p>
                    <small>
                      {item.verification} · score {item.score}
                    </small>
                  </a>
                ))
              ) : (
                <p className="muted-text">No reliable public match found.</p>
              )}
            </>
          ) : (
            <EmptyState
              title="Ready for intake"
              body="Describe a support problem to retrieve related public incidents and prepare a traceable draft."
            />
          )}
        </section>
      </div>
    </div>
  );
}

function KnowledgeBase() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getIncidents()
      .then(setIncidents)
      .finally(() => setLoading(false));
  }, []);

  const visible = useMemo(
    () =>
      query
        ? incidents.filter((incident) =>
            `${incident.title} ${incident.description || ""}`
              .toLowerCase()
              .includes(query.toLowerCase()),
          )
        : incidents,
    [incidents, query],
  );

  return (
    <div className="page-stack">
      <div className="page-title">
        <div>
          <span className="eyebrow">SOURCE EXPLORER</span>
          <h1>Knowledge Base</h1>
          <p>Browse incidents with provenance, status, and technical signals intact.</p>
        </div>
        <div className="search-box">
          <Search size={16} />
          <input
            placeholder="Filter indexed incidents"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
      </div>

      <section className="panel table-panel">
        <div className="table-toolbar">
          <span>
            {loading ? "Loading…" : `${visible.length} incidents visible`}
          </span>
          <span className="badge muted">Public GitHub issues</span>
        </div>
        {visible.length ? (
          <div className="incident-list">
            {visible.map((incident) => (
              <a
                href={incident.source_url}
                target="_blank"
                rel="noreferrer"
                className="incident-row"
                key={incident.id}
              >
                <div className="incident-id">
                  #{String(incident.id).padStart(4, "0")}
                </div>
                <div className="incident-main">
                  <b>{incident.title}</b>
                  <p>
                    {incident.description?.slice(0, 180) ||
                      "No description provided."}
                  </p>
                  <div className="row-tags">
                    <span>{incident.product || "Unknown product"}</span>
                    {incident.error_codes?.slice(0, 3).map((code) => (
                      <span className="code-pill" key={code}>
                        {code}
                      </span>
                    ))}
                  </div>
                </div>
                <div className={`state ${incident.status}`}>{incident.status}</div>
                <ArrowUpRight size={16} />
              </a>
            ))}
          </div>
        ) : (
          <EmptyState
            title="Knowledge base is empty"
            body="Run the GitHub pilot collector to import public incidents."
          />
        )}
      </section>
    </div>
  );
}

function SearchLab() {
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!query) return;

    setBusy(true);
    try {
      setResponse(await searchIncidents(query));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page-stack">
      <div className="page-title">
        <div>
          <span className="eyebrow">RETRIEVAL OBSERVATORY</span>
          <h1>Search Lab</h1>
          <p>
            Inspect how FAISS, RRF, and Cross-Encoder ranking surface incident
            and documentation evidence.
          </p>
        </div>
      </div>

      <form className="search-hero" onSubmit={submit}>
        <Search size={20} />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Try: authentication 401, webhook timeout, database migration…"
        />
        <button className="primary-button" disabled={busy}>
          {busy ? "Searching…" : "Search"}
        </button>
      </form>

      {response && (
        <>
          <div className="retrieval-meta">
            <span>{response.results.length} results</span>
            <span>{response.retrieval_method}</span>
            <span>{response.dense_backend}</span>
            <span>{response.reranker_status}</span>
            <span>{response.latency_ms} ms</span>
          </div>
          <div className="result-grid">
            {response.results.map((item) => (
              <a
                className="evidence-card"
                href={item.source_url}
                target="_blank"
                rel="noreferrer"
                key={`${item.source_type}:${item.source_id}`}
              >
                <div>
                  <span className="rank">0{item.rank}</span>
                  <b>{item.title}</b>
                </div>
                <p>{item.excerpt}</p>
                <small>
                  {item.verification} · {item.metadata.product || item.source_type}
                </small>
              </a>
            ))}
          </div>
          {!response.results.length && (
            <EmptyState
              title="No reliable match"
              body="Try an exact error code, product name, or component."
            />
          )}
        </>
      )}
    </div>
  );
}

function Sources() {
  const [sources, setSources] = useState<DataSource[]>([]);
  const [repository, setRepository] = useState("appsmithorg/appsmith");
  const [limit, setLimit] = useState(50);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const refresh = () => getSources().then(setSources);

  useEffect(() => {
    void refresh();
  }, []);

  const run = async () => {
    setBusy(true);
    setMessage("");
    try {
      const result = await syncGithub(repository, limit);
      setMessage(`${result.items_created} new issues imported · ${result.items_seen} seen`);
      void refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Sync failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page-stack">
      <div className="page-title">
        <div>
          <span className="eyebrow">INGESTION CONTROL</span>
          <h1>Data Sources</h1>
          <p>
            Run bounded syncs with source provenance. Model downloads require a
            separate STANDARD setup.
          </p>
        </div>
      </div>

      <section className="panel connector-panel">
        <div className="connector-logo">
          <GitBranch size={24} />
        </div>
        <div className="connector-copy">
          <span className="eyebrow">OFFICIAL REST API</span>
          <h2>GitHub Issues</h2>
          <p>
            Collect public issues, labels, error signatures, and original URLs.
            Pull requests are excluded.
          </p>
        </div>
        <div className="connector-controls">
          <input
            value={repository}
            onChange={(event) => setRepository(event.target.value)}
            placeholder="owner/repository"
          />
          <div className="limit-control">
            <label htmlFor="sync-limit">Limit</label>
            <input
              id="sync-limit"
              type="number"
              min={1}
              max={100}
              value={limit}
              onChange={(event) => setLimit(Number(event.target.value))}
            />
          </div>
          <button className="primary-button" onClick={run} disabled={busy}>
            <RefreshCw className={busy ? "spin" : ""} size={16} />
            {busy ? "Syncing…" : "Run pilot sync"}
          </button>
        </div>
        {message && <div className="sync-message">{message}</div>}
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">CONFIGURED SOURCES</span>
            <h2>Provenance registry</h2>
          </div>
        </div>
        {sources.length ? (
          sources.map((source) => (
            <div className="source-row" key={source.id}>
              <div className="source-icon">
                <GitBranch size={16} />
              </div>
              <div>
                <b>{source.name}</b>
                <small>{source.uri}</small>
              </div>
              <span className="badge success">
                {source.last_synced_at ? "Synced" : "Ready"}
              </span>
            </div>
          ))
        ) : (
          <EmptyState
            title="No source configured"
            body="Run a bounded GitHub pilot sync above."
          />
        )}
      </section>
    </div>
  );
}

export function App() {
  const [view, setView] = useState<View>("overview");
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);

  useEffect(() => {
    getDashboard()
      .then(setDashboard)
      .catch(() =>
        setDashboard({
          incidents: 0,
          documents: 0,
          images: 0,
          logs: 0,
          tickets: 0,
          products: [],
          frequent_errors: [],
          recent_syncs: [],
          search_mode: "LIGHT",
        }),
      );
  }, [view]);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <Headphones size={18} />
          </div>
          <div>
            <b>supportfusion</b>
            <span>AI OPERATIONS</span>
          </div>
        </div>

        <div className="workspace-switcher">
          <span className="workspace-dot" />
          Local workspace
          <span>⌄</span>
        </div>

        <nav>
          {navigation.map((item) => (
            <button
              className={view === item.id ? "active" : ""}
              onClick={() => setView(item.id)}
              key={item.id}
            >
              <item.icon size={17} />
              {item.label}
              {item.id === "copilot" && <span className="nav-new">NEW</span>}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="mode-card">
            <div className="mode-line">
              <span className="live-dot" />
              {dashboard?.search_mode || "LIGHT"} mode
            </div>
            <p>CPU-friendly retrieval active</p>
          </div>
          <div className="user-row">
            <div className="avatar">BB</div>
            <div>
              <b>Bilal Bouizdouzene</b>
              <small>Engineer workspace</small>
            </div>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumb">
            <span>Workspace</span>
            <b>/</b>
            <strong>{navigation.find((item) => item.id === view)?.label}</strong>
          </div>
          <div className="top-actions">
            <span className="connection">
              <span className="live-dot" /> API connected
            </span>
            <button className="icon-button" aria-label="Messages">
              <MessageSquare size={17} />
            </button>
            <button className="icon-button" aria-label="Activity">
              <Activity size={17} />
            </button>
          </div>
        </header>

        {view === "overview" && (
          <Overview dashboard={dashboard} onNavigate={setView} />
        )}
        {view === "copilot" && <Copilot />}
        {view === "knowledge" && <KnowledgeBase />}
        {view === "search" && <SearchLab />}
        {view === "sources" && <Sources />}
      </main>
    </div>
  );
}

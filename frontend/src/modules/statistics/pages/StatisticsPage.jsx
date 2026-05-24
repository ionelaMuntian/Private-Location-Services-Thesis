import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  LineChart, Line, Cell,
} from "recharts";
import "../styles/statistics.css";

const BENCHMARK_URL = "http://127.0.0.1:8000/client/poi/benchmark";
const HISTORY_URL = "http://127.0.0.1:8000/client/poi/benchmark/history";
const SIM_URL = "http://127.0.0.1:8000/client/poi/simulate-performance";
const SIM_HISTORY_URL = "http://127.0.0.1:8000/client/poi/simulate-performance/history";
const BENCHMARK_TIMEOUT_MS = 7200000;
const SIM_TIMEOUT_MS = 14400000; // 4 h — openfhe_ss × 60 calls

const CATEGORIES = ["hospital", "school", "university", "hotel", "clinic", "bank"];
const SCHEME_OPTIONS = ["plaintext", "ckks", "concrete", "openfhe_ss"];
const CONCRETE_N_OPTIONS = [1, 5, 12, 13, 14, 15];
const OPENFHE_N_OPTIONS = [1, 5, 12, 13, 14, 15, 22, 43, 62, 122];
const DEFAULT_LAT = 46.77;
const DEFAULT_LON = 23.59;

function fmtMs(v) {
  if (v === null || v === undefined) return "—";
  const n = Number(v);
  if (isNaN(n)) return "—";
  if (n >= 60000) return `${(n / 60000).toFixed(1)} min`;
  if (n >= 1000) return `${(n / 1000).toFixed(2)} s`;
  return `${n.toFixed(1)} ms`;
}

function fmtBytes(v) {
  if (v === null || v === undefined || v === 0) return v === 0 ? "0 B" : "—";
  const n = Number(v);
  if (isNaN(n) || n === 0) return "—";
  if (n >= 1048576) return `${(n / 1048576).toFixed(2)} MB`;
  if (n >= 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${n} B`;
}

function fmtTimestamp(ts) {
  if (!ts) return "";
  const d = new Date(ts);
  return d.toLocaleString("en-GB", {
    day: "2-digit", month: "short",
    hour: "2-digit", minute: "2-digit",
  });
}

export default function StatisticsPage() {
  const navigate = useNavigate();

  const [category, setCategory] = useState("clinic");
  const [lat, setLat] = useState(DEFAULT_LAT);
  const [lon, setLon] = useState(DEFAULT_LON);
  const [selectedSchemes, setSelectedSchemes] = useState(["plaintext", "ckks", "openfhe_ss"]);
  const [selectedN, setSelectedN] = useState([]);

  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [progress, setProgress] = useState("");
  const [error, setError] = useState("");

  const [history, setHistory] = useState([]);
  const [currentSession, setCurrentSession] = useState(null);

  // --- Performance simulation state ---
  const [simLoading, setSimLoading] = useState(false);
  const [simError, setSimError] = useState("");
  const [simSession, setSimSession] = useState(null);
  const [simHistory, setSimHistory] = useState([]);
  const [simElapsed, setSimElapsed] = useState(0);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) { setHistoryLoading(false); return; }

    const benchmarkReq = axios
      .get(HISTORY_URL, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => {
        const sessions = res.data?.sessions || [];
        setHistory(sessions);
        if (sessions.length > 0) setCurrentSession(sessions[0]);
      })
      .catch(() => {});

    const simReq = axios
      .get(SIM_HISTORY_URL, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => {
        const sessions = res.data?.sessions || [];
        setSimHistory(sessions);
        if (sessions.length > 0) setSimSession(sessions[0]);
      })
      .catch(() => {});

    Promise.allSettled([benchmarkReq, simReq]).finally(() => setHistoryLoading(false));
  }, []);

  const toggleScheme = (s) =>
    setSelectedSchemes((prev) =>
      prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]
    );

  const toggleN = (n) =>
    setSelectedN((prev) =>
      prev.includes(n) ? prev.filter((x) => x !== n) : [...prev, n]
    );

  const hasConcrete = selectedSchemes.includes("concrete");
  const hasOpenfhe = selectedSchemes.includes("openfhe_ss");
  const availableN = hasConcrete
    ? CONCRETE_N_OPTIONS
    : hasOpenfhe
    ? OPENFHE_N_OPTIONS
    : [];

  useEffect(() => {
    setSelectedN((prev) => prev.filter((n) => availableN.includes(n)));
  }, [hasConcrete, hasOpenfhe]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleRunBenchmark = async () => {
    const token = localStorage.getItem("access_token");
    if (!token) { navigate("/login"); return; }
    setLoading(true);
    setError("");
    setCurrentSession(null);
    const concreteNValues = hasConcrete
      ? [...selectedN].filter((n) => CONCRETE_N_OPTIONS.includes(n)).sort((a, b) => a - b)
      : [];
    const openfheNValues = hasOpenfhe
      ? [...selectedN].filter((n) => OPENFHE_N_OPTIONS.includes(n)).sort((a, b) => a - b)
      : [];
    const total = selectedSchemes.length + concreteNValues.length + openfheNValues.length;
    setProgress(`Starting benchmark (${total} runs)…`);
    try {
      const response = await axios.post(
        BENCHMARK_URL,
        {
          category,
          latitude: Number(lat),
          longitude: Number(lon),
          k: 1,
          schemes: selectedSchemes,
          concrete_n_values: concreteNValues,
          openfhe_n_values: openfheNValues,
        },
        {
          headers: { Authorization: `Bearer ${token}` },
          timeout: BENCHMARK_TIMEOUT_MS,
          onDownloadProgress: () =>
            setProgress("Benchmark running — waiting for all schemes to complete…"),
        }
      );
      const session = response.data;
      setCurrentSession(session);
      setHistory((prev) => [session, ...prev].slice(0, 20));
      setProgress("");
    } catch (err) {
      const msg =
        err?.response?.data?.detail?.detail ||
        err?.response?.data?.detail ||
        err?.message ||
        "Benchmark failed.";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setLoading(false);
    }
  };

  const handleRunSimulation = async () => {
    const token = localStorage.getItem("access_token");
    if (!token) { navigate("/login"); return; }
    setSimLoading(true);
    setSimError("");
    setSimElapsed(0);

    const startMs = Date.now();
    const ticker = setInterval(() => setSimElapsed(Math.floor((Date.now() - startMs) / 1000)), 1000);

    try {
      const response = await axios.post(
        SIM_URL,
        {},
        { headers: { Authorization: `Bearer ${token}` }, timeout: SIM_TIMEOUT_MS }
      );
      const session = response.data;
      setSimSession(session);
      setSimHistory((prev) => [session, ...prev].slice(0, 10));
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || "Simulation failed.";
      setSimError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      clearInterval(ticker);
      setSimLoading(false);
    }
  };

  const runs = currentSession?.runs || [];
  const successRuns = runs.filter((r) => !r.error);
  const concreteNRuns = runs
    .filter((r) => r.scheme === "concrete" && r.label !== "concrete" && !r.error)
    .sort((a, b) => (a.n_candidates || 0) - (b.n_candidates || 0));
  const openfheNRuns = runs
    .filter((r) => r.scheme === "openfhe_ss" && r.label !== "openfhe_ss" && !r.error)
    .sort((a, b) => (a.n_candidates || 0) - (b.n_candidates || 0));

  const phaseData = successRuns.map((r) => {
    const enc = r.timing?.encrypt_ms || 0;
    const srv = r.timing?.server_eval_ms || 0;
    const dec = r.timing?.decrypt_ms || 0;
    const upl = r.timing?.upload_ms || 0;
    const fch = r.timing?.fetch_ms || 0;
    const tot = r.timing?.client_total_ms || 0;
    const other = Math.max(0, tot - enc - srv - dec - upl - fch);
    return {
      name: r.label,
      "Encrypt": +enc.toFixed(1),
      "Server eval": +srv.toFixed(1),
      "Decrypt": +dec.toFixed(1),
      "Other": +other.toFixed(1),
    };
  });

  const allNScaleN = [...new Set([
    ...concreteNRuns.map((r) => r.n_candidates),
    ...openfheNRuns.map((r) => r.n_candidates),
  ])].sort((a, b) => a - b);
  const lineData = allNScaleN.map((n) => {
    const cr = concreteNRuns.find((r) => r.n_candidates === n);
    const or = openfheNRuns.find((r) => r.n_candidates === n);
    const entry = { N: n };
    if (cr) entry["Concrete total"] = +(cr.timing?.client_total_ms || 0).toFixed(1);
    if (or) entry["OpenFHE SS total"] = +(or.timing?.client_total_ms || 0).toFixed(1);
    return entry;
  });

  const sizeData = successRuns
    .filter((r) => (r.sizes?.ciphertext_bytes || 0) + (r.sizes?.key_bytes || 0) > 0)
    .map((r) => ({
      name: r.label,
      "Ciphertext": r.sizes?.ciphertext_bytes ?? 0,
      "Keys": r.sizes?.key_bytes ?? 0,
    }));

  const accuracyData = successRuns
    .filter((r) => r.accuracy != null && r.scheme !== "plaintext")
    .map((r) => ({
      name: r.label,
      "Relative error (%)": +(r.accuracy?.relative_error_pct ?? 0).toFixed(2),
      match: r.accuracy?.top1_match,
    }));

  return (
    <div className="stats-page">
      <div className="poi-background-grid" />

      <div className="poi-shell">
        <aside className="poi-sidebar">
          <div className="poi-sidebar-card">
            <p className="poi-sidebar-kicker">Services</p>
            <nav className="poi-sidebar-nav">
              <button className="poi-nav-item" type="button" onClick={() => navigate("/poi-search")}>
                Nearest POI Search
              </button>
              <button className="poi-nav-item" type="button" onClick={() => navigate("/location-sharing")}>
                Location Sharing
              </button>
              <button className="poi-nav-item" type="button" onClick={() => navigate("/anomaly-detection")}>
                Impossible Travel Detection
              </button>
              <button className="poi-nav-item active" type="button">
                Statistics &amp; Benchmarks
              </button>
            </nav>
            <button className="poi-back-btn" type="button" onClick={() => navigate("/home")}>
              Back to Dashboard
            </button>
          </div>
        </aside>

        <main className="poi-main">
          <div className="poi-container">
            <header className="poi-topbar">
              <div>
                <p className="poi-eyebrow">Performance Analysis</p>
                <h1>Statistics &amp; Benchmarks</h1>
                <p className="poi-subtitle">
                  Compare standard FHE metrics across schemes: encryption time, server evaluation,
                  decryption, and communication overhead. Results are saved and reload automatically.
                </p>
              </div>
            </header>

            {/* Config card */}
            <div className="stats-config-card poi-card">
              <div className="poi-card-header">
                <h3>Benchmark Configuration</h3>
              </div>

              <div className="stats-config-grid">
                <label className="stats-label">
                  Category
                  <select value={category} onChange={(e) => setCategory(e.target.value)} className="stats-input">
                    {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                </label>

                <label className="stats-label">
                  Latitude (°)
                  <input type="number" value={lat} onChange={(e) => setLat(e.target.value)} className="stats-input" step="any" />
                </label>

                <label className="stats-label">
                  Longitude (°)
                  <input type="number" value={lon} onChange={(e) => setLon(e.target.value)} className="stats-input" step="any" />
                </label>

                <div className="stats-label">
                  Schemes
                  <div className="stats-checkbox-row">
                    {SCHEME_OPTIONS.map((s) => (
                      <label key={s} className="stats-checkbox-label">
                        <input
                          type="checkbox"
                          checked={selectedSchemes.includes(s)}
                          onChange={() => toggleScheme(s)}
                        />
                        {s}
                      </label>
                    ))}
                  </div>
                </div>

                {(hasConcrete || hasOpenfhe) && (
                  <div className="stats-label">
                    {hasConcrete && hasOpenfhe
                      ? "Concrete + OpenFHE SS N-scaling runs"
                      : hasConcrete
                      ? "Concrete N-scaling runs"
                      : "OpenFHE SS N-scaling runs"}
                    <div className="stats-checkbox-row">
                      {availableN.map((n) => (
                        <label key={n} className="stats-checkbox-label">
                          <input
                            type="checkbox"
                            checked={selectedN.includes(n)}
                            onChange={() => toggleN(n)}
                          />
                          N={n}
                        </label>
                      ))}
                    </div>
                    <p className="stats-hint">
                      {hasConcrete && hasOpenfhe
                        ? "Only N values with pre-compiled Concrete circuits are available when both schemes are selected. OpenFHE SS runs use the matching dataset category for each N."
                        : hasConcrete
                        ? "Concrete N-scaling runs execute one pre-compiled circuit per N value. Large values can take several minutes."
                        : "OpenFHE SS N-scaling runs use the dataset category that naturally has ~N POIs. OpenFHE SS always pads to 128 slots internally."}
                    </p>
                  </div>
                )}
              </div>

              <button
                className="primary-btn stats-run-btn"
                onClick={handleRunBenchmark}
                disabled={loading || (selectedSchemes.length === 0 && selectedN.length === 0)}
              >
                {loading ? "Running benchmark…" : "Run Benchmark"}
              </button>

              {loading && progress && <p className="stats-progress">{progress}</p>}
              {error && <div className="poi-alert poi-alert-error">{error}</div>}
            </div>

            {/* History browser */}
            {!historyLoading && history.length > 0 && (
              <div className="poi-card stats-section">
                <div className="poi-card-header">
                  <h3>Session History</h3>
                  <p>
                    Results are persisted across container restarts.
                    Click a session to view its results.
                  </p>
                </div>
                <div className="stats-history-scroll">
                  {history.map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      className={`stats-session-card${currentSession?.id === s.id ? " active" : ""}`}
                      onClick={() => setCurrentSession(s)}
                    >
                      <span className="stats-session-time">{fmtTimestamp(s.timestamp)}</span>
                      <span className="stats-session-cat">{s.category}</span>
                      <span className="stats-session-runs">
                        {(s.runs || []).filter((r) => !r.error).length} / {(s.runs || []).length} runs
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Empty state */}
            {!historyLoading && !loading && runs.length === 0 && (
              <div className="poi-card stats-section stats-empty">
                <p>No benchmark data yet. Configure the options above and click <strong>Run Benchmark</strong>.</p>
                <p className="stats-hint">Results will be saved and automatically reloaded on your next visit.</p>
              </div>
            )}

            {/* HE paper metrics table */}
            {runs.length > 0 && (
              <div className="poi-card stats-section">
                <div className="poi-card-header">
                  <h3>FHE Performance Metrics</h3>
                  <p>
                    Standard metrics from FHE research papers — encryption time, server-side evaluation,
                    decryption, and communication overhead.
                    {currentSession?.timestamp && (
                      <span className="stats-session-badge">
                        {fmtTimestamp(currentSession.timestamp)} · {currentSession.category}
                      </span>
                    )}
                  </p>
                </div>
                <div className="poi-table-wrap">
                  <table className="poi-table stats-metrics-table">
                    <thead>
                      <tr>
                        <th>Scheme</th>
                        <th>N POIs</th>
                        <th title="Client: prepare_query_ms">Encrypt</th>
                        <th title="Concrete: upload_keys_ms">Key upload</th>
                        <th title="Concrete: candidate_fetch_ms">Fetch cand.</th>
                        <th title="Server: evaluation_ms or computation_ms">Server eval</th>
                        <th title="Client: parse_response_ms">Decrypt</th>
                        <th>Client total</th>
                        <th>Server total</th>
                        <th>Ciphertext</th>
                        <th>Eval keys</th>
                      </tr>
                    </thead>
                    <tbody>
                      {runs.map((r) =>
                        r.error ? (
                          <tr key={r.label} className="stats-error-row">
                            <td><strong>{r.label}</strong></td>
                            <td colSpan={10} className="stats-error-cell">{r.error}</td>
                          </tr>
                        ) : (
                          <tr key={r.label}>
                            <td><strong>{r.label}</strong></td>
                            <td>{r.n_candidates ?? "—"}</td>
                            <td>{fmtMs(r.timing?.encrypt_ms)}</td>
                            <td>{fmtMs(r.timing?.upload_ms)}</td>
                            <td>{fmtMs(r.timing?.fetch_ms)}</td>
                            <td className="stats-highlight-cell">{fmtMs(r.timing?.server_eval_ms)}</td>
                            <td>{fmtMs(r.timing?.decrypt_ms)}</td>
                            <td><strong>{fmtMs(r.timing?.client_total_ms)}</strong></td>
                            <td>{fmtMs(r.timing?.server_total_ms)}</td>
                            <td>{fmtBytes(r.sizes?.ciphertext_bytes)}</td>
                            <td>{fmtBytes(r.sizes?.key_bytes)}</td>
                          </tr>
                        )
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Accuracy table */}
            {successRuns.some((r) => r.accuracy != null) && (
              <div className="poi-card stats-section">
                <div className="poi-card-header">
                  <h3>Result Accuracy</h3>
                  <p>
                    Plaintext is the ground truth. Each HE scheme is evaluated on whether it returns
                    the correct nearest POI and how close its reported distance is to the true distance.
                  </p>
                </div>
                <div className="poi-table-wrap">
                  <table className="poi-table stats-metrics-table">
                    <thead>
                      <tr>
                        <th>Scheme</th>
                        <th>N POIs</th>
                        <th>POI returned</th>
                        <th>Distance (km)</th>
                        <th>Top-1 correct</th>
                        <th title="|d_HE − d_plaintext|">Distance error</th>
                        <th title="|d_HE − d_plaintext| / d_plaintext × 100">Relative error</th>
                      </tr>
                    </thead>
                    <tbody>
                      {successRuns.map((r) => {
                        const acc = r.accuracy;
                        const isPlaintext = r.scheme === "plaintext";
                        const match = acc?.top1_match;
                        return (
                          <tr key={r.label}>
                            <td><strong>{r.label}</strong></td>
                            <td>{r.n_candidates ?? "—"}</td>
                            <td className="stats-poi-name">{r.result?.name ?? "—"}</td>
                            <td>{r.result?.distance_km != null ? `${Number(r.result.distance_km).toFixed(4)} km` : "—"}</td>
                            <td>
                              {isPlaintext ? (
                                <span className="stats-badge stats-badge-ref">reference</span>
                              ) : match === true ? (
                                <span className="stats-badge stats-badge-ok">✓ yes</span>
                              ) : match === false ? (
                                <span className="stats-badge stats-badge-err">✗ no</span>
                              ) : "—"}
                            </td>
                            <td>
                              {isPlaintext ? "0.0000 km" : acc?.distance_error_km != null ? `${acc.distance_error_km.toFixed(4)} km` : "—"}
                            </td>
                            <td className={acc?.relative_error_pct > 5 ? "stats-error-cell" : ""}>
                              {isPlaintext ? "0.00 %" : acc?.relative_error_pct != null ? `${acc.relative_error_pct.toFixed(2)} %` : "—"}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Relative error bar chart */}
                {accuracyData.length > 0 && (
                  <div className="stats-accuracy-chart">
                    <p className="stats-accuracy-chart-label">Relative distance error vs plaintext ground truth</p>
                    <ResponsiveContainer width="100%" height={220}>
                      <BarChart
                        data={accuracyData}
                        margin={{ top: 8, right: 16, left: 0, bottom: 48 }}
                        barCategoryGap="35%"
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(28,105,115,0.1)" />
                        <XAxis
                          dataKey="name"
                          tick={{ fontSize: 11, fill: "#6b655d" }}
                          angle={-30}
                          textAnchor="end"
                          interval={0}
                        />
                        <YAxis
                          tick={{ fontSize: 11, fill: "#6b655d" }}
                          tickFormatter={(v) => `${v}%`}
                          domain={[0, "auto"]}
                        />
                        <Tooltip
                          formatter={(v) => [`${v} %`, "Relative error"]}
                          contentStyle={{ borderRadius: 10, fontSize: 12 }}
                        />
                        <Bar dataKey="Relative error (%)" radius={[4, 4, 0, 0]}>
                          {accuracyData.map((entry, i) => (
                            <Cell
                              key={i}
                              fill={
                                entry.match === false ? "#c94040"
                                : entry["Relative error (%)"] > 5 ? "#e06b2d"
                                : "#1c6973"
                              }
                            />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                    <p className="stats-hint" style={{ textAlign: "center" }}>
                      Green = correct POI, orange = small error (&gt;5%), red = wrong POI returned
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Charts */}
            {successRuns.length > 0 && (
              <div className="stats-charts-grid">

                {/* Phase breakdown stacked bar */}
                <div className="poi-card stats-chart-card">
                  <div className="poi-card-header">
                    <h3>Time Breakdown by Phase</h3>
                    <p>Encrypt · Server eval · Decrypt · Other client overhead (stacked).</p>
                  </div>
                  <ResponsiveContainer width="100%" height={320}>
                    <BarChart data={phaseData} margin={{ top: 8, right: 16, left: 0, bottom: 72 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(28,105,115,0.1)" />
                      <XAxis
                        dataKey="name"
                        tick={{ fontSize: 11, fill: "#6b655d" }}
                        angle={-35}
                        textAnchor="end"
                        interval={0}
                      />
                      <YAxis
                        tick={{ fontSize: 11, fill: "#6b655d" }}
                        tickFormatter={(v) =>
                          v >= 60000 ? `${(v / 60000).toFixed(0)}min`
                          : v >= 1000 ? `${(v / 1000).toFixed(0)}s`
                          : `${v}ms`
                        }
                      />
                      <Tooltip
                        formatter={(v, name) => [fmtMs(v), name]}
                        contentStyle={{ borderRadius: 10, fontSize: 12 }}
                      />
                      <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
                      <Bar dataKey="Encrypt" stackId="a" fill="#1c6973" />
                      <Bar dataKey="Server eval" stackId="a" fill="#5ba3aa" />
                      <Bar dataKey="Decrypt" stackId="a" fill="#e89a5d" />
                      <Bar dataKey="Other" stackId="a" fill="#d0cbc3" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                {/* Communication overhead */}
                {sizeData.length > 0 && (
                  <div className="poi-card stats-chart-card">
                    <div className="poi-card-header">
                      <h3>Communication Overhead</h3>
                      <p>Bytes sent to server per query: ciphertext + evaluation keys.</p>
                    </div>
                    <ResponsiveContainer width="100%" height={320}>
                      <BarChart data={sizeData} margin={{ top: 8, right: 16, left: 0, bottom: 72 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(28,105,115,0.1)" />
                        <XAxis
                          dataKey="name"
                          tick={{ fontSize: 11, fill: "#6b655d" }}
                          angle={-35}
                          textAnchor="end"
                          interval={0}
                        />
                        <YAxis
                          tick={{ fontSize: 11, fill: "#6b655d" }}
                          tickFormatter={(v) =>
                            v >= 1048576 ? `${(v / 1048576).toFixed(1)}MB`
                            : v >= 1024 ? `${(v / 1024).toFixed(0)}KB`
                            : `${v}B`
                          }
                        />
                        <Tooltip
                          formatter={(v, name) => [fmtBytes(v), name]}
                          contentStyle={{ borderRadius: 10, fontSize: 12 }}
                        />
                        <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
                        <Bar dataKey="Ciphertext" stackId="b" fill="#1c6973" />
                        <Bar dataKey="Keys" stackId="b" fill="#e89a5d" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}

                {/* N vs latency (shown when ≥2 N-scaling runs exist across either scheme) */}
                {(concreteNRuns.length >= 2 || openfheNRuns.length >= 2) && (
                  <div className="poi-card stats-chart-card">
                    <div className="poi-card-header">
                      <h3>N vs Latency</h3>
                      <p>Client-side total latency as the number of candidate POIs grows.</p>
                    </div>
                    <ResponsiveContainer width="100%" height={320}>
                      <LineChart data={lineData} margin={{ top: 8, right: 16, left: 0, bottom: 24 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(28,105,115,0.1)" />
                        <XAxis
                          dataKey="N"
                          label={{ value: "N candidates", position: "insideBottom", offset: -12, fontSize: 11, fill: "#6b655d" }}
                          tick={{ fontSize: 11, fill: "#6b655d" }}
                        />
                        <YAxis
                          tick={{ fontSize: 11, fill: "#6b655d" }}
                          tickFormatter={(v) =>
                            v >= 60000 ? `${(v / 60000).toFixed(0)}min`
                            : v >= 1000 ? `${(v / 1000).toFixed(0)}s`
                            : `${v}ms`
                          }
                        />
                        <Tooltip
                          formatter={(v, name) => [fmtMs(v), name]}
                          contentStyle={{ borderRadius: 10, fontSize: 12 }}
                        />
                        <Legend wrapperStyle={{ fontSize: 12 }} />
                        {concreteNRuns.length >= 1 && (
                          <Line type="monotone" dataKey="Concrete total" stroke="#1c6973" strokeWidth={2} dot={{ r: 4 }} />
                        )}
                        {openfheNRuns.length >= 1 && (
                          <Line type="monotone" dataKey="OpenFHE SS total" stroke="#e06b2d" strokeWidth={2} strokeDasharray="5 3" dot={{ r: 4 }} />
                        )}
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>
            )}
            {/* ================================================================
                PERFORMANCE SIMULATION SECTION
            ================================================================ */}
            <div className="stats-sim-divider">
              <span>Performance Simulation</span>
            </div>

            {/* Simulation trigger card */}
            <div className="poi-card stats-section">
              <div className="poi-card-header">
                <h3>Compute Performance</h3>
                <p>
                  Runs each FHE scheme over <strong>10 simulated user locations × 6 categories</strong>,
                  comparing results against plaintext ground truth.
                  Computes Top-1 accuracy, mean distance error, RMSE, and relative error per scheme and category.
                </p>
                <p className="stats-hint">
                  Estimated time: Concrete ~5–60 min · OpenFHE SS ~30 min.
                  Runs are sequential to keep memory usage low. Results persist across container restarts.
                </p>
              </div>

              <button
                className="primary-btn stats-run-btn"
                onClick={handleRunSimulation}
                disabled={simLoading}
              >
                {simLoading
                  ? `Running simulation… ${simElapsed > 0 ? `(${simElapsed}s elapsed)` : ""}`
                  : "Compute Performance"}
              </button>

              {simError && <div className="poi-alert poi-alert-error" style={{ marginTop: 12 }}>{simError}</div>}
            </div>

            {/* Simulation history browser */}
            {simHistory.length > 0 && (
              <div className="poi-card stats-section">
                <div className="poi-card-header">
                  <h3>Simulation History</h3>
                  <p>Click a past session to view its accuracy results.</p>
                </div>
                <div className="stats-history-scroll">
                  {simHistory.map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      className={`stats-session-card${simSession?.id === s.id ? " active" : ""}`}
                      onClick={() => setSimSession(s)}
                    >
                      <span className="stats-session-time">{fmtTimestamp(s.timestamp)}</span>
                      <span className="stats-session-cat">{s.n_test_points} points</span>
                      <span className="stats-session-runs">
                        {(s.schemes || []).join(" · ")}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Simulation results */}
            {simSession?.summary && <SimulationResults session={simSession} />}
          </div>
        </main>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// SimulationResults — rendered below the main page when simulation data exists
// ---------------------------------------------------------------------------
const SIM_SCHEME_LABELS = { concrete: "Concrete PBS", openfhe_ss: "OpenFHE SS" };
const SIM_SCHEME_COLORS = { concrete: "#1c6973", openfhe_ss: "#e06b2d" };

function SimulationResults({ session }) {
  const { summary, n_test_points, timestamp, categories = [], schemes = [] } = session;

  // Overall summary table rows
  const summaryRows = schemes.map((s) => {
    const d = summary[s] || {};
    return { scheme: s, ...d };
  });

  // Per-category accuracy chart data — one entry per category
  const catAccData = (categories.length ? categories : ["hospital","school","university","hotel","clinic","bank"])
    .map((cat) => {
      const entry = { category: cat };
      schemes.forEach((s) => {
        const acc = summary[s]?.per_category?.[cat]?.top1_accuracy;
        entry[SIM_SCHEME_LABELS[s] || s] = acc != null ? +(acc * 100).toFixed(1) : null;
      });
      return entry;
    });

  // Per-category mean distance error chart data
  const catErrData = (categories.length ? categories : ["hospital","school","university","hotel","clinic","bank"])
    .map((cat) => {
      const entry = { category: cat };
      schemes.forEach((s) => {
        const err = summary[s]?.per_category?.[cat]?.mean_distance_error_km;
        entry[SIM_SCHEME_LABELS[s] || s] = err != null ? +err.toFixed(4) : null;
      });
      return entry;
    });

  return (
    <>
      {/* Overall summary table */}
      <div className="poi-card stats-section">
        <div className="poi-card-header">
          <h3>Overall Accuracy Summary</h3>
          <p>
            Aggregated over {n_test_points} test points × {(categories.length || 6)} categories
            = {n_test_points * (categories.length || 6)} queries per scheme.
            {timestamp && (
              <span className="stats-session-badge">{fmtTimestamp(timestamp)}</span>
            )}
          </p>
        </div>
        <div className="poi-table-wrap">
          <table className="poi-table stats-metrics-table">
            <thead>
              <tr>
                <th>Scheme</th>
                <th title="Queries returning the same POI as plaintext">Top-1 accuracy</th>
                <th title="Mean |d_HE − d_plaintext|">Mean dist. error</th>
                <th title="√(mean(|d_HE − d_pt|²)) — standard paper metric">RMSE</th>
                <th title="Worst-case absolute error">Max error</th>
                <th title="Mean (|d_HE − d_pt| / d_pt) × 100">Mean rel. error</th>
                <th>Runs</th>
                <th>Errors</th>
              </tr>
            </thead>
            <tbody>
              {summaryRows.map((r) => (
                <tr key={r.scheme}>
                  <td><strong>{SIM_SCHEME_LABELS[r.scheme] || r.scheme}</strong></td>
                  <td className={r.top1_accuracy != null && r.top1_accuracy < 0.9 ? "stats-error-cell" : "stats-highlight-cell"}>
                    {r.top1_accuracy != null ? `${(r.top1_accuracy * 100).toFixed(1)} %` : "—"}
                  </td>
                  <td>{r.mean_distance_error_km != null ? `${r.mean_distance_error_km.toFixed(4)} km` : "—"}</td>
                  <td>{r.rmse_distance_error_km != null ? `${r.rmse_distance_error_km.toFixed(4)} km` : "—"}</td>
                  <td>{r.max_distance_error_km != null ? `${r.max_distance_error_km.toFixed(4)} km` : "—"}</td>
                  <td>{r.mean_relative_error_pct != null ? `${r.mean_relative_error_pct.toFixed(2)} %` : "—"}</td>
                  <td>{r.total ?? "—"}</td>
                  <td>{r.error_count ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Per-category breakdown table */}
      <div className="poi-card stats-section">
        <div className="poi-card-header">
          <h3>Per-Category Accuracy</h3>
          <p>Top-1 accuracy and mean distance error broken down by POI category.</p>
        </div>
        <div className="poi-table-wrap">
          <table className="poi-table stats-metrics-table">
            <thead>
              <tr>
                <th>Category</th>
                {schemes.flatMap((s) => [
                  <th key={`${s}-acc`}>{(SIM_SCHEME_LABELS[s] || s)} top-1</th>,
                  <th key={`${s}-err`}>{(SIM_SCHEME_LABELS[s] || s)} mean err</th>,
                ])}
              </tr>
            </thead>
            <tbody>
              {(categories.length ? categories : ["hospital","school","university","hotel","clinic","bank"]).map((cat) => (
                <tr key={cat}>
                  <td><strong>{cat}</strong></td>
                  {schemes.flatMap((s) => {
                    const cd = summary[s]?.per_category?.[cat] || {};
                    return [
                      <td key={`${s}-acc`} className={cd.top1_accuracy != null && cd.top1_accuracy < 0.9 ? "stats-error-cell" : ""}>
                        {cd.top1_accuracy != null ? `${(cd.top1_accuracy * 100).toFixed(0)} %` : "—"}
                      </td>,
                      <td key={`${s}-err`}>
                        {cd.mean_distance_error_km != null ? `${cd.mean_distance_error_km.toFixed(4)} km` : "—"}
                      </td>,
                    ];
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Charts */}
      <div className="stats-charts-grid">
        {/* Top-1 accuracy per category */}
        <div className="poi-card stats-chart-card">
          <div className="poi-card-header">
            <h3>Top-1 Accuracy by Category</h3>
            <p>Percentage of test points where the FHE scheme returned the correct nearest POI.</p>
          </div>
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={catAccData} margin={{ top: 8, right: 16, left: 0, bottom: 48 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(28,105,115,0.1)" />
              <XAxis dataKey="category" tick={{ fontSize: 11, fill: "#6b655d" }} angle={-30} textAnchor="end" interval={0} />
              <YAxis tick={{ fontSize: 11, fill: "#6b655d" }} tickFormatter={(v) => `${v}%`} domain={[0, 100]} />
              <Tooltip formatter={(v) => [`${v} %`]} contentStyle={{ borderRadius: 10, fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
              {schemes.map((s) => (
                <Bar key={s} dataKey={SIM_SCHEME_LABELS[s] || s} fill={SIM_SCHEME_COLORS[s] || "#888"} radius={[4, 4, 0, 0]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Mean distance error per category */}
        <div className="poi-card stats-chart-card">
          <div className="poi-card-header">
            <h3>Mean Distance Error by Category</h3>
            <p>Mean |d_HE − d_plaintext| in km — lower is more accurate.</p>
          </div>
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={catErrData} margin={{ top: 8, right: 16, left: 0, bottom: 48 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(28,105,115,0.1)" />
              <XAxis dataKey="category" tick={{ fontSize: 11, fill: "#6b655d" }} angle={-30} textAnchor="end" interval={0} />
              <YAxis tick={{ fontSize: 11, fill: "#6b655d" }} tickFormatter={(v) => `${v} km`} />
              <Tooltip formatter={(v) => [`${v} km`]} contentStyle={{ borderRadius: 10, fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
              {schemes.map((s) => (
                <Bar key={s} dataKey={SIM_SCHEME_LABELS[s] || s} fill={SIM_SCHEME_COLORS[s] || "#888"} radius={[4, 4, 0, 0]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </>
  );
}

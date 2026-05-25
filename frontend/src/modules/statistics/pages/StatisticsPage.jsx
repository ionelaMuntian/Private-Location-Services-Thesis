import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import {
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  LineChart, Line,
} from "recharts";
import "../styles/statistics.css";

const BENCHMARK_URL = "http://127.0.0.1:8000/client/poi/benchmark";
const HISTORY_URL = "http://127.0.0.1:8000/client/poi/benchmark/history";
const SIM_URL = "http://127.0.0.1:8000/client/poi/simulate-performance";
const SIM_HISTORY_URL = "http://127.0.0.1:8000/client/poi/simulate-performance/history";
const BENCHMARK_TIMEOUT_MS = 7200000;
const SIM_TIMEOUT_MS = 14400000;

const SCHEME_OPTIONS = ["plaintext", "concrete", "openfhe_ss"];
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

function fmtMsShort(v) {
  if (v >= 60000) return `${(v / 60000).toFixed(0)}min`;
  if (v >= 1000) return `${(v / 1000).toFixed(0)}s`;
  return `${v}ms`;
}

function fmtBytes(v) {
  if (v === null || v === undefined || v === 0) return v === 0 ? "0 B" : "—";
  const n = Number(v);
  if (isNaN(n) || n === 0) return "—";
  if (n >= 1048576) return `${(n / 1048576).toFixed(2)} MB`;
  if (n >= 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${n} B`;
}

function fmtBytesShort(v) {
  if (v >= 1048576) return `${(v / 1048576).toFixed(1)}MB`;
  if (v >= 1024) return `${(v / 1024).toFixed(0)}KB`;
  return `${v}B`;
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

  const [lat, setLat] = useState(DEFAULT_LAT);
  const [lon, setLon] = useState(DEFAULT_LON);
  const [selectedSchemes, setSelectedSchemes] = useState(["plaintext", "openfhe_ss"]);
  const [selectedN, setSelectedN] = useState([]);

  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [progress, setProgress] = useState("");
  const [error, setError] = useState("");

  const [history, setHistory] = useState([]);
  const [currentSession, setCurrentSession] = useState(null);

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
          category: "hospital",
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

  const allNSpecificRuns = runs.filter((r) =>
    (r.scheme === "concrete" && r.label !== "concrete") ||
    (r.scheme === "openfhe_ss" && r.label !== "openfhe_ss")
  );
  const concreteNRuns = allNSpecificRuns
    .filter((r) => r.scheme === "concrete" && !r.error)
    .sort((a, b) => (a.n_candidates || 0) - (b.n_candidates || 0));
  const openfheNRuns = allNSpecificRuns
    .filter((r) => r.scheme === "openfhe_ss" && !r.error)
    .sort((a, b) => (a.n_candidates || 0) - (b.n_candidates || 0));

  const baseRuns = runs.filter((r) => r.scheme === "plaintext");

  const allNValues = [...new Set(
    allNSpecificRuns.map((r) => r.n_candidates).filter((n) => n != null)
  )].sort((a, b) => a - b);

  const concretePhaseLineData = runs
    .filter((r) => r.scheme === "concrete" && !r.error)
    .sort((a, b) => (a.n_candidates || 0) - (b.n_candidates || 0))
    .map((r) => ({
      name: r.n_candidates != null ? `N=${r.n_candidates}` : r.label,
      "Encrypt": +(r.timing?.encrypt_ms || 0).toFixed(1),
      "Server eval": +(r.timing?.server_eval_ms || 0).toFixed(1),
      "Decrypt": +(r.timing?.decrypt_ms || 0).toFixed(1),
    }));

  const openfhePhaseLineData = runs
    .filter((r) => r.scheme === "openfhe_ss" && !r.error)
    .sort((a, b) => (a.n_candidates || 0) - (b.n_candidates || 0))
    .map((r) => ({
      name: r.n_candidates != null ? `N=${r.n_candidates}` : r.label,
      "Encrypt": +(r.timing?.encrypt_ms || 0).toFixed(1),
      "Server eval": +(r.timing?.server_eval_ms || 0).toFixed(1),
      "Decrypt": +(r.timing?.decrypt_ms || 0).toFixed(1),
    }));

  const concreteSizeData = runs
    .filter((r) => r.scheme === "concrete" && !r.error && (r.sizes?.ciphertext_bytes || 0) + (r.sizes?.key_bytes || 0) > 0)
    .sort((a, b) => (a.n_candidates || 0) - (b.n_candidates || 0))
    .map((r) => ({
      name: r.n_candidates != null ? `N=${r.n_candidates}` : r.label,
      "Ciphertext": r.sizes?.ciphertext_bytes ?? 0,
      "Keys": r.sizes?.key_bytes ?? 0,
    }));

  const openfheSizeData = runs
    .filter((r) => r.scheme === "openfhe_ss" && !r.error && (r.sizes?.ciphertext_bytes || 0) + (r.sizes?.key_bytes || 0) > 0)
    .sort((a, b) => (a.n_candidates || 0) - (b.n_candidates || 0))
    .map((r) => ({
      name: r.n_candidates != null ? `N=${r.n_candidates}` : r.label,
      "Ciphertext": r.sizes?.ciphertext_bytes ?? 0,
      "Keys": r.sizes?.key_bytes ?? 0,
    }));

  const accuracyLineData = allNValues.map((n) => {
    const cr = allNSpecificRuns.find((r) => r.scheme === "concrete" && r.n_candidates === n && !r.error && r.accuracy != null);
    const or = allNSpecificRuns.find((r) => r.scheme === "openfhe_ss" && r.n_candidates === n && !r.error && r.accuracy != null);
    const entry = { N: n };
    if (cr) entry["Concrete"] = +(cr.accuracy?.poi_distance_km ?? 0).toFixed(4);
    if (or) entry["OpenFHE SS"] = +(or.accuracy?.poi_distance_km ?? 0).toFixed(4);
    return entry;
  }).filter((e) => e.Concrete != null || e["OpenFHE SS"] != null);

  const lineData = allNValues.map((n) => {
    const cr = concreteNRuns.find((r) => r.n_candidates === n);
    const or = openfheNRuns.find((r) => r.n_candidates === n);
    const entry = { N: n };
    if (cr) entry["Concrete total"] = +(cr.timing?.client_total_ms || 0).toFixed(1);
    if (or) entry["OpenFHE SS total"] = +(or.timing?.client_total_ms || 0).toFixed(1);
    return entry;
  });

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
              </div>
            </header>

            <div className="stats-config-card poi-card">
              <div className="poi-card-header">
                <h3>Benchmark Configuration</h3>
              </div>

              <div className="stats-config-grid">
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


            {!historyLoading && !loading && runs.length === 0 && (
              <div className="poi-card stats-section stats-empty">
                <p>No benchmark data yet. Configure the options above and click <strong>Run Benchmark</strong>.</p>
              </div>
            )}

            {runs.length > 0 && (
              <div className="poi-card stats-section">
                <div className="poi-card-header">
                  <h3>FHE Performance Metrics</h3>
                </div>
                <div className="stats-plain-wrap">
                  <table className="stats-plain-table">
                    <thead>
                      <tr>
                        <th>N</th>
                        <th>Scheme</th>
                        <th>Encrypt</th>
                        <th>Server eval</th>
                        <th>Decrypt</th>
                        <th>Total</th>
                        <th>Ciphertext</th>
                        <th>Eval keys</th>
                      </tr>
                    </thead>
                    <tbody>
                      {baseRuns.map((r) =>
                        r.error ? (
                          <tr key={r.label}>
                            <td>{r.n_candidates ?? "—"}</td>
                            <td><strong>{r.label}</strong></td>
                            <td colSpan={6}>{r.error}</td>
                          </tr>
                        ) : (
                          <tr key={r.label}>
                            <td>{r.n_candidates ?? "—"}</td>
                            <td><strong>{r.label}</strong></td>
                            <td>{fmtMs(r.timing?.encrypt_ms)}</td>
                            <td>{fmtMs(r.timing?.server_eval_ms)}</td>
                            <td>{fmtMs(r.timing?.decrypt_ms)}</td>
                            <td><strong>{fmtMs(r.timing?.client_total_ms)}</strong></td>
                            <td>{fmtBytes(r.sizes?.ciphertext_bytes)}</td>
                            <td>{fmtBytes(r.sizes?.key_bytes)}</td>
                          </tr>
                        )
                      )}
                      {allNValues.flatMap((n) => {
                        const cr = allNSpecificRuns.find((r) => r.scheme === "concrete" && r.n_candidates === n);
                        const or = allNSpecificRuns.find((r) => r.scheme === "openfhe_ss" && r.n_candidates === n);
                        const schemeRows = [
                          cr ? { label: "Concrete", run: cr } : null,
                          or ? { label: "OpenFHE SS", run: or } : null,
                        ].filter(Boolean);
                        if (schemeRows.length === 0) return [];
                        return schemeRows.map(({ label, run }, idx) => (
                          <tr key={run.label}>
                            {idx === 0 && (
                              <td rowSpan={schemeRows.length}>
                                <strong>{n}</strong>
                              </td>
                            )}
                            {run.error ? (
                              <>
                                <td>{label}</td>
                                <td colSpan={6}>{run.error}</td>
                              </>
                            ) : (
                              <>
                                <td>{label}</td>
                                <td>{fmtMs(run.timing?.encrypt_ms)}</td>
                                <td>{fmtMs(run.timing?.server_eval_ms)}</td>
                                <td>{fmtMs(run.timing?.decrypt_ms)}</td>
                                <td><strong>{fmtMs(run.timing?.client_total_ms)}</strong></td>
                                <td>{fmtBytes(run.sizes?.ciphertext_bytes)}</td>
                                <td>{fmtBytes(run.sizes?.key_bytes)}</td>
                              </>
                            )}
                          </tr>
                        ));
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {successRuns.some((r) => r.accuracy != null) && (
              <div className="poi-card stats-section">
                <div className="poi-card-header">
                  <h3>Result Accuracy</h3>
                </div>
                <div className="stats-plain-wrap">
                  <table className="stats-plain-table">
                    <thead>
                      <tr>
                        <th>N</th>
                        <th>Scheme</th>
                        <th>POI returned</th>
                        <th>Distance (km)</th>
                        <th>Top-1 correct</th>
                        <th>Dist. A→B</th>
                      </tr>
                    </thead>
                    <tbody>
                      {baseRuns.filter((r) => !r.error && r.accuracy != null).map((r) => {
                        const acc = r.accuracy;
                        const isPlaintext = r.scheme === "plaintext";
                        const match = acc?.top1_match;
                        return (
                          <tr key={r.label}>
                            <td>{r.n_candidates ?? "—"}</td>
                            <td><strong>{r.label}</strong></td>
                            <td>{r.result?.name ?? "—"}</td>
                            <td>{r.result?.distance_km != null ? `${Number(r.result.distance_km).toFixed(4)} km` : "—"}</td>
                            <td>{isPlaintext ? "reference" : match === true ? "Yes" : match === false ? "No" : "—"}</td>
                            <td>
                              {isPlaintext ? "—" : acc?.poi_distance_km != null ? `${acc.poi_distance_km.toFixed(4)} km` : "—"}
                            </td>
                          </tr>
                        );
                      })}
                      {allNValues.flatMap((n) => {
                        const cr = allNSpecificRuns.find((r) => r.scheme === "concrete" && r.n_candidates === n && !r.error && r.accuracy != null);
                        const or = allNSpecificRuns.find((r) => r.scheme === "openfhe_ss" && r.n_candidates === n && !r.error && r.accuracy != null);
                        const schemeRows = [
                          cr ? { label: "Concrete", run: cr } : null,
                          or ? { label: "OpenFHE SS", run: or } : null,
                        ].filter(Boolean);
                        if (schemeRows.length === 0) return [];
                        return schemeRows.map(({ label, run }, idx) => {
                          const acc = run.accuracy;
                          const match = acc?.top1_match;
                          return (
                            <tr key={run.label}>
                              {idx === 0 && (
                                <td rowSpan={schemeRows.length}>
                                  <strong>{n}</strong>
                                </td>
                              )}
                              <td>{label}</td>
                              <td>{run.result?.name ?? "—"}</td>
                              <td>{run.result?.distance_km != null ? `${Number(run.result.distance_km).toFixed(4)} km` : "—"}</td>
                              <td>{match === true ? "Yes" : match === false ? "No" : "—"}</td>
                              <td>
                                {acc?.poi_distance_km != null ? `${acc.poi_distance_km.toFixed(4)} km` : "—"}
                              </td>
                            </tr>
                          );
                        });
                      })}
                    </tbody>
                  </table>
                </div>

                {accuracyLineData.length > 0 && (
                  <div className="stats-accuracy-chart">
                    <ResponsiveContainer width="100%" height={220}>
                      <LineChart data={accuracyLineData} margin={{ top: 8, right: 16, left: 0, bottom: 24 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(28,105,115,0.1)" />
                        <XAxis
                          dataKey="N"
                          label={{ value: "N candidates", position: "insideBottom", offset: -12, fontSize: 11, fill: "#6b655d" }}
                          tick={{ fontSize: 11, fill: "#6b655d" }}
                        />
                        <YAxis
                          tick={{ fontSize: 11, fill: "#6b655d" }}
                          tickFormatter={(v) => `${v} km`}
                          domain={[0, "auto"]}
                        />
                        <Tooltip
                          formatter={(v, name) => [`${v} km`, name]}
                          contentStyle={{ borderRadius: 10, fontSize: 12 }}
                        />
                        <Legend wrapperStyle={{ fontSize: 12 }} />
                        <Line type="monotone" dataKey="Concrete" stroke="#2563eb" strokeWidth={2} dot={{ r: 5 }} connectNulls={false} />
                        <Line type="monotone" dataKey="OpenFHE SS" stroke="#e11d48" strokeWidth={2} strokeDasharray="5 3" dot={{ r: 5 }} connectNulls={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>
            )}

            {successRuns.length > 0 && (
              <div className="stats-charts-grid">
                {concretePhaseLineData.length > 0 && (
                  <div className="poi-card stats-chart-card">
                    <div className="poi-card-header">
                      <h3>Time Breakdown — Concrete</h3>
                    </div>
                    <ResponsiveContainer width="100%" height={320}>
                      <LineChart data={concretePhaseLineData} margin={{ top: 8, right: 16, left: 0, bottom: 48 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(28,105,115,0.1)" />
                        <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#6b655d" }} angle={-30} textAnchor="end" interval={0} />
                        <YAxis tick={{ fontSize: 11, fill: "#6b655d" }} tickFormatter={fmtMsShort} />
                        <Tooltip formatter={(v, name) => [fmtMs(v), name]} contentStyle={{ borderRadius: 10, fontSize: 12 }} />
                        <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
                        <Line type="monotone" dataKey="Encrypt" stroke="#2563eb" strokeWidth={2} dot={{ r: 4 }} />
                        <Line type="monotone" dataKey="Server eval" stroke="#e11d48" strokeWidth={2} dot={{ r: 4 }} />
                        <Line type="monotone" dataKey="Decrypt" stroke="#d97706" strokeWidth={2} dot={{ r: 4 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                )}

                {openfhePhaseLineData.length > 0 && (
                  <div className="poi-card stats-chart-card">
                    <div className="poi-card-header">
                      <h3>Time Breakdown — OpenFHE SS</h3>
                    </div>
                    <ResponsiveContainer width="100%" height={320}>
                      <LineChart data={openfhePhaseLineData} margin={{ top: 8, right: 16, left: 0, bottom: 48 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(28,105,115,0.1)" />
                        <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#6b655d" }} angle={-30} textAnchor="end" interval={0} />
                        <YAxis tick={{ fontSize: 11, fill: "#6b655d" }} tickFormatter={fmtMsShort} />
                        <Tooltip formatter={(v, name) => [fmtMs(v), name]} contentStyle={{ borderRadius: 10, fontSize: 12 }} />
                        <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
                        <Line type="monotone" dataKey="Encrypt" stroke="#2563eb" strokeWidth={2} dot={{ r: 4 }} />
                        <Line type="monotone" dataKey="Server eval" stroke="#e11d48" strokeWidth={2} dot={{ r: 4 }} />
                        <Line type="monotone" dataKey="Decrypt" stroke="#d97706" strokeWidth={2} dot={{ r: 4 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                )}

                {concreteSizeData.length > 0 && (
                  <div className="poi-card stats-chart-card">
                    <div className="poi-card-header">
                      <h3>Communication Overhead — Concrete</h3>
                    </div>
                    <ResponsiveContainer width="100%" height={320}>
                      <LineChart data={concreteSizeData} margin={{ top: 8, right: 16, left: 0, bottom: 48 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(28,105,115,0.1)" />
                        <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#6b655d" }} angle={-30} textAnchor="end" interval={0} />
                        <YAxis tick={{ fontSize: 11, fill: "#6b655d" }} tickFormatter={fmtBytesShort} />
                        <Tooltip formatter={(v, name) => [fmtBytes(v), name]} contentStyle={{ borderRadius: 10, fontSize: 12 }} />
                        <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
                        <Line type="monotone" dataKey="Ciphertext" stroke="#1c6973" strokeWidth={2} dot={{ r: 4 }} />
                        <Line type="monotone" dataKey="Keys" stroke="#e89a5d" strokeWidth={2} dot={{ r: 4 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                )}

                {openfheSizeData.length > 0 && (
                  <div className="poi-card stats-chart-card">
                    <div className="poi-card-header">
                      <h3>Communication Overhead — OpenFHE SS</h3>
                    </div>
                    <ResponsiveContainer width="100%" height={320}>
                      <LineChart data={openfheSizeData} margin={{ top: 8, right: 16, left: 0, bottom: 48 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(28,105,115,0.1)" />
                        <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#6b655d" }} angle={-30} textAnchor="end" interval={0} />
                        <YAxis tick={{ fontSize: 11, fill: "#6b655d" }} tickFormatter={fmtBytesShort} />
                        <Tooltip formatter={(v, name) => [fmtBytes(v), name]} contentStyle={{ borderRadius: 10, fontSize: 12 }} />
                        <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
                        <Line type="monotone" dataKey="Ciphertext" stroke="#1c6973" strokeWidth={2} dot={{ r: 4 }} />
                        <Line type="monotone" dataKey="Keys" stroke="#e89a5d" strokeWidth={2} dot={{ r: 4 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                )}

                {lineData.length >= 1 && (concreteNRuns.length >= 1 || openfheNRuns.length >= 1) && (
                  <div className="poi-card stats-chart-card">
                    <div className="poi-card-header">
                      <h3>N vs Latency</h3>
                    </div>
                    <ResponsiveContainer width="100%" height={320}>
                      <LineChart data={lineData} margin={{ top: 8, right: 16, left: 0, bottom: 24 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(28,105,115,0.1)" />
                        <XAxis
                          dataKey="N"
                          label={{ value: "N candidates", position: "insideBottom", offset: -12, fontSize: 11, fill: "#6b655d" }}
                          tick={{ fontSize: 11, fill: "#6b655d" }}
                        />
                        <YAxis tick={{ fontSize: 11, fill: "#6b655d" }} tickFormatter={fmtMsShort} />
                        <Tooltip formatter={(v, name) => [fmtMs(v), name]} contentStyle={{ borderRadius: 10, fontSize: 12 }} />
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

            <div className="stats-sim-divider">
              <span>Performance Simulation</span>
            </div>

            <div className="poi-card stats-section">
              <div className="poi-card-header">
                <h3>Compute Performance</h3>
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

            {simHistory.length > 0 && (
              <div className="poi-card stats-section">
                <div className="poi-card-header">
                  <h3>Simulation History</h3>
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

            {simSession?.summary && <SimulationResults session={simSession} />}
          </div>
        </main>
      </div>
    </div>
  );
}

const SIM_SCHEME_LABELS = { concrete: "Concrete PBS", openfhe_ss: "OpenFHE SS" };
const SIM_SCHEME_COLORS = { concrete: "#1c6973", openfhe_ss: "#e06b2d" };

function SimulationResults({ session }) {
  const { summary, timestamp, categories = [], schemes = [] } = session;

  const summaryRows = schemes.map((s) => {
    const d = summary[s] || {};
    return { scheme: s, ...d };
  });

  const catAccData = (categories.length ? categories : ["hospital", "school", "stationery", "post_office", "cosmetics", "gallery"])
    .map((cat) => {
      const entry = { category: cat };
      schemes.forEach((s) => {
        const acc = summary[s]?.per_category?.[cat]?.top1_accuracy;
        entry[SIM_SCHEME_LABELS[s] || s] = acc != null ? +(acc * 100).toFixed(1) : null;
      });
      return entry;
    });

  const catErrData = (categories.length ? categories : ["hospital", "school", "stationery", "post_office", "cosmetics", "gallery"])
    .map((cat) => {
      const entry = { category: cat };
      schemes.forEach((s) => {
        const err = summary[s]?.per_category?.[cat]?.mean_poi_distance_km;
        entry[SIM_SCHEME_LABELS[s] || s] = err != null ? +err.toFixed(4) : null;
      });
      return entry;
    });

  return (
    <>
      <div className="poi-card stats-section">
        <div className="poi-card-header">
          <h3>Overall Accuracy Summary</h3>
          {timestamp && (
            <span className="stats-session-badge">{fmtTimestamp(timestamp)}</span>
          )}
        </div>
        <div className="stats-plain-wrap">
          <table className="stats-plain-table">
            <thead>
              <tr>
                <th>Scheme</th>
                <th>Top-1 accuracy</th>
                <th>Mean dist. A→B</th>
                <th>RMSE</th>
                <th>Max dist. A→B</th>
                <th>Runs</th>
                <th>Errors</th>
              </tr>
            </thead>
            <tbody>
              {summaryRows.map((r) => (
                <tr key={r.scheme}>
                  <td><strong>{SIM_SCHEME_LABELS[r.scheme] || r.scheme}</strong></td>
                  <td>
                    {r.top1_accuracy != null ? `${(r.top1_accuracy * 100).toFixed(1)} %` : "—"}
                  </td>
                  <td>{r.mean_poi_distance_km != null ? `${r.mean_poi_distance_km.toFixed(4)} km` : "—"}</td>
                  <td>{r.rmse_poi_distance_km != null ? `${r.rmse_poi_distance_km.toFixed(4)} km` : "—"}</td>
                  <td>{r.max_poi_distance_km != null ? `${r.max_poi_distance_km.toFixed(4)} km` : "—"}</td>
                  <td>{r.total ?? "—"}</td>
                  <td>{r.error_count ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="poi-card stats-section">
        <div className="poi-card-header">
          <h3>Per-Category Accuracy</h3>
        </div>
        <div className="stats-plain-wrap">
          <table className="stats-plain-table">
            <thead>
              <tr>
                <th>Category</th>
                {schemes.flatMap((s) => [
                  <th key={`${s}-acc`}>{SIM_SCHEME_LABELS[s] || s} top-1</th>,
                  <th key={`${s}-err`}>{SIM_SCHEME_LABELS[s] || s} mean dist.</th>,
                ])}
              </tr>
            </thead>
            <tbody>
              {(categories.length ? categories : ["hospital", "school", "stationery", "post_office", "cosmetics", "gallery"]).map((cat) => (
                <tr key={cat}>
                  <td><strong>{cat}</strong></td>
                  {schemes.flatMap((s) => {
                    const cd = summary[s]?.per_category?.[cat] || {};
                    return [
                      <td key={`${s}-acc`}>
                        {cd.top1_accuracy != null ? `${(cd.top1_accuracy * 100).toFixed(0)} %` : "—"}
                      </td>,
                      <td key={`${s}-err`}>
                        {cd.mean_poi_distance_km != null ? `${cd.mean_poi_distance_km.toFixed(4)} km` : "—"}
                      </td>,
                    ];
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="stats-charts-grid">
        <div className="poi-card stats-chart-card">
          <div className="poi-card-header">
            <h3>Top-1 Accuracy by Category</h3>
          </div>
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={catAccData} margin={{ top: 8, right: 16, left: 0, bottom: 48 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(28,105,115,0.1)" />
              <XAxis dataKey="category" tick={{ fontSize: 11, fill: "#6b655d" }} angle={-30} textAnchor="end" interval={0} />
              <YAxis tick={{ fontSize: 11, fill: "#6b655d" }} tickFormatter={(v) => `${v}%`} domain={[0, 100]} />
              <Tooltip formatter={(v) => [`${v} %`]} contentStyle={{ borderRadius: 10, fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
              {schemes.map((s) => (
                <Line key={s} type="monotone" dataKey={SIM_SCHEME_LABELS[s] || s} stroke={SIM_SCHEME_COLORS[s] || "#888"} strokeWidth={2} dot={{ r: 4 }} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="poi-card stats-chart-card">
          <div className="poi-card-header">
            <h3>Mean Distance A→B by Category</h3>
          </div>
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={catErrData} margin={{ top: 8, right: 16, left: 0, bottom: 48 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(28,105,115,0.1)" />
              <XAxis dataKey="category" tick={{ fontSize: 11, fill: "#6b655d" }} angle={-30} textAnchor="end" interval={0} />
              <YAxis tick={{ fontSize: 11, fill: "#6b655d" }} tickFormatter={(v) => `${v} km`} />
              <Tooltip formatter={(v) => [`${v} km`]} contentStyle={{ borderRadius: 10, fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
              {schemes.map((s) => (
                <Line key={s} type="monotone" dataKey={SIM_SCHEME_LABELS[s] || s} stroke={SIM_SCHEME_COLORS[s] || "#888"} strokeWidth={2} dot={{ r: 4 }} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </>
  );
}

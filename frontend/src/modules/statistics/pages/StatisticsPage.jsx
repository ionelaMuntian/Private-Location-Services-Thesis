import { useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  LineChart, Line, ReferenceLine,
} from "recharts";
import "../styles/statistics.css";

const BENCHMARK_URL = "http://127.0.0.1:8000/client/poi/benchmark";
const BENCHMARK_TIMEOUT_MS = 7200000; // 2 hours — Concrete N=20 can be very slow

const CATEGORIES = ["hospital", "school", "university", "hotel", "clinic", "bank"];
const CONCRETE_N_OPTIONS = [1, 2, 5, 10, 20];
const SCHEME_OPTIONS = ["plaintext", "ckks", "openfhe_ss"];

const DEFAULT_LAT = 5902000.0;
const DEFAULT_LON = 2622000.0;

function fmtMs(v) {
  if (v === null || v === undefined) return "—";
  const n = Number(v);
  if (n >= 60000) return `${(n / 60000).toFixed(1)} min`;
  if (n >= 1000) return `${(n / 1000).toFixed(2)} s`;
  return `${n.toFixed(1)} ms`;
}

function fmtBytes(v) {
  if (!v && v !== 0) return "—";
  const n = Number(v);
  if (n === 0) return "0 B";
  if (n >= 1048576) return `${(n / 1048576).toFixed(2)} MB`;
  if (n >= 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${n} B`;
}

function getTotalMs(run) {
  return Number(run.timing?.client?.total_ms || 0);
}

function getServerMs(run) {
  return Number(run.timing?.server?.total_ms || 0);
}

function getClientMs(run) {
  const total = getTotalMs(run);
  const server = getServerMs(run);
  return Math.max(0, total - server);
}

export default function StatisticsPage() {
  const navigate = useNavigate();

  const [category, setCategory] = useState("clinic");
  const [lat, setLat] = useState(DEFAULT_LAT);
  const [lon, setLon] = useState(DEFAULT_LON);
  const [selectedSchemes, setSelectedSchemes] = useState(["plaintext", "ckks", "openfhe_ss"]);
  const [selectedN, setSelectedN] = useState([1, 2, 5, 10]);

  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState("");
  const [error, setError] = useState("");
  const [results, setResults] = useState(null);

  const toggleScheme = (s) =>
    setSelectedSchemes((prev) =>
      prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]
    );

  const toggleN = (n) =>
    setSelectedN((prev) =>
      prev.includes(n) ? prev.filter((x) => x !== n) : [...prev, n]
    );

  const handleRunBenchmark = async () => {
    const token = localStorage.getItem("access_token");
    if (!token) { navigate("/login"); return; }

    setLoading(true);
    setError("");
    setResults(null);

    const total = selectedSchemes.length + selectedN.length;
    setProgress(`Starting benchmark (${total} runs)...`);

    try {
      const response = await axios.post(
        BENCHMARK_URL,
        {
          category,
          latitude_m: Number(lat),
          longitude_m: Number(lon),
          k: 1,
          schemes: selectedSchemes,
          concrete_n_values: selectedN.sort((a, b) => a - b),
        },
        {
          headers: { Authorization: `Bearer ${token}` },
          timeout: BENCHMARK_TIMEOUT_MS,
          onDownloadProgress: () => setProgress("Benchmark running — waiting for all runs to complete..."),
        }
      );
      setResults(response.data);
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

  const runs = results?.runs || [];

  const schemeRuns = runs.filter((r) => r.scheme !== "concrete");
  const concreteRuns = runs
    .filter((r) => r.scheme === "concrete")
    .sort((a, b) => (a.n_candidates || 0) - (b.n_candidates || 0));

  const barData = runs.map((r) => ({
    name: r.label,
    "Client (ms)": parseFloat(getClientMs(r).toFixed(2)),
    "Server (ms)": parseFloat(getServerMs(r).toFixed(2)),
  }));

  const lineData = concreteRuns.map((r) => ({
    N: r.n_candidates,
    "Total (ms)": parseFloat(getTotalMs(r).toFixed(2)),
    "Server (ms)": parseFloat(getServerMs(r).toFixed(2)),
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
                  Compare timing and payload sizes across HE schemes and Concrete N values.
                  Concrete queries can take minutes per run — select N values carefully.
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
                  Latitude (m)
                  <input type="number" value={lat} onChange={(e) => setLat(e.target.value)} className="stats-input" step="any" />
                </label>

                <label className="stats-label">
                  Longitude (m)
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

                <div className="stats-label">
                  Concrete N values
                  <div className="stats-checkbox-row">
                    {CONCRETE_N_OPTIONS.map((n) => (
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
                  <p className="stats-hint">N=20 can take ~4h. Deselect if running quickly.</p>
                </div>
              </div>

              <button
                className="primary-btn stats-run-btn"
                onClick={handleRunBenchmark}
                disabled={loading || (selectedSchemes.length === 0 && selectedN.length === 0)}
              >
                {loading ? "Running benchmark..." : "Run Benchmark"}
              </button>

              {loading && progress && <p className="stats-progress">{progress}</p>}
              {error && <div className="poi-alert poi-alert-error">{error}</div>}
            </div>

            {runs.length > 0 && (
              <>
                {/* Timing table */}
                <div className="poi-card stats-section">
                  <div className="poi-card-header">
                    <h3>Timing Results</h3>
                    <p>All times include key generation, encryption, network, and decryption where applicable.</p>
                  </div>
                  <div className="poi-table-wrap">
                    <table className="poi-table">
                      <thead>
                        <tr>
                          <th>Label</th>
                          <th>Scheme</th>
                          <th>N candidates</th>
                          <th>Client total</th>
                          <th>Server total</th>
                          <th>Combined total</th>
                          <th>Server eval</th>
                        </tr>
                      </thead>
                      <tbody>
                        {runs.map((r) => (
                          <tr key={r.label}>
                            <td><strong>{r.label}</strong></td>
                            <td>{r.scheme}</td>
                            <td>{r.n_candidates ?? "—"}</td>
                            <td>{fmtMs(r.timing?.client?.total_ms)}</td>
                            <td>{fmtMs(r.timing?.server?.total_ms)}</td>
                            <td><strong>{fmtMs(getTotalMs(r))}</strong></td>
                            <td>{fmtMs(r.timing?.server?.evaluation_ms ?? r.timing?.server?.computation_ms)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Size table */}
                <div className="poi-card stats-section">
                  <div className="poi-card-header">
                    <h3>Payload Size Metrics</h3>
                    <p>
                      Ciphertext = encrypted query sent to server. Key = evaluation / public key sent to server.
                      For OpenFHE, sizes represent serialized context strings.
                    </p>
                  </div>
                  <div className="poi-table-wrap">
                    <table className="poi-table">
                      <thead>
                        <tr>
                          <th>Label</th>
                          <th>Scheme</th>
                          <th>Ciphertext size</th>
                          <th>Key size</th>
                          <th>Total overhead</th>
                        </tr>
                      </thead>
                      <tbody>
                        {runs.map((r) => {
                          const ct = r.sizes?.ciphertext_bytes ?? 0;
                          const ky = r.sizes?.key_bytes ?? 0;
                          return (
                            <tr key={r.label}>
                              <td><strong>{r.label}</strong></td>
                              <td>{r.scheme}</td>
                              <td>{fmtBytes(ct)}</td>
                              <td>{fmtBytes(ky)}</td>
                              <td><strong>{fmtBytes(ct + ky)}</strong></td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Charts */}
                <div className="stats-charts-grid">
                  {/* Bar chart: scheme comparison */}
                  <div className="poi-card stats-chart-card">
                    <div className="poi-card-header">
                      <h3>Scheme Comparison</h3>
                      <p>Total time per scheme (client + server, stacked).</p>
                    </div>
                    <ResponsiveContainer width="100%" height={320}>
                      <BarChart data={barData} margin={{ top: 8, right: 16, left: 0, bottom: 64 }}>
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
                          tickFormatter={(v) => v >= 1000 ? `${(v / 1000).toFixed(0)}s` : `${v}ms`}
                        />
                        <Tooltip
                          formatter={(v, name) => [fmtMs(v), name]}
                          contentStyle={{ borderRadius: 10, fontSize: 12 }}
                        />
                        <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
                        <Bar dataKey="Client (ms)" stackId="a" fill="#1c6973" radius={[0, 0, 0, 0]} />
                        <Bar dataKey="Server (ms)" stackId="a" fill="#5ba3aa" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>

                  {/* Line chart: Concrete N vs time */}
                  {concreteRuns.length >= 2 && (
                    <div className="poi-card stats-chart-card">
                      <div className="poi-card-header">
                        <h3>Concrete: N vs Time</h3>
                        <p>How evaluation time grows as the number of candidate POIs increases.</p>
                      </div>
                      <ResponsiveContainer width="100%" height={320}>
                        <LineChart data={lineData} margin={{ top: 8, right: 16, left: 0, bottom: 16 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="rgba(28,105,115,0.1)" />
                          <XAxis
                            dataKey="N"
                            label={{ value: "N (candidates)", position: "insideBottom", offset: -8, fontSize: 11, fill: "#6b655d" }}
                            tick={{ fontSize: 11, fill: "#6b655d" }}
                          />
                          <YAxis
                            tick={{ fontSize: 11, fill: "#6b655d" }}
                            tickFormatter={(v) => v >= 60000 ? `${(v / 60000).toFixed(0)}min` : v >= 1000 ? `${(v / 1000).toFixed(0)}s` : `${v}ms`}
                          />
                          <Tooltip
                            formatter={(v, name) => [fmtMs(v), name]}
                            contentStyle={{ borderRadius: 10, fontSize: 12 }}
                          />
                          <Legend wrapperStyle={{ fontSize: 12 }} />
                          <Line type="monotone" dataKey="Total (ms)" stroke="#1c6973" strokeWidth={2} dot={{ r: 4 }} />
                          <Line type="monotone" dataKey="Server (ms)" stroke="#e06b2d" strokeWidth={2} strokeDasharray="5 3" dot={{ r: 4 }} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  )}

                  {/* Bar chart: payload sizes */}
                  {runs.some((r) => (r.sizes?.ciphertext_bytes || 0) + (r.sizes?.key_bytes || 0) > 0) && (
                    <div className="poi-card stats-chart-card">
                      <div className="poi-card-header">
                        <h3>Payload Size Comparison</h3>
                        <p>Total bytes sent to server per query (ciphertext + keys).</p>
                      </div>
                      <ResponsiveContainer width="100%" height={320}>
                        <BarChart
                          data={runs.map((r) => ({
                            name: r.label,
                            "Ciphertext (B)": r.sizes?.ciphertext_bytes ?? 0,
                            "Keys (B)": r.sizes?.key_bytes ?? 0,
                          }))}
                          margin={{ top: 8, right: 16, left: 0, bottom: 64 }}
                        >
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
                            tickFormatter={(v) => v >= 1048576 ? `${(v / 1048576).toFixed(1)}MB` : v >= 1024 ? `${(v / 1024).toFixed(0)}KB` : `${v}B`}
                          />
                          <Tooltip
                            formatter={(v, name) => [fmtBytes(v), name]}
                            contentStyle={{ borderRadius: 10, fontSize: 12 }}
                          />
                          <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
                          <Bar dataKey="Ciphertext (B)" stackId="b" fill="#1c6973" radius={[0, 0, 0, 0]} />
                          <Bar dataKey="Keys (B)" stackId="b" fill="#e89a5d" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

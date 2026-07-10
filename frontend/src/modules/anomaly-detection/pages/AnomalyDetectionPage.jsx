import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import "../../poi-search/styles/poi-search.css";
import "../styles/anomaly-detection.css";

const SAMPLES_URL = "http://127.0.0.1:8000/client/anomaly-detection/samples";
const INFER_URL = "http://127.0.0.1:8000/client/anomaly-detection/infer";
const REQUEST_TIMEOUT_MS = 1800000;

const MODES = [
  { value: "plaintext", title: "Plaintext" },
  { value: "encrypted", title: "Encrypted" },
  { value: "both", title: "Both" },
];

function formatMs(value) {
  if (value === null || value === undefined) return "—";
  return `${Number(value).toFixed(2)} ms`;
}

function formatProbability(value) {
  if (value === null || value === undefined) return "—";
  return `${(Number(value) * 100).toFixed(2)}%`;
}

function ResultCard({ title, result }) {
  if (!result) return null;

  const predictedAnomaly = result.prediction === 1;
  const actualAnomaly = result.true_label === 1;

  return (
    <div className="poi-card anomaly-result-card">
      <div className="poi-card-header">
        <h3>{title}</h3>
      </div>

      <div className="anomaly-badge-row">
        <span className={`anomaly-badge ${predictedAnomaly ? "anomaly-badge-anomaly" : "anomaly-badge-normal"}`}>
          Predicted: {predictedAnomaly ? "Anomaly" : "Normal"}
        </span>
        <span className={`anomaly-badge ${actualAnomaly ? "anomaly-badge-anomaly" : "anomaly-badge-normal"}`}>
          Ground truth: {actualAnomaly ? "Anomaly" : "Normal"}
        </span>
      </div>

      <div className="poi-simple-metrics">
        <div className="poi-simple-metric-card">
          <span className="poi-simple-metric-label">Probability</span>
          <strong className="poi-simple-metric-value">{formatProbability(result.probability)}</strong>
        </div>
        <div className="poi-simple-metric-card">
          <span className="poi-simple-metric-label">Latency</span>
          <strong className="poi-simple-metric-value">{formatMs(result.latency_ms)}</strong>
        </div>
      </div>
    </div>
  );
}

export default function AnomalyDetectionPage() {
  const navigate = useNavigate();

  const [samples, setSamples] = useState([]);
  const [sampleId, setSampleId] = useState(null);
  const [mode, setMode] = useState("plaintext");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingSamples, setLoadingSamples] = useState(true);
  const [error, setError] = useState("");

  const handleUnauthorized = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("token_type");
    localStorage.removeItem("username");
    navigate("/login");
  };

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      navigate("/login");
      return;
    }

    axios
      .get(SAMPLES_URL, { headers: { Authorization: `Bearer ${token}` } })
      .then((response) => {
        const list = response.data?.samples || [];
        setSamples(list);
        if (list.length > 0) setSampleId(list[0].id);
      })
      .catch((err) => {
        if (err?.response?.status === 401 || err?.response?.status === 403) {
          handleUnauthorized();
          return;
        }
        setError("Failed to load test samples. Is the training notebook's artifact export up to date?");
      })
      .finally(() => setLoadingSamples(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navigate]);

  const handleRun = async (e) => {
    e.preventDefault();
    if (sampleId === null) return;

    const token = localStorage.getItem("access_token");
    if (!token) {
      handleUnauthorized();
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await axios.post(
        INFER_URL,
        { sample_id: sampleId, mode },
        { headers: { Authorization: `Bearer ${token}` }, timeout: REQUEST_TIMEOUT_MS }
      );
      setResult(response.data);
    } catch (err) {
      if (err?.response?.status === 401 || err?.response?.status === 403) {
        handleUnauthorized();
        return;
      }

      const backendMessage =
        err?.response?.data?.detail?.detail ||
        err?.response?.data?.detail ||
        err?.message ||
        "Inference failed. Check that both backend services are running.";

      setError(
        typeof backendMessage === "string" ? backendMessage : JSON.stringify(backendMessage)
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="poi-page">
      <div className="poi-background-grid"></div>

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
              <button className="poi-nav-item active" type="button">
                Risk Based Authentication
              </button>
              <button className="poi-nav-item" type="button" onClick={() => navigate("/statistics")}>
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
                <p className="poi-eyebrow">Anomaly Detection</p>
                <h1>Risk Based Authentication</h1>
              </div>
            </header>

            <div className="poi-content-grid">
              <section className="poi-card poi-form-card">
                <div className="poi-card-header">
                  <h3>Run Inference on a Test Sample</h3>
                </div>

                <form onSubmit={handleRun} className="poi-form">
                  <label>
                    Test Sample
                    <select
                      value={sampleId ?? ""}
                      onChange={(e) => setSampleId(Number(e.target.value))}
                      disabled={loadingSamples || samples.length === 0}
                    >
                      {samples.length === 0 && <option value="">No samples available</option>}
                      {samples.map((sample) => (
                        <option key={sample.id} value={sample.id}>
                          {sample.label}
                        </option>
                      ))}
                    </select>
                  </label>

                  <div className="full-width anomaly-tab-grid anomaly-mode-grid">
                    {MODES.map((m) => (
                      <button
                        key={m.value}
                        type="button"
                        className={`anomaly-tab-box${mode === m.value ? " active" : ""}`}
                        onClick={() => setMode(m.value)}
                      >
                        <span className="anomaly-tab-title">{m.title}</span>
                      </button>
                    ))}
                  </div>

                  <div className="full-width poi-form-actions">
                    <button className="primary-btn" type="submit" disabled={loading || sampleId === null}>
                      {loading ? "Running..." : "Run Inference"}
                    </button>
                  </div>
                </form>

                {error && <div className="poi-alert poi-alert-error">{error}</div>}
              </section>

              <section className="poi-card poi-results-card">
                <div className="poi-card-header">
                  <h3>Results</h3>
                </div>

                {!result && <p className="poi-empty">Run inference to see results here.</p>}

                {result && (
                  <div className="anomaly-results-grid">
                    <ResultCard title="Plaintext" result={result.plaintext} />
                    <ResultCard title="Encrypted (FHE)" result={result.encrypted} />
                  </div>
                )}
              </section>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

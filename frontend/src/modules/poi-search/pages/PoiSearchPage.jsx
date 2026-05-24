import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import "../styles/poi-search.css";

const API_URL = "http://127.0.0.1:8000/client/poi/nearest-k";

const REQUEST_TIMEOUT_MS = 1800000;

const initialForm = {
  category: "hospital",
  k: 2,
  latitude: 46.77,
  longitude: 23.59,
  scheme: "plaintext",
};

function formatMs(value) {
  if (value === null || value === undefined) return "—";
  return `${Number(value).toFixed(3)} ms`;
}

function computeCombinedMs(metrics) {
  const clientTotal = Number(metrics?.client?.total_ms || 0);
  const serverTotal = Number(metrics?.server?.total_ms || 0);

  if (!clientTotal && !serverTotal) return null;
  return clientTotal + serverTotal;
}

function SimpleMetrics({ metrics, scheme }) {
  if (!metrics) return null;

  const clientTotal = metrics?.client?.total_ms ?? null;
  const serverTotal = metrics?.server?.total_ms ?? null;
  const combinedTotal = computeCombinedMs(metrics);

  return (
    <div className="poi-simple-metrics">
      <div className="poi-simple-metric-card">
        <span className="poi-simple-metric-label">Scheme</span>
        <strong className="poi-simple-metric-value">{scheme}</strong>
      </div>

      <div className="poi-simple-metric-card">
        <span className="poi-simple-metric-label">Total client time</span>
        <strong className="poi-simple-metric-value">{formatMs(clientTotal)}</strong>
      </div>

      <div className="poi-simple-metric-card">
        <span className="poi-simple-metric-label">Total server time</span>
        <strong className="poi-simple-metric-value">{formatMs(serverTotal)}</strong>
      </div>

      <div className="poi-simple-metric-card">
        <span className="poi-simple-metric-label">Client + server</span>
        <strong className="poi-simple-metric-value">{formatMs(combinedTotal)}</strong>
      </div>
    </div>
  );
}

function ResultsTable({ results }) {
  if (!results || results.length === 0) {
    return <p className="poi-empty">No results available.</p>;
  }

  return (
    <div className="poi-table-wrap">
      <table className="poi-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Category</th>
            <th>Latitude</th>
            <th>Longitude</th>
            <th>Distance (km)</th>
          </tr>
        </thead>
        <tbody>
          {results.map((poi) => (
            <tr key={`${poi.id}-${poi.name}`}>
              <td>{poi.name}</td>
              <td>{poi.category}</td>
              <td>{poi.latitude}</td>
              <td>{poi.longitude}</td>
              <td>{poi.distance_km}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AllRunsComparison({ runs }) {
  if (!runs || runs.length === 0) {
    return <p className="poi-empty">No comparison data available.</p>;
  }

  return (
    <div className="poi-all-runs">
      <div className="poi-table-wrap">
        <table className="poi-table poi-comparison-table">
          <thead>
            <tr>
              <th>Scheme</th>
              <th>Total client time</th>
              <th>Total server time</th>
              <th>Client + server</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.scheme}>
                <td>{run.scheme}</td>
                <td>{formatMs(run.metrics?.client?.total_ms)}</td>
                <td>{formatMs(run.metrics?.server?.total_ms)}</td>
                <td>{formatMs(computeCombinedMs(run.metrics))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="poi-run-results-list">
        {runs.map((run) => (
          <div className="poi-run-results-block" key={`results-${run.scheme}`}>
            <div className="poi-subsection-header">
              <h4>Results for {run.scheme}</h4>
            </div>
            <ResultsTable results={run.results} />
          </div>
        ))}
      </div>
    </div>
  );
}

export default function PoiSearchPage() {
  const navigate = useNavigate();

  const [form, setForm] = useState(initialForm);
  const [results, setResults] = useState([]);
  const [responseMetrics, setResponseMetrics] = useState(null);
  const [selectedScheme, setSelectedScheme] = useState(null);
  const [allRuns, setAllRuns] = useState([]);
  const [mode, setMode] = useState("single");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      navigate("/login");
    }
  }, [navigate]);

  const hasResults = useMemo(() => results.length > 0, [results]);
  const hasAllRuns = useMemo(() => allRuns.length > 0, [allRuns]);

  const handleChange = (field, value) => {
    setForm((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const resetResponseState = () => {
    setResults([]);
    setResponseMetrics(null);
    setSelectedScheme(null);
    setAllRuns([]);
    setMode("single");
  };

  const handleUnauthorized = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("token_type");
    localStorage.removeItem("username");
    navigate("/login");
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    const token = localStorage.getItem("access_token");
    if (!token) {
      handleUnauthorized();
      return;
    }

    setLoading(true);
    setError("");
    resetResponseState();

    try {
      const payload = {
        category: form.category,
        k: Number(form.k),
        latitude: Number(form.latitude),
        longitude: Number(form.longitude),
        scheme: form.scheme,
      };

      const response = await axios.post(API_URL, payload, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
        timeout: REQUEST_TIMEOUT_MS,
      });

      const data = response.data;

      if (data.mode === "all") {
        setMode("all");
        setAllRuns(data.runs || []);
      } else {
        setMode("single");
        setSelectedScheme(data.scheme);
        setResponseMetrics(data.metrics || null);
        setResults(data.results || []);
      }
    } catch (err) {
      console.error(err);

      if (err?.response?.status === 401 || err?.response?.status === 403) {
        handleUnauthorized();
        return;
      }

      const backendMessage =
        err?.response?.data?.detail?.detail ||
        err?.response?.data?.detail ||
        err?.message ||
        "Request failed. Check that both backend services are running.";

      setError(
        typeof backendMessage === "string"
          ? backendMessage
          : JSON.stringify(backendMessage)
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
              <button className="poi-nav-item active" type="button">
                Nearest POI Search
              </button>

              <button
                className="poi-nav-item"
                type="button"
                onClick={() => navigate("/location-sharing")}
              >
                Location Sharing
              </button>

              <button
                className="poi-nav-item"
                type="button"
                onClick={() => navigate("/anomaly-detection")}
              >
                Impossible Travel Detection
              </button>

              <button
                className="poi-nav-item"
                type="button"
                onClick={() => navigate("/statistics")}
              >
                Statistics & Benchmarks
              </button>
            </nav>

            <button
              className="poi-back-btn"
              type="button"
              onClick={() => navigate("/home")}
            >
              Back to Dashboard
            </button>
          </div>
        </aside>

        <main className="poi-main">
          <div className="poi-container">
            <header className="poi-topbar">
              <div>
                <p className="poi-eyebrow">Nearest Points of Interest</p>
                <h1>Search Nearby Services</h1>
                <p className="poi-subtitle">
                  Search for the nearest POIs by category using privacy-preserving
                  distance computation.
                </p>
              </div>
            </header>

            <div className="poi-content-grid">
              <section className="poi-card poi-form-card">
                <div className="poi-card-header">
                  <h3>Query Form</h3>
                  <p>Choose a category and enter the query parameters below.</p>
                </div>

                <form onSubmit={handleSubmit} className="poi-form">
                  <label>
                    Category
                    <select
                      value={form.category}
                      onChange={(e) => handleChange("category", e.target.value)}
                    >
                      <option value="hospital">hospital</option>
                      <option value="school">school</option>
                      <option value="stationery">stationery</option>
                      <option value="post_office">post_office</option>
                      <option value="cosmetics">cosmetics</option>
                      <option value="gallery">gallery</option>
                    </select>
                  </label>

                  <label>
                    K
                    <input
                      type="number"
                      min="1"
                      max="50"
                      value={form.k}
                      onChange={(e) => handleChange("k", e.target.value)}
                    />
                  </label>

                  <label>
                    Latitude (°)
                    <input
                      type="number"
                      step="any"
                      value={form.latitude}
                      onChange={(e) => handleChange("latitude", e.target.value)}
                    />
                  </label>

                  <label>
                    Longitude (°)
                    <input
                      type="number"
                      step="any"
                      value={form.longitude}
                      onChange={(e) => handleChange("longitude", e.target.value)}
                    />
                  </label>

                  <label className="full-width">
                    Scheme
                    <select
                      value={form.scheme}
                      onChange={(e) => handleChange("scheme", e.target.value)}
                    >
                      <option value="plaintext">plaintext</option>
                      <option value="ckks">ckks</option>
                      <option value="concrete">concrete</option>
                      <option value="openfhe_ss">openfhe_ss (scheme switching)</option>
                      <option value="all">all</option>
                    </select>
                  </label>

                  {form.scheme === "ckks" && (
                    <div className="full-width poi-alert">
                      CKKS uses approximate homomorphic encryption and is suited
                      for real-valued coordinates.
                    </div>
                  )}

                  {form.scheme === "concrete" && (
                    <div className="full-width poi-alert">
                      Concrete uses TFHE — slower than CKKS/BFV but supports
                      exact integer arithmetic. Each query may take several
                      minutes; please be patient.
                    </div>
                  )}

                  {form.scheme === "openfhe_ss" && (
                    <div className="full-width poi-alert">
                      OpenFHE Scheme Switching — server computes argmin directly
                      on encrypted distances via CKKS→FHEW switching. Returns
                      top-1 result. First request may take longer (key setup).
                    </div>
                  )}

                  {form.scheme === "all" && (
                    <div className="full-width poi-alert">
                      All mode runs plaintext, CKKS, and OpenFHE Scheme Switching.
                    </div>
                  )}

                  <div className="full-width poi-form-actions">
                    <button className="primary-btn" type="submit" disabled={loading}>
                      {loading ? "Searching..." : "Search Nearest POIs"}
                    </button>
                  </div>
                </form>

                {error && <div className="poi-alert poi-alert-error">{error}</div>}
              </section>

              <section className="poi-card poi-results-card">
                <div className="poi-card-header">
                  <h3>Results</h3>
                  <p>
                    {mode === "all"
                      ? "Comparison across plaintext, CKKS, and OpenFHE Scheme Switching."
                      : "Returned nearest points of interest."}
                  </p>
                </div>

                {loading && (
                  <p className="poi-empty">
                    {form.scheme === "all"
                      ? "Running plaintext, CKKS, and OpenFHE Scheme Switching..."
                      : form.scheme === "concrete"
                      ? "Running Concrete FHE — this may take several minutes..."
                      : form.scheme === "openfhe_ss"
                      ? "Running OpenFHE Scheme Switching — please wait..."
                      : "Searching for nearest POIs..."}
                  </p>
                )}

                {!loading && mode === "single" && !hasResults && !error && (
                  <p className="poi-empty">
                    No results yet. Run a query to see results.
                  </p>
                )}

                {!loading && mode === "single" && hasResults && (
                  <>
                    {responseMetrics && (
                      <SimpleMetrics
                        metrics={responseMetrics}
                        scheme={selectedScheme}
                      />
                    )}
                    <ResultsTable results={results} />
                  </>
                )}

                {!loading && mode === "all" && !hasAllRuns && !error && (
                  <p className="poi-empty">
                    No comparison results yet. Run a query to compare the schemes.
                  </p>
                )}

                {!loading && mode === "all" && hasAllRuns && (
                  <AllRunsComparison runs={allRuns} />
                )}
              </section>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
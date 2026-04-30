import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import "../styles/poi-search.css";

const API_URL = "http://127.0.0.1:8000/client/poi/nearest-k";
const SEARCH_BY_NAME_URL = "http://127.0.0.1:8000/client/poi/search-by-name";

const initialForm = {
  searchType: "category",
  category: "bank",
  nameQuery: "",
  k: 2,
  latitude_m: 5741384.185332346,
  longitude_m: 2362254.8313645967,
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

function ResultsTable({ results, showDistance = true }) {
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
            {showDistance && <th>Distance (km)</th>}
          </tr>
        </thead>
        <tbody>
          {results.map((poi) => (
            <tr key={`${poi.id}-${poi.name}`}>
              <td>{poi.name}</td>
              <td>{poi.category}</td>
              <td>{poi.latitude}</td>
              <td>{poi.longitude}</td>
              {showDistance && <td>{poi.distance_km}</td>}
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
            <ResultsTable results={run.results} showDistance={true} />
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
  const isNameSearch = form.searchType === "name";
  const shouldShowDistance =
    !isNameSearch && selectedScheme !== "name-search";

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
      if (form.searchType === "name") {
        if (!form.nameQuery.trim()) {
          setError("Please enter a POI name.");
          setLoading(false);
          return;
        }

        const response = await axios.get(SEARCH_BY_NAME_URL, {
          params: {
            q: form.nameQuery.trim(),
            limit: Number(form.k),
          },
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        const data = response.data;

        setMode("single");
        setSelectedScheme("name-search");
        setResponseMetrics(null);
        setResults(data.results || []);
        return;
      }

      const payload = {
        category: form.category,
        k: Number(form.k),
        latitude_m: Number(form.latitude_m),
        longitude_m: Number(form.longitude_m),
        scheme: form.scheme,
      };

      const response = await axios.post(API_URL, payload, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
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
                  Search POIs either by category with privacy-preserving distance
                  computation, or by name using direct lookup.
                </p>
              </div>
            </header>

            <div className="poi-content-grid">
              <section className="poi-card poi-form-card">
                <div className="poi-card-header">
                  <h3>Query Form</h3>
                  <p>Choose a search type and enter the query parameters below.</p>
                </div>

                <div className="poi-search-type-switch">
                  <button
                    type="button"
                    className={`poi-search-type-btn ${
                      form.searchType === "category" ? "active" : ""
                    }`}
                    onClick={() => handleChange("searchType", "category")}
                  >
                    By Category
                  </button>

                  <button
                    type="button"
                    className={`poi-search-type-btn ${
                      form.searchType === "name" ? "active" : ""
                    }`}
                    onClick={() => handleChange("searchType", "name")}
                  >
                    By Name
                  </button>
                </div>

                <form onSubmit={handleSubmit} className="poi-form">
                  {form.searchType === "category" ? (
                    <label>
                      Category
                      <select
                        value={form.category}
                        onChange={(e) => handleChange("category", e.target.value)}
                      >
                        <option value="bank">bank</option>
                        <option value="cafe">cafe</option>
                        <option value="supermarket">supermarket</option>
                        <option value="dentist">dentist</option>
                        <option value="fitness_centre">fitness_centre</option>
                        <option value="fast_food">fast_food</option>
                        <option value="pharmacy">pharmacy</option>
                      </select>
                    </label>
                  ) : (
                    <label className="full-width">
                      POI Name
                      <input
                        type="text"
                        value={form.nameQuery}
                        onChange={(e) => handleChange("nameQuery", e.target.value)}
                        placeholder="e.g. Libra, Mega Image, Ted's Coffee"
                      />
                    </label>
                  )}

                  <label>
                    K / Limit
                    <input
                      type="number"
                      min="1"
                      max="50"
                      value={form.k}
                      onChange={(e) => handleChange("k", e.target.value)}
                    />
                  </label>

                  {form.searchType === "category" && (
                    <>
                      <label>
                        Latitude (m)
                        <input
                          type="number"
                          step="any"
                          value={form.latitude_m}
                          onChange={(e) => handleChange("latitude_m", e.target.value)}
                        />
                      </label>

                      <label>
                        Longitude (m)
                        <input
                          type="number"
                          step="any"
                          value={form.longitude_m}
                          onChange={(e) => handleChange("longitude_m", e.target.value)}
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
                          <option value="bfv">bfv</option>
                          <option value="concrete">concrete</option>
                          <option value="all">all</option>
                        </select>
                      </label>

                      {form.scheme === "ckks" && (
                        <div className="full-width poi-alert">
                          CKKS uses approximate homomorphic encryption and is suited for
                          real-valued coordinates.
                        </div>
                      )}

                      {form.scheme === "bfv" && (
                        <div className="full-width poi-alert">
                          BFV uses exact integer arithmetic with scaled coordinates.
                        </div>
                      )}

                      {form.scheme === "concrete" && (
                        <div className="full-width poi-alert">
                          Concrete is currently unstable. Use it separately only if you
                          want to test it on its own.
                        </div>
                      )}

                      {form.scheme === "all" && (
                        <div className="full-width poi-alert">
                          All mode currently runs plaintext, CKKS, and BFV only.
                        </div>
                      )}
                    </>
                  )}

                  <div className="full-width poi-form-actions">
                    <button className="primary-btn" type="submit" disabled={loading}>
                      {loading
                        ? form.searchType === "name"
                          ? "Searching by name..."
                          : "Searching..."
                        : form.searchType === "name"
                        ? "Search POIs by Name"
                        : "Search Nearest POIs"}
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
                      ? "Comparison across the working schemes."
                      : form.searchType === "name"
                      ? "Returned POIs matching the entered name."
                      : "Returned nearest points of interest."}
                  </p>
                </div>

                {loading && (
                  <p className="poi-empty">
                    {form.searchType === "name"
                      ? "Searching by name..."
                      : form.scheme === "all"
                      ? "Running plaintext, CKKS, and BFV..."
                      : "Searching for nearest POIs..."}
                  </p>
                )}

                {!loading && mode === "single" && !hasResults && !error && (
                  <p className="poi-empty">No results yet. Run a query to see results.</p>
                )}

                {!loading && mode === "single" && hasResults && (
                  <>
                    {responseMetrics && (
                      <SimpleMetrics metrics={responseMetrics} scheme={selectedScheme} />
                    )}
                    <ResultsTable
                      results={results}
                      showDistance={shouldShowDistance}
                    />
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
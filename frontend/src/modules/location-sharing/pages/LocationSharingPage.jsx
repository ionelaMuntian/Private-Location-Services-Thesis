import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import "../../poi-search/styles/poi-search.css";
import "../styles/location-sharing.css";

const API_BASE_URL = "http://127.0.0.1:8000";
const MY_COMPANIES_URL = `${API_BASE_URL}/client/company/my-companies`;
const LATEST_LOCATION_URL = `${API_BASE_URL}/client/company/latest-location`;
const MY_STATUS_URL = (companyId) =>
  `${API_BASE_URL}/client/company/companies/${companyId}/my-status`;

const POLL_INTERVAL_MS = 5000;
const MAX_POLL_ATTEMPTS = 60;

const initialForm = {
  homeLatitude: 46.77,
  homeLongitude: 23.59,
  homeRadius: 500,
  currentLatitude: 46.78,
  currentLongitude: 23.59,
};

function degToMercatorLon(lon) {
  return lon * 20037508.34 / 180;
}

function degToMercatorLat(lat) {
  return Math.log(Math.tan((90 + lat) * Math.PI / 360)) * 20037508.34 / Math.PI;
}

export default function LocationSharingPage() {
  const navigate = useNavigate();

  const [form, setForm] = useState(initialForm);
  const [company, setCompany] = useState(null);
  const [savedData, setSavedData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [companyLoading, setCompanyLoading] = useState(false);
  const [error, setError] = useState("");
  const [verificationStatus, setVerificationStatus] = useState(null);
  const [polling, setPolling] = useState(false);
  const pollAttemptsRef = useRef(0);
  const pollTimerRef = useRef(null);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    setPolling(false);
    pollAttemptsRef.current = 0;
  }, []);

  const pollStatus = useCallback(
    async (companyId, token) => {
      if (pollAttemptsRef.current >= MAX_POLL_ATTEMPTS) {
        stopPolling();
        return;
      }

      pollAttemptsRef.current += 1;

      try {
        const response = await axios.get(MY_STATUS_URL(companyId), {
          headers: { Authorization: `Bearer ${token}` },
        });

        const data = response.data;

        if (!data.pending) {
          setVerificationStatus(data);
          stopPolling();
          return;
        }
      } catch {

      }

      pollTimerRef.current = setTimeout(
        () => pollStatus(companyId, token),
        POLL_INTERVAL_MS
      );
    },
    [stopPolling]
  );

  const startPolling = useCallback(
    (companyId) => {
      stopPolling();
      const token = localStorage.getItem("access_token");
      if (!token) return;
      setPolling(true);
      setVerificationStatus(null);
      pollAttemptsRef.current = 0;
      pollTimerRef.current = setTimeout(
        () => pollStatus(companyId, token),
        POLL_INTERVAL_MS
      );
    },
    [pollStatus, stopPolling]
  );

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      navigate("/login");
      return;
    }

    loadAssignedCompany(token);
  }, [navigate]);

  const handleUnauthorized = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("token_type");
    localStorage.removeItem("username");
    navigate("/login");
  };

  const loadAssignedCompany = async (token) => {
    setCompanyLoading(true);
    setError("");

    try {
      const response = await axios.get(MY_COMPANIES_URL, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      const companies = response.data?.companies || [];

      if (companies.length > 0) {
        setCompany(companies[0]);
      } else {
        setCompany(null);
      }
    } catch (err) {
      console.error(err);

      if (err?.response?.status === 401 || err?.response?.status === 403) {
        handleUnauthorized();
        return;
      }

      setError("Could not load the assigned company.");
    } finally {
      setCompanyLoading(false);
    }
  };

  const handleChange = (field, value) => {
    setForm((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    const token = localStorage.getItem("access_token");
    if (!token) {
      handleUnauthorized();
      return;
    }

    if (!company) {
      setError("No company is assigned to this user yet.");
      return;
    }

    setLoading(true);
    setError("");
    setSuccessMessage("");

    try {
      await axios.post(
        LATEST_LOCATION_URL,
        {
          company_id: Number(company.id),
          current_lat_m: degToMercatorLat(Number(form.currentLatitude)),
          current_lon_m: degToMercatorLon(Number(form.currentLongitude)),
          home_lat_m: degToMercatorLat(Number(form.homeLatitude)),
          home_lon_m: degToMercatorLon(Number(form.homeLongitude)),
          home_radius_m: Number(form.homeRadius),
        },
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      const preparedData = {
        companyName: company.name,
        homeLatitude: Number(form.homeLatitude),
        homeLongitude: Number(form.homeLongitude),
        homeRadius: Number(form.homeRadius),
        currentLatitude: Number(form.currentLatitude),
        currentLongitude: Number(form.currentLongitude),
      };

      setSavedData(preparedData);
      startPolling(company.id);
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
        "Could not save the location data.";

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
    <div className="location-page">
      <div className="location-background-grid"></div>

      <div className="location-shell">
        <aside className="location-sidebar">
          <div className="location-sidebar-card">
            <p className="location-sidebar-kicker">Services</p>

            <nav className="location-sidebar-nav">
              <button
                className="location-nav-item"
                type="button"
                onClick={() => navigate("/poi-search")}
              >
                Nearest POI Search
              </button>

              <button className="location-nav-item active" type="button">
                Location Sharing
              </button>

              <button
                className="location-nav-item"
                type="button"
                onClick={() => navigate("/anomaly-detection")}
              >
                Risk Based Authentication
              </button>

              <button
                className="location-nav-item"
                type="button"
                onClick={() => navigate("/statistics")}
              >
                Statistics &amp; Benchmarks
              </button>
            </nav>

            <button
              className="location-back-btn"
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
                <p className="poi-eyebrow">Encrypted Location Sharing</p>
                <h1>Manage Shared Location with Company</h1>
              </div>
            </header>

            <div className="poi-content-grid">
              <section className="poi-card poi-form-card">
                <div className="poi-card-header">
                  <h3>Query Form</h3>
                </div>

                <form onSubmit={handleSubmit} className="poi-form location-form">
                  <label className="full-width location-form-row">
                    <span>Company</span>
                    <input
                      type="text"
                      value={
                        companyLoading
                          ? "Loading assigned company..."
                          : company
                          ? company.name
                          : "No company assigned yet"
                      }
                      disabled
                    />
                  </label>

                  <div className="location-form-column">
                    <label className="location-form-row">
                      <span>Home Latitude (°)</span>
                      <input
                        type="number"
                        step="any"
                        value={form.homeLatitude}
                        onChange={(e) => handleChange("homeLatitude", e.target.value)}
                      />
                    </label>

                    <label className="location-form-row">
                      <span>Home Longitude (°)</span>
                      <input
                        type="number"
                        step="any"
                        value={form.homeLongitude}
                        onChange={(e) => handleChange("homeLongitude", e.target.value)}
                      />
                    </label>

                    <label className="location-form-row">
                      <span>Home Radius (m)</span>
                      <input
                        type="number"
                        min="1"
                        value={form.homeRadius}
                        onChange={(e) => handleChange("homeRadius", e.target.value)}
                      />
                    </label>
                  </div>

                  <div className="location-form-column">
                    <label className="location-form-row">
                      <span>Current Latitude (°)</span>
                      <input
                        type="number"
                        step="any"
                        value={form.currentLatitude}
                        onChange={(e) => handleChange("currentLatitude", e.target.value)}
                      />
                    </label>

                    <label className="location-form-row">
                      <span>Current Longitude (°)</span>
                      <input
                        type="number"
                        step="any"
                        value={form.currentLongitude}
                        onChange={(e) => handleChange("currentLongitude", e.target.value)}
                      />
                    </label>
                  </div>

                  <div className="full-width poi-form-actions">
                    <button className="primary-btn" type="submit" disabled={loading || !company}>
                      {loading ? "Saving..." : "Share / Update Location"}
                    </button>
                  </div>
                </form>

                {error && <div className="poi-alert poi-alert-error">{error}</div>}
              </section>

              <section className="poi-card poi-results-card">
                <div className="poi-card-header">
                  <h3>Current State</h3>
                </div>

                {!savedData ? (
                  <p className="poi-empty">No location update submitted yet.</p>
                ) : (
                  <div className="poi-simple-metrics">
                    <div className="poi-simple-metric-card">
                      <span className="poi-simple-metric-label">Company</span>
                      <strong className="poi-simple-metric-value">{savedData.companyName}</strong>
                    </div>

                    <div className="poi-simple-metric-card">
                      <span className="poi-simple-metric-label">Home Latitude</span>
                      <strong className="poi-simple-metric-value">{savedData.homeLatitude}°</strong>
                    </div>

                    <div className="poi-simple-metric-card">
                      <span className="poi-simple-metric-label">Home Longitude</span>
                      <strong className="poi-simple-metric-value">{savedData.homeLongitude}°</strong>
                    </div>

                    <div className="poi-simple-metric-card">
                      <span className="poi-simple-metric-label">Home Radius</span>
                      <strong className="poi-simple-metric-value">{savedData.homeRadius} m</strong>
                    </div>

                    <div className="poi-simple-metric-card">
                      <span className="poi-simple-metric-label">Current Latitude</span>
                      <strong className="poi-simple-metric-value">{savedData.currentLatitude}°</strong>
                    </div>

                    <div className="poi-simple-metric-card">
                      <span className="poi-simple-metric-label">Current Longitude</span>
                      <strong className="poi-simple-metric-value">{savedData.currentLongitude}°</strong>
                    </div>

                    <div className="poi-simple-metric-card">
                      <span className="poi-simple-metric-label">Verification</span>
                      <strong className="poi-simple-metric-value">
                        {polling
                          ? "Polling for result..."
                          : verificationStatus
                          ? "Result received"
                          : "Waiting for company check"}
                      </strong>
                    </div>
                  </div>
                )}

                {verificationStatus && !verificationStatus.pending && (
                  <div className="location-verification-result">
                    <div className="poi-card-header">
                      <h3>Verification Result</h3>
                      <p>Computed on encrypted data by the service provider. Decrypted by both parties.</p>
                    </div>

                    <div className="location-result-badges">
                      <span
                        className={`location-badge ${verificationStatus.in_country ? "location-badge-ok" : "location-badge-fail"}`}
                      >
                        {verificationStatus.in_country ? "✓" : "✗"} In Country
                      </span>

                      <span
                        className={`location-badge ${verificationStatus.at_office ? "location-badge-ok" : "location-badge-fail"}`}
                      >
                        {verificationStatus.at_office ? "✓" : "✗"} At Office
                      </span>

                      <span
                        className={`location-badge ${verificationStatus.at_home ? "location-badge-ok" : "location-badge-fail"}`}
                      >
                        {verificationStatus.at_home ? "✓" : "✗"} At Home
                      </span>
                    </div>

                    {verificationStatus.last_updated && (
                      <p className="location-result-timestamp">
                        Last checked: {new Date(verificationStatus.last_updated).toLocaleString([], {
                          year: "numeric",
                          month: "2-digit",
                          day: "2-digit",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </p>
                    )}
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
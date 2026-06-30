import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
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
  const [successMessage, setSuccessMessage] = useState("");
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
      setSuccessMessage(
        "Location data was saved. The company can now run a compliance check. Polling for your result..."
      );
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
            <p className="location-sidebar-kicker">Employee</p>

            <nav className="location-sidebar-nav">
              <button className="location-nav-item active" type="button">
                Location Sharing
              </button>

              <button
                className="location-nav-item"
                type="button"
                onClick={() => navigate("/poi-search")}
              >
                Nearest POI Search
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

        <main className="location-main">
          <div className="location-container">
            <header className="location-topbar">
              <p className="location-eyebrow">Encrypted Location Sharing</p>
              <h1>Manage Shared Location with Company</h1>
            </header>

            <section className="location-content">
              <form onSubmit={handleSubmit} className="location-form">
                <div className="location-section">
                  <h2 className="location-section-title">Company</h2>

                  <div className="location-company-display">
                    {companyLoading
                      ? "Loading assigned company..."
                      : company
                      ? company.name
                      : "No company assigned yet"}
                  </div>
                </div>

                <div className="location-section location-section-spaced">
                  <h2 className="location-section-title">Home Address</h2>

                  <div className="location-form-grid">
                    <label>
                      Home Latitude (°)
                      <input
                        type="number"
                        step="any"
                        value={form.homeLatitude}
                        onChange={(e) =>
                          handleChange("homeLatitude", e.target.value)
                        }
                      />
                    </label>

                    <label>
                      Home Longitude (°)
                      <input
                        type="number"
                        step="any"
                        value={form.homeLongitude}
                        onChange={(e) =>
                          handleChange("homeLongitude", e.target.value)
                        }
                      />
                    </label>

                    <label>
                      Home Radius (m)
                      <input
                        type="number"
                        min="1"
                        value={form.homeRadius}
                        onChange={(e) =>
                          handleChange("homeRadius", e.target.value)
                        }
                      />
                    </label>
                  </div>
                </div>

                <div className="location-section location-section-spaced">
                  <h2 className="location-section-title">Current Location</h2>

                  <div className="location-form-grid">
                    <label>
                      Current Latitude (°)
                      <input
                        type="number"
                        step="any"
                        value={form.currentLatitude}
                        onChange={(e) =>
                          handleChange("currentLatitude", e.target.value)
                        }
                      />
                    </label>

                    <label>
                      Current Longitude (°)
                      <input
                        type="number"
                        step="any"
                        value={form.currentLongitude}
                        onChange={(e) =>
                          handleChange("currentLongitude", e.target.value)
                        }
                      />
                    </label>
                  </div>
                </div>

                <div className="location-actions">
                  <button
                    className="location-primary-btn"
                    type="submit"
                    disabled={loading || !company}
                  >
                    {loading ? "Saving..." : "Share / Update Location"}
                  </button>

                  {!company && !companyLoading && (
                    <p className="location-no-company-hint">
                      You must be assigned to a company before sharing your
                      location. Ask your company admin to add you.
                    </p>
                  )}
                </div>

                {error && (
                  <div className="location-alert location-alert-error">
                    {error}
                  </div>
                )}

                {successMessage && (
                  <div className="location-alert location-alert-success">
                    {successMessage}
                  </div>
                )}
              </form>

              <section className="location-summary">
                <h2 className="location-section-title">Current State</h2>
                <p className="location-section-subtitle">
                  Latest values saved in the trusted client backend.
                </p>

                {!savedData ? (
                  <p className="location-empty">
                    No location update submitted yet.
                  </p>
                ) : (
                  <div className="location-summary-list">
                    <div className="location-summary-row">
                      <span>Company</span>
                      <strong>{savedData.companyName}</strong>
                    </div>

                    <div className="location-summary-row">
                      <span>Home Latitude</span>
                      <strong>{savedData.homeLatitude}°</strong>
                    </div>

                    <div className="location-summary-row">
                      <span>Home Longitude</span>
                      <strong>{savedData.homeLongitude}°</strong>
                    </div>

                    <div className="location-summary-row">
                      <span>Home Radius</span>
                      <strong>{savedData.homeRadius} m</strong>
                    </div>

                    <div className="location-summary-row">
                      <span>Current Latitude</span>
                      <strong>{savedData.currentLatitude}°</strong>
                    </div>

                    <div className="location-summary-row">
                      <span>Current Longitude</span>
                      <strong>{savedData.currentLongitude}°</strong>
                    </div>

                    <div className="location-summary-row">
                      <span>Verification</span>
                      <strong>
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
                    <h3 className="location-section-title">
                      Verification Result
                    </h3>
                    <p className="location-section-subtitle">
                      Computed on encrypted data by the service provider.
                      Decrypted by both parties.
                    </p>

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
                        Last checked:{" "}
                        {new Date(verificationStatus.last_updated).toLocaleString()}
                      </p>
                    )}
                  </div>
                )}
              </section>
            </section>
          </div>
        </main>
      </div>
    </div>
  );
}
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import "../styles/location-sharing.css";

const API_BASE_URL = "http://127.0.0.1:8000";
const HOME_LOCATION_URL = `${API_BASE_URL}/client/company/home-location`;
const MY_COMPANIES_URL = `${API_BASE_URL}/client/company/my-companies`;

const initialForm = {
  homeLatitude: 5741200,
  homeLongitude: 2362100,
  homeRadius: 500,
  currentLatitude: 5741384.185332346,
  currentLongitude: 2362254.8313645967,
};

export default function LocationSharingPage() {
  const navigate = useNavigate();

  const [form, setForm] = useState(initialForm);
  const [company, setCompany] = useState(null);
  const [savedData, setSavedData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [companyLoading, setCompanyLoading] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

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

  const persistHomeAddress = async (token) => {
    await axios.post(
      HOME_LOCATION_URL,
      {
        encrypted_home_lat_m: String(form.homeLatitude),
        encrypted_home_lon_m: String(form.homeLongitude),
        home_radius_m: Number(form.homeRadius),
      },
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }
    );
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
      await persistHomeAddress(token);

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
        "Home address was saved and the current location was updated successfully."
      );
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
        "Could not update the location data.";

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
                      Home Latitude (m)
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
                      Home Longitude (m)
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
                      Current Latitude (m)
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
                      Current Longitude (m)
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
                    {loading ? "Updating..." : "Share / Update Location"}
                  </button>
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
                  Latest values prepared for encrypted processing.
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
                      <strong>{savedData.homeLatitude}</strong>
                    </div>

                    <div className="location-summary-row">
                      <span>Home Longitude</span>
                      <strong>{savedData.homeLongitude}</strong>
                    </div>

                    <div className="location-summary-row">
                      <span>Home Radius</span>
                      <strong>{savedData.homeRadius} m</strong>
                    </div>

                    <div className="location-summary-row">
                      <span>Current Latitude</span>
                      <strong>{savedData.currentLatitude}</strong>
                    </div>

                    <div className="location-summary-row">
                      <span>Current Longitude</span>
                      <strong>{savedData.currentLongitude}</strong>
                    </div>
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
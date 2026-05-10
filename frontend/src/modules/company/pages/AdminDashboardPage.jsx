// frontend/src/modules/company/pages/AdminDashboardPage.jsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import "../../poi-search/styles/poi-search.css";

const API_BASE_URL = "http://127.0.0.1:8000";
const COMPANY_API = `${API_BASE_URL}/client/company`;

const initialCompanyForm = {
  name: "Demo Company",
  allowed_country: "Romania",
  office_name: "Cluj Office",
  office_lat_m: 5741384.185332346,
  office_lon_m: 2362254.8313645967,
  office_radius_m: 300,

  country_north_m: 5900000,
  country_south_m: 5300000,
  country_east_m: 3300000,
  country_west_m: 2200000,

  encrypted_office_lat_m: "encrypted-office-lat-placeholder",
  encrypted_office_lon_m: "encrypted-office-lon-placeholder",
  encrypted_office_radius_m: "encrypted-office-radius-placeholder",
  encrypted_country_policy: "encrypted-country-bounds-placeholder",
};

export default function AdminDashboardPage() {
  const navigate = useNavigate();

  const [companyForm, setCompanyForm] = useState(initialCompanyForm);
  const [companies, setCompanies] = useState([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState("");
  const [allUsers, setAllUsers] = useState([]);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [employees, setEmployees] = useState([]);

  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const token = localStorage.getItem("access_token");
  const username = localStorage.getItem("username");

  const authHeaders = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };

  const handleUnauthorized = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("token_type");
    localStorage.removeItem("username");
    navigate("/login");
  };

  const handleChange = (field, value) => {
    setCompanyForm((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const loadCompanies = async () => {
    const response = await fetch(`${COMPANY_API}/admin/companies`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (response.status === 401 || response.status === 403) {
      handleUnauthorized();
      return;
    }

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data?.detail || "Could not load companies.");
    }

    const loadedCompanies = data.companies || [];
    setCompanies(loadedCompanies);

    if (loadedCompanies.length > 0 && !selectedCompanyId) {
      const firstId = String(loadedCompanies[0].id);
      setSelectedCompanyId(firstId);
      await loadEmployees(firstId);
    }
  };

  const loadAllUsers = async () => {
    const response = await fetch(`${API_BASE_URL}/auth/users`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (response.status === 401 || response.status === 403) {
      handleUnauthorized();
      return;
    }

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data?.detail || "Could not load users.");
    }

    setAllUsers(data.users || []);
  };

  const loadEmployees = async (companyId = selectedCompanyId) => {
    if (!companyId) return;

    const response = await fetch(
      `${COMPANY_API}/companies/${companyId}/users-status`,
      {
        headers: { Authorization: `Bearer ${token}` },
      }
    );

    if (response.status === 401 || response.status === 403) {
      handleUnauthorized();
      return;
    }

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data?.detail || "Could not load employees.");
    }

    setEmployees(data.users || []);
  };

  useEffect(() => {
    if (!token) {
      navigate("/login");
      return;
    }

    if (username !== "admin") {
      navigate("/home");
      return;
    }

    Promise.all([loadCompanies(), loadAllUsers()]).catch((err) =>
      setError(err.message)
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCreateCompany = async (event) => {
    event.preventDefault();

    setLoading(true);
    setError("");
    setMessage("");

    try {
      const payload = {
        ...companyForm,
        office_lat_m: Number(companyForm.office_lat_m),
        office_lon_m: Number(companyForm.office_lon_m),
        office_radius_m: Number(companyForm.office_radius_m),
        country_north_m: Number(companyForm.country_north_m),
        country_south_m: Number(companyForm.country_south_m),
        country_east_m: Number(companyForm.country_east_m),
        country_west_m: Number(companyForm.country_west_m),
      };

      const response = await fetch(`${COMPANY_API}/companies`, {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data?.detail || "Could not save company policy.");
      }

      setMessage("Company policy saved.");
      await loadCompanies();
    } catch (err) {
      setError(err.message || "Could not save company policy.");
    } finally {
      setLoading(false);
    }
  };

  const handleAddEmployee = async () => {
    if (!selectedCompanyId || !selectedUserId) {
      setError("Select a company and an employee.");
      return;
    }

    setLoading(true);
    setError("");
    setMessage("");

    try {
      const response = await fetch(`${COMPANY_API}/employees`, {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify({
          company_id: Number(selectedCompanyId),
          user_id: Number(selectedUserId),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data?.detail || "Could not add employee.");
      }

      setMessage("Employee added.");
      await loadEmployees(selectedCompanyId);
    } catch (err) {
      setError(err.message || "Could not add employee.");
    } finally {
      setLoading(false);
    }
  };

  const handleCompanyChange = async (value) => {
    setSelectedCompanyId(value);
    setEmployees([]);
    setError("");

    const company = companies.find((item) => String(item.id) === String(value));
    if (company) {
      setCompanyForm((prev) => ({
        ...prev,
        ...company,
      }));
    }

    await loadEmployees(value);
  };

  const handleLogout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("token_type");
    localStorage.removeItem("username");
    navigate("/login");
  };

  return (
    <div className="poi-page">
      <div className="poi-background-grid"></div>

      <div className="poi-shell">
        <aside className="poi-sidebar">
          <div className="poi-sidebar-card">
            <p className="poi-sidebar-kicker">Company Admin</p>

            <nav className="poi-sidebar-nav">
              <button className="poi-nav-item active" type="button">
                Admin Dashboard
              </button>

              <button
                className="poi-nav-item"
                type="button"
                onClick={() => navigate("/home")}
              >
                User Dashboard
              </button>
            </nav>

            <button className="poi-back-btn" type="button" onClick={handleLogout}>
              Log out
            </button>
          </div>
        </aside>

        <main className="poi-main">
          <div className="poi-container">
            <header className="poi-topbar">
              <div>
                <p className="poi-eyebrow">Company Compliance</p>
                <h1>Manage Office, Country Bounds and Employees</h1>
                <p className="poi-subtitle">
                  The company defines encrypted policy inputs and monitors only
                  final boolean employee status values.
                </p>
              </div>
            </header>

            <div className="poi-content-grid">
              <section className="poi-card poi-form-card">
                <div className="poi-card-header">
                  <h3>Company Policy</h3>
                  <p>Declare office coordinates and country bounding coordinates.</p>
                </div>

                <form className="poi-form" onSubmit={handleCreateCompany}>
                  <label>
                    Company
                    <select
                      value={selectedCompanyId}
                      onChange={(e) => handleCompanyChange(e.target.value)}
                    >
                      <option value="">New company</option>
                      {companies.map((company) => (
                        <option key={company.id} value={company.id}>
                          {company.name}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label>
                    Company Name
                    <input
                      value={companyForm.name}
                      onChange={(e) => handleChange("name", e.target.value)}
                    />
                  </label>

                  <label>
                    Country Name
                    <input
                      value={companyForm.allowed_country}
                      onChange={(e) =>
                        handleChange("allowed_country", e.target.value)
                      }
                    />
                  </label>

                  <label>
                    Office Name
                    <input
                      value={companyForm.office_name}
                      onChange={(e) => handleChange("office_name", e.target.value)}
                    />
                  </label>

                  <label>
                    Office Latitude (m)
                    <input
                      type="number"
                      step="any"
                      value={companyForm.office_lat_m}
                      onChange={(e) => handleChange("office_lat_m", e.target.value)}
                    />
                  </label>

                  <label>
                    Office Longitude (m)
                    <input
                      type="number"
                      step="any"
                      value={companyForm.office_lon_m}
                      onChange={(e) => handleChange("office_lon_m", e.target.value)}
                    />
                  </label>

                  <label>
                    Office Radius (m)
                    <input
                      type="number"
                      step="any"
                      value={companyForm.office_radius_m}
                      onChange={(e) =>
                        handleChange("office_radius_m", e.target.value)
                      }
                    />
                  </label>

                  <label>
                    North
                    <input
                      type="number"
                      step="any"
                      value={companyForm.country_north_m}
                      onChange={(e) =>
                        handleChange("country_north_m", e.target.value)
                      }
                    />
                  </label>

                  <label>
                    South
                    <input
                      type="number"
                      step="any"
                      value={companyForm.country_south_m}
                      onChange={(e) =>
                        handleChange("country_south_m", e.target.value)
                      }
                    />
                  </label>

                  <label>
                    East
                    <input
                      type="number"
                      step="any"
                      value={companyForm.country_east_m}
                      onChange={(e) =>
                        handleChange("country_east_m", e.target.value)
                      }
                    />
                  </label>

                  <label>
                    West
                    <input
                      type="number"
                      step="any"
                      value={companyForm.country_west_m}
                      onChange={(e) =>
                        handleChange("country_west_m", e.target.value)
                      }
                    />
                  </label>

                  <div className="full-width poi-form-actions">
                    <button className="primary-btn" type="submit" disabled={loading}>
                      {loading ? "Saving..." : "Save Company Policy"}
                    </button>
                  </div>
                </form>

                {message && <div className="poi-alert">{message}</div>}
                {error && <div className="poi-alert poi-alert-error">{error}</div>}
              </section>

              <section className="poi-card poi-results-card">
                <div className="poi-card-header">
                  <h3>Employees</h3>
                  <p>Add normal users as employees and view their compliance status.</p>
                </div>

                <div className="poi-form">
                  <label className="full-width">
                    Add Employee
                    <select
                      value={selectedUserId}
                      onChange={(e) => setSelectedUserId(e.target.value)}
                    >
                      <option value="">Select user</option>
                      {allUsers.map((user) => (
                        <option key={user.id} value={user.id}>
                          {user.username} — {user.email}
                        </option>
                      ))}
                    </select>
                  </label>

                  <div className="full-width poi-form-actions">
                    <button
                      className="primary-btn"
                      type="button"
                      disabled={loading || !selectedCompanyId || !selectedUserId}
                      onClick={handleAddEmployee}
                    >
                      Add Employee
                    </button>
                  </div>
                </div>

                {employees.length === 0 ? (
                  <p className="poi-empty">No employees added yet.</p>
                ) : (
                  <div className="poi-table-wrap">
                    <table className="poi-table">
                      <thead>
                        <tr>
                          <th>Employee</th>
                          <th>Email</th>
                          <th>In Country</th>
                          <th>At Home</th>
                          <th>At Office</th>
                          <th>Last Updated</th>
                        </tr>
                      </thead>
                      <tbody>
                        {employees.map((employee) => (
                          <tr key={employee.user_id}>
                            <td>{employee.username}</td>
                            <td>{employee.email}</td>
                            <td>{formatBool(employee.in_country)}</td>
                            <td>{formatBool(employee.at_home)}</td>
                            <td>{formatBool(employee.at_office)}</td>
                            <td>{employee.last_updated || "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
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

function formatBool(value) {
  if (value === true) return "Yes";
  if (value === false) return "No";
  return "Pending";
}
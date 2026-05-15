import { useEffect, useMemo, useState } from "react";
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
  const [selectedStatusUserId, setSelectedStatusUserId] = useState("");

  const [loading, setLoading] = useState(false);
  const [checkingCompliance, setCheckingCompliance] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const token = localStorage.getItem("access_token");
  const username = localStorage.getItem("username");

  const authHeaders = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };

  const selectedEmployeeStatus = useMemo(() => {
    return employees.find(
      (employee) => String(employee.user_id) === String(selectedStatusUserId)
    );
  }, [employees, selectedStatusUserId]);

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

    const loadedEmployees = data.users || [];
    setEmployees(loadedEmployees);

    if (loadedEmployees.length > 0 && !selectedStatusUserId) {
      setSelectedStatusUserId(String(loadedEmployees[0].user_id));
    }

    if (loadedEmployees.length === 0) {
      setSelectedStatusUserId("");
    }
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
      const firstCompany = loadedCompanies[0];
      const firstId = String(firstCompany.id);

      setSelectedCompanyId(firstId);
      setCompanyForm((prev) => ({
        ...prev,
        ...firstCompany,
      }));

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
      setSelectedUserId("");

      await loadEmployees(selectedCompanyId);
    } catch (err) {
      setError(err.message || "Could not add employee.");
    } finally {
      setLoading(false);
    }
  };

  const handleRunComplianceCheck = async () => {
    if (!selectedCompanyId || !selectedStatusUserId) {
      setError("Select a company and an employee first.");
      return;
    }

    setCheckingCompliance(true);
    setError("");
    setMessage("");

    try {
      const response = await fetch(
        `${COMPANY_API}/companies/${selectedCompanyId}/employees/${selectedStatusUserId}/run-compliance-check`,
        {
          method: "POST",
          headers: authHeaders,
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data?.detail || "Could not run compliance check.");
      }

      setMessage(
        `Compliance check completed. In country: ${formatBool(
          data.final_in_country
        )}, at home: ${formatBool(data.final_at_home)}, at office: ${formatBool(
          data.final_at_office
        )}.`
      );

      await loadEmployees(selectedCompanyId);
    } catch (err) {
      setError(err.message || "Could not run compliance check.");
    } finally {
      setCheckingCompliance(false);
    }
  };

  const handleCompanyChange = async (value) => {
    setSelectedCompanyId(value);
    setEmployees([]);
    setSelectedStatusUserId("");
    setError("");
    setMessage("");

    const company = companies.find((item) => String(item.id) === String(value));

    if (company) {
      setCompanyForm((prev) => ({
        ...prev,
        ...company,
      }));

      await loadEmployees(value);
    } else {
      setCompanyForm(initialCompanyForm);
    }
  };

  const handleStatusEmployeeChange = (value) => {
    setSelectedStatusUserId(value);
    setError("");
    setMessage("");
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

            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "24px",
                width: "100%",
              }}
            >
              <section className="poi-card">
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
              </section>

              <section className="poi-card">
                <div className="poi-card-header">
                  <h3>Add Employees</h3>
                  <p>
                    Select a registered user and assign the user to the selected
                    company.
                  </p>
                </div>

                <div className="poi-form">
                  <label className="full-width">
                    Employee
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
                      {loading ? "Adding..." : "Add Employee"}
                    </button>
                  </div>
                </div>
              </section>

              <section className="poi-card">
                <div className="poi-card-header">
                  <h3>Employee Compliance Status</h3>
                  <p>
                    Select an employee, then run the encrypted compliance check.
                    The company receives only the final boolean status.
                  </p>
                </div>

                {employees.length === 0 ? (
                  <p className="poi-empty">No employees added yet.</p>
                ) : (
                  <>
                    <div className="poi-form">
                      <label className="full-width">
                        Employee
                        <select
                          value={selectedStatusUserId}
                          onChange={(e) =>
                            handleStatusEmployeeChange(e.target.value)
                          }
                        >
                          <option value="">Select employee</option>
                          {employees.map((employee) => (
                            <option
                              key={employee.user_id}
                              value={employee.user_id}
                            >
                              {employee.username} — {employee.email}
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>

                    {!selectedEmployeeStatus ? (
                      <p className="poi-empty">
                        Select an employee to view the status.
                      </p>
                    ) : (
                      <>
                        <div className="poi-table-wrap">
                          <table className="poi-table">
                            <tbody>
                              <tr>
                                <th>Employee</th>
                                <td>{selectedEmployeeStatus.username}</td>
                              </tr>

                              <tr>
                                <th>Email</th>
                                <td>{selectedEmployeeStatus.email}</td>
                              </tr>

                              <tr>
                                <th>In Country</th>
                                <td>
                                  {formatBool(selectedEmployeeStatus.in_country)}
                                </td>
                              </tr>

                              <tr>
                                <th>At Home</th>
                                <td>
                                  {formatBool(selectedEmployeeStatus.at_home)}
                                </td>
                              </tr>

                              <tr>
                                <th>At Office</th>
                                <td>
                                  {formatBool(selectedEmployeeStatus.at_office)}
                                </td>
                              </tr>

                              <tr>
                                <th>Last Updated</th>
                                <td>
                                  {selectedEmployeeStatus.last_updated || "—"}
                                </td>
                              </tr>
                            </tbody>
                          </table>
                        </div>

                        <div className="full-width poi-form-actions">
                          <button
                            className="primary-btn"
                            type="button"
                            disabled={
                              checkingCompliance ||
                              loading ||
                              !selectedCompanyId ||
                              !selectedStatusUserId
                            }
                            onClick={handleRunComplianceCheck}
                          >
                            {checkingCompliance
                              ? "Running Check..."
                              : "Run Compliance Check"}
                          </button>

                          <button
                            className="primary-btn"
                            type="button"
                            disabled={!selectedCompanyId || loading}
                            onClick={() => loadEmployees(selectedCompanyId)}
                          >
                            Refresh Status
                          </button>
                        </div>
                      </>
                    )}
                  </>
                )}
              </section>

              {(message || error) && (
                <section className="poi-card">
                  {message && <div className="poi-alert">{message}</div>}
                  {error && <div className="poi-alert poi-alert-error">{error}</div>}
                </section>
              )}
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
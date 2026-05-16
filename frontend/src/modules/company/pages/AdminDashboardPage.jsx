import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import "../../poi-search/styles/poi-search.css";

const API_BASE_URL = "http://127.0.0.1:8000";
const COMPANY_API = `${API_BASE_URL}/client/company`;

const BLANK_FORM = {
  name: "Technical University of Cluj-Napoca",
  allowed_country: "Romania",
  office_name: "Cluj Office",
  office_lat_m: 5901100,
  office_lon_m: 2626008,
  office_radius_m: 300,
  country_north_m: 6120000,
  country_south_m: 5424000,
  country_east_m: 3302000,
  country_west_m: 2256000,
};

export default function AdminDashboardPage() {
  const navigate = useNavigate();

  const [currentPage, setCurrentPage] = useState("company-policy");

  // Shared
  const [companies, setCompanies] = useState([]);
  const [allUsers, setAllUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  // Page 1 — Create Company
  const [createForm, setCreateForm] = useState(BLANK_FORM);

  // Page 2 — Update Company
  const [updateCompanyId, setUpdateCompanyId] = useState("");
  const [updateForm, setUpdateForm] = useState(BLANK_FORM);

  // Page 3 — Manage Employees
  const [manageCompanyId, setManageCompanyId] = useState("");
  const [employees, setEmployees] = useState([]);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [selectedStatusUserId, setSelectedStatusUserId] = useState("");
  const [checkingCompliance, setCheckingCompliance] = useState(false);
  const [complianceResult, setComplianceResult] = useState(null);

  const token = localStorage.getItem("access_token");
  const username = localStorage.getItem("username");

  const authHeaders = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };

  const selectedEmployeeStatus = useMemo(
    () => employees.find((e) => String(e.user_id) === String(selectedStatusUserId)),
    [employees, selectedStatusUserId]
  );

  const handleUnauthorized = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("token_type");
    localStorage.removeItem("username");
    navigate("/login");
  };

  const clearFeedback = () => {
    setMessage("");
    setError("");
  };

  const handlePageChange = (page) => {
    setCurrentPage(page);
    clearFeedback();
  };

  const handleLogout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("token_type");
    localStorage.removeItem("username");
    navigate("/login");
  };

  // ── Data loaders ──────────────────────────────────────────────────────────

  const loadCompanies = async () => {
    const res = await fetch(`${COMPANY_API}/admin/companies`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.status === 401 || res.status === 403) { handleUnauthorized(); return []; }
    const data = await res.json();
    if (!res.ok) throw new Error(data?.detail || "Could not load companies.");
    const list = data.companies || [];
    setCompanies(list);
    return list;
  };

  const loadAllUsers = async () => {
    const res = await fetch(`${API_BASE_URL}/auth/users`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.status === 401 || res.status === 403) { handleUnauthorized(); return; }
    const data = await res.json();
    if (!res.ok) throw new Error(data?.detail || "Could not load users.");
    setAllUsers(data.users || []);
  };

  const loadEmployees = async (companyId, currentStatusUserId) => {
    if (!companyId) return;
    const res = await fetch(`${COMPANY_API}/companies/${companyId}/users-status`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.status === 401 || res.status === 403) { handleUnauthorized(); return; }
    const data = await res.json();
    if (!res.ok) throw new Error(data?.detail || "Could not load employees.");
    const list = data.users || [];
    setEmployees(list);
    if (list.length > 0 && !currentStatusUserId) {
      setSelectedStatusUserId(String(list[0].user_id));
    }
    if (list.length === 0) setSelectedStatusUserId("");
  };

  useEffect(() => {
    if (!token) { navigate("/login"); return; }
    if (username !== "admin") { navigate("/home"); return; }
    Promise.all([loadCompanies(), loadAllUsers()]).catch((err) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Page 1 handlers ───────────────────────────────────────────────────────

  const handleCreateCompany = async (e) => {
    e.preventDefault();
    setLoading(true);
    clearFeedback();
    try {
      const payload = numberiseForm(createForm);
      const res = await fetch(`${COMPANY_API}/companies`, {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Could not create company.");
      setMessage("Company created successfully.");
      await loadCompanies();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // ── Page 2 handlers ───────────────────────────────────────────────────────

  const handleSelectUpdateCompany = (companyId) => {
    setUpdateCompanyId(companyId);
    clearFeedback();
    if (!companyId) { setUpdateForm(BLANK_FORM); return; }
    const company = companies.find((c) => String(c.id) === String(companyId));
    if (company) {
      setUpdateForm({
        name: company.name,
        allowed_country: company.allowed_country,
        office_name: company.office_name,
        office_lat_m: company.office_lat_m,
        office_lon_m: company.office_lon_m,
        office_radius_m: company.office_radius_m,
        country_north_m: company.country_north_m ?? "",
        country_south_m: company.country_south_m ?? "",
        country_east_m: company.country_east_m ?? "",
        country_west_m: company.country_west_m ?? "",
      });
    }
  };

  const handleUpdateCompany = async (e) => {
    e.preventDefault();
    if (!updateCompanyId) { setError("Select a company first."); return; }
    setLoading(true);
    clearFeedback();
    try {
      const res = await fetch(`${COMPANY_API}/companies/${updateCompanyId}`, {
        method: "PUT",
        headers: authHeaders,
        body: JSON.stringify(numberiseForm(updateForm)),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Could not update company.");
      setMessage("Company updated successfully.");
      await loadCompanies();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteCompany = async () => {
    if (!updateCompanyId) { setError("Select a company first."); return; }
    if (!window.confirm("Delete this company? All associated data will be removed.")) return;
    setLoading(true);
    clearFeedback();
    try {
      const res = await fetch(`${COMPANY_API}/companies/${updateCompanyId}`, {
        method: "DELETE",
        headers: authHeaders,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Could not delete company.");
      setMessage("Company deleted.");
      setUpdateCompanyId("");
      setUpdateForm(BLANK_FORM);
      await loadCompanies();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // ── Page 3 handlers ───────────────────────────────────────────────────────

  const handleSelectManageCompany = async (companyId) => {
    setManageCompanyId(companyId);
    setEmployees([]);
    setSelectedStatusUserId("");
    setComplianceResult(null);
    clearFeedback();
    if (companyId) {
      try { await loadEmployees(companyId, ""); }
      catch (err) { setError(err.message); }
    }
  };

  const handleAddEmployee = async () => {
    if (!manageCompanyId || !selectedUserId) {
      setError("Select a company and a user.");
      return;
    }
    setLoading(true);
    clearFeedback();
    try {
      const res = await fetch(`${COMPANY_API}/employees`, {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify({
          company_id: Number(manageCompanyId),
          user_id: Number(selectedUserId),
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Could not add employee.");
      setMessage("Employee added.");
      setSelectedUserId("");
      await loadEmployees(manageCompanyId, selectedStatusUserId);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRunComplianceCheck = async () => {
    if (!manageCompanyId || !selectedStatusUserId) {
      setError("Select a company and an employee first.");
      return;
    }
    setCheckingCompliance(true);
    setComplianceResult(null);
    clearFeedback();
    try {
      const res = await fetch(
        `${COMPANY_API}/companies/${manageCompanyId}/employees/${selectedStatusUserId}/run-compliance-check`,
        { method: "POST", headers: authHeaders }
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Could not run compliance check.");
      setComplianceResult(data);
      await loadEmployees(manageCompanyId, selectedStatusUserId);
    } catch (err) {
      setError(err.message);
    } finally {
      setCheckingCompliance(false);
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="poi-page">
      <div className="poi-background-grid"></div>
      <div className="poi-shell">
        <aside className="poi-sidebar">
          <div className="poi-sidebar-card">
            <p className="poi-sidebar-kicker">Company Admin</p>
            <nav className="poi-sidebar-nav">
              <button
                className={`poi-nav-item ${currentPage === "company-policy" ? "active" : ""}`}
                type="button"
                onClick={() => handlePageChange("company-policy")}
              >
                Company Policy
              </button>
              <button
                className={`poi-nav-item ${currentPage === "update-company" ? "active" : ""}`}
                type="button"
                onClick={() => handlePageChange("update-company")}
              >
                Update Company
              </button>
              <button
                className={`poi-nav-item ${currentPage === "manage-employees" ? "active" : ""}`}
                type="button"
                onClick={() => handlePageChange("manage-employees")}
              >
                Manage Employees
              </button>
            </nav>
            <button className="poi-back-btn" type="button" onClick={handleLogout}>
              Log out
            </button>
          </div>
        </aside>

        <main className="poi-main">
          <div className="poi-container">

            {/* ── Page 1: Company Policy (Create) ── */}
            {currentPage === "company-policy" && (
              <>
                <header className="poi-topbar">
                  <div>
                    <p className="poi-eyebrow">Company Admin</p>
                    <h1>Create Company Policy</h1>
                    <p className="poi-subtitle">
                      Define a new company with encrypted office location and country bounds.
                    </p>
                  </div>
                </header>

                <div style={{ display: "flex", flexDirection: "column", gap: "24px", width: "100%" }}>
                  <section className="poi-card">
                    <div className="poi-card-header">
                      <h3>New Company</h3>
                      <p>All coordinates are in Web Mercator meters (EPSG:3857).</p>
                    </div>
                    <form className="poi-form" onSubmit={handleCreateCompany}>
                      <CompanyFormFields form={createForm} onChange={(f, v) => setCreateForm((p) => ({ ...p, [f]: v }))} />
                      <div className="full-width poi-form-actions">
                        <button className="primary-btn" type="submit" disabled={loading}>
                          {loading ? "Creating..." : "Create Company"}
                        </button>
                      </div>
                    </form>
                  </section>

                  <FeedbackSection message={message} error={error} />
                </div>
              </>
            )}

            {/* ── Page 2: Update Company ── */}
            {currentPage === "update-company" && (
              <>
                <header className="poi-topbar">
                  <div>
                    <p className="poi-eyebrow">Company Admin</p>
                    <h1>Update Company</h1>
                    <p className="poi-subtitle">
                      Edit office location, country bounds, or delete the company.
                    </p>
                  </div>
                </header>

                <div style={{ display: "flex", flexDirection: "column", gap: "24px", width: "100%" }}>
                  <section className="poi-card">
                    <div className="poi-card-header">
                      <h3>Select Company</h3>
                    </div>
                    <div className="poi-form">
                      <label className="full-width">
                        Company
                        <select
                          value={updateCompanyId}
                          onChange={(e) => handleSelectUpdateCompany(e.target.value)}
                        >
                          <option value="">— select a company —</option>
                          {companies.map((c) => (
                            <option key={c.id} value={c.id}>{c.name}</option>
                          ))}
                        </select>
                      </label>
                    </div>
                  </section>

                  {updateCompanyId && (
                    <section className="poi-card">
                      <div className="poi-card-header">
                        <h3>Edit Details</h3>
                        <p>Changes re-encrypt all location values with the current HE keys.</p>
                      </div>
                      <form className="poi-form" onSubmit={handleUpdateCompany}>
                        <CompanyFormFields
                          form={updateForm}
                          onChange={(f, v) => setUpdateForm((p) => ({ ...p, [f]: v }))}
                        />
                        <div className="full-width poi-form-actions">
                          <button className="primary-btn" type="submit" disabled={loading}>
                            {loading ? "Saving..." : "Save Changes"}
                          </button>
                          <button
                            className="primary-btn"
                            type="button"
                            disabled={loading}
                            onClick={handleDeleteCompany}
                            style={{ background: "var(--color-error, #e53e3e)" }}
                          >
                            {loading ? "Deleting..." : "Delete Company"}
                          </button>
                        </div>
                      </form>
                    </section>
                  )}

                  {!updateCompanyId && companies.length === 0 && (
                    <p className="poi-empty">No companies yet. Create one on the Company Policy page.</p>
                  )}

                  <FeedbackSection message={message} error={error} />
                </div>
              </>
            )}

            {/* ── Page 3: Manage Employees ── */}
            {currentPage === "manage-employees" && (
              <>
                <header className="poi-topbar">
                  <div>
                    <p className="poi-eyebrow">Company Admin</p>
                    <h1>Manage Employees</h1>
                    <p className="poi-subtitle">
                      Assign employees to a company and run encrypted compliance checks.
                    </p>
                  </div>
                </header>

                <div style={{ display: "flex", flexDirection: "column", gap: "24px", width: "100%" }}>
                  {/* Company selector */}
                  <section className="poi-card">
                    <div className="poi-card-header">
                      <h3>Select Company</h3>
                    </div>
                    <div className="poi-form">
                      <label className="full-width">
                        Company
                        <select
                          value={manageCompanyId}
                          onChange={(e) => handleSelectManageCompany(e.target.value)}
                        >
                          <option value="">— select a company —</option>
                          {companies.map((c) => (
                            <option key={c.id} value={c.id}>{c.name}</option>
                          ))}
                        </select>
                      </label>
                    </div>
                  </section>

                  {/* Add employee */}
                  {manageCompanyId && (
                    <section className="poi-card">
                      <div className="poi-card-header">
                        <h3>Add Employee</h3>
                        <p>Assign a registered user to this company.</p>
                      </div>
                      <div className="poi-form">
                        <label className="full-width">
                          User
                          <select
                            value={selectedUserId}
                            onChange={(e) => setSelectedUserId(e.target.value)}
                          >
                            <option value="">Select user</option>
                            {allUsers.map((u) => (
                              <option key={u.id} value={u.id}>
                                {u.username} — {u.email}
                              </option>
                            ))}
                          </select>
                        </label>
                        <div className="full-width poi-form-actions">
                          <button
                            className="primary-btn"
                            type="button"
                            disabled={loading || !selectedUserId}
                            onClick={handleAddEmployee}
                          >
                            {loading ? "Adding..." : "Add Employee"}
                          </button>
                        </div>
                      </div>
                    </section>
                  )}

                  {/* Compliance status */}
                  {manageCompanyId && (
                    <section className="poi-card">
                      <div className="poi-card-header">
                        <h3>Compliance Status</h3>
                        <p>
                          Select an employee and run the encrypted compliance check. Both the
                          HE result and the plaintext reference are shown side by side.
                        </p>
                      </div>

                      {employees.length === 0 ? (
                        <p className="poi-empty">No employees assigned yet.</p>
                      ) : (
                        <>
                          <div className="poi-form">
                            <label className="full-width">
                              Employee
                              <select
                                value={selectedStatusUserId}
                                onChange={(e) => {
                                  setSelectedStatusUserId(e.target.value);
                                  setComplianceResult(null);
                                  clearFeedback();
                                }}
                              >
                                <option value="">Select employee</option>
                                {employees.map((e) => (
                                  <option key={e.user_id} value={e.user_id}>
                                    {e.username} — {e.email}
                                  </option>
                                ))}
                              </select>
                            </label>
                          </div>

                          {selectedEmployeeStatus && (
                            <>
                              {/* Persistent status table */}
                              <div className="poi-table-wrap">
                                <table className="poi-table">
                                  <thead>
                                    <tr>
                                      <th></th>
                                      <th style={{ textAlign: "center" }}>HE (encrypted)</th>
                                      <th style={{ textAlign: "center" }}>Plaintext</th>
                                      <th style={{ textAlign: "center" }}>Match</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    <tr>
                                      <th>Employee</th>
                                      <td colSpan={3}>{selectedEmployeeStatus.username}</td>
                                    </tr>
                                    <tr>
                                      <th>Email</th>
                                      <td colSpan={3}>{selectedEmployeeStatus.email}</td>
                                    </tr>
                                    <tr>
                                      <th>In Country</th>
                                      <td style={{ textAlign: "center" }}>{formatBool(selectedEmployeeStatus.in_country)}</td>
                                      <td style={{ textAlign: "center" }}>{formatBool(selectedEmployeeStatus.plaintext_in_country)}</td>
                                      <td style={{ textAlign: "center" }}>{matchBadge(selectedEmployeeStatus.in_country, selectedEmployeeStatus.plaintext_in_country)}</td>
                                    </tr>
                                    <tr>
                                      <th>At Home</th>
                                      <td style={{ textAlign: "center" }}>{formatBool(selectedEmployeeStatus.at_home)}</td>
                                      <td style={{ textAlign: "center" }}>{formatBool(selectedEmployeeStatus.plaintext_at_home)}</td>
                                      <td style={{ textAlign: "center" }}>{matchBadge(selectedEmployeeStatus.at_home, selectedEmployeeStatus.plaintext_at_home)}</td>
                                    </tr>
                                    <tr>
                                      <th>At Office</th>
                                      <td style={{ textAlign: "center" }}>{formatBool(selectedEmployeeStatus.at_office)}</td>
                                      <td style={{ textAlign: "center" }}>{formatBool(selectedEmployeeStatus.plaintext_at_office)}</td>
                                      <td style={{ textAlign: "center" }}>{matchBadge(selectedEmployeeStatus.at_office, selectedEmployeeStatus.plaintext_at_office)}</td>
                                    </tr>
                                    <tr>
                                      <th>Last Updated</th>
                                      <td colSpan={3}>{selectedEmployeeStatus.last_updated || "—"}</td>
                                    </tr>
                                  </tbody>
                                </table>
                              </div>

                              <div className="full-width poi-form-actions">
                                <button
                                  className="primary-btn"
                                  type="button"
                                  disabled={checkingCompliance || loading}
                                  onClick={handleRunComplianceCheck}
                                >
                                  {checkingCompliance ? "Running Check..." : "Run Compliance Check"}
                                </button>
                                <button
                                  className="primary-btn"
                                  type="button"
                                  disabled={loading}
                                  onClick={() => loadEmployees(manageCompanyId, selectedStatusUserId)}
                                >
                                  Refresh
                                </button>
                              </div>

                              {/* Fresh result from the last check in this session */}
                              {complianceResult && (
                                <div style={{ marginTop: "20px" }}>
                                  <h4 style={{ marginBottom: "10px", color: "var(--text-primary, #e2e8f0)" }}>
                                    Latest Check — {complianceResult.username}
                                  </h4>
                                  <div className="poi-table-wrap">
                                    <table className="poi-table">
                                      <thead>
                                        <tr>
                                          <th>Metric</th>
                                          <th style={{ textAlign: "center" }}>HE (encrypted)</th>
                                          <th style={{ textAlign: "center" }}>Plaintext</th>
                                          <th style={{ textAlign: "center" }}>Match</th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        <tr>
                                          <th>At Home</th>
                                          <td style={{ textAlign: "center" }}>{formatBool(complianceResult.final_at_home)}</td>
                                          <td style={{ textAlign: "center" }}>{formatBool(complianceResult.plaintext_at_home)}</td>
                                          <td style={{ textAlign: "center" }}>{matchBadge(complianceResult.final_at_home, complianceResult.plaintext_at_home)}</td>
                                        </tr>
                                        <tr>
                                          <th>At Office</th>
                                          <td style={{ textAlign: "center" }}>{formatBool(complianceResult.final_at_office)}</td>
                                          <td style={{ textAlign: "center" }}>{formatBool(complianceResult.plaintext_at_office)}</td>
                                          <td style={{ textAlign: "center" }}>{matchBadge(complianceResult.final_at_office, complianceResult.plaintext_at_office)}</td>
                                        </tr>
                                        <tr>
                                          <th>In Country</th>
                                          <td style={{ textAlign: "center" }}>{formatBool(complianceResult.final_in_country)}</td>
                                          <td style={{ textAlign: "center" }}>{formatBool(complianceResult.plaintext_in_country)}</td>
                                          <td style={{ textAlign: "center" }}>{matchBadge(complianceResult.final_in_country, complianceResult.plaintext_in_country)}</td>
                                        </tr>
                                      </tbody>
                                    </table>
                                  </div>
                                </div>
                              )}
                            </>
                          )}
                        </>
                      )}
                    </section>
                  )}

                  <FeedbackSection message={message} error={error} />
                </div>
              </>
            )}

          </div>
        </main>
      </div>
    </div>
  );
}

// ── Shared form fields component ─────────────────────────────────────────────

function CompanyFormFields({ form, onChange }) {
  return (
    <>
      <label>
        Company Name
        <input value={form.name} onChange={(e) => onChange("name", e.target.value)} />
      </label>

      <label>
        Country Name
        <input value={form.allowed_country} onChange={(e) => onChange("allowed_country", e.target.value)} />
      </label>

      <label>
        Office Name
        <input value={form.office_name} onChange={(e) => onChange("office_name", e.target.value)} />
      </label>

      <label>
        Office Latitude (m)
        <input type="number" step="any" value={form.office_lat_m} onChange={(e) => onChange("office_lat_m", e.target.value)} />
      </label>

      <label>
        Office Longitude (m)
        <input type="number" step="any" value={form.office_lon_m} onChange={(e) => onChange("office_lon_m", e.target.value)} />
      </label>

      <label>
        Office Radius (m)
        <input type="number" step="any" value={form.office_radius_m} onChange={(e) => onChange("office_radius_m", e.target.value)} />
      </label>

      <label>
        Country North (m)
        <input type="number" step="any" value={form.country_north_m} onChange={(e) => onChange("country_north_m", e.target.value)} />
      </label>

      <label>
        Country South (m)
        <input type="number" step="any" value={form.country_south_m} onChange={(e) => onChange("country_south_m", e.target.value)} />
      </label>

      <label>
        Country East (m)
        <input type="number" step="any" value={form.country_east_m} onChange={(e) => onChange("country_east_m", e.target.value)} />
      </label>

      <label>
        Country West (m)
        <input type="number" step="any" value={form.country_west_m} onChange={(e) => onChange("country_west_m", e.target.value)} />
      </label>
    </>
  );
}

// ── Feedback banner ───────────────────────────────────────────────────────────

function FeedbackSection({ message, error }) {
  if (!message && !error) return null;
  return (
    <section className="poi-card">
      {message && <div className="poi-alert">{message}</div>}
      {error && <div className="poi-alert poi-alert-error">{error}</div>}
    </section>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function numberiseForm(form) {
  return {
    ...form,
    office_lat_m: Number(form.office_lat_m),
    office_lon_m: Number(form.office_lon_m),
    office_radius_m: Number(form.office_radius_m),
    country_north_m: Number(form.country_north_m),
    country_south_m: Number(form.country_south_m),
    country_east_m: Number(form.country_east_m),
    country_west_m: Number(form.country_west_m),
  };
}

function formatBool(value) {
  if (value === true) return "Yes";
  if (value === false) return "No";
  return "Pending";
}

function matchBadge(he, plaintext) {
  if (he == null || plaintext == null) return "—";
  if (he === plaintext) {
    return (
      <span style={{ color: "var(--color-success, #48bb78)", fontWeight: 600 }}>
        OK
      </span>
    );
  }
  return (
    <span style={{ color: "var(--color-error, #e53e3e)", fontWeight: 600 }}>
      MISMATCH
    </span>
  );
}

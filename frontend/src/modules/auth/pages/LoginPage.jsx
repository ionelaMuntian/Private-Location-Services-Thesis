import { useState } from "react";
import { useNavigate } from "react-router-dom";
import PageShell from "../../../components/PageShell";
import "../styles/login.css";

const API_BASE_URL = "http://127.0.0.1:8000";

export default function LoginPage() {
  const navigate = useNavigate();

  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  const resetMessages = () => {
    setErrorMessage("");
    setSuccessMessage("");
  };

  const handleModeChange = (nextMode) => {
    setMode(nextMode);
    resetMessages();
  };

  const handleLogin = async (event) => {
    event.preventDefault();
    resetMessages();
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username,
          password,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data?.detail || "Login failed.");
      }

      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("token_type", data.token_type || "bearer");
      localStorage.setItem("username", username);

      setSuccessMessage("Login successful.");
      navigate("/home");
    } catch (error) {
      setErrorMessage(error.message || "Login failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleSignup = async (event) => {
    event.preventDefault();
    resetMessages();
    setLoading(true);

    try {
      const registerResponse = await fetch(`${API_BASE_URL}/auth/register`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username,
          email,
          password,
        }),
      });

      const registerData = await registerResponse.json();

      if (!registerResponse.ok) {
        throw new Error(registerData?.detail || "Sign up failed.");
      }

      const loginResponse = await fetch(`${API_BASE_URL}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username,
          password,
        }),
      });

      const loginData = await loginResponse.json();

      if (!loginResponse.ok) {
        throw new Error(loginData?.detail || "Automatic login after sign up failed.");
      }

      localStorage.setItem("access_token", loginData.access_token);
      localStorage.setItem("token_type", loginData.token_type || "bearer");
      localStorage.setItem("username", username);

      setSuccessMessage("Account created successfully.");
      navigate("/home");
    } catch (error) {
      setErrorMessage(error.message || "Sign up failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <PageShell className="login-page">
      <div className="login-layout">
        <div className="login-grid"></div>
        <div className="login-glow glow-left"></div>
        <div className="login-glow glow-right"></div>

        <section className="login-left">
          <p className="login-kicker">Bachelor Thesis</p>

          <h1>
            <span className="login-title-main">
              A Homomorphic Encryption Approach to
            </span>
            <span className="login-title-highlight">
              Location-Based Services
            </span>
          </h1>

          <div className="login-tags">
            <span>Trusted Client</span>
            <span>Encrypted Queries</span>
            <span>POI Search</span>
          </div>
        </section>

        <section className="login-right">
          <div className="login-card">
            <div className="login-card-header">
              <h2>{mode === "login" ? "Welcome back" : "Create account"}</h2>
              <p className="login-subtitle">
                {mode === "login"
                  ? "Sign in to access encrypted location-based search."
                  : "Create an account to start using the trusted client."}
              </p>
            </div>

            <div className="login-toggle">
              <button
                type="button"
                className={`toggle-btn ${mode === "login" ? "active" : ""}`}
                onClick={() => handleModeChange("login")}
              >
                Log in
              </button>
              <button
                type="button"
                className={`toggle-btn ${mode === "signup" ? "active" : ""}`}
                onClick={() => handleModeChange("signup")}
              >
                Sign up
              </button>
            </div>

            <form
              className="auth-form"
              onSubmit={mode === "login" ? handleLogin : handleSignup}
            >
              <div className="form-group">
                <label htmlFor="username">Username</label>
                <input
                  id="username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter your username"
                  required
                />
              </div>

              {mode === "signup" && (
                <div className="form-group">
                  <label htmlFor="email">Email</label>
                  <input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="Enter your email"
                    required
                  />
                </div>
              )}

              <div className="form-group">
                <label htmlFor="password">Password</label>
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  required
                />
              </div>

              {errorMessage && (
                <p className="auth-message auth-error">{errorMessage}</p>
              )}

              {successMessage && (
                <p className="auth-message auth-success">{successMessage}</p>
              )}

              <button className="login-btn" type="submit" disabled={loading}>
                {loading
                  ? mode === "login"
                    ? "Logging in..."
                    : "Creating account..."
                  : mode === "login"
                  ? "Log in"
                  : "Sign up"}
              </button>
            </form>
          </div>
        </section>
      </div>
    </PageShell>
  );
}
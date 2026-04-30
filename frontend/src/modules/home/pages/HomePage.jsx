import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import PageShell from "../../../components/PageShell";
import ServiceCard from "../../../components/ServiceCard";
import "../styles/home.css";

export default function HomePage() {
  const navigate = useNavigate();

  useEffect(() => {
    const token = localStorage.getItem("access_token");

    if (!token) {
      navigate("/login");
    }
  }, [navigate]);

  const handleSignOut = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("token_type");
    localStorage.removeItem("username");
    navigate("/login");
  };

  const username = localStorage.getItem("username");

  return (
    <PageShell className="home-page">
      <div className="home-layout">
        <div className="home-grid"></div>
        <div className="home-glow glow-left"></div>
        <div className="home-glow glow-right"></div>

        <header className="topbar">
          <div>
            <p className="eyebrow">Trusted Client Dashboard</p>
            <h1>
              <span className="home-title-main">Privacy-Preserving</span>
              <span className="home-title-highlight">Location-Based Services</span>
            </h1>
            <p className="home-subtitle">
              {username
                ? `Welcome, ${username}. Select one of the available modules to continue.`
                : "Select one of the available modules to continue."}
            </p>
          </div>

          <button className="signout-btn" onClick={handleSignOut}>
            Sign out
          </button>
        </header>

        <section className="services-grid">
          <ServiceCard
            title="Nearest Points of Interest"
            description="Search nearby hospitals, pharmacies, and other places using Plaintext, CKKS, BFV, or Concrete query flows."
            route="/poi-search"
            status="Ready"
          />

          <ServiceCard
            title="Location Sharing"
            description="Share and compare protected locations through privacy-preserving computation."
            route="/location-sharing"
            status="Planned"
          />

          <ServiceCard
            title="Impossible Travel Detection"
            description="Inspect suspicious travel patterns while reducing direct exposure of location history."
            route="/anomaly-detection"
            status="Planned"
          />

          <div className="home-grid-spacer"></div>

          <ServiceCard
            title="Statistics & Benchmarks"
            description="View scheme comparisons, execution time, latency, encryption overhead, and performance charts."
            route="/statistics"
            status="Ready"
          />

          <div className="home-grid-spacer"></div>
        </section>
      </div>
    </PageShell>
  );
}
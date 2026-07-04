import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import ServiceCard from "../../../components/ServiceCard";
import "../styles/home.css";

export default function HomePage() {
  const navigate = useNavigate();

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) navigate("/login");
  }, [navigate]);

  const handleSignOut = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("token_type");
    localStorage.removeItem("username");
    navigate("/login");
  };

  const username = localStorage.getItem("username");

  return (
    <div className="home-page">
      <header className="home-topbar">
        <span className="home-topbar-title">Privacy-Preserving Location-Based Services</span>
        <div className="home-topbar-right">
          {username && <span className="home-topbar-user">{username}</span>}
          <button className="signout-btn" onClick={handleSignOut}>Sign out</button>
        </div>
      </header>

      <div className="home-content">
        <h1 className="home-heading">
          Welcome to<br />
          <span>Location Services</span>
        </h1>

        <div className="services-grid">
          <ServiceCard title="Nearest Points of Interest" route="/poi-search" icon="poi" />
          <ServiceCard title="Location Sharing" route="/location-sharing" icon="sharing" />
          <ServiceCard title="Risk Based Authentication" route="/anomaly-detection" icon="anomaly" />
          <ServiceCard title="Statistics & Benchmarks" route="/statistics" icon="stats" />
        </div>
      </div>
    </div>
  );
}

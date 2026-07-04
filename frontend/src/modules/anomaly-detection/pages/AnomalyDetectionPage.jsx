import { useState } from "react";
import { useNavigate } from "react-router-dom";
import "../../poi-search/styles/poi-search.css";
import "../styles/anomaly-detection.css";
import NotebookViewer from "../components/NotebookViewer";

const NOTEBOOK_URL = "/notebooks/impossible_travel_model.ipynb";
const NOTEBOOK_IMAGES_BASE_URL = "/notebooks";

export default function AnomalyDetectionPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("results");

  return (
    <div className="poi-page">
      <div className="poi-background-grid"></div>

      <div className="poi-shell">
        <aside className="poi-sidebar">
          <div className="poi-sidebar-card">
            <p className="poi-sidebar-kicker">Services</p>
            <nav className="poi-sidebar-nav">
              <button className="poi-nav-item" type="button" onClick={() => navigate("/poi-search")}>
                Nearest POI Search
              </button>
              <button className="poi-nav-item" type="button" onClick={() => navigate("/location-sharing")}>
                Location Sharing
              </button>
              <button className="poi-nav-item active" type="button">
                Risk Based Authentication
              </button>
              <button className="poi-nav-item" type="button" onClick={() => navigate("/statistics")}>
                Statistics &amp; Benchmarks
              </button>
            </nav>
            <button className="poi-back-btn" type="button" onClick={() => navigate("/home")}>
              Back to Dashboard
            </button>
          </div>
        </aside>

        <main className="poi-main">
          <div className="poi-container">
            <header className="poi-topbar">
              <div>
                <p className="poi-eyebrow">Future Module</p>
                <h1>Risk Based Authentication</h1>
              </div>
            </header>

            <div className="anomaly-tab-grid">
              <button
                type="button"
                className={`anomaly-tab-box${activeTab === "results" ? " active" : ""}`}
                onClick={() => setActiveTab("results")}
              >
                <span className="anomaly-tab-title">Results</span>
              </button>

              <button
                type="button"
                className={`anomaly-tab-box${activeTab === "source" ? " active" : ""}`}
                onClick={() => setActiveTab("source")}
              >
                <span className="anomaly-tab-title">Source Code</span>
              </button>
            </div>

            {activeTab === "source" && (
              <section className="poi-card nb-viewer-card">
                <NotebookViewer url={NOTEBOOK_URL} imagesBaseUrl={NOTEBOOK_IMAGES_BASE_URL} />
              </section>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

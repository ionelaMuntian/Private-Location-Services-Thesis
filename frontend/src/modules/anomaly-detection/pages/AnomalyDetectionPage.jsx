// frontend/src/modules/anomaly-detection/pages/AnomalyDetectionPage.jsx
import { useNavigate } from "react-router-dom";
import "../styles/anomaly-detection.css";

export default function AnomalyDetectionPage() {
  const navigate = useNavigate();

  return (
    <div className="anomaly-page">
      <section className="anomaly-card">
        <p className="anomaly-kicker">Future Module</p>
        <h1>Impossible Travel Detection</h1>
        <p>
          This module will later include encrypted anomaly detection for detecting
          impossible travel patterns using privacy-preserving location histories.
        </p>

        <button type="button" onClick={() => navigate("/home")}>
          Back to Dashboard
        </button>
      </section>
    </div>
  );
}
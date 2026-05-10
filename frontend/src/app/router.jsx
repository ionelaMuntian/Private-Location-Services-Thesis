// frontend/src/app/router.jsx
import { Routes, Route, Navigate } from "react-router-dom";
import LoginPage from "../modules/auth/pages/LoginPage";
import HomePage from "../modules/home/pages/HomePage";
import PoiSearchPage from "../modules/poi-search/pages/PoiSearchPage";
import LocationSharingPage from "../modules/location-sharing/pages/LocationSharingPage";
import AdminDashboardPage from "../modules/company/pages/AdminDashboardPage";
import AnomalyDetectionPage from "../modules/anomaly-detection/pages/AnomalyDetectionPage";

export function AppRouter() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/home" element={<HomePage />} />
      <Route path="/poi-search" element={<PoiSearchPage />} />
      <Route path="/location-sharing" element={<LocationSharingPage />} />
      <Route path="/admin-dashboard" element={<AdminDashboardPage />} />
      <Route path="/anomaly-detection" element={<AnomalyDetectionPage />} />

      {/* Temporary until you implement the statistics page */}
      <Route path="/statistics" element={<Navigate to="/poi-search" replace />} />
    </Routes>
  );
}
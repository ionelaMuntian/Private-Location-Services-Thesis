import { useNavigate } from "react-router-dom";

export default function ServiceCard({ title, route }) {
  const navigate = useNavigate();

  return (
    <div className="service-card">
      <h3>{title}</h3>
      <button onClick={() => navigate(route)}>Open service</button>
    </div>
  );
}

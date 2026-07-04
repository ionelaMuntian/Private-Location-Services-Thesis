import { useNavigate } from "react-router-dom";
import ServiceIcon from "./ServiceIcon";

export default function ServiceCard({ title, route, icon }) {
  const navigate = useNavigate();

  return (
    <div className="service-card">
      <h3>{title}</h3>
      <div className="service-card-icon">
        <ServiceIcon name={icon} />
      </div>
      <button onClick={() => navigate(route)}>Open service</button>
    </div>
  );
}

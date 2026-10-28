import { Navigate } from "react-router-dom";

export function ExpertLoginPage() {
  return <Navigate to="/login?tab=expert" replace />;
}

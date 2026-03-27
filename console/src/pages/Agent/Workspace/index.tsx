import { Navigate } from "react-router-dom";

export default function WorkspacePage() {
  return <Navigate replace to="/agents?tab=workspace" />;
}

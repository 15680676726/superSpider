import { Navigate, useLocation } from "react-router-dom";

function normalizeRuntimeTab(rawTab: string | null): string | null {
  if (rawTab === "governance" || rawTab === "recovery" || rawTab === "automation") {
    return rawTab;
  }
  return null;
}

export default function WorkspacePage() {
  const location = useLocation();
  const nextParams = new URLSearchParams(location.search);
  const tab = normalizeRuntimeTab(nextParams.get("tab"));
  if (tab) {
    nextParams.set("tab", tab);
  } else {
    nextParams.delete("tab");
  }
  const query = nextParams.toString();
  return <Navigate replace to={query ? `/runtime-center?${query}` : "/runtime-center"} />;
}

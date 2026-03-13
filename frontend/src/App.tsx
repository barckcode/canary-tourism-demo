import { Routes, Route } from "react-router-dom";
import AppShell from "./components/layout/AppShell";
import DashboardPage from "./pages/DashboardPage";
import ForecastPage from "./pages/ForecastPage";
import ProfilesPage from "./pages/ProfilesPage";
import DataExplorerPage from "./pages/DataExplorerPage";

function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/forecast" element={<ForecastPage />} />
        <Route path="/profiles" element={<ProfilesPage />} />
        <Route path="/data" element={<DataExplorerPage />} />
      </Routes>
    </AppShell>
  );
}

export default App;

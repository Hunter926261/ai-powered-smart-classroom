import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AppProvider } from "./context/AppContext";
import Sidebar from "./components/Sidebar";

// Pages
import Dashboard           from "./pages/Dashboard";
import StudentRegistration from "./pages/StudentRegistration";
import StartClass          from "./pages/StartClass";
import Attendance          from "./pages/Attendance";
import AttentionAnalytics  from "./pages/AttentionAnalytics";
import IoTControl          from "./pages/IoTControl";
import History             from "./pages/History";

function App() {
  return (
    <BrowserRouter>
      <AppProvider>
        <div className="app-layout">
          <Sidebar />
          <div className="main-content">
            <Routes>
              <Route path="/"             element={<Dashboard />} />
              <Route path="/registration" element={<StudentRegistration />} />
              <Route path="/start-class"  element={<StartClass />} />
              <Route path="/attendance"   element={<Attendance />} />
              <Route path="/analytics"    element={<AttentionAnalytics />} />
              <Route path="/iot"          element={<IoTControl />} />
              <Route path="/history"      element={<History />} />
            </Routes>
          </div>
        </div>
      </AppProvider>
    </BrowserRouter>
  );
}

export default App;
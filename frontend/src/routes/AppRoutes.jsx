import { BrowserRouter, Routes, Route } from "react-router-dom";

import MainLayout from "../layouts/MainLayout";

import Dashboard from "../pages/Dashboard";
import StudentRegistration from "../pages/StudentRegistration";
import Attendance from "../pages/Attendance";
import Settings from "../pages/Settings";

const AppRoutes = () => {
  return (
    <BrowserRouter>
      <MainLayout>
        <Routes>
          <Route path="/" element={<Dashboard />} />

          <Route
            path="/students"
            element={<StudentRegistration />}
          />

          <Route
            path="/attendance"
            element={<Attendance />}
          />

          <Route
            path="/settings"
            element={<Settings />}
          />
        </Routes>
      </MainLayout>
    </BrowserRouter>
  );
};

export default AppRoutes;
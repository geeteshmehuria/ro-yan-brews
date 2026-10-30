import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import AdminApp from "./admin/AdminApp.jsx";
import AdminLogin from "./admin/AdminLogin.jsx";
import { initBackButton } from "./backButton.js";
import CustomerApp from "./customer/CustomerApp.jsx";
import "./index.css";

// The Android app (npm run build:android) is the owner's dashboard only; the website has both.
const ADMIN_ONLY = import.meta.env.VITE_APP_TARGET === "admin";

initBackButton();

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <div className="orb orb1" />
      <div className="orb orb2" />
      <Routes>
        <Route path="/admin" element={<AdminApp />} />
        <Route path="*" element={ADMIN_ONLY ? <AdminLogin /> : <CustomerApp />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);

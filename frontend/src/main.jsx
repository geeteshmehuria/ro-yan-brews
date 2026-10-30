import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import AdminApp from "./admin/AdminApp.jsx";
import { installBackButton } from "./backButton.js";
import CustomerApp from "./customer/CustomerApp.jsx";
import { DialogHost } from "./dialog.jsx";
import "./index.css";

// The website and the Android app run the same screens: customers get the menu, and the
// owner's login opens the dashboard (/admin). In the app, Android's Back closes what's open.
installBackButton();

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <div className="orb orb1" />
      <div className="orb orb2" />
      <Routes>
        <Route path="/admin" element={<AdminApp />} />
        <Route path="*" element={<CustomerApp />} />
      </Routes>
      <DialogHost />
    </BrowserRouter>
  </React.StrictMode>
);

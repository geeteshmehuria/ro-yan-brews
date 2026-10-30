import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { getSession, logout } from "../api.js";
import { Login } from "../customer/Login.jsx";

// Login screen of the owner's Android app: the app is admin-only, so a customer account is
// turned away instead of being sent to the customer screens (which aren't in the app).
export default function AdminLogin() {
  const navigate = useNavigate();
  const [err, setErr] = useState("");
  if (getSession()?.is_admin) return <Navigate to="/admin" replace />;

  const onDone = ({ is_admin }) => {
    if (is_admin) return navigate("/admin", { replace: true });
    logout();
    setErr("This app is only for the stall owner. Customers can order on the Ro-Yan website.");
  };

  return (
    <>
      {/* key: start the login over after a refused account */}
      <Login key={err} onDone={onDone} allowGoogle={false}
        title="Ro-Yan Admin" subtitle="Owner sign-in — we'll email you a code" />
      {err && <p className="mx-6 -mt-6 text-center text-sm text-danger">{err}</p>}
    </>
  );
}

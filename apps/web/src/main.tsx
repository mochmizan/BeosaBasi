import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./theme.css";
import "./styles.css";
import "./styles-pages.css";
import "./styles-upload.css";

// Dev: Prism memvalidasi cookie sesi kontrak. Isi cookie tiruan agar mock:api
// bisa dipakai tanpa login Google. Tidak pernah aktif di produksi.
if (import.meta.env.DEV && !document.cookie.includes("beosabasi_session=")) {
  document.cookie = "beosabasi_session=dev; path=/; SameSite=Lax";
}

const root = document.getElementById("root");
if (root !== null) {
  ReactDOM.createRoot(root).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}

import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";
import "./studio.css";
import "./preferences.css";
import "./library.css";
import "./usability.css";
import "./cleanup.css";
import "./keyframes.css";
import "./recovery.css";
import "./friendly.css";
import "@fontsource/ibm-plex-sans/latin-400.css";
import "@fontsource/ibm-plex-sans/latin-500.css";
import "@fontsource/ibm-plex-sans/latin-600.css";
import "@fontsource/ibm-plex-sans-arabic/arabic-400.css";
import "@fontsource/ibm-plex-sans-arabic/arabic-600.css";
import "@fontsource/ibm-plex-mono/latin-500.css";
import "./desk.css";

// Theme changes apply instantly: suspend colour transitions for the frame in which
// data-theme or data-accent changes, so controls never sit half-way between themes.
if (typeof MutationObserver !== "undefined") {
  new MutationObserver(() => {
    const root = document.documentElement;
    root.classList.add("theme-switching");
    requestAnimationFrame(() => requestAnimationFrame(() => root.classList.remove("theme-switching")));
  }).observe(document.documentElement, {attributes: true, attributeFilter: ["data-theme", "data-accent"]});
}

class ErrorBoundary extends React.Component<{ children: React.ReactNode }, { error: Error | null }> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error("SceneForge UI crashed:", error, info);
  }
  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 32, fontFamily: "sans-serif", maxWidth: 640, margin: "40px auto" }}>
          <h2>Something went wrong in the UI</h2>
          <p>
            This is a bug, not something you did. Please reload the page. If it keeps happening,
            copy the error below and share it so it can be fixed.
          </p>
          <pre style={{ background: "#fdecea", padding: 12, borderRadius: 6, whiteSpace: "pre-wrap", fontSize: 12 }}>
            {this.state.error.message}
            {"\n"}
            {this.state.error.stack}
          </pre>
          <button onClick={() => window.location.reload()} style={{ padding: "8px 16px", marginTop: 8 }}>
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);

import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";

import { authStatus, requestMagicLink } from "./api";
import { t } from "./i18n";
import type { ExtensionMessage } from "./types";
import "./popup.css";

interface PublicState {
  id: string;
  status: string;
  startedAt: string;
  uploadedParts: number;
  durationMs: number;
  packageHash?: string;
  error?: string;
  unavailableArtifacts: number;
  captureFinished: boolean;
}

function App() {
  const [capture, setCapture] = useState<PublicState | null>(null);
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [email, setEmail] = useState("");
  const [linkSent, setLinkSent] = useState(false);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 1_000);
    return () => clearInterval(timer);
  }, []);

  async function refresh() {
    const hasSession = await authStatus().catch(() => false);
    setAuthenticated(hasSession);
    if (!hasSession) return;
    const response = await send({ type: "GET_STATE" });
    if (response.ok) setCapture(response.result as PublicState | null);
  }

  async function act(message: ExtensionMessage) {
    setBusy(true);
    setError(undefined);
    try {
      const response = await send(message);
      if (!response.ok) throw new Error(String(response.error));
      setCapture(response.result as PublicState | null);
    } catch (caught) {
      setError(String(caught));
    } finally {
      setBusy(false);
    }
  }

  const recording = capture?.status === "recording";
  return (
    <main>
      <header>
        <span className="brand-mark" aria-hidden="true">
          C
        </span>
        <div>
          <strong>{t("appName")}</strong>
          <small>{t("appTagline")}</small>
        </div>
      </header>

      {authenticated === false && (
        <section>
          <h1>{t("loginTitle")}</h1>
          <p>{t("loginBody")}</p>
          <label>
            {t("emailLabel")}
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <button
            disabled={busy || !email}
            onClick={() => {
              setBusy(true);
              setError(undefined);
              void requestMagicLink(email)
                .then(() => setLinkSent(true))
                .catch((caught: unknown) => setError(String(caught)))
                .finally(() => setBusy(false));
            }}
          >
            {t("sendAccessLink")}
          </button>
          {linkSent && <p className="success">{t("accessLinkSent")}</p>}
        </section>
      )}

      {authenticated && !capture && (
        <section>
          <h1>{t("newCaptureTitle")}</h1>
          <p>{t("newCaptureBody")}</p>
          <p className="notice">{t("sensitiveDataNotice")}</p>
          <label className="consent">
            <input
              type="checkbox"
              checked={consent}
              onChange={(event) => setConsent(event.target.checked)}
            />
            {t("captureConsent")}
          </label>
          <button
            disabled={!consent || busy}
            onClick={() => void act({ type: "START_CAPTURE", consent })}
          >
            {t("startCapture")}
          </button>
        </section>
      )}

      {authenticated && capture && (
        <section>
          <div className="status-row">
            <span className={`dot ${recording ? "recording" : ""}`} />
            <strong>{statusLabel(capture.status)}</strong>
            <time>{formatDuration(capture.durationMs)}</time>
          </div>
          <dl>
            <div>
              <dt>{t("uploadedParts")}</dt>
              <dd>{capture.uploadedParts}</dd>
            </div>
            <div>
              <dt>{t("connection")}</dt>
              <dd>{t("active")}</dd>
            </div>
            <div>
              <dt>{t("session")}</dt>
              <dd title={capture.id}>{capture.id.slice(0, 12)}…</dd>
            </div>
            <div>
              <dt>{t("unavailable")}</dt>
              <dd>{capture.unavailableArtifacts}</dd>
            </div>
          </dl>
          {capture.unavailableArtifacts > 0 && (
            <p className="notice">{t("partialCapture")}</p>
          )}
          {recording && (
            <div className="actions">
              <button
                className="secondary"
                disabled={busy}
                onClick={() => void act({ type: "ADD_SCREENSHOT" })}
              >
                {t("screenshot")}
              </button>
              <button
                className="secondary"
                disabled={busy}
                onClick={() =>
                  void act({ type: "ADD_MARKER", note: t("manualMarker") })
                }
              >
                {t("marker")}
              </button>
              <button
                className="danger"
                disabled={busy}
                onClick={() => void act({ type: "STOP_CAPTURE" })}
              >
                {t("finishAndDownload")}
              </button>
            </div>
          )}
          {["interrupted", "error"].includes(capture.status) &&
            !capture.captureFinished && (
              <button
                disabled={busy}
                onClick={() => void act({ type: "RESUME_CAPTURE" })}
              >
                {t("resumeCapture")}
              </button>
            )}
          {capture.status === "error" && capture.captureFinished && (
            <button
              disabled={busy}
              onClick={() => void act({ type: "STOP_CAPTURE" })}
            >
              {t("retryFinalization")}
            </button>
          )}
          {capture.status === "complete" && (
            <>
              <p className="success">{t("captureComplete")}</p>
              <button
                className="secondary"
                onClick={() => void act({ type: "DISMISS_RESULT" })}
              >
                {t("newCapture")}
              </button>
            </>
          )}
        </section>
      )}
      {(error || capture?.error) && (
        <p role="alert" className="error">
          {error ?? capture?.error}
        </p>
      )}
      <footer>{t("legalDisclaimer")}</footer>
    </main>
  );
}

async function send(message: ExtensionMessage) {
  return chrome.runtime.sendMessage(message) as Promise<{
    ok: boolean;
    result?: unknown;
    error?: unknown;
  }>;
}

function formatDuration(milliseconds: number): string {
  const seconds = Math.floor(milliseconds / 1_000);
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

function statusLabel(status: string): string {
  return (
    {
      starting: t("statusStarting"),
      recording: t("statusRecording"),
      finalizing: t("statusFinalizing"),
      complete: t("statusComplete"),
      interrupted: t("statusInterrupted"),
      error: t("statusError"),
    }[status] ?? status
  );
}

createRoot(document.querySelector("#root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

import { sha256 } from "@noble/hashes/sha2.js";
import { bytesToHex } from "@chitaozinho/protocol";
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
  integrityStatus?: string;
  timestampStatus?: string;
  blockchainStatus?: string;
  storageStatus?: string;
  error?: string;
  unavailableArtifacts: number;
  captureFinished: boolean;
}

type Screen = "home" | "new" | "captures" | "verify" | "settings";

function App() {
  const [capture, setCapture] = useState<PublicState | null>(null);
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [email, setEmail] = useState("");
  const [linkSent, setLinkSent] = useState(false);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [screen, setScreen] = useState<Screen>("home");
  const [sessions, setSessions] = useState<PublicState[]>([]);
  const [verificationHash, setVerificationHash] = useState<string>();

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 1_000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    document.querySelector<HTMLElement>("[data-view-heading]")?.focus();
  }, [authenticated, screen, capture?.id, capture?.status]);

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
      const result = response.result as PublicState | null;
      setCapture(result);
      if (!result) setScreen("home");
    } catch (caught) {
      setError(String(caught));
    } finally {
      setBusy(false);
    }
  }

  async function openCaptures() {
    setBusy(true);
    setError(undefined);
    try {
      const response = await send({ type: "LIST_SESSIONS" });
      if (!response.ok) throw new Error(String(response.error));
      setSessions(response.result as PublicState[]);
      setScreen("captures");
    } catch (caught) {
      setError(String(caught));
    } finally {
      setBusy(false);
    }
  }

  async function hashPackage(file: File) {
    setBusy(true);
    setError(undefined);
    setVerificationHash(undefined);
    try {
      const hasher = sha256.create();
      const chunkSize = 4 * 1024 * 1024;
      for (let offset = 0; offset < file.size; offset += chunkSize) {
        hasher.update(
          new Uint8Array(
            await file.slice(offset, offset + chunkSize).arrayBuffer(),
          ),
        );
      }
      setVerificationHash(`sha256:${bytesToHex(hasher.digest())}`);
    } catch (caught) {
      setError(String(caught));
    } finally {
      setBusy(false);
    }
  }

  async function downloadCapture(sessionId: string) {
    setBusy(true);
    setError(undefined);
    try {
      const response = await send({ type: "DOWNLOAD_PACKAGE", sessionId });
      if (!response.ok) throw new Error(String(response.error));
    } catch (caught) {
      setError(String(caught));
    } finally {
      setBusy(false);
    }
  }

  const recording = capture?.status === "recording";
  return (
    <main aria-busy={busy}>
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
          <h1 data-view-heading tabIndex={-1}>
            {t("loginTitle")}
          </h1>
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
          {linkSent && (
            <p className="success" role="status">
              {t("accessLinkSent")}
            </p>
          )}
        </section>
      )}

      {authenticated === null && (
        <p role="status" data-view-heading tabIndex={-1}>
          {t("loading")}
        </p>
      )}

      {authenticated && !capture && screen === "home" && (
        <section>
          <h1 data-view-heading tabIndex={-1}>
            {t("homeTitle")}
          </h1>
          <div className="menu-grid">
            <button onClick={() => setScreen("new")}>{t("newCapture")}</button>
            <button className="secondary" onClick={() => void openCaptures()}>
              {t("myCaptures")}
            </button>
            <button className="secondary" onClick={() => setScreen("verify")}>
              {t("verifyPackage")}
            </button>
            <button className="secondary" onClick={() => setScreen("settings")}>
              {t("settings")}
            </button>
          </div>
        </section>
      )}

      {authenticated && !capture && screen === "new" && (
        <section>
          <BackButton onClick={() => setScreen("home")} />
          <h1 data-view-heading tabIndex={-1}>
            {t("newCaptureTitle")}
          </h1>
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

      {authenticated && !capture && screen === "captures" && (
        <section>
          <BackButton onClick={() => setScreen("home")} />
          <h1 data-view-heading tabIndex={-1}>
            {t("myCaptures")}
          </h1>
          {sessions.length === 0 ? (
            <p>{t("noCaptures")}</p>
          ) : (
            <ul className="capture-list">
              {sessions.map((session) => (
                <li key={session.id}>
                  <div>
                    <strong>{statusLabel(session.status)}</strong>
                    <small>
                      {new Date(session.startedAt).toLocaleString()}
                    </small>
                    <code title={session.id}>{session.id.slice(0, 12)}…</code>
                  </div>
                  {session.status === "complete" && (
                    <button
                      className="secondary compact"
                      disabled={busy}
                      onClick={() => void downloadCapture(session.id)}
                    >
                      {t("downloadAgain")}
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {authenticated && !capture && screen === "verify" && (
        <section>
          <BackButton onClick={() => setScreen("home")} />
          <h1 data-view-heading tabIndex={-1}>
            {t("verifyPackage")}
          </h1>
          <p>{t("verifyPackageBody")}</p>
          <label>
            {t("selectPackage")}
            <input
              type="file"
              accept=".zip,application/zip"
              disabled={busy}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void hashPackage(file);
              }}
            />
          </label>
          {verificationHash && (
            <output
              className="hash-output"
              aria-label={t("calculatedHash")}
              role="status"
            >
              {verificationHash}
            </output>
          )}
          <p className="notice">{t("fullVerificationNotice")}</p>
        </section>
      )}

      {authenticated && !capture && screen === "settings" && (
        <section>
          <BackButton onClick={() => setScreen("home")} />
          <h1 data-view-heading tabIndex={-1}>
            {t("settings")}
          </h1>
          <dl>
            <div>
              <dt>{t("language")}</dt>
              <dd>{chrome.i18n.getUILanguage()}</dd>
            </div>
            <div>
              <dt>{t("apiEnvironment")}</dt>
              <dd>{t("localDevelopment")}</dd>
            </div>
            <div>
              <dt>{t("version")}</dt>
              <dd>{__CHITAOZINHO_BUILD__.version}</dd>
            </div>
          </dl>
          <p>{t("settingsBody")}</p>
        </section>
      )}

      {authenticated && capture && (
        <section>
          <div className="status-row" role="status" aria-live="polite">
            <span
              className={`dot ${recording ? "recording" : ""}`}
              aria-hidden="true"
            />
            <strong data-view-heading tabIndex={-1}>
              {statusLabel(capture.status)}
            </strong>
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
            <p className="notice" role="status">
              {t("partialCapture")}
            </p>
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
          {["error", "interrupted"].includes(capture.status) &&
            !capture.captureFinished && (
              <button
                className="danger"
                disabled={busy}
                onClick={() => {
                  if (window.confirm(t("discardCaptureConfirmation"))) {
                    void act({ type: "DISCARD_FAILED_CAPTURE" });
                  }
                }}
              >
                {t("discardCapture")}
              </button>
            )}
          {capture.status === "complete" && (
            <>
              <p className="success" role="status">
                {t("captureComplete")}
              </p>
              <dl className="result-list">
                <Result
                  label={t("integrity")}
                  value={formatResult(capture.integrityStatus)}
                />
                <Result
                  label={t("timestamp")}
                  value={formatResult(capture.timestampStatus)}
                />
                <Result
                  label={t("blockchain")}
                  value={formatResult(capture.blockchainStatus)}
                />
                <Result
                  label={t("retention")}
                  value={formatResult(capture.storageStatus)}
                />
              </dl>
              {capture.packageHash && (
                <>
                  <strong>{t("packageHash")}</strong>
                  <output className="hash-output">{capture.packageHash}</output>
                </>
              )}
              <button
                className="secondary"
                disabled={busy}
                onClick={() => void downloadCapture(capture.id)}
              >
                {t("downloadAgain")}
              </button>
              <p className="notice">{t("fullVerificationNotice")}</p>
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
      {busy && (
        <p className="sr-only" role="status">
          {t("working")}
        </p>
      )}
      <footer>{t("legalDisclaimer")}</footer>
    </main>
  );
}

function BackButton({ onClick }: { onClick: () => void }) {
  return (
    <button className="back-button" onClick={onClick}>
      ← {t("back")}
    </button>
  );
}

function Result({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
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

function formatResult(status?: string): string {
  if (!status) return t("unknown");
  return (
    {
      complete: t("integral"),
      incomplete: t("incomplete"),
      pending: t("pending"),
      confirmed: t("confirmed"),
      not_requested: t("notRequested"),
      not_submitted: t("notSubmitted"),
      submitted: t("submitted"),
      pending_confirmation: t("pendingConfirmation"),
      valid: t("valid"),
      invalid: t("invalid"),
      verification_failed: t("verificationFailed"),
      staging: t("staging"),
      stored: t("stored"),
      locked: t("locked"),
      retention_failed: t("retentionFailed"),
      unknown: t("unknown"),
    }[status] ?? status
  );
}

createRoot(document.querySelector("#root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";

import { authStatus, requestMagicLink } from "./api";
import { documentLanguage, t } from "./i18n";
import type { ExtensionMessage } from "./types";
import "./popup.css";

document.documentElement.lang = documentLanguage(chrome.i18n.getUILanguage());

interface PublicState {
  id: string;
  status: string;
  startedAt: string;
  pageTitle?: string;
  pageOrigin?: string;
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

type Screen = "home" | "new" | "captures" | "settings";

function App() {
  const usesLocalAuthentication =
    window.location.protocol === "chrome-extension:" &&
    __CHITAOZINHO_ENDPOINTS__.environment === "desenvolvimento";
  const [capture, setCapture] = useState<PublicState | null>(null);
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [email, setEmail] = useState("");
  const [linkSent, setLinkSent] = useState(false);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [technicalError, setTechnicalError] = useState<string>();
  const [screen, setScreen] = useState<Screen>("home");
  const [sessions, setSessions] = useState<PublicState[]>([]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 1_000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    document.querySelector<HTMLElement>("[data-view-heading]")?.focus();
  }, [authenticated, screen, capture?.id, capture?.status]);

  async function refresh(): Promise<boolean> {
    const hasSession =
      usesLocalAuthentication || (await authStatus().catch(() => false));
    setAuthenticated(hasSession);
    if (!hasSession) return false;
    const response = await send({ type: "GET_STATE" });
    if (response.ok) setCapture(response.result as PublicState | null);
    return true;
  }

  async function requestAccessLink() {
    setBusy(true);
    setError(undefined);
    setTechnicalError(undefined);
    try {
      await requestMagicLink(email);
      setLinkSent(true);
    } catch (caught) {
      const detail = errorDetail(caught);
      if (
        __CHITAOZINHO_ENDPOINTS__.environment === "desenvolvimento" &&
        detail.includes("authentication unavailable")
      ) {
        setAuthenticated(true);
        setError(undefined);
        setTechnicalError(undefined);
        return;
      }
      // The local API authenticates automatically and intentionally has no
      // magic-link endpoint. Recover if the popup still showed its stale login
      // state while the development server was starting.
      if (await refresh()) {
        setError(undefined);
        setTechnicalError(undefined);
      } else {
        showError(caught);
      }
    } finally {
      setBusy(false);
    }
  }

  function showError(caught: unknown) {
    const detail = errorDetail(caught);
    setError(friendlyError(detail));
    setTechnicalError(detail);
  }

  async function act(message: ExtensionMessage) {
    setBusy(true);
    setError(undefined);
    setTechnicalError(undefined);
    try {
      const response = await send(message);
      if (!response.ok) throw response.error;
      const result = response.result as PublicState | null;
      setCapture(result);
      if (!result) setScreen("home");
    } catch (caught) {
      showError(caught);
    } finally {
      setBusy(false);
    }
  }

  async function openCaptures() {
    setBusy(true);
    setError(undefined);
    setTechnicalError(undefined);
    try {
      const response = await send({ type: "LIST_SESSIONS" });
      if (!response.ok) throw response.error;
      setSessions(response.result as PublicState[]);
      setScreen("captures");
    } catch (caught) {
      showError(caught);
    } finally {
      setBusy(false);
    }
  }

  async function downloadCapture(sessionId: string) {
    setBusy(true);
    setError(undefined);
    setTechnicalError(undefined);
    try {
      const response = await send({ type: "DOWNLOAD_PACKAGE", sessionId });
      if (!response.ok) throw response.error;
    } catch (caught) {
      showError(caught);
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
        {authenticated && !capture && screen === "home" && (
          <button
            className="icon-button"
            aria-label={t("settings")}
            title={t("settings")}
            onClick={() => setScreen("settings")}
          >
            ⚙
          </button>
        )}
      </header>

      {__CHITAOZINHO_ENDPOINTS__.environment === "beta" && (
        <aside className="beta-notice" aria-label={t("betaTitle")}>
          <strong>{t("betaTitle")}</strong>
          <span>{t("betaRetention")}</span>
          <small>{t("betaNoImmutability")}</small>
        </aside>
      )}

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
            onClick={() => void requestAccessLink()}
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
          <p className="lead">{t("homeBody")}</p>
          <button className="hero-action" onClick={() => setScreen("new")}>
            <span aria-hidden="true">＋</span>
            <span>
              <strong>{t("newEvidence")}</strong>
              <small>{t("newEvidenceHint")}</small>
            </span>
          </button>
          <div className="secondary-actions">
            <button className="secondary" onClick={() => void openCaptures()}>
              {t("myEvidence")}
            </button>
            <a
              className="button secondary"
              href={__CHITAOZINHO_ENDPOINTS__.verifier}
              target="_blank"
              rel="noreferrer"
            >
              {t("verifyEvidence")}
            </a>
          </div>
        </section>
      )}

      {authenticated && !capture && screen === "new" && (
        <section>
          <BackButton onClick={() => setScreen("home")} />
          <p className="step-label">{t("beforeStarting")}</p>
          <h1 data-view-heading tabIndex={-1}>
            {t("newCaptureTitle")}
          </h1>
          <p>{t("newCaptureBody")}</p>
          <ol className="preparation-list">
            <li>{t("prepareContext")}</li>
            <li>{t("prepareNavigation")}</li>
            <li>{t("prepareFinish")}</li>
          </ol>
          <details className="disclosure">
            <summary>{t("responsibleUse")}</summary>
            <p>{t("sensitiveDataNotice")}</p>
          </details>
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
            {t("myEvidence")}
          </h1>
          {sessions.length === 0 ? (
            <p>{t("noCaptures")}</p>
          ) : (
            <ul className="capture-list">
              {sessions.map((session) => (
                <li key={session.id}>
                  <div>
                    <strong>
                      {session.pageTitle || t("untitledEvidence")}
                    </strong>
                    <small>
                      {session.pageOrigin || statusLabel(session.status)}
                    </small>
                    <small>
                      {new Date(session.startedAt).toLocaleString()}
                    </small>
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

      {authenticated && !capture && screen === "settings" && (
        <section>
          <BackButton onClick={() => setScreen("home")} />
          <h1 data-view-heading tabIndex={-1}>
            {t("settings")}
          </h1>
          <dl className="technical-list">
            <Result
              label={t("environment")}
              value={__CHITAOZINHO_ENDPOINTS__.environment}
            />
            <Result
              label={t("apiEnvironment")}
              value={new URL(__CHITAOZINHO_ENDPOINTS__.api).host}
            />
            <Result
              label={t("verifier")}
              value={new URL(__CHITAOZINHO_ENDPOINTS__.verifier).host}
            />
            <Result label={t("language")} value={chrome.i18n.getUILanguage()} />
            <Result
              label={t("version")}
              value={__CHITAOZINHO_BUILD__.version}
            />
          </dl>
          <p>{t("settingsBody")}</p>
        </section>
      )}

      {authenticated && capture && (
        <section>
          <div className="status-row">
            <span
              className={`dot ${recording ? "recording" : ""}`}
              aria-hidden="true"
            />
            <strong
              data-view-heading
              tabIndex={-1}
              role="status"
              aria-live="polite"
            >
              {statusLabel(capture.status)}
            </strong>
            <time
              aria-label={`${t("duration")}: ${formatDuration(capture.durationMs)}`}
            >
              {formatDuration(capture.durationMs)}
            </time>
          </div>
          {recording && (
            <p className="saving-state">
              <span aria-hidden="true">✓</span> {t("savingContinuously")}
            </p>
          )}
          {capture.unavailableArtifacts > 0 && (
            <p className="notice" role="status">
              {t("partialCapture")}
            </p>
          )}
          {recording && (
            <div className="actions">
              <div className="secondary-actions">
                <button
                  className="secondary"
                  disabled={busy}
                  onClick={() => void act({ type: "ADD_SCREENSHOT" })}
                >
                  {t("recordImage")}
                </button>
                <button
                  className="secondary"
                  disabled={busy}
                  onClick={() =>
                    void act({ type: "ADD_MARKER", note: t("manualMarker") })
                  }
                >
                  {t("markMoment")}
                </button>
              </div>
              <button
                disabled={busy}
                onClick={() => void act({ type: "STOP_CAPTURE" })}
              >
                {t("finishEvidence")}
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
                className="text-danger"
                disabled={busy}
                onClick={() => {
                  if (window.confirm(t("discardCaptureConfirmation")))
                    void act({ type: "DISCARD_FAILED_CAPTURE" });
                }}
              >
                {t("discardCapture")}
              </button>
            )}
          {capture.status === "complete" && (
            <>
              <div className="completion">
                <span aria-hidden="true">✓</span>
                <div>
                  <h1>{t("evidenceReady")}</h1>
                  <p>{t("captureComplete")}</p>
                </div>
              </div>
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
              <div className="actions">
                <button
                  disabled={busy}
                  onClick={() => void downloadCapture(capture.id)}
                >
                  {t("downloadAgain")}
                </button>
                <a
                  className="button secondary"
                  href={__CHITAOZINHO_ENDPOINTS__.verifier}
                  target="_blank"
                  rel="noreferrer"
                >
                  {t("verifyNow")}
                </a>
                <button
                  className="secondary"
                  onClick={() => void act({ type: "DISMISS_RESULT" })}
                >
                  {t("newEvidence")}
                </button>
              </div>
            </>
          )}
          <details className="disclosure technical-details">
            <summary>{t("technicalDetails")}</summary>
            <dl className="technical-list">
              <Result
                label={t("uploadedParts")}
                value={String(capture.uploadedParts)}
              />
              <Result
                label={t("unavailable")}
                value={String(capture.unavailableArtifacts)}
              />
              <Result
                label={t("session")}
                value={`${capture.id.slice(0, 12)}…`}
              />
            </dl>
            {capture.packageHash && (
              <output className="hash-output" aria-label={t("packageHash")}>
                {capture.packageHash}
              </output>
            )}
          </details>
        </section>
      )}

      {(error || capture?.error) && (
        <div role="alert" className="error">
          <strong>{error ?? friendlyError(capture?.error ?? "")}</strong>
          <p>{t("capturePreserved")}</p>
          {(technicalError || capture?.error) && (
            <details>
              <summary>{t("technicalDetails")}</summary>
              <code>{technicalError ?? capture?.error}</code>
            </details>
          )}
        </div>
      )}
      {busy && (
        <p className="sr-only" role="status">
          {t("working")}
        </p>
      )}
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

function errorDetail(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === "string") return error;
  try {
    return JSON.stringify(error);
  } catch {
    return String(error);
  }
}

export function friendlyError(detail: string): string {
  const normalized = detail.toLowerCase();
  if (
    normalized.includes("screen not found") ||
    normalized.includes("active tab is unavailable")
  )
    return t("errorNoTab");
  if (
    normalized.includes("cannot be discarded") ||
    normalized.includes("current state")
  )
    return t("errorStateChanged");
  if (
    normalized.includes("failed to fetch") ||
    normalized.includes("network") ||
    normalized.includes("connection")
  )
    return t("errorConnection");
  if (normalized.includes("422") || normalized.includes("upload"))
    return t("errorUpload");
  return t("errorUnexpected");
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
      expired: t("expired"),
      expiration_failed: t("expirationFailed"),
      unknown: t("unknown"),
    }[status] ?? status
  );
}

createRoot(document.querySelector("#root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

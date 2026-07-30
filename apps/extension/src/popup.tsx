import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";

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
}

function App() {
  const [capture, setCapture] = useState<PublicState | null>(null);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 1_000);
    return () => clearInterval(timer);
  }, []);

  async function refresh() {
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
          <strong>Chitãozinho</strong>
          <small>captura verificável</small>
        </div>
      </header>

      {!capture && (
        <section>
          <h1>Nova captura</h1>
          <p>
            Coleta vídeo da aba, screenshots, DOM, texto visível e metadados
            declarados pelo navegador. Não prova autoria nem veracidade do
            conteúdo.
          </p>
          <p className="notice">
            Não use para dados de crianças, saúde, finanças ou segredos
            empresariais. Navegue mostrando contexto e respeite direitos de
            terceiros.
          </p>
          <label className="consent">
            <input
              type="checkbox"
              checked={consent}
              onChange={(event) => setConsent(event.target.checked)}
            />
            Entendi os dados coletados, limites e riscos.
          </label>
          <button
            disabled={!consent || busy}
            onClick={() => void act({ type: "START_CAPTURE", consent })}
          >
            Iniciar captura da aba
          </button>
        </section>
      )}

      {capture && (
        <section>
          <div className="status-row">
            <span className={`dot ${recording ? "recording" : ""}`} />
            <strong>{statusLabel(capture.status)}</strong>
            <time>{formatDuration(capture.durationMs)}</time>
          </div>
          <dl>
            <div>
              <dt>Partes enviadas</dt>
              <dd>{capture.uploadedParts}</dd>
            </div>
            <div>
              <dt>Conexão</dt>
              <dd>ativa</dd>
            </div>
            <div>
              <dt>Sessão</dt>
              <dd title={capture.id}>{capture.id.slice(0, 12)}…</dd>
            </div>
          </dl>
          {recording && (
            <div className="actions">
              <button
                className="secondary"
                disabled={busy}
                onClick={() => void act({ type: "ADD_SCREENSHOT" })}
              >
                Screenshot
              </button>
              <button
                className="secondary"
                disabled={busy}
                onClick={() =>
                  void act({ type: "ADD_MARKER", note: "Marcador manual" })
                }
              >
                Marcador
              </button>
              <button
                className="danger"
                disabled={busy}
                onClick={() => void act({ type: "STOP_CAPTURE" })}
              >
                Finalizar e baixar
              </button>
            </div>
          )}
          {["interrupted", "error"].includes(capture.status) && (
            <button
              disabled={busy}
              onClick={() => void act({ type: "RESUME_CAPTURE" })}
            >
              Retomar nesta aba
            </button>
          )}
          {capture.status === "complete" && (
            <>
              <p className="success">
                Captura finalizada. O pacote foi enviado para a pasta de
                downloads.
              </p>
              <button
                className="secondary"
                onClick={() => void act({ type: "DISMISS_RESULT" })}
              >
                Nova captura
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
      <footer>
        Integridade técnica não equivale a validade jurídica definitiva.
      </footer>
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
      starting: "Preparando",
      recording: "Gravando",
      finalizing: "Finalizando",
      complete: "Concluída",
      interrupted: "Interrompida",
      error: "Erro",
    }[status] ?? status
  );
}

createRoot(document.querySelector("#root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

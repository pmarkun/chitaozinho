import React, { useState } from "react";
import { createRoot } from "react-dom/client";

import {
  EvidenceValidationError,
  type VerificationReport,
  verifyEvidencePackage,
} from "./validator";
import "./styles.css";

type Page = "verify" | "methodology";

function App() {
  const [page, setPage] = useState<Page>("verify");
  return (
    <>
      <header className="site-header">
        <a className="brand" href="/" aria-label="Chitãozinho — início">
          <span aria-hidden="true">C</span>
          Chitãozinho
        </a>
        <nav aria-label="Principal">
          <button
            className={page === "verify" ? "active" : ""}
            onClick={() => setPage("verify")}
          >
            Validar pacote
          </button>
          <button
            className={page === "methodology" ? "active" : ""}
            onClick={() => setPage("methodology")}
          >
            Metodologia
          </button>
        </nav>
      </header>
      {page === "verify" ? <Verifier /> : <Methodology />}
      <footer>
        Integridade técnica não equivale a autoria, veracidade ou validação
        jurídica definitiva.
      </footer>
    </>
  );
}

function Verifier() {
  const [packageFile, setPackageFile] = useState<File>();
  const [checksumFile, setChecksumFile] = useState<File>();
  const [proofFile, setProofFile] = useState<File>();
  const [trustedKey, setTrustedKey] = useState("");
  const [report, setReport] = useState<VerificationReport>();
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false);

  async function verify() {
    if (!packageFile) {
      setError("Selecione o ZIP principal da captura.");
      return;
    }
    setRunning(true);
    setError("");
    setReport(undefined);
    try {
      const result = await verifyEvidencePackage({
        packageFile,
        ...(checksumFile ? { checksumFile } : {}),
        ...(proofFile ? { proofBundleFile: proofFile } : {}),
        ...(trustedKey.trim()
          ? { trustedServerKeyHex: trustedKey.trim() }
          : {}),
      });
      setReport(result);
    } catch (caught) {
      setError(
        caught instanceof EvidenceValidationError
          ? caught.message
          : "A validação falhou de forma inesperada.",
      );
    } finally {
      setRunning(false);
    }
  }

  return (
    <main id="main-content">
      <section className="hero">
        <p className="eyebrow">Verificação independente</p>
        <h1>Confira uma captura sem enviar seus arquivos</h1>
        <p>
          Selecione os pacotes abaixo. A validação acontece inteiramente neste
          navegador, inclusive quando esta página é usada offline.
        </p>
        <div className="privacy-note" role="note">
          <strong>Privacidade:</strong> nenhum byte dos arquivos selecionados é
          transmitido ao Chitãozinho.
        </div>
      </section>

      <section className="panel" aria-labelledby="files-heading">
        <h2 id="files-heading">Arquivos</h2>
        <div className="file-grid">
          <FileField
            id="package"
            label="ZIP principal"
            required
            accept=".zip,application/zip"
            file={packageFile}
            onChange={setPackageFile}
          />
          <FileField
            id="checksum"
            label="Checksum .sha256"
            accept=".sha256,text/plain"
            file={checksumFile}
            onChange={setChecksumFile}
          />
          <FileField
            id="proofs"
            label="ZIP complementar de provas"
            accept=".zip,application/zip"
            file={proofFile}
            onChange={setProofFile}
          />
        </div>
        <label className="key-field" htmlFor="trusted-key">
          Chave pública operacional confiável
          <span>Opcional, Ed25519 em hexadecimal</span>
          <input
            id="trusted-key"
            value={trustedKey}
            onChange={(event) => setTrustedKey(event.target.value)}
            inputMode="text"
            autoComplete="off"
            spellCheck={false}
            placeholder="64 caracteres hexadecimais"
          />
        </label>
        <p className="field-help">
          Sem uma chave obtida por canal independente, o validador confirma a
          consistência criptográfica, mas marca a confiança como autodeclarada.
        </p>
        <button
          className="primary"
          disabled={running || !packageFile}
          onClick={() => void verify()}
        >
          {running ? "Validando…" : "Validar agora"}
        </button>
        <div aria-live="polite" aria-atomic="true">
          {error && (
            <div className="error" role="alert">
              <strong>Pacote inválido ou não verificável</strong>
              <p>{error}</p>
            </div>
          )}
        </div>
      </section>

      {report && <Report report={report} />}
    </main>
  );
}

function FileField({
  id,
  label,
  required = false,
  accept,
  file,
  onChange,
}: {
  id: string;
  label: string;
  required?: boolean;
  accept: string;
  file: File | undefined;
  onChange: (file: File | undefined) => void;
}) {
  return (
    <label className="file-field" htmlFor={id}>
      <span>
        {label}
        {required && <strong aria-label="obrigatório"> *</strong>}
      </span>
      <input
        id={id}
        type="file"
        required={required}
        accept={accept}
        onChange={(event) => onChange(event.target.files?.[0])}
      />
      <small>
        {file
          ? `${file.name} · ${formatBytes(file.size)}`
          : "Selecionar arquivo"}
      </small>
    </label>
  );
}

function Report({ report }: { report: VerificationReport }) {
  const label =
    report.result === "integral" ? "Íntegro" : "Íntegro, mas incompleto";
  return (
    <section className="panel report" aria-labelledby="result-heading">
      <div className="result-heading">
        <div>
          <p className="eyebrow">Resultado</p>
          <h2 id="result-heading">{label}</h2>
        </div>
        <span className="result-badge">Verificado</span>
      </div>
      <dl className="summary">
        <div>
          <dt>Sessão</dt>
          <dd>{report.sessionId}</dd>
        </div>
        <div>
          <dt>Arquivos verificados</dt>
          <dd>{report.membersVerified}</dd>
        </div>
        <div>
          <dt>Prova temporal</dt>
          <dd>{temporalLabel(report.temporalProof)}</dd>
        </div>
        <div>
          <dt>Confiança</dt>
          <dd>
            {report.trustMode === "custom_operational_key"
              ? "Chave confirmada separadamente"
              : "Chave autodeclarada pelo pacote"}
          </dd>
        </div>
      </dl>
      <h3>Verificações</h3>
      <ul className="checks">
        {report.checks.map((check) => (
          <li key={check.id} className={check.status}>
            <span aria-hidden="true">
              {check.status === "valid" ? "✓" : "!"}
            </span>
            <div>
              <strong>{check.label}</strong>
              <p>{check.detail}</p>
            </div>
          </li>
        ))}
      </ul>
      <div className="actions">
        <button
          className="secondary"
          onClick={() =>
            download(
              `chitaozinho-verification-${report.sessionId}.json`,
              JSON.stringify(report, null, 2),
              "application/json",
            )
          }
        >
          Baixar JSON
        </button>
        <button
          className="secondary"
          onClick={() =>
            download(
              `chitaozinho-verification-${report.sessionId}.html`,
              htmlReport(report),
              "text/html",
            )
          }
        >
          Baixar relatório HTML
        </button>
      </div>
      <p className="package-hash">
        <strong>SHA-256 do ZIP:</strong> <code>{report.packageHash}</code>
      </p>
    </section>
  );
}

function Methodology() {
  return (
    <main id="main-content" className="methodology">
      <section className="hero">
        <p className="eyebrow">Metodologia v0.1</p>
        <h1>O que a evidência demonstra</h1>
        <p>
          O Chitãozinho combina hashes, assinaturas, recibos, fontes externas de
          tempo e armazenamento imutável. Nenhum mecanismo isolado é tratado
          como prova suficiente.
        </p>
      </section>
      <section className="method-grid">
        <article>
          <span>01</span>
          <h2>Captura</h2>
          <p>
            A extensão registra vídeo, screenshots, DOM e metadados. Cada parte
            recebe SHA-256 antes do upload e entra numa cadeia assinada.
          </p>
        </article>
        <article>
          <span>02</span>
          <h2>Recibos</h2>
          <p>
            O servidor recalcula os hashes e assina recibos sequenciais depois
            da persistência. Reenvios divergentes são recusados.
          </p>
        </article>
        <article>
          <span>03</span>
          <h2>Tempo</h2>
          <p>
            RFC 3161 e OpenTimestamps demonstram que o hash já existia até um
            limite externo; não afirmam o instante exato da captura.
          </p>
        </article>
        <article>
          <span>04</span>
          <h2>Preservação</h2>
          <p>
            Ceph Object Lock impede alteração e exclusão antecipada. Ele
            complementa, mas não substitui, hashes e provas temporais.
          </p>
        </article>
      </section>
      <section className="panel prose">
        <h2>Limites essenciais</h2>
        <p>
          Um resultado íntegro demonstra que os bytes correspondem ao pacote
          assinado e à sequência registrada. Não demonstra autoria material,
          identidade civil, veracidade do conteúdo ou validade jurídica
          definitiva.
        </p>
        <p>
          Horários do navegador são declarados pelo cliente. Horários dos
          recibos dependem do servidor. A TSA e o Bitcoin fornecem limites
          temporais independentes para o hash do manifesto.
        </p>
        <p>
          A chave raiz ou seu fingerprint deve ser obtido por outro canal.
          Receber pacote, validador e chave exclusivamente do mesmo servidor
          reduz a independência da verificação.
        </p>
      </section>
    </main>
  );
}

function temporalLabel(value: VerificationReport["temporalProof"]): string {
  return {
    not_provided: "Não fornecida",
    pending: "Pendente",
    signed_claims_only: "Vínculo assinado; validar externamente pela CLI",
  }[value];
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function download(name: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}

function htmlReport(report: VerificationReport): string {
  const checks = report.checks
    .map(
      (check) =>
        `<li><strong>${escapeHtml(check.label)}</strong>: ${escapeHtml(check.detail)}</li>`,
    )
    .join("");
  return `<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Verificação Chitãozinho</title><h1>Relatório de verificação</h1><dl><dt>Resultado</dt><dd>${escapeHtml(report.result)}</dd><dt>Sessão</dt><dd>${escapeHtml(report.sessionId)}</dd><dt>SHA-256</dt><dd>${escapeHtml(report.packageHash)}</dd><dt>Prova temporal</dt><dd>${escapeHtml(report.temporalProof)}</dd><dt>Confiança</dt><dd>${escapeHtml(report.trustMode)}</dd></dl><h2>Verificações</h2><ul>${checks}</ul><h2>Limitações</h2><p>Este relatório demonstra integridade e rastreabilidade técnica. Não comprova autoria, veracidade material ou validade jurídica definitiva.</p></html>`;
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    void navigator.serviceWorker.register("/sw.js");
  });
}

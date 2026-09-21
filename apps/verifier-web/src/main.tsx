import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";

import {
  EvidenceValidationError,
  type VerificationReport,
  verifyEvidencePackage,
} from "./validator";
import "./styles.css";
import { Privacy } from "./privacy";
import { Construction, isConstructionHost } from "./construction";

const PROOF_API_BASE_URL =
  import.meta.env.VITE_PROOF_API_BASE_URL ?? "https://api.evidencias.org.br";

type Page = "home" | "verify" | "methodology" | "privacy";

const routes: Record<Page, string> = {
  home: "/",
  verify: "/validar",
  methodology: "/metodologia",
  privacy: "/privacidade",
};

function pageFromPath(): Page {
  if (location.pathname.startsWith("/privacidade")) return "privacy";
  if (location.pathname.startsWith("/validar")) return "verify";
  if (location.pathname.startsWith("/metodologia")) return "methodology";
  return "home";
}

function App() {
  if (isConstructionHost(location.hostname)) return <Construction />;
  return <BetaApp />;
}

function BetaApp() {
  const [page, setPage] = useState<Page>(pageFromPath);

  useEffect(() => {
    const update = () => setPage(pageFromPath());
    window.addEventListener("popstate", update);
    return () => window.removeEventListener("popstate", update);
  }, []);

  function navigate(next: Page) {
    history.pushState({}, "", routes[next]);
    setPage(next);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  useEffect(() => {
    document.title = `${page === "privacy" ? "Política de privacidade" : page === "verify" ? "Validar evidência" : page === "methodology" ? "Como funciona" : "Capture e verifique"} — Evidências`;
    document.getElementById("main-content")?.focus({ preventScroll: true });
  }, [page]);

  return (
    <>
      <a className="skip-link" href="#main-content">
        Pular para o conteúdo
      </a>
      <header className="site-header">
        <button className="brand" onClick={() => navigate("home")}>
          Evidências
        </button>
        <nav aria-label="Principal">
          <NavButton active={page === "home"} onClick={() => navigate("home")}>
            Início
          </NavButton>
          <NavButton
            active={page === "verify"}
            onClick={() => navigate("verify")}
          >
            Validar evidência
          </NavButton>
          <NavButton
            active={page === "methodology"}
            onClick={() => navigate("methodology")}
          >
            Como funciona
          </NavButton>
        </nav>
      </header>
      {page === "home" && <Home navigate={navigate} />}
      {page === "verify" && <Verifier />}
      {page === "methodology" && <Methodology navigate={navigate} />}
      {page === "privacy" && <Privacy />}
      <footer>
        <div>
          <strong>Evidências</strong>
          <p>Registro e verificação de evidências digitais.</p>
          <a href="/privacidade">Política de privacidade</a>
        </div>
      </footer>
    </>
  );
}

function NavButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      className={active ? "active" : ""}
      aria-current={active ? "page" : undefined}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function ExtensionDownload() {
  return (
    <section className="extension-download" aria-labelledby="extension-heading">
      <h2 id="extension-heading">Quer capturar uma evidência?</h2>
      <p>
        Baixe a extensão beta para Chrome 116 ou superior no computador. Para
        validar um pacote nesta página, não é preciso instalar nada.
      </p>
      <a
        className="primary button"
        href="https://github.com/pmarkun/chitaozinho/releases/download/v0.1.5/chitaozinho-extension-0.1.5.zip"
      >
        Baixar extensão beta · ZIP
      </a>
      <details>
        <summary>Como instalar no Chrome</summary>
        <ol>
          <li>Baixe o ZIP e descompacte em uma pasta permanente.</li>
          <li>
            Digite <code>chrome://extensions</code> na barra de endereços.
          </li>
          <li>
            Ative o <strong>Modo do desenvolvedor</strong>.
          </li>
          <li>
            Clique em <strong>Carregar sem compactação</strong> e selecione a
            pasta que contém o arquivo <code>manifest.json</code>.
          </li>
          <li>Abra Evidências pelo menu de extensões do Chrome.</li>
        </ol>
        <p>
          A instalação é manual, não automática. Mantenha a pasta no computador.
          Esta opção não instala a extensão no celular.
        </p>
        <p>
          Já usa uma versão anterior? Preserve seus ZIPs. Descompacte esta
          versão na mesma pasta e clique em Atualizar em chrome://extensions.
          Não desinstale a extensão: isso remove os dados locais.
        </p>
      </details>
      <p className="extension-note">
        Versão 0.1.5 · Beta para dados não críticos. Arquivos somente no seu
        dispositivo; o servidor registra hashes, não uma cópia dos arquivos.
      </p>
    </section>
  );
}

function Home({ navigate }: { navigate: (page: Page) => void }) {
  return (
    <main id="main-content" tabIndex={-1} className="home">
      <section className="home-hero">
        <div>
          <p className="eyebrow">Registro digital · Beta</p>
          <h1>
            Registre evidências digitais. Compartilhe registros verificáveis.
          </h1>
          <p className="hero-copy">
            Capture conteúdos da internet com seu contexto e reúna arquivos,
            informações da coleta e assinaturas digitais em um único pacote.
            Compartilhe esse registro para que outras pessoas possam conferir
            sua integridade.
          </p>
          <div className="hero-actions">
            <a className="primary button" href="#extension-heading">
              Baixar extensão
            </a>
            <button className="secondary" onClick={() => navigate("verify")}>
              Verificar evidência
            </button>
          </div>
          <p className="field-help">
            Chrome no computador · Instalação manual nesta fase
          </p>
        </div>
        <ol className="capture-steps" aria-label="Da captura à verificação">
          <li>
            <span aria-hidden="true">01</span>
            <div>
              <h2>Registre com contexto</h2>
              <p>Capture o conteúdo, sua origem e a sequência da navegação.</p>
            </div>
          </li>
          <li>
            <span aria-hidden="true">02</span>
            <div>
              <h2>Organize e compartilhe</h2>
              <p>
                Baixe um pacote com os arquivos e as informações que documentam
                a coleta, pronto para compartilhar.
              </p>
            </div>
          </li>
          <li>
            <span aria-hidden="true">03</span>
            <div>
              <h2>Confira a integridade</h2>
              <p>
                Quem recebe pode verificar se os arquivos correspondem ao
                registro assinado, sem precisar acessar sua conta.
              </p>
            </div>
          </li>
        </ol>
      </section>
      <section className="beta-notice" aria-labelledby="beta-heading">
        <h2 id="beta-heading">Antes de começar</h2>
        <div>
          <p>
            Beta para dados não críticos. Os arquivos ficam no seu dispositivo.
            Não guardamos uma cópia para recuperação no servidor.
          </p>
          <p>
            Preserve o ZIP original em um local seguro e compartilhe-o apenas
            com as pessoas que precisam ter acesso ao registro.
          </p>
        </div>
      </section>
      <ExtensionDownload />
    </main>
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
      setError("Selecione o ZIP principal da evidência.");
      return;
    }
    setRunning(true);
    setError("");
    setReport(undefined);
    try {
      setReport(
        await verifyEvidencePackage({
          packageFile,
          ...(checksumFile ? { checksumFile } : {}),
          ...(proofFile ? { proofBundleFile: proofFile } : {}),
          ...(trustedKey.trim()
            ? { trustedServerKeyHex: trustedKey.trim() }
            : {}),
          proofApiBaseUrl: PROOF_API_BASE_URL,
        }),
      );
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
    <main id="main-content" tabIndex={-1} className="verify-page">
      <section className="page-intro">
        <p className="eyebrow">Verificação independente</p>
        <h1>Valide um pacote de evidências</h1>
        <p>
          Os arquivos são processados neste navegador e não são enviados. Após a
          conferência local, consultamos a API usando somente o identificador da
          sessão e o hash do manifesto para localizar a prova temporal.
        </p>
      </section>
      <section className="panel" aria-labelledby="files-heading">
        <div className="panel-heading">
          <div>
            <span>Passo 1</span>
            <h2 id="files-heading">Escolha o ZIP original</h2>
          </div>
          <span className="local-badge">Processamento local</span>
        </div>
        <fieldset disabled={running} className="verification-inputs">
          <legend className="sr-only">Arquivos e opções de verificação</legend>
          <FileField
            id="package"
            label="ZIP da evidência"
            required
            accept=".zip,application/zip"
            file={packageFile}
            onChange={(file) => {
              setPackageFile(file);
              setChecksumFile(undefined);
              setProofFile(undefined);
              setReport(undefined);
              setError("");
            }}
            prominent
          />
          <details className="optional-section">
            <summary>Adicionar comprovantes opcionais</summary>
            <p>
              O complemento é localizado automaticamente quando está disponível.
              Você também pode fornecer uma cópia recebida por outro meio para
              fazer a verificação offline.
            </p>
            <div className="file-grid">
              <FileField
                key={`checksum-${packageFile?.name}-${packageFile?.lastModified}`}
                id="checksum"
                label="Checksum .sha256"
                accept=".sha256,text/plain"
                file={checksumFile}
                onChange={(file) => {
                  setChecksumFile(file);
                  setReport(undefined);
                  setError("");
                }}
              />
              <FileField
                key={`proofs-${packageFile?.name}-${packageFile?.lastModified}`}
                id="proofs"
                label="ZIP complementar de provas"
                accept=".zip,application/zip"
                file={proofFile}
                onChange={(file) => {
                  setProofFile(file);
                  setReport(undefined);
                  setError("");
                }}
              />
            </div>
          </details>
          <details className="optional-section">
            <summary>Verificação avançada de confiança</summary>
            <label className="key-field" htmlFor="trusted-key">
              Chave pública operacional <span>Ed25519 em hexadecimal</span>
              <input
                id="trusted-key"
                value={trustedKey}
                onChange={(event) => {
                  setTrustedKey(event.target.value);
                  setReport(undefined);
                  setError("");
                }}
                autoComplete="off"
                spellCheck={false}
                placeholder="64 caracteres hexadecimais"
              />
            </label>
            <p className="field-help">
              Uma chave obtida separadamente permite confirmar a identidade
              operacional que assinou o pacote.
            </p>
          </details>
        </fieldset>
        <button
          className="primary verify-button"
          disabled={running || !packageFile}
          onClick={() => void verify()}
        >
          {running ? "Validando integridade…" : "Validar evidência"}
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
      <div aria-live="polite">{report && <Report report={report} />}</div>
      <p className="field-help">
        A verificação não confirma a veracidade do conteúdo nem substitui a
        análise do contexto.
      </p>
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
  prominent = false,
}: {
  id: string;
  label: string;
  required?: boolean;
  accept: string;
  file: File | undefined;
  onChange: (file: File | undefined) => void;
  prominent?: boolean;
}) {
  return (
    <label
      className={`file-field ${prominent ? "prominent" : ""}`}
      htmlFor={id}
    >
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
    report.result === "integral"
      ? "Integridade confirmada"
      : "Integridade confirmada com ausências declaradas";
  return (
    <section className="panel report" aria-labelledby="result-heading">
      <div className="result-heading">
        <div>
          <p className="eyebrow">Resultado</p>
          <h2 id="result-heading">{label}</h2>
        </div>
        <span className="result-badge">✓ Verificado</span>
      </div>
      <p className="result-summary">
        Os arquivos presentes correspondem ao índice assinado e à sequência
        registrada no pacote.
      </p>
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
            {report.trustMode === "root_certified"
              ? "Chave certificada pela raiz oficial"
              : report.trustMode === "custom_operational_key"
                ? "Chave confirmada separadamente"
                : "Assinatura consistente com a chave do pacote"}
          </dd>
        </div>
      </dl>
      <h3>Camadas verificadas</h3>
      <ul className="checks">
        {report.checks.map((check) => (
          <li key={check.id} className={check.status}>
            <span aria-hidden="true">
              {check.status === "valid"
                ? "✓"
                : check.status === "info"
                  ? "i"
                  : "!"}
            </span>
            <div>
              <strong>{check.label}</strong>
              <p>{check.detail}</p>
            </div>
          </li>
        ))}
      </ul>
      <div className="actions">
        {report.proofBundleUrl && (
          <a className="secondary button" href={report.proofBundleUrl}>
            Baixar complemento temporal
          </a>
        )}
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
          Baixar relatório JSON
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
      <details className="package-hash">
        <summary>Identificador técnico do pacote</summary>
        <code>{report.packageHash}</code>
      </details>
    </section>
  );
}

function Methodology({ navigate }: { navigate: (page: Page) => void }) {
  return (
    <main id="main-content" tabIndex={-1} className="methodology">
      <section className="page-intro">
        <p className="eyebrow">Metodologia v0.3 · Guarda local</p>
        <h1>Como o Evidências fortalece uma evidência digital</h1>
        <p>
          A metodologia combina observação do navegador, encadeamento
          criptográfico, recibos assinados, fontes externas de tempo e
          verificação independente. Neste beta, os arquivos ficam no
          dispositivo; o servidor registra hashes e provas técnicas, sem receber
          seu conteúdo.
        </p>
      </section>
      <section className="attests panel">
        <p className="eyebrow">O que é atestado</p>
        <h2>Garantias técnicas verificáveis</h2>
        <ul>
          <li>Os arquivos correspondem aos hashes e ao índice assinado.</li>
          <li>
            Os artefatos pertencem à mesma sessão e à sequência registrada.
          </li>
          <li>
            Alterações, remoções, duplicações e reordenações são detectáveis.
          </li>
          <li>
            Os recibos identificam o que o servidor confirmou: o registro dos
            hashes ou, no modo de guarda remota, a persistência dos arquivos.
          </li>
          <li>
            As provas temporais vinculam o hash a fontes externas quando
            presentes.
          </li>
          <li>
            O pacote pode ser verificado por terceiros sem depender do servidor.
          </li>
        </ul>
      </section>
      <section className="method-grid">
        <article>
          <span>01</span>
          <h2>Captura contextual</h2>
          <p>
            A extensão registra vídeo da navegação, imagens, estrutura da
            página, texto visível e metadados. Cada artefato declara método,
            origem técnica e estado.
          </p>
        </article>
        <article>
          <span>02</span>
          <h2>Cadeia de integridade</h2>
          <p>
            Cada evento referencia o hash anterior e recebe a assinatura da
            chave efêmera da sessão. A cadeia preserva a ordem da coleta e
            evidencia qualquer ruptura.
          </p>
        </article>
        <article>
          <span>03</span>
          <h2>Recibos assinados</h2>
          <p>
            No modo só-hash, o servidor assina o registro dos hashes declarados
            pela extensão, sem receber os arquivos. No modo opcional de guarda
            remota, ele também confere os bytes e confirma a persistência.
            Reenvios divergentes são recusados.
          </p>
        </article>
        <article>
          <span>04</span>
          <h2>Manifesto e assinaturas</h2>
          <p>
            Ao finalizar, cliente e servidor assinam documentos que vinculam
            sessão, artefatos, lacunas declaradas e identidade das versões de
            software utilizadas.
          </p>
        </article>
        <article>
          <span>05</span>
          <h2>Provas de tempo</h2>
          <p>
            O beta usa OpenTimestamps, com confirmação posterior no Bitcoin. Uma
            prova pendente ainda não é uma confirmação. RFC 3161 é uma camada
            prevista na arquitetura, não uma garantia deste beta.
          </p>
        </article>
        <article>
          <span>06</span>
          <h2>Preservação imutável</h2>
          <p>
            Fora deste beta: Ceph com Object Lock pode impedir alteração ou
            exclusão durante a retenção. O armazenamento atual não oferece essa
            proteção.
          </p>
        </article>
        <article>
          <span>07</span>
          <h2>Verificação independente</h2>
          <p>
            O verificador recalcula hashes e valida índice, cadeia, assinaturas,
            recibos e completude localmente. Esta interface confere os vínculos
            assinados das provas temporais; a verificação criptográfica completa
            dessas provas é feita pelo verificador de linha de comando.
          </p>
        </article>
        <article>
          <span>08</span>
          <h2>Resultado reproduzível</h2>
          <p>
            Metodologia, formatos e identidade do software são versionados. O
            relatório separa claramente resultado geral, confiança e estado de
            cada camada.
          </p>
        </article>
      </section>
      <section className="panel prose">
        <h2>Como apresentar a evidência</h2>
        <p>
          Preserve o ZIP original e seu checksum, valide o pacote, exporte o
          relatório e mantenha juntos os complementos temporais recebidos
          depois. O hash externo permite identificar exatamente o arquivo
          analisado.
        </p>
        <h2>Escopo da atestação</h2>
        <p>
          O Evidências atesta integridade técnica, continuidade da coleta,
          vínculo entre artefatos e sequência e, quando a prova correspondente
          estiver presente, existência temporal dos bytes registrados. A
          apreciação jurídica considera esse conjunto técnico junto ao contexto
          do caso.
        </p>
        <button className="primary" onClick={() => navigate("verify")}>
          Validar uma evidência
        </button>
      </section>
    </main>
  );
}

function temporalLabel(value: VerificationReport["temporalProof"]): string {
  return {
    not_provided: "Não fornecida",
    pending: "Pendente",
    signed_claims_only: "Vínculo assinado disponível",
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
  return `<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Verificação Evidências</title><h1>Relatório de verificação</h1><p><strong>${report.result === "integral" ? "Integridade confirmada" : "Integridade confirmada com ausências declaradas"}</strong></p><dl><dt>Resultado</dt><dd>${escapeHtml(report.result)}</dd><dt>Sessão</dt><dd>${escapeHtml(report.sessionId)}</dd><dt>SHA-256</dt><dd>${escapeHtml(report.packageHash)}</dd><dt>Prova temporal</dt><dd>${escapeHtml(report.temporalProof)}</dd><dt>Confiança</dt><dd>${escapeHtml(report.trustMode)}</dd></dl><h2>Verificações</h2><ul>${checks}</ul><h2>Escopo da atestação</h2><p>Este relatório atesta a integridade técnica, a continuidade da coleta e o vínculo entre os artefatos e a sequência registrados no pacote. A apreciação jurídica considera esse conjunto técnico junto ao contexto do caso.</p></html>`;
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
if (
  import.meta.env.PROD &&
  !isConstructionHost(location.hostname) &&
  "serviceWorker" in navigator
)
  window.addEventListener("load", () => {
    void navigator.serviceWorker.register("/sw.js");
  });

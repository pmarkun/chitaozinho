import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";

import {
  EvidenceValidationError,
  type VerificationReport,
  verifyEvidencePackage,
} from "./validator";
import "./styles.css";

type Page = "home" | "verify" | "methodology";

const routes: Record<Page, string> = {
  home: "/",
  verify: "/validar",
  methodology: "/metodologia",
};

function pageFromPath(): Page {
  if (location.pathname.startsWith("/validar")) return "verify";
  if (location.pathname.startsWith("/metodologia")) return "methodology";
  return "home";
}

function App() {
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

  return (
    <>
      <a className="skip-link" href="#main-content">
        Pular para o conteúdo
      </a>
      <header className="site-header">
        <button className="brand" onClick={() => navigate("home")}>
          <span aria-hidden="true">C</span>
          <span>
            Chitãozinho <small>Evidência digital verificável</small>
          </span>
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
            Metodologia
          </NavButton>
        </nav>
      </header>
      {page === "home" && <Home navigate={navigate} />}
      {page === "verify" && <Verifier />}
      {page === "methodology" && <Methodology navigate={navigate} />}
      <footer>
        <strong>Chitãozinho</strong>
        <span>Pacotes íntegros, rastreáveis e verificáveis.</span>
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

function Home({ navigate }: { navigate: (page: Page) => void }) {
  const installUrl = import.meta.env.VITE_EXTENSION_INSTALL_URL as
    string | undefined;
  return (
    <main id="main-content" className="home">
      <section className="home-hero">
        <div>
          <p className="eyebrow">Evidência digital com cadeia de integridade</p>
          <h1>Registre a web. Preserve o contexto. Comprove a integridade.</h1>
          <p className="hero-copy">
            Transforme conteúdo exibido no navegador em um pacote de evidência
            digital íntegro, rastreável e verificável.
          </p>
          <div className="hero-actions">
            {installUrl && (
              <a className="primary button" href={installUrl}>
                Instalar extensão
              </a>
            )}
            <button className="primary" onClick={() => navigate("verify")}>
              Validar uma evidência
            </button>
            <button
              className="text-button"
              onClick={() => navigate("methodology")}
            >
              Conhecer a metodologia →
            </button>
          </div>
        </div>
        <EvidenceCard />
      </section>

      <section className="comparison" aria-labelledby="comparison-title">
        <p className="eyebrow">Além do print</p>
        <h2 id="comparison-title">
          Um registro que preserva a história completa
        </h2>
        <div className="comparison-grid">
          <article>
            <span>Print isolado</span>
            <p>
              Registra uma imagem sem demonstrar sua sequência, contexto ou
              alterações posteriores.
            </p>
          </article>
          <article className="highlight">
            <span>Pacote Chitãozinho</span>
            <p>
              Reúne vídeo, imagens, estrutura da página, metadados, hashes,
              assinaturas, recibos e provas de tempo.
            </p>
          </article>
        </div>
      </section>

      <section className="steps" aria-labelledby="steps-title">
        <p className="eyebrow">Como funciona</p>
        <h2 id="steps-title">Da coleta à verificação em três etapas</h2>
        <div className="three-columns">
          <article>
            <b>01</b>
            <h3>Registre</h3>
            <p>
              Navegue pelo conteúdo mostrando origem, datas, perfis e contexto
              relevante.
            </p>
          </article>
          <article>
            <b>02</b>
            <h3>Preserve</h3>
            <p>
              Receba um ZIP assinado que vincula arquivos, sequência da captura
              e recibos do servidor.
            </p>
          </article>
          <article>
            <b>03</b>
            <h3>Valide</h3>
            <p>
              Confirme a integridade online ou offline, sem enviar os arquivos
              para o Chitãozinho.
            </p>
          </article>
        </div>
      </section>

      <section className="guarantees" aria-labelledby="guarantees-title">
        <div>
          <p className="eyebrow">Forças do projeto</p>
          <h2 id="guarantees-title">Cada camada reforça a evidência</h2>
        </div>
        <ul>
          <li>
            <strong>Integridade verificável</strong>
            <span>
              Qualquer alteração nos bytes é localizada por hashes e pelo índice
              assinado.
            </span>
          </li>
          <li>
            <strong>Sequência rastreável</strong>
            <span>
              Remoção, duplicação ou reordenação rompe a cadeia criptográfica.
            </span>
          </li>
          <li>
            <strong>Persistência comprovada</strong>
            <span>
              Recibos são assinados somente depois do armazenamento de cada
              parte.
            </span>
          </li>
          <li>
            <strong>Marcos temporais externos</strong>
            <span>
              RFC 3161 e OpenTimestamps vinculam o hash a fontes independentes
              de tempo.
            </span>
          </li>
          <li>
            <strong>Preservação imutável</strong>
            <span>
              Object Lock protege os pacotes durante o prazo de retenção
              configurado.
            </span>
          </li>
          <li>
            <strong>Auditoria independente</strong>
            <span>
              Metodologia versionada e verificadores abertos permitem reproduzir
              a análise.
            </span>
          </li>
        </ul>
      </section>

      <section className="closing-cta">
        <p className="eyebrow">Verificação local</p>
        <h2>Já recebeu um pacote Chitãozinho?</h2>
        <p>
          Confira sua integridade agora. Os arquivos permanecem no seu
          dispositivo.
        </p>
        <button className="primary" onClick={() => navigate("verify")}>
          Validar evidência
        </button>
      </section>
    </main>
  );
}

function EvidenceCard() {
  return (
    <div
      className="evidence-card"
      aria-label="Exemplo de pacote de evidência íntegro"
    >
      <div className="evidence-card-head">
        <span className="seal">✓</span>
        <span>
          <small>Pacote de evidência</small>
          <strong>Integridade confirmada</strong>
        </span>
      </div>
      <dl>
        <div>
          <dt>Arquivos</dt>
          <dd>Verificados</dd>
        </div>
        <div>
          <dt>Sequência</dt>
          <dd>Íntegra</dd>
        </div>
        <div>
          <dt>Assinaturas</dt>
          <dd>Válidas</dd>
        </div>
        <div>
          <dt>Prova temporal</dt>
          <dd>Confirmada</dd>
        </div>
      </dl>
      <code>sha256:4c7a…91ef</code>
    </div>
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
    <main id="main-content" className="verify-page">
      <section className="page-intro">
        <p className="eyebrow">Verificação independente</p>
        <h1>Confirme a integridade de uma evidência</h1>
        <p>
          Todo o processamento acontece neste navegador. Nenhum byte dos
          arquivos selecionados é transmitido.
        </p>
      </section>
      <section className="panel" aria-labelledby="files-heading">
        <div className="panel-heading">
          <div>
            <span>Passo 1</span>
            <h2 id="files-heading">Selecione o pacote principal</h2>
          </div>
          <span className="local-badge">Processamento local</span>
        </div>
        <FileField
          id="package"
          label="ZIP da evidência"
          required
          accept=".zip,application/zip"
          file={packageFile}
          onChange={setPackageFile}
          prominent
        />
        <details className="optional-section">
          <summary>Adicionar comprovantes opcionais</summary>
          <p>
            O checksum e o complemento podem confirmar camadas adicionais quando
            acompanham o pacote.
          </p>
          <div className="file-grid">
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
        </details>
        <details className="optional-section">
          <summary>Verificação avançada de confiança</summary>
          <label className="key-field" htmlFor="trusted-key">
            Chave pública operacional <span>Ed25519 em hexadecimal</span>
            <input
              id="trusted-key"
              value={trustedKey}
              onChange={(event) => setTrustedKey(event.target.value)}
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
            {report.trustMode === "custom_operational_key"
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
    <main id="main-content" className="methodology">
      <section className="page-intro">
        <p className="eyebrow">Metodologia v0.2</p>
        <h1>Como o Chitãozinho fortalece uma evidência digital</h1>
        <p>
          A metodologia combina observação do navegador, encadeamento
          criptográfico, recibos assinados, fontes externas de tempo e
          preservação imutável.
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
            Os recibos vinculam cada parte à persistência confirmada pelo
            servidor.
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
          <h2>Recibos de persistência</h2>
          <p>
            O servidor recalcula os hashes e assina recibos sequenciais somente
            depois de persistir os bytes. Reenvios divergentes são recusados e
            registrados.
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
            RFC 3161 e OpenTimestamps demonstram que o hash do manifesto já
            existia até os marcos validados por autoridades e pela blockchain do
            Bitcoin.
          </p>
        </article>
        <article>
          <span>06</span>
          <h2>Preservação imutável</h2>
          <p>
            Em ambientes probatórios, Ceph Object Lock com retenção protege
            originais e provas contra alteração ou exclusão antecipada.
          </p>
        </article>
        <article>
          <span>07</span>
          <h2>Verificação independente</h2>
          <p>
            O verificador recalcula hashes e valida índice, cadeia, assinaturas,
            recibos, completude e provas temporais online ou offline,
            processando tudo localmente.
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
          O Chitãozinho atesta integridade técnica, continuidade da coleta,
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
  return `<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Verificação Chitãozinho</title><h1>Relatório de verificação</h1><p><strong>${report.result === "integral" ? "Integridade confirmada" : "Integridade confirmada com ausências declaradas"}</strong></p><dl><dt>Resultado</dt><dd>${escapeHtml(report.result)}</dd><dt>Sessão</dt><dd>${escapeHtml(report.sessionId)}</dd><dt>SHA-256</dt><dd>${escapeHtml(report.packageHash)}</dd><dt>Prova temporal</dt><dd>${escapeHtml(report.temporalProof)}</dd><dt>Confiança</dt><dd>${escapeHtml(report.trustMode)}</dd></dl><h2>Verificações</h2><ul>${checks}</ul><h2>Escopo da atestação</h2><p>Este relatório atesta a integridade técnica, a continuidade da coleta e o vínculo entre os artefatos e a sequência registrados no pacote. A apreciação jurídica considera esse conjunto técnico junto ao contexto do caso.</p></html>`;
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
if (import.meta.env.PROD && "serviceWorker" in navigator)
  window.addEventListener("load", () => {
    void navigator.serviceWorker.register("/sw.js");
  });

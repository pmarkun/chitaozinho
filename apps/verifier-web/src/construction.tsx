import { useEffect } from "react";

import "./construction.css";

export function isConstructionHost(hostname: string): boolean {
  return (
    hostname === "evidencias.org.br" || hostname === "www.evidencias.org.br"
  );
}

export function Construction() {
  useEffect(() => {
    document.title = "Evidências — em construção";
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", "#00004b");
    document.querySelector('link[rel="manifest"]')?.remove();
    if ("serviceWorker" in navigator) {
      void navigator.serviceWorker
        .getRegistrations()
        .then((registrations) =>
          Promise.all(
            registrations.map((registration) => registration.unregister()),
          ),
        );
    }
  }, []);

  return (
    <main id="main-content" className="construction-page" tabIndex={-1}>
      <div className="construction-stars" aria-hidden="true">
        ✦ · . ✧ . · ✦ . ✧ · . ✦
      </div>
      <section
        className="construction-window"
        aria-labelledby="construction-title"
      >
        <div className="construction-titlebar">
          <span>evidencias.org.br</span>
          <span aria-hidden="true">_ □ ×</span>
        </div>

        <div className="construction-content">
          <p className="construction-kicker">★★★ em breve na internet ★★★</p>
          <h1 id="construction-title">Evidências</h1>
          <p className="construction-blink">SITE EM CONSTRUÇÃO</p>

          <img
            className="construction-gif"
            src="/under-construction.gif"
            alt="Placa animada de obras com luzes piscando"
            width="320"
            height="120"
          />

          <p className="construction-copy">
            Estamos preparando um espaço para registrar e verificar evidências
            digitais. Volte em breve.
          </p>

          <div className="construction-status" aria-label="Status da obra">
            <span>Status:</span>
            <div className="construction-progress" aria-hidden="true">
              <span />
            </div>
            <strong>carregando…</strong>
          </div>

          <a
            className="construction-beta"
            href="https://beta.evidencias.org.br/"
          >
            Entrar na versão beta
          </a>

          <p className="construction-note">
            Melhor visualizado em qualquer navegador moderno — mas com saudade
            de 1998.
          </p>
        </div>
      </section>

      <footer className="construction-footer">Evidências · desde 2026</footer>
    </main>
  );
}

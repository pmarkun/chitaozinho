# Changelog

Mudanças relevantes do Chitãozinho são registradas aqui. As versões seguem
[Semantic Versioning](https://semver.org/) e os artefatos publicados estão nas
[releases do GitHub](https://github.com/pmarkun/chitaozinho/releases).

## Unreleased

- Corrige o descarte de upgrades OpenTimestamps parciais antes de uma nova
  tentativa.
- Simplifica a estrutura e a documentação do repositório para colaboradores.

## 0.1.1 — 2026-09-02

- Adiciona ancoragem de raízes Merkle em calendários públicos OpenTimestamps.
- Tenta novamente provas ainda pendentes de confirmação no Bitcoin.
- Conecta declarativamente os secrets do cron OpenTimestamps no Railway.

## 0.1.0 — 2026-09-02

- Publica o beta no Railway com API, worker, expiração, PostgreSQL, Bucket,
  OpenBao e verificador web.
- Adiciona autenticação por magic link via Resend e isolamento por usuário.
- Entrega extensão Chromium, pacote verificável e verificadores web e CLI.
- Publica artefatos reproduzíveis, SBOMs e assinaturas Sigstore.

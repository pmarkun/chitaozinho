# Changelog

Mudanças relevantes do Chitãozinho são registradas aqui. As versões seguem
[Semantic Versioning](https://semver.org/) e os artefatos publicados estão nas
[releases do GitHub](https://github.com/pmarkun/chitaozinho/releases).

## Unreleased

## 0.1.8 — 2026-10-01

- Substitui a 0.1.7 após o check de segurança, preservando os créditos, logos
  e Termos de Uso aprovados.
- Atualiza GitPython para corrigir GHSA-59cr-6r3x-644w.

## 0.1.7 — 2026-10-01

- Atualiza os realizadores e a parceria com Conectas, com logos institucionais.
- Publica os Termos de Uso no site e na página offline da extensão.
- Exige aceite explícito da versão atual antes de cada nova captura e registra
  a versão nos dados locais da coleta.
- Incorpora correções de segurança do verificador já implantadas no beta.

## 0.1.6 — 2026-09-30

- Preserva a reprodução do áudio da aba durante a gravação.
- Adiciona captura de tela/janela com áudio autorizado pelo seletor do Chrome,
  conforme suporte do sistema operacional, e aviso quando o áudio faltar.
- Adiciona microfone opcional, desligado por padrão, com autorização explícita
  e mistura de áudio somente no arquivo gravado.
- Atualiza a política de privacidade para os novos modos de captura.
- Testes automatizados verificam dois sinais de áudio no WebM; Zoom e
  dispositivos reais em cada plataforma ainda precisam de teste manual.

- Remove a exigência de e-mail do beta `hash_only`, mantendo magic link como
  módulo opcional para guarda remota.
- Consulta e baixa automaticamente complementos OpenTimestamps no verificador,
  sem enviar os arquivos capturados.
- Valida a chave operacional pela raiz pública oficial e mostra guarda local
  como informação, não como falha.
- Inicia lotes OpenTimestamps pelo worker contínuo, com o cron como recuperação.
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

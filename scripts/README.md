# Scripts

Execute os scripts a partir da raiz, dentro de `nix develop`. Esta lista também
documenta por que cada entrada existe.

| Script | Classe | Finalidade |
| --- | --- | --- |
| `check` | CI e desenvolvimento | Gate completo do repositório |
| `check-repository-hygiene.py` | CI | Rejeita artefatos gerados e links locais quebrados |
| `security-audit` | CI e segurança | OSV, segredos e configuração com Trivy |
| `check-protocol-compatibility` | CI | Impede mudança de protocolo sem versão |
| `check-extension-reproducibility` | CI | Compara dois ZIPs da extensão |
| `check-verifier-reproducibility` | CI | Compara builds isolados do verificador Rust |
| `check-oci-reproducibility` | CI | Compara imagens OCI reproduzíveis |
| `check-ceph-config.py` | CI | Valida versão e contrato do Ceph |
| `check-openbao-config.py` | CI | Valida policy e configuração do OpenBao |
| `check-railway-config.py` | CI | Valida a topologia declarativa do beta |
| `check-monitoring-config.py` | CI | Valida o contrato dos alertas |
| `local-services` | Desenvolvimento | Inicia e encerra PostgreSQL e Garage locais |
| `test-service-integration` | CI e desenvolvimento | Exercita PostgreSQL e S3 reais em isolamento |
| `test-postgres-backup-restore` | CI e operação | Testa backup, restore, migração e cadeia de auditoria |
| `check-database-recovery.py` | Interno | Apoia a validação de restore PostgreSQL |
| `test-s3-object-lock` | Operação | Ensaia Object Lock em um bucket descartável aprovado |
| `provision-ceph-bucket` | Operação | Provisiona Ceph RGW com as proteções exigidas |
| `check-public-environment.py` | Operação | Probe público somente leitura de TLS e endpoints |
| `smoke-railway-beta` | Operação | Executa captura sintética completa no beta |
| `key-management` | Operação offline | Gera raiz, certificado e revogações |
| `measure-browser-resources` | Qualidade manual | Coleta CPU, memória e I/O do Chrome |
| `analyze_browser_resources.py` | Qualidade manual | Avalia a coleta contra os limites definidos |
| `package-extension` | Release, interno | Produz ZIP determinístico da extensão |
| `build-release-artifacts` | Release | Gera artefatos, checksums e SBOMs |

Scripts marcados como internos são chamados por outra entrada e não são uma API
separada. Operações que alteram infraestrutura ou usam dados reais continuam
dependendo de autorização e revisão dos alvos.

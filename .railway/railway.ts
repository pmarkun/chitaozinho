import {
  bucket,
  defineRailway,
  fn,
  github,
  postgres,
  preserve,
  project,
  ref,
  service,
  volume,
} from "railway/iac";

const region = "us-east4-eqdc4a";
const mib = 1024 * 1024;

export default defineRailway(() => {
  const source = github("pmarkun/chitaozinho", { branch: "main" });
  const database = postgres("postgres", { region });
  const evidence = bucket("chitaozinho-beta", { region: "iad" });
  const openbaoData = volume("openbao-data", {
    region,
    sizeMB: 1024,
    allowOnlineResize: true,
  });

  const backendEnv = {
    CHITAOZINHO_ENV: "beta",
    CHITAOZINHO_DATABASE_URL: database.env.DATABASE_URL,
    CHITAOZINHO_STORAGE_BACKEND: "s3",
    CHITAOZINHO_STORAGE_PROVIDER: "railway",
    CHITAOZINHO_S3_ENDPOINT_URL: ref(evidence, "ENDPOINT"),
    CHITAOZINHO_S3_REGION: ref(evidence, "REGION"),
    CHITAOZINHO_S3_BUCKET: ref(evidence, "BUCKET"),
    CHITAOZINHO_S3_ACCESS_KEY_ID: ref(evidence, "ACCESS_KEY_ID"),
    CHITAOZINHO_S3_SECRET_ACCESS_KEY: ref(evidence, "SECRET_ACCESS_KEY"),
    CHITAOZINHO_RETENTION_DAYS: "30",
    CHITAOZINHO_PUBLIC_BASE_URL: "https://api-staging.up.railway.app",
    CHITAOZINHO_AUTH_MODE: "magic_link",
    CHITAOZINHO_AUTH_TOKEN_PEPPER: preserve(),
    CHITAOZINHO_EMAIL_PROVIDER: "resend",
    CHITAOZINHO_RESEND_API_KEY: preserve(),
    CHITAOZINHO_RESEND_FROM: preserve(),
    CHITAOZINHO_EXTENSION_IDS: "ekdgmdbnkfmjeppmmceeigojgemklpgd",
    CHITAOZINHO_METRICS_TOKEN: preserve(),
    CHITAOZINHO_OPENBAO_ADDR: "https://openbao.railway.internal:8200",
    CHITAOZINHO_OPENBAO_ROLE_ID: preserve(),
    CHITAOZINHO_OPENBAO_SECRET_ID: preserve(),
    CHITAOZINHO_OPENBAO_TRANSIT_KEY: "chitaozinho-server",
    CHITAOZINHO_OPENBAO_TRANSIT_KEY_VERSION: "1",
    CHITAOZINHO_OPENBAO_CA_BUNDLE: "/app/infra/openbao/ca.crt",
    CHITAOZINHO_SERVER_KEY_ID: "chitaozinho-server-v1",
    CHITAOZINHO_SERVER_CERTIFICATE_JSON: preserve(),
    CHITAOZINHO_SERVER_REVOCATION_LIST_JSON: preserve(),
    CHITAOZINHO_SERVER_ROOT_PUBLIC_JSON: preserve(),
    CHITAOZINHO_SOFTWARE_COMMIT: "${{RAILWAY_GIT_COMMIT_SHA}}",
    CHITAOZINHO_SOFTWARE_BUILD_HASH_PATH: "/app/SOURCE_SHA256",
  };

  const api = service("api", {
    source,
    build: { builder: "DOCKERFILE", dockerfilePath: "Dockerfile" },
    start:
      'sh -c \'exec uvicorn chitaozinho_api.main:create_app --factory --host 0.0.0.0 --port "$PORT" --no-access-log\'',
    preDeploy: "alembic upgrade head",
    healthcheck: "/readyz",
    healthcheckTimeout: 30,
    replicas: { [region]: 1 },
    deploy: {
      restartPolicyType: "ON_FAILURE",
      restartPolicyMaxRetries: 5,
      limitOverride: { containers: { memoryBytes: 384 * mib } },
    },
    networking: {
      serviceDomains: { "api-staging.up.railway.app": { port: 8000 } },
    },
    env: backendEnv,
  });

  const worker = service("worker", {
    source,
    build: { builder: "DOCKERFILE", dockerfilePath: "Dockerfile" },
    start: "python -m chitaozinho_api.worker",
    replicas: { [region]: 1 },
    deploy: {
      restartPolicyType: "ON_FAILURE",
      restartPolicyMaxRetries: 5,
      limitOverride: { containers: { memoryBytes: 256 * mib } },
    },
    env: backendEnv,
  });

  const cleanup = fn("retention-cleanup", {
    source,
    build: { builder: "DOCKERFILE", dockerfilePath: "Dockerfile" },
    start: "python -m chitaozinho_api.retention_cleanup",
    deploy: {
      cronSchedule: "15 3 * * *",
      restartPolicyType: "NEVER",
      limitOverride: { containers: { memoryBytes: 256 * mib } },
    },
    env: backendEnv,
  });

  const openbao = service("openbao", {
    source,
    build: { builder: "DOCKERFILE", dockerfilePath: "Dockerfile.openbao" },
    replicas: { [region]: 1 },
    deploy: {
      restartPolicyType: "ON_FAILURE",
      restartPolicyMaxRetries: 5,
      limitOverride: { containers: { memoryBytes: 512 * mib } },
    },
    volumeMounts: { "/openbao/data": openbaoData },
    env: {
      OPENBAO_TLS_CERT_PEM: preserve(),
      OPENBAO_TLS_KEY_PEM: preserve(),
      RAILWAY_RUN_UID: "0",
    },
  });

  const verifierWeb = service("verifier-web", {
    source,
    build: { builder: "DOCKERFILE", dockerfilePath: "Dockerfile.verifier-web" },
    healthcheck: "/health",
    healthcheckTimeout: 30,
    replicas: { [region]: 1 },
    deploy: {
      restartPolicyType: "ON_FAILURE",
      restartPolicyMaxRetries: 5,
      limitOverride: { containers: { memoryBytes: 128 * mib } },
    },
    networking: {
      serviceDomains: { "verifier-web-staging.up.railway.app": { port: 8080 } },
    },
  });

  return project("chitaozinho", {
    resources: [database, evidence, openbaoData, api, worker, cleanup, openbao, verifierWeb],
  });
});

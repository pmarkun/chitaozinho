mod package;

use std::path::PathBuf;

use anyhow::Result;
use clap::{Parser, Subcommand};

#[derive(Debug, Parser)]
#[command(
    name = "chitaozinho-verify",
    version,
    about = "Offline evidence verifier"
)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Debug, Subcommand)]
enum Command {
    /// Print protocol and schema versions understood by this verifier.
    Version,
    /// Build a signed evidence package without modifying the source directory.
    Pack {
        #[arg(long)]
        source: PathBuf,
        #[arg(long)]
        output: PathBuf,
        #[arg(long)]
        server_seed_hex: String,
    },
    /// Verify a package without backend or network access.
    Verify {
        package: PathBuf,
        #[arg(long)]
        proof_bundle: Option<PathBuf>,
        #[arg(long, requires = "proof_bundle")]
        tsa_ca_bundle: Option<PathBuf>,
        #[arg(long, requires = "tsa_ca_bundle")]
        tsa_crl_bundle: Option<PathBuf>,
        #[arg(long, required_unless_present = "trusted_root_key_hex")]
        trusted_server_key_hex: Option<String>,
        #[arg(long, required_unless_present = "trusted_server_key_hex")]
        trusted_root_key_hex: Option<String>,
        #[arg(long)]
        json: bool,
        #[arg(long)]
        html_report: Option<PathBuf>,
    },
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Command::Version => {
            println!("protocol_version=0.1.0");
            println!("schema_version=0.1.0");
        }
        Command::Pack {
            source,
            output,
            server_seed_hex,
        } => {
            let seed = package::decode_array::<32>(&server_seed_hex, "server seed")?;
            let result = package::pack(&source, &output, &seed)?;
            println!("package={}", result.package_path.display());
            println!("sha256={}", result.sha256);
            println!("hash_file={}", result.hash_path.display());
        }
        Command::Verify {
            package,
            proof_bundle,
            tsa_ca_bundle,
            tsa_crl_bundle,
            trusted_server_key_hex,
            trusted_root_key_hex,
            json,
            html_report,
        } => {
            let trust =
                match (trusted_server_key_hex, trusted_root_key_hex) {
                    (Some(value), None) => package::TrustAnchor::Operational(
                        package::decode_array::<32>(&value, "trusted server key")?,
                    ),
                    (None, Some(value)) => package::TrustAnchor::Root(package::decode_array::<32>(
                        &value,
                        "trusted root key",
                    )?),
                    _ => anyhow::bail!("choose exactly one trusted key mode"),
                };
            let report = match proof_bundle {
                Some(bundle) => package::verify_with_proof_bundle_and_trust_anchor(
                    &package,
                    &bundle,
                    &trust,
                    tsa_ca_bundle.as_deref(),
                    tsa_crl_bundle.as_deref(),
                )?,
                None => package::verify_with_trust_anchor(&package, &trust)?,
            };
            if let Some(path) = html_report {
                package::write_html_report(&report, &path)?;
            }
            if json {
                println!("{}", serde_json::to_string_pretty(&report)?);
            } else {
                println!("result={}", report.result);
                println!("session_id={}", report.session_id);
                println!("members={}", report.members_verified);
                println!("temporal_proof={}", report.temporal_proof);
                println!("attestations={}", report.attestations_verified);
                println!("trust_mode={}", report.trust_mode);
                for check in report.checks {
                    println!("check={} status=valid", check);
                }
            }
        }
    }
    Ok(())
}

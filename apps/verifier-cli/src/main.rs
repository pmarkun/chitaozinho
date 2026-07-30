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
        trusted_server_key_hex: String,
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
            trusted_server_key_hex,
            json,
            html_report,
        } => {
            let key = package::decode_array::<32>(&trusted_server_key_hex, "trusted server key")?;
            let report = package::verify(&package, &key)?;
            if let Some(path) = html_report {
                package::write_html_report(&report, &path)?;
            }
            if json {
                println!("{}", serde_json::to_string_pretty(&report)?);
            } else {
                println!("result={}", report.result);
                println!("session_id={}", report.session_id);
                println!("members={}", report.members_verified);
                for check in report.checks {
                    println!("check={} status=valid", check);
                }
            }
        }
    }
    Ok(())
}

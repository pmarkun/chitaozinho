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
}

fn main() {
    let cli = Cli::parse();
    match cli.command {
        Command::Version => {
            println!("protocol_version=0.1.0");
            println!("schema_version=0.1.0");
        }
    }
}

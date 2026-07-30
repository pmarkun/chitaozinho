{
  description = "Chitaozinho development environment";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in
    {
      devShells = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
        in
        {
          default = pkgs.mkShell {
            packages = with pkgs; [
              actionlint
              cargo
              clippy
              cosign
              docker-client
              garage
              jq
              nodejs_22
              opentofu
              openssl
              pkg-config
              pnpm
              postgresql_17
              python313
              ruff
              rustc
              rustfmt
              syft
              unzip
              uv
              zip
            ];

            env = {
              UV_PROJECT_ENVIRONMENT = ".venv";
            };

            shellHook = ''
              unset LD_LIBRARY_PATH
              echo "Chitaozinho dev shell"
              echo "Node $(node --version) | Python $(python --version) | Rust $(rustc --version)"
            '';
          };
        });
    };
}

{
  description = "Flake utils demo";

  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    poetry2nix = {
      url = "github:nix-community/poetry2nix";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.flake-utils.follows = "flake-utils";
    };
  };

  outputs = { self, nixpkgs, flake-utils, poetry2nix }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        p2n = poetry2nix.lib.mkPoetry2Nix {
          pkgs = pkgs;
        };
        python = pkgs.python312;
      in
      {
        packages = {
          zilch = p2n.mkPoetryApplication {
            projectDir = self;
            python = python;
          };
          default = self.packages.${system}.zilch;
        };
        devShells = {
          default = pkgs.mkShell {
            packages = [
              (p2n.mkPoetryEnv {
                projectDir = ./.;
                python = python;
                editablePackageSources = {
                  zilch = ./.;
                };
              })
              # non-Python packages go here
              pkgs.ruff
              pkgs.poetry
            ];
          };
        };
      }
    );
}

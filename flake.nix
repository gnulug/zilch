{
  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    source-0.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  };
  outputs = { self, flake-utils, nixpkgs, ... }@inputs:
    flake-utils.lib.eachDefaultSystem (system:
      {
        devShells = {
          default = nixpkgs.legacyPackages.${system}.mkShell {
            buildInputs = [
              inputs.source-0.legacyPackages.${system}.aria
            ];
          };
        };
      }
    )
  ;
}

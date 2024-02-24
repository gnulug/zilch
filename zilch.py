#!/usr/bin/env python3

from __future__ import annotations
import dataclasses
import pathlib
import click
import subprocess
import json

SEARCH_CMD = lambda source, term: ['nix', 'search', source, *term, '--json']

def simplify_attrpath(d):
    """Simplify attribute path from 'nix search'"""
    return {k.split('.')[-1]:v for k, v in d.items()}

@click.group(no_args_is_help=True)
@click.option('--debug/--no-debug', default=False)
def cli(debug):
    # click.echo(f"Debug mode is {'on' if debug else 'off'}")
    pass

@cli.command(no_args_is_help=True)  # @cli, not @click!
@click.argument('term', nargs=-1)
@click.option('--source', default="nixpkgs")
def search(term, source):
    o = subprocess.run(
        SEARCH_CMD(source, term),
        capture_output=True,
        check=True
    )
    packages = simplify_attrpath(json.loads(o.stdout))
    print(json.dumps(packages))


root = pathlib.Path(__file__).parent


@dataclasses.dataclass(frozen=True)
class Project:
    """The data in the project-local store"""
    path: pathlib.Path
    packages: list[NixPackage]

    def get_package(self, attribute_name: str, flake: str) -> NixPackage:
        if self.packages:
            raise NotImplementedError()
            # return a package from the latest version of this flake.
        else:
            # somehow get the "latest" version of flake
            pass
            raise NotImplementedError()

    def write_out(self) -> None:
        """Call this, and then do `git add -A & nix develop`"""
        flake_vers = {
            package.flake_ver
            for package in self.packages
        }
        flake_vers2name = {
            source: f"source-{i}"
            for i, source in enumerate(sorted(flake_vers))
        }
        input_lines = list(set(
            f"{flake_vers2name[package.flake_ver]}.url = \"{package.flake}\";"
            for package in self.packages
        ))
        package_lines = [
            f"inputs.{flake_vers2name[package.flake_ver]}.legacyPackages.${{system}}.{package.attribute}"
            for package in self.packages
        ]
        (root / "flake.nix").write_text(
            (root / "flake.nix.template")
            .read_text()
            .replace("INPUTS_HERE", ("\n" + 4 * " ").join(input_lines))
            .replace("PACKAGES_HERE", ("\n" + 14 * " ").join(package_lines))
        )
        # TODO: write package.version into flake.lock somehow

@dataclasses.dataclass(frozen=True)
class NixPackage:
    """A uniquely identified package in a flake with a specific commit."""
    flake: str
    version: str
    attribute: str

    @property
    def flake_ver(self) -> tuple[str, str]:
        return (self.flake, self.version)


if __name__ == "__main__":
    project = Project(
        path=pathlib.Path("test"),
        packages=[
            NixPackage("github:NixOS/nixpkgs/nixpkgs-unstable", "f63ce824cd2f036216eb5f637dfef31e1a03ee89", "aria")
        ],
    )
    project.write_out()

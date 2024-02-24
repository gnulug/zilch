#!/usr/bin/env python3

import click
import subprocess
import pathlib
import os
import json
from api import Project
import rich
from rich.console import Console
from rich.panel import Panel
from rich.segment import Segment
from rich.style import Style

console = Console(highlight=False)

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


@cli.command(no_args_is_help=True)  # @cli, not @click!
@click.argument("path", type=pathlib.Path)
@click.argument('cmd', nargs=-1)
def shell(path, cmd):
    if not cmd:
        cmd = (os.environ.get("SHELL", "/bin/bash"),)
    project = Project.from_path(path)
    project.develop(*cmd)
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
    version: str | None
    attribute: str
    description: str | None

    @property
    def flake_ver(self) -> tuple[str, str]:
        return (self.flake, self.version)

    @property
    def family(self) -> str:
        """Attribute family.  e.g legacyPackages"""
        return self.attribute.split('.', 2)[0]

    @property
    def system(self) -> str:
        """Architecture and OS"""
        return self.attribute.split('.', 2)[1]

    @property
    def name(self) -> str:
        """Package name"""
        return self.attribute.split('.', 2)[2]

    # def __rich__(self):
    #     # colors = itertools.cycle(("red", "green"))
    #     # x = "[blue]:[blue/]".join(
    #     #     f"[{color}]{self.name}[{color}/]".format(t=t, color=next(colors))
    #     #     for t in self.tag.split(":")
    #     # )
    #     return f"[bright_white]* {self.name}[/bright_white] ({self.version})"
    #     # yield f"  {self.description}"

    # def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
    #     yield f"[green]{self.name}[/green] ({self.version})"
    #     yield f"  {self.description}\n"


def parse_attrpath(path):
    """Parse attribute path from 'nix search'

    Args:
        path (str): attribute path

    Returns:
        (attr_family, system, name)
    """
    parts = path.split('.')
    return parts[0], parts[1], '.'.join(parts[2:])


if __name__ == "__main__":
    cli()

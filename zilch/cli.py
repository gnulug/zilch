import pathlib
import click
import subprocess
import json
import os
import sys
import platformdirs
import os
from typing import Mapping, Any
from dataclasses import asdict, dataclass
from rich.table import Table
from rich.padding import Padding

from .api import NixPackage, NixSource, ZilchProject
from console import console

SOURCE = "nixpkgs"
INDENT = 2

@dataclass
class Context:
    verbose: bool
    path: pathlib.Path
    project: ZilchProject
    source: NixSource

@click.group(no_args_is_help=True)
@click.help_option("--help", "-h")
@click.option('--verbose', default=True, is_flag=True)
@click.option('--source', default="nixpkgs")
@click.option(
    "--path",
    type=pathlib.Path,
    default=None,
    help="path/to/dir containing zilch.toml or path/to/zilch.toml. Defaults to $ZILCH_PATH or $XDG_CONFIG_HOME (or platform equivalent)",
)
@click.pass_context
def cli(ctx: click.Context, verbose: bool, source: str, path: pathlib.Path) -> None:
    project = ZilchProject.from_path(path)
    ctx.obj = Context(
        verbose,
        path,
        project,
        project.sources[source] if source is not None else None
    )
    if ctx.obj.verbose:
        print("Using zilch.toml from", ctx.obj.path)

@cli.command(no_args_is_help=True)  # @cli, not @click!
@click.help_option("--help", "-h")
@click.argument('terms', nargs=-1)
@click.pass_obj
def search(ctx: Context, terms: list[str]) -> None:
    sources = ctx.project.sources.values() if ctx.source is None else [ctx.source]
    for source in sources:
        console.rule(f"[yellow]{source.alias}")
        o = subprocess.run(
            ['nix', 'search', source.url, *terms, '--json'],
            capture_output=True,
            check=True
        )
        for k, v in json.loads(o.stdout).items():
            p = NixPackage(k, source, v['version'], v['description'])
            console.print(f"[green]{p.name}[/green] ({p.version})")
            if p.description != '':
                console.print(Padding.indent(f"{p.description}", INDENT))
            console.print('')


@cli.command(no_args_is_help=True)  # @cli, not @click!
@click.help_option("--help", "-h")
@click.argument('term')
@click.option(
    "--any-source/--match-source",
    default=True,
    help=(
        "Whether to remove every package of this name regardless of source,"
        " or only those with a matching source"
    ),
)
@click.pass_obj
def info(ctx: Context, term: str, any_source: bool) -> None:
    for p in ctx.project.packages:
        if p.name == term and (p.source is None or any_source or p.source == ctx.source):
            console.print(f"[green]{p.name}[/green]")
            t = Table(show_lines=False, show_header=False, box=None, pad_edge=False)
            t.add_column()
            t.add_column()
            t.add_row('description:', p.description)
            t.add_row('version:', p.version)
            t.add_row('attribute:', p.attribute)
            t.add_row('source:', p.source.alias)
            console.print(Padding.indent(t, INDENT))
            break
    else:
        console.print(f'No package [bold]{term}[/bold] is installed')


@cli.command(no_args_is_help=True)  # @cli, not @click!
@click.help_option("--help", "-h")
@click.argument('packages', nargs=-1)
@click.pass_obj
def install(ctx: Context, packages: list[str]) -> None:
    for package in packages:
        ctx.project.add_package(
            NixPackage.from_name(package, ctx.source)
        )
    ctx.project.sync()

@cli.command(no_args_is_help=True)  # @cli, not @click!
@click.help_option("--help", "-h")
@click.pass_obj
def autoremove(ctx: Context) -> None:
    ctx.project.sync()
    ctx.project.autoremove()

@cli.command(no_args_is_help=True)  # @cli, not @click!
@click.help_option("--help", "-h")
@click.option(
    "--any-source/--match-source",
    default=True,
    help=(
        "Whether to remove every package of this name regardless of source,"
        " or only those with a matching source"
    ),
)
@click.argument('packages', nargs=-1)
@click.help_option("--help", "-h")
@click.pass_obj
def uninstall(ctx: Context, any_source: bool, packages: list[str]) -> None:
    for package in packages:
        ctx.project.remove_package(
            NixPackage.from_name(package, ctx.source),
            any_source=any_source,
        )
    ctx.project.sync()

@cli.command(no_args_is_help=True)  # @cli, not @click!
@click.help_option("--help", "-h")
@click.argument('cmd', nargs=-1)
@click.pass_context # need the whole Click context to run ctx.exit(...)
def shell(ctx: click.Context, cmd: list[str]) -> None:
    ctx.obj.project.sync()
    env_vars = ctx.obj.project.get_env_vars()
    proc = subprocess.run(
        cmd,
        env={**os.environ, **env_vars},
        check=False,
    )
    ctx.exit(proc.returncode)

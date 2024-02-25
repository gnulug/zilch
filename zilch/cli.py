import pathlib
import click
import subprocess
import json
import os
import platformdirs
import typing
from dataclasses import asdict
from rich.table import Table
from rich.padding import Padding

from .api import NixPackage, Project
from console import console

SOURCE = "github:NixOS/nixpkgs/nixpkgs-unstable"

@click.group(no_args_is_help=True)
@click.option('--verbose', default=True, is_flag=True)
@click.option('--source', default=SOURCE)
@click.option(
    "--path",
    type=pathlib.Path,
    default=pathlib.Path(os.getenv("ZILCH_PATH", platformdirs.user_config_dir() + "/zilch")),
    help="path/to/dir containing zilch.toml or path/to/zilch.toml. Defaults to $ZILCH_PATH or $XDG_CONFIG_HOME (or platform equivalent)",
)
@click.pass_context
def cli(ctx: click.Context, verbose: bool, source: bool, path: pathlib.Path) -> None:
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["source"] = source
    ctx.obj["path"] = path
    if ctx.obj["verbose"]:
        print("Using zilch.toml from", ctx.obj["path"])

@cli.command(no_args_is_help=True)  # @cli, not @click!
@click.argument('terms', nargs=-1)
@click.pass_context
def search(ctx: click.Context, terms: list[str]) -> None:
    o = subprocess.run(
        ['nix', 'search', ctx.obj["source"], *terms, '--json'],
        capture_output=True,
        check=True
    )
    for k, v in json.loads(o.stdout).items():
        p = NixPackage(k, ctx.obj["source"], None, v['version'], v['description'])
        console.print(f"[green]{p.name}[/green] ({p.version})")
        if p.description != '':
            console.print(f"  {p.description}")
        console.print('')


@cli.command(no_args_is_help=True)  # @cli, not @click!
@click.argument('term')
@click.option('--source', default=SOURCE)
@click.option(
    "--any-source/--match-source",
    default=True,
    help=(
        "Whether to remove every package of this name regardless of source,"
        " or only those with a matching source"
    ),
)
@click.pass_context
def info(ctx: click.Context, term: str, any_source: bool) -> None:
    project = Project.from_path(ctx.obj["path"])
    for p in project.packages:
        if p.name == term and (p.source is None or any_source or p.source == ctx.obj["source"]):
            t = Table(show_lines=False, show_header=False, box=None, pad_edge=False)
            t.add_column()
            t.add_column()
            for k, v in asdict(p).items():
                t.add_row(k + ':', v)
                # console.print(f"  {k}: {v}")
            console.print(f"[green]{p.name}[/green]")
            console.print(Padding(t, (0, 0, 0, 2)))
            break
    else:
        print('Package not found')


@cli.command(no_args_is_help=True)  # @cli, not @click!
@click.argument('packages', nargs=-1)
@click.pass_context
def install(ctx: click.Context, packages: list[str]) -> None:
    project = Project.from_path(ctx.obj["path"])
    new_packages = [
        project.get_latest_compatible(package, ctx.obj["source"])
        for package in packages
    ]
    project.install(new_packages)

@cli.command(no_args_is_help=True)  # @cli, not @click!
@click.pass_context
def autoremove(ctx: click.Context) -> None:
    project = Project.from_path(ctx.obj["path"])
    project.autoremove()

@cli.command(no_args_is_help=True)  # @cli, not @click!
@click.option(
    "--any-source/--match-source",
    default=True,
    help=(
        "Whether to remove every package of this name regardless of source,"
        " or only those with a matching source"
    ),
)
@click.argument('packages', nargs=-1)
@click.pass_context
def remove(ctx: click.Context, any_source: bool, packages: list[str]) -> None:
    project = Project.from_path(ctx.obj["path"])
    new_packages = typing.cast(list[NixPackage], list(filter(
        bool,
        (
            project.get_existing_package(package, ctx.obj["source"], any_source=any_source)
            for package in packages
        ),
    )))
    project.remove(new_packages)

@cli.command(no_args_is_help=True)  # @cli, not @click!
@click.argument('cmd', nargs=-1)
@click.pass_context
def shell(ctx: click.Context, cmd: list[str]) -> None:
    if not cmd:
        cmd = [os.environ.get("SHELL", "/bin/bash")]
    project = Project.from_path(ctx.obj["path"])
    proc = project.shell(cmd, interactive=True)
    ctx.exit(proc.returncode)

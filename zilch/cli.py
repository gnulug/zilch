import pathlib
import click
import subprocess
import json
import os
import platformdirs
import os
from dataclasses import asdict
from typing import Mapping, Any
from rich.table import Table
from rich.padding import Padding

from .api import NixPackage, NixSource, ZilchProject
from console import console

SOURCE = None

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
    ctx.obj["path"] = path
    ctx.obj["project"] = ZilchProject.from_path(path)
    ctx.obj["source"] = ctx.obj["project"].sources[source] if source is not None else None
    if ctx.obj["verbose"]:
        print("Using zilch.toml from", ctx.obj["path"])

@cli.command(no_args_is_help=True)  # @cli, not @click!
@click.argument('terms', nargs=-1)
@click.pass_obj
def search(ctx: Mapping[str, Any], terms: list[str]) -> None:
    sources = ctx["project"].sources if ctx["source"] is None else [ctx["source"]]
    for name, source in sources.items():
        console.rule(f"[yellow]{name}")
        o = subprocess.run(
            ['nix', 'search', source.url, *terms, '--json'],
            capture_output=True,
            check=True
        )
        for k, v in json.loads(o.stdout).items():
            p = NixPackage(k, source, v['version'], v['description'])
            console.print(f"[green]{p.name}[/green] ({p.version})")
            if p.description != '':
                console.print(Padding.indent(f"{p.description}", 2))
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
    for p in ctx.obj["project"].packages:
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
    for package in packages:
        ctx.obj["project"].add_package(
            NixPackage.from_name(package, ctx.obj["source"])
        )
    ctx.obj["project"].sync()

@cli.command(no_args_is_help=True)  # @cli, not @click!
@click.pass_context
def autoremove(ctx: click.Context) -> None:
    ctx.obj["project"].sync()
    ctx.obj["project"].autoremove()

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
    for package in packages:
        ctx.obj["project"].remove_package(
            NixPackage.from_name(package, ctx.obj["source"]),
            any_source=any_source,
        )
    ctx.obj["project"].sync()

@cli.command(no_args_is_help=True)  # @cli, not @click!
@click.argument('cmd', nargs=-1)
@click.pass_context
def shell(ctx: click.Context, cmd: list[str]) -> None:
    if not cmd:
        cmd = [os.environ.get("SHELL", "/bin/bash")]
    ctx.obj["project"].sync()
    env_vars = ctx.obj["project"].get_env_vars()
    os.execvpe(cmd[0], cmd, {**os.environ, **env_vars})

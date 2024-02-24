#!/usr/bin/env python3

import pathlib
import click
import subprocess
import json
from dataclasses import asdict
from rich.table import Table
from rich.padding import Padding

from api import NixPackage, Project
from console import console

SOURCE = "github:NixOS/nixpkgs/nixpkgs-unstable"
SEARCH_CMD = lambda source, terms: ['nix', 'search', source, *terms, '--json']

@click.group(no_args_is_help=True)
@click.option('--debug/--no-debug', default=False)
def cli(debug):
    # click.echo(f"Debug mode is {'on' if debug else 'off'}")
    pass

@cli.command(no_args_is_help=True)  # @cli, not @click!
@click.argument('terms', nargs=-1)
@click.option('--source', default=SOURCE)
def search(terms, source):
    o = subprocess.run(
        SEARCH_CMD(source, terms),
        capture_output=True,
        check=True
    )
    packages = []
    for k, v in json.loads(o.stdout).items():
        p = NixPackage(k, source, None, v['version'], v['description'])
        console.print(f"[green]{p.name}[/green] ({p.version})")
        if p.description != '':
            console.print(f"  {p.description}")
        console.print('')


@cli.command(no_args_is_help=True)  # @cli, not @click!
@click.argument('term')
@click.option('--source', default=SOURCE)
def info(term, source):
    from api import project
    for p in project.packages:
        if p.name == term and (p.source is None or p.source == source):
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
@click.argument("path", type=pathlib.Path)
@click.argument('cmd', nargs=-1)
def shell(path, cmd):
    if not cmd:
        cmd = (os.environ.get("SHELL", "/bin/bash"),)
    project = Project.from_path(path)
    project.develop(*cmd)

if __name__ == "__main__":
    cli()
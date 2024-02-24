#!/usr/bin/env python3

import pathlib
import click
import subprocess
import json
import rich

from zilch import NixPackage, console
from cli import cli

SEARCH_CMD = lambda source, term: ['nix', 'search', source, *term, '--json']

@cli.command(no_args_is_help=True)  # @cli, not @click!
@click.argument('term', nargs=-1)
@click.option('--source', default="nixpkgs")
def search(term, source):
    o = subprocess.run(
        SEARCH_CMD(source, term),
        capture_output=True,
        check=True
    )
    packages = []
    for k, v in json.loads(o.stdout).items():
        p = NixPackage(source, k, None, v['version'], v['description'])
        console.print(f"[green]{p.name}[/green] ({p.version})")
        if p.description is not '':
            console.print(f"  {p.description}")
        console.print('')

@cli.command(no_args_is_help=True)  # @cli, not @click!
@click.argument("path", type=pathlib.Path)
@click.argument('cmd', nargs=-1)
def shell(path, cmd):
    if not cmd:
        cmd = (os.environ.get("SHELL", "/bin/bash"),)
    project = Project.from_path(path)
    project.develop(*cmd)

@click.group(no_args_is_help=True)
@click.option('--debug/--no-debug', default=False)
def cli(debug):
    # click.echo(f"Debug mode is {'on' if debug else 'off'}")
    pass

if __name__ == "__main__":
    cli()
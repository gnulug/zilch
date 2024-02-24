#!/usr/bin/env python3

from __future__ import annotations
import dataclasses
import pathlib
import click
import subprocess
import json
import rich

from zilch import NixPackage, console

SEARCH_CMD = lambda source, term: ['nix', 'search', source, *term, '--json']

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
    packages = []
    for k, v in json.loads(o.stdout).items():
        p = NixPackage(source, v['version'], k, v['description'])
        console.print(f"[green]{p.name}[/green] ({p.version})")
        if p.description is not '':
            console.print(f"  {p.description}")
        console.print('')

if __name__ == "__main__":
    cli()
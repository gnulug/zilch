#!/usr/bin/env python3

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

if __name__ == '__main__':
    cli()
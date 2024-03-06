# How to setup the development environment

## With Nix

All dependencies except for Nix itself and Linux, can be handled by Nix. Make sure you have [Flakes enabled](https://nixos.wiki/wiki/Flakes#Other_Distros.2C_without_Home-Manager).

```
$ nix develop

(shell) $ python --version
Python 3.12.2

(shell) $ zilch

(shell) $ pytest

(shell) $ ruff check --fix .

(shell) $ exit

$ : Nix also supports running a single command
$ nix develop --command ruff check --fix .
```

If one enables direnv, `use flake`, then entering the development environment would be automatic. However, direnv is optional; you will always be able to enter the Nix environment explicitly above.

## Without Nix

Poetry can manage pure-Python dependencies from PyPI, but *you* have to manage: Python, Poetry, Ruff, and Nix.

```
$ : To install the dependencies of the current project (in a venv)
$ poetry install

$ : To run Python command inside the dev environment
$ poetry run python -c 'import tomlkit'

$ poetry run pytest

$ poetry run zilch

$ : So you don't have to write "poetry run" in front of everything
$ poetry shell

(venv) $ python -c 'import tomlkit'

(venv) $ pytest

(venv) $ zilch

(venv) $ exit
```

# How to check your code

Run `./pre-commit.sh` to run some pre-commit checks. Some may install this to run every time you make a `git commit`:

```
$ ln --symbolic ../../pre-commit.sh .git/hooks/pre-commit
```

This script needs to be run from within the environment described above.

`./ci.sh` will run in GitHub CI at some point.

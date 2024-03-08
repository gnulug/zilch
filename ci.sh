#!/usr/bin/env sh
set -ex

ruff check .

mypy --package zilch

mypy tests/*.py

pytest -v

poetry build

nix build

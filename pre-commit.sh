#!/usr/bin/env sh
set -ex

ruff check --fix .
mypy --package zilch
mypy tests/*.py
poetry build

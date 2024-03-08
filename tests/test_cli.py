import subprocess
import os
import pathlib
import pytest
from click.testing import CliRunner
import platformdirs
import zilch.cli

def test_zilch_project_uses_flag() -> None:
   runner = CliRunner()
   with runner.isolated_filesystem() as _tmpdir:
      tmpdir = pathlib.Path(_tmpdir)
      (tmpdir / "zilch.toml").write_text("")
      runner.invoke(
         zilch.cli.cli,
         ["--path", "option_zilch.toml", "shell", "true"],
         catch_exceptions=False,
         env={
            "ZILCH_PATH": str(tmpdir / "env_zilch.toml"),
         },
      )
      assert (pathlib.Path(tmpdir) / "option_zilch.toml").exists(), (
         "Zilch should use/create explicit option before env var and cwd"
      )

def test_zilch_project_uses_env() -> None:
   runner = CliRunner()
   with runner.isolated_filesystem() as _tmpdir:
      tmpdir = pathlib.Path(_tmpdir)
      (tmpdir / "zilch.toml").write_text("")
      runner.invoke(
         zilch.cli.cli,
         ["shell", "true"],
         catch_exceptions=False,
         env={
            "ZILCH_PATH": str(tmpdir / "env_zilch.toml"),
         },
      )
      assert (pathlib.Path(tmpdir) / "env_zilch.toml").exists(), (
         "Zilch should use/create env var before cwd"
      )

def test_zilch_project_uses_cwd() -> None:
   runner = CliRunner()
   with runner.isolated_filesystem() as _tmpdir:
      tmpdir = pathlib.Path(_tmpdir)
      (tmpdir / "zilch.toml").write_text("")
      runner.invoke(
         zilch.cli.cli,
         ["shell", "true"],
         catch_exceptions=False,
      )

@pytest.mark.skipif(
   not bool(int(os.environ.get("CLEAN_VM", "0"))),
   reason="Declining to run tests that modify $HOME because we are not running in CLEAN_VM",
)
def test_zilch_project_uses_global() -> None:
   runner = CliRunner()
   with runner.isolated_filesystem():
      runner.invoke(
         zilch.cli.cli,
         ["shell", "true"],
         catch_exceptions=False,
      )
      p = pathlib.Path(platformdirs.user_config_dir()) / "zilch/zilch.toml"
      assert p.exists(), "Zilch should use/create user-global scope"

def test_search() -> None:
   runner = CliRunner()
   with runner.isolated_filesystem() as _tmpdir:
      tmpdir = pathlib.Path(_tmpdir)
      (tmpdir / "zilch.toml").write_text("")
      runner.invoke(
         zilch.cli.cli,
         ["search", "aria2c"],
         catch_exceptions=False,
      )

package = "hello"
executable = "hello"
which_executable = subprocess.run(["which", executable], check=False, capture_output=True)
@pytest.mark.skipif(
   which_executable.returncode == 0,
   reason=f"You already have {package}, so we can't test its installation/removal. Try choosing a different package/executable",
)
def test_install_remove() -> None:
   runner = CliRunner()
   with runner.isolated_filesystem() as _tmpdir:
      tmpdir = pathlib.Path(_tmpdir)
      (tmpdir / "zilch.toml").write_text("")
      result = runner.invoke(
         zilch.cli.cli,
         ["shell", "which", executable],
         catch_exceptions=False,
      )
      # We can't check the output of `zilch shell which` because that gets written to this process's stdout/stderr.
      # Not the special stdout/stderr fixture created by runner.invoke.
      assert result.exit_code != 0
      runner.invoke(
         zilch.cli.cli,
         ["install", package],
         catch_exceptions=False,
      )
      result = runner.invoke(
         zilch.cli.cli,
         ["shell", "which", executable],
         catch_exceptions=False,
      )
      assert result.exit_code == 0
      runner.invoke(
         zilch.cli.cli,
         ["uninstall", package],
         catch_exceptions=False,
      )
      result = runner.invoke(
         zilch.cli.cli,
         ["shell", "which", executable],
         catch_exceptions=False,
      )
      assert result.exit_code != 0

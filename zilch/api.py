from __future__ import annotations
import tomlkit
import functools
import os
import urllib.parse
import sys
import platformdirs
import dataclasses
import tempfile
import json
import pathlib
import subprocess
import typing
root = pathlib.Path(__file__).parent.parent

def parse_attrpath(path) -> tuple[str, str, str]:
    """Parse attribute path from 'nix search'

    Args:
        path (str): attribute path

    Returns:
        (attr_family, system, name)
    """
    parts = path.split('.')
    return parts[0], parts[1], '.'.join(parts[2:])

@functools.cache
def get_system() -> str:
    """Get the Nix current system/platform"""
    system = subprocess.run(
        ["nix", "eval", "--impure", "--raw", "--expr", "builtins.currentSystem"],
        check=True,
        capture_output=True,
        text=True
    ).stdout.strip()
    return system


@dataclasses.dataclass(frozen=True)
class Project:
    """The data in the project-local store"""
    toml_doc: tomlkit.toml_document.TOMLDocument
    toml_path: pathlib.Path
    resource_path: pathlib.Path
    packages: list[NixPackage]

    @staticmethod
    def from_path(toml_path: pathlib.Path) -> Project:
        """Initializes a Zilch project from a path/to/dir containing zilch.toml or path/to/zilch.toml"""
        if toml_path.is_dir():
            toml_path = toml_path / "zilch.toml"
        toml_path.parent.mkdir(exist_ok=True, parents=True)
        if not toml_path.exists():
            toml_path.write_text("")
        toml_doc = tomlkit.parse(toml_path.read_text())
        resource_path = pathlib.Path(platformdirs.user_data_dir()) / "zilch" / urllib.parse.quote(str(toml_path.parent), safe="")
        if "packages" not in toml_doc:
            toml_doc.append("packages", tomlkit.aot())
        packages = [
            NixPackage(
                f"legacyPackages.{get_system()}.{package['name']}",
                package["source"],
                package["source_version"],
            )
            for package in toml_doc["packages"]
        ]
        toml_doc.setdefault("version", 1)
        proj = Project(toml_doc, toml_path, resource_path, packages)
        return proj

    def write_toml(self) -> None:
        self.toml_path.write_text(tomlkit.dumps(self.toml_doc))

    def get_latest_compatible(self, name: str, source: str) -> NixPackage:
        source_version = next(
            (
                package.source_version
                for package in self.packages
                if package.source == source
            ),
            None,
        )
        if source_version:
            return NixPackage(
                f"legacyPackages.{get_system()}.{name}",
                source,
                source_version,
            )
        else:
            with tempfile.TemporaryDirectory() as _tmpdir:
                tmpdir = pathlib.Path(_tmpdir)
                (tmpdir / "flake.nix").write_text(
                    "{ inputs.test.url = \"SOURCE_URL_HERE\"; outputs = inputs: {}; }"
                    .replace("SOURCE_URL_HERE", source)
                )
                subprocess.run(
                    ["nix", "flake", "lock"],
                    capture_output=True,
                    check=True,
                    cwd=tmpdir,
                )
                source_version = json.loads((tmpdir / "flake.lock").read_text())["nodes"]["test"]["locked"]["rev"]
            return NixPackage(
                f"legacyPackages.{get_system()}.{name}",
                source,
                source_version,
            )

    def install(self, packages: list[NixPackage]) -> None:
        for package in packages:
            if package not in self.packages:
                self.packages.append(package)
                self.toml_doc["packages"].append({
                    "name": package.name,
                    "source": package.source,
                    "source_version": package.source_version,
                })
        self.write_toml()
        self.sync()

    def get_existing_package(self, name: str, source: str, any_source: bool) -> NixPackage | None:
        """Returns the NixPackage for an asssociated attribute, if exists"""
        for package in self.packages:
            if package.name == name and (any_source or package.source == source):
                return package
        else:
            print(f"Could not find package {attribute} {source} {any_source}")
            return None

    def get_nix_path(self, package: NixPackage) -> pathlib.Path:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmproot = pathlib.Path(tmpdir)
            (tmproot / "flake.nix").write_text(self.format_flake())
            source_pairs2name = self.get_source_pairs2name()
            return pathlib.Path(subprocess.run(
                ["nix", "eval", "--raw", f".#{package.name}-{source_pairs2name[package.source_pair]}"],
                cwd=tmproot,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip())

    def is_installed(self, package: NixPackage) -> bool:
        if package in self.packages:
            return self.get_nix_path(package).exists()
        else:
            return False

    def remove(self, packages: list[NixPackage]) -> None:
        any_changes = False
        for package in packages:
            try:
                idx = self.packages.index(package)
            except ValueError:
                print(f"{package} not installed")
            else:
                print(f"Removing {package}")
                del self.packages[idx]
                del self.toml_doc["packages"][idx]
                any_changes = True
        if any_changes:
            self.write_toml()
            self.sync()

    def autoremove(self) -> None:
        subprocess.run(
            ["nix", "store", "gc"],
            check=True,
            capture_output=False,
            # This output can get propagated to the user
        )

    def get_source_pairs2name(self) -> typing.Mapping[tuple[str, str], str]:
        source_pairs = {
            package.source_pair
            for package in self.packages
        }
        # TODO: use better names than source-0, source-1
        return {
            source: f"source-{i}"
            for i, source in enumerate(sorted(source_pairs))
        }

    def format_flake(self) -> str:
        source_pairs2name = self.get_source_pairs2name()
        input_lines = list(set(
            f"{source_pairs2name[package.source_pair]}.url = \"{package.source}\";"
            for package in self.packages
        ))
        package_lines = [
            f"inputs.{source_pairs2name[package.source_pair]}.legacyPackages.${{system}}.{package.name}"
            for package in self.packages
        ]
        name_equals_package_lines = [
            f"{package.name}-{source_pairs2name[package.source_pair]} = inputs.{source_pairs2name[package.source_pair]}.legacyPackages.${{system}}.{package.name};"
            for package in self.packages
        ]
        return (
            (root / "flake.nix.template")
            .read_text()
            .replace("INPUTS_HERE", ("\n" + 4 * " ").join(input_lines))
            .replace("PACKAGES_HERE", ("\n" + 14 * " ").join(package_lines))
            .replace("NAME_EQUALS_PACKAGE_HERE", ("\n" + 10 * " ").join(name_equals_package_lines))
        )

    def sync(self) -> None:
        self.resource_path.mkdir(exist_ok=True, parents=True)
        flake = self.format_flake()
        (self.resource_path / "flake.nix").write_text(flake)
        print("Doing sync")
        proc = subprocess.run(
            ["nix", "build", ".#zilch-env"],
            cwd=self.resource_path,
            check=False,
            capture_output=True,
        )
        if proc.returncode != 0:
            print(flake)
            sys.stdout.buffer.write(proc.stdout)
            sys.stderr.buffer.write(proc.stderr)
            proc.check_returncode()

    def shell(self, cmd: list[str], interactive: bool) -> subprocess.CompletedProcess[bytes]:
        self.sync()
        proc = subprocess.run(
            ["nix", "shell", ".#zilch-env", "--command", "/usr/bin/env", "--chdir", os.getcwd(), *cmd],
            cwd=self.resource_path,
            check=False,
            capture_output=not interactive,
        )
        if not interactive and proc.returncode != 0:
            sys.stdout.buffer.write(proc.stdout)
            sys.stderr.buffer.write(proc.stderr)
            proc.check_returncode()
        return proc


    def env_vars(self) -> typing.Mapping[str, str]:
        script = "import os, json; print(json.dumps(os.environ))"
        inner_env = json.loads(self.shell([sys.executable, "-c", script], interactive=False).stdout)
        outer_env = dict(os.environ)
        return {
            key: value
            for key, value in inner_env.items()
            if outer_env[key] != value
        }
        # Following how direnv gets their shells set up
        # https://github.com/direnv/direnv/blob/4da566cee14dbd8e75f3cd04622e5983c02a0c1c/stdlib.sh#L1274k
        # Unfortunately, that method gets many unrelated environment variables, like TMP and TEMP set to random things
        # profile = tmproot / "profile"
        # profile.mkdir()
        # proc = subprocess.run(
        #     ["nix", "print-dev-env", "--profile", str(profile), "--json", "."],
        #     check=True,
        #     capture_output=True,
        # )
        # _output = json.loads(proc.stdout)
        # return {}


@dataclasses.dataclass(frozen=True)
class NixPackage:
    """A uniquely identified package in a source with a specific commit.

    Note that in Nix lingo, the "source" is really a flake, however we want to hide nix-specific terminology.

    """
    attribute: str
    source: str
    source_version: str | None = None
    version: str | None = None
    description: str | None = None

    @property
    def source_pair(self) -> tuple[str, str]:
        assert self.source_version, "NixPackage.source_pair called for a package that we don't have source_version"
        return (self.source, self.source_version)

    @property
    def family(self) -> str:
        """Attribute family.  e.g legacyPackages"""
        return self.attribute.split('.', 2)[0]

    @property
    def system(self) -> str:
        """Architecture and OS"""
        return self.attribute.split('.', 2)[1]

    @property
    def name(self) -> str:
        """Package name"""
        return self.attribute.split('.', 2)[2]

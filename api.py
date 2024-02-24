from __future__ import annotations
import tomlkit
import functools
import dataclasses
import json
import pathlib
import subprocess
import typing
import tempfile
root = pathlib.Path(__file__).parent

def parse_attrpath(path) -> tuple[str, str, str]:
    """Parse attribute path from 'nix search'

    Args:
        path (str): attribute path

    Returns:
        (attr_family, system, name)
    """
    parts = path.split('.')
    return parts[0], parts[1], '.'.join(parts[2:])

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
    path: pathlib.Path

    @functools.cached_property
    def packages(self) -> list[NixPackage]:
        return [
            NixPackage(f"legacyPackages.{get_system()}." + package['name'], package["source"], package["source_version"])
            for package in self.toml_doc.get("packages", [])
        ]

    def _validate(self) -> None:
        self.packages # validate that packages parsed correctly

    @staticmethod
    def from_path(path: pathlib.Path) -> Project:
        """Initializes a Zilch project from a path/to/dir containing zilch.toml or path/to/zilch.toml"""
        if path.is_dir():
            path = path / "zilch.toml"
        toml_doc = tomlkit.parse(path.read_text())
        proj = Project(toml_doc, path)
        proj._validate()
        return proj

    def get_latest_package(self, attribute_name: str, source: str) -> NixPackage:
        if self.packages:
            raise NotImplementedError()
            # return a package from the latest version of this source.
        else:
            # somehow get the "latest" version of source
            pass
            raise NotImplementedError()

    def format_flake(self) -> str:
        source_pairs = {
            package.source_pair
            for package in self.packages
        }
        # TODO: use better names than source-0, source-1
        source_pairs2name = {
            source: f"source-{i}"
            for i, source in enumerate(sorted(source_pairs))
        }
        input_lines = list(set(
            f"{source_pairs2name[package.source_pair]}.url = \"{package.source}\";"
            for package in self.packages
        ))
        package_lines = [
            f"inputs.{source_pairs2name[package.source_pair]}.legacyPackages.${{system}}.{package.attribute}"
            for package in self.packages
        ]
        return (
            (root / "flake.nix.template")
            .read_text()
            .replace("INPUTS_HERE", ("\n" + 4 * " ").join(input_lines))
            .replace("PACKAGES_HERE", ("\n" + 14 * " ").join(package_lines))
        )

    def develop(self, *cmd: bytes) -> subprocess.CompletedProcess[bytes]:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmproot = pathlib.Path(tmpdir)
            (tmproot / "flake.nix").write_text(self.format_flake())
            return subprocess.run(
                ["nix", "develop", "--command", *cmd],
                check=False,
                capture_output=False,
            )
        # TODO: write package.version into flake.lock somehow

    def env_vars(self) -> typing.Mapping[str, str]:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmproot = pathlib.Path(tmpdir)
            (tmproot / "flake.nix").write_text(self.format_flake())
            # Following how direnv gets their shells set up
            # https://github.com/direnv/direnv/blob/4da566cee14dbd8e75f3cd04622e5983c02a0c1c/stdlib.sh#L1274
            profile = tmproot / "profile"
            profile.mkdir()
            proc = subprocess.run(
                ["nix", "print-dev-env", "--profile", str(profile), "--json", "."],
                check=True,
                capture_output=True,
            )
            output = json.loads(proc.stdout)
            return {}


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
        return (self.source, self.source_version)

    @property
    def flake_ver(self) -> tuple[str, str]:
        return (self.flake, self.version)

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


project = Project(
    path=pathlib.Path("test"),
    toml_doc={'packages':[
        dict(
            source="github:NixOS/nixpkgs/nixpkgs-unstable",
            name="aria",
            source_version="f63ce824cd2f036216eb5f637dfef31e1a03ee89",
        )
    ],
    }
)

if __name__ == "__main__":
    project.develop(b'env')

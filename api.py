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
    path: pathlib.Path

    @functools.cached_property
    def packages(self) -> list[NixPackage]:
        return [
            NixPackage(
                f"legacyPackages.{get_system()}.{package['name']}",
                package["source"],
                package["source_version"],
            )
            for package in self.toml_doc.get("packages", [])
        ]

    def _validate(self) -> None:
        self.packages # validate that packages parsed correctly

    @staticmethod
    def from_path(path: pathlib.Path) -> Project:
        """Initializes a Zilch project from a path/to/dir containing zilch.toml or path/to/zilch.toml"""
        if path.is_dir():
            path = path / "zilch.toml"
        path.parent.mkdir(exist_ok=True, parents=True)
        if not path.exists():
            path.write_text("")
        toml_doc = tomlkit.parse(path.read_text())
        proj = Project(toml_doc, path)
        proj._validate()
        return proj

    def write(self) -> None:
        self.toml_doc.setdefault("version", 1)
        self.path.write_text(tomlkit.dumps(self.toml_doc))

    def get_latest_compatible(self, attribute: str, source: str) -> NixPackage:
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
                f"legacyPackages.{get_system()}.{attribute}",
                source,
                source_version,
            )
        else:
            # with tempfile.TemporaryDirectory(delete=False) as _tmpdir:
            _tmpdir = "/tmp/zilch"
            pathlib.Path(_tmpdir).mkdir(exist_ok=True, parents=True)
            if True:
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
                f"legacyPackages.{get_system()}.{attribute}",
                source,
                source_version,
            )

    def install(self, packages: list[NixPackage]) -> None:
        self.toml_doc.setdefault("packages", []).extend(
            {
                "name": package.name,
                "source": package.source,
                "source_version": package.source_version,
            }
            for package in packages
        )
        self.shell(["true"], False)

    def get_existing_package(self, attribute: str, source: str, any_source: bool) -> NixPackage | None:
        """Returns the NixPackage for an asssociated attribute, if exists"""
        for package in self.toml_doc.get("packages", []):
            if package.attribute == attribute and (any_source or package.source == source):
                return package
        return None

    def get_nix_path(self, packages: list[NixPackage]) -> list[str | None]:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmproot = pathlib.Path(tmpdir)
            (tmproot / "flake.nix").write_text(self.format_flake())
            source_pairs2name = self.get_source_pairs2name()
            ret: list[str | None] = []
            for package in packages:
                # $ nix path-info --derivation .\#nixosConfigurations.pluto.config.system.build.toplevel
                path = subprocess.run(
                    ["nix", "eval", "--raw", f".#{package.attribute}-{source_pairs2name[package.source_pair]}"],
                    cwd=tmproot,
                    # capture_output=True,
                    # text=True,
                    check=True,
                ).stdout
                # ret.append(path)
                ret.append("false")
            return ret

    def remove(self, packages: list[NixPackage]) -> None:
        self.shell(["true"], False)
        for package in packages:
            self.toml_doc.remove(package)
        raise NotImplementedError()
        # TODO: nix gc?

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
            f"inputs.{source_pairs2name[package.source_pair]}.legacyPackages.${{system}}.{package.attribute}"
            for package in self.packages
        ]
        name_equals_package_lines = [
            f"{package.attribute}-{source_pairs2name[package.source_pair]} = inputs.{source_pairs2name[package.source_pair]}.legacyPackages.${{system}}.{package.attribute};"
            for package in self.packages
        ]
        return (
            (root / "flake.nix.template")
            .read_text()
            .replace("INPUTS_HERE", ("\n" + 4 * " ").join(input_lines))
            .replace("PACKAGES_HERE", ("\n" + 14 * " ").join(package_lines))
            .replace("NAME_EQUALS_PACKAGE_HERE", ("\n" + 10 * " ").join(name_equals_package_lines))
        )

    def shell(self, cmd: str, interactive: bool) -> subprocess.CompletedProcess[bytes]:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmproot = pathlib.Path(tmpdir)
            (tmproot / "flake.nix").write_text(self.format_flake())
            return subprocess.run(
                ["nix", "develop", "--command", *cmd],
                cwd=tmproot,
                check=not interactive,
                capture_output=not interactive,
            )
        # TODO: write package.version into flake.lock somehow

    # TODO: there should be a way to build this environment in a consistent locatoin
    # That way Nix's gc won't gc it.

    def env_vars(self) -> typing.Mapping[str, str]:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmproot = pathlib.Path(tmpdir)
            (tmproot / "flake.nix").write_text(self.format_flake())
            # Following how direnv gets their shells set up
            # https://github.com/direnv/direnv/blob/4da566cee14dbd8e75f3cd04622e5983c02a0c1c/stdlib.sh#L1274k
            # 
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

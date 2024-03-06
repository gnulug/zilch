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


TomlAoT = tomlkit.items.AoT


_T = typing.TypeVar("_T")
def expect_type(typ: type[_T], data: typing.Any) -> _T:
    if not isinstance(data, typ):
        raise TypeError(f"Expected type {typ} for {data}")
    return data


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
        ["nix", "eval", "--impure", "--raw", "--expr",
         "builtins.currentSystem"],
        check=True,
        capture_output=True,
        text=True
    ).stdout.strip()
    return system

class ZilchError(Exception):
    pass


class ZilchTomlError(ZilchError):
    pass


DEFAULT_USER_GLOBAL = pathlib.Path(platformdirs.user_config_dir()) / "zilch/zilch.toml"


@dataclasses.dataclass(frozen=True)
class ZilchProject:
    """In-memory representation of the data in the project-local store.

    Note that this class wraps two (2) copies of the data: one in native Python objects; the other in tomlkit.
    *Both* have to be modified simultaneously.
    - The Python representation is necessary for actually operating on the objects.
    - The TOML representation is necessary to support round-tripping (especially TOML comments).
    Another possible design would be to only hold the TOML copy in memory, and write the Python objects as @propery's.
    Whether we switch to that design or not, callers of this class will not care."""
    toml_doc: tomlkit.toml_document.TOMLDocument
    toml_path: pathlib.Path
    version: tuple[int, ...]
    resource_path: pathlib.Path
    sources: dict[str, NixSource]
    packages: list[NixPackage]

    @staticmethod
    def from_path(toml_path: pathlib.Path | None) -> ZilchProject:
        """Initializes a Zilch project from a path/to/zilch.toml or path/to/dir containing zilch.toml"""

        if toml_path is None:
            if "ZILCH_PATH" in os.environ:
                toml_path = pathlib.Path(os.environ["ZILCH_PATH"])
            elif pathlib.Path("zilch.toml").exists():
                toml_path = pathlib.Path("zilch.toml")
            else:
                toml_path = DEFAULT_USER_GLOBAL

        if toml_path.is_dir():
            path = toml_path / "zilch.toml"

        # TODO: nice error handling when toml can't be created
        toml_path.parent.mkdir(exist_ok=True, parents=True)

        # Parse TOML
        if not toml_path.exists():
            toml_path.write_text("")
        toml_doc = tomlkit.parse(toml_path.read_text())

        # Parse version
        version = tuple(map(
            int,
            toml_doc.setdefault("version", "1.0").split(".")
        ))

        # Parse resource path
        default_resource_path = pathlib.Path("/").joinpath(
            platformdirs.user_data_dir(),
            "zilch",
            urllib.parse.quote(str(toml_path.parent), safe=""),
        )
        resource_path = pathlib.Path(toml_doc.get("resource_path", str(default_resource_path)))
        resource_path.mkdir(exist_ok=True, parents=True)

        # Parse and validate sources
        no_sources = "sources" not in toml_doc
        sources_list = [
            NixSource(source["url"], source["alias"], source["rev"])
            for source in toml_doc.setdefault("sources", tomlkit.aot())
        ]
        if len(sources_list) != len(set(map(lambda source: source.alias, sources_list))):
            raise ZilchTomlError(
                "Some sources in the TOML have the same name"
            )
        sources = {
            source.alias: source
            for source in sources_list
        }

        packages: list[NixPackage] = []
        for package in toml_doc.setdefault("packages", tomlkit.aot()):
            if package["source"] not in sources:
                raise ZilchTomlError(
                    f"Package source of {package} is not in sources section"
                )
            packages.append(NixPackage(
                f"legacyPackages.{get_system()}.{package['name']}",
                sources[package["source"]],
            ))

        # Deduplicate packages
        for i in range(len(packages)):
            if i >= len(packages):
                break
            for j in range(i + 1, len(packages)):
                if packages[i] == packages[j]:
                    del packages[j]
                    del expect_type(TomlAoT, toml_doc["packages"])[j]
                    print("Removing duplicate", packages[j])

        project = ZilchProject(
            toml_doc,
            toml_path,
            version,
            resource_path,
            sources,
            packages,
        )
        if no_sources:
            project.add_source(DEFAULT_SOURCE)
        project._validate()
        return project

    # TODO: Use Deal to check this invariant before/after each method.
    # https://deal.readthedocs.io/index.html
    def _validate(self) -> None:
        # Validate packages
        toml_packages = expect_type(TomlAoT, self.toml_doc["packages"])
        assert len(self.packages) == len(toml_packages)
        for package, package_dict in zip(self.packages, toml_packages):
            assert package.name == package_dict["name"]
            assert package.source.alias == package_dict["source"]

        # Validate sources
        toml_sources = expect_type(TomlAoT, self.toml_doc["packages"])
        assert len(self.sources) == len(toml_sources)
        for (alias, source), source_dict in zip(self.sources.items(), toml_sources):
            assert source.url == source_dict["url"]
            assert source.alias == source_dict["alias"] == alias
            assert source.rev == source_dict["rev"]
            assert source.rev is not None

    def _write_toml(self) -> None:
        self._validate()
        self.toml_path.write_text(tomlkit.dumps(self.toml_doc))

    def _write_flake(self) -> None:
        input_lines_with_rev = list(set(
            f"{source.alias}.url = \"{source.url}{'?rev=' + source.rev if source.rev is not None else ''}\";"
            for source in self.sources.values()
        ))
        input_lines = list(set(
            f"{source.alias}.url = \"{source.url}\";"
            for source in self.sources.values()
        ))
        package_lines = [
            f"inputs.{package.source.alias}.legacyPackages.${{system}}.{package.name}"
            for package in self.packages
        ]
        name_equals_package_lines = [
            f"{package.source.alias}-{package.name} = inputs.{package.source.alias}.legacyPackages.${{system}}.{package.name};"
            for package in self.packages
        ]
        # Note: In order to get the flake at the locked rev,
        # We will write the `flake.nix` with rev hardcoded, call `nix flake lock`, and then write the `flake.nix` with no rev hardcoded.
        # This ensures the `flake.lock` has the right rev, but also the rev should not appear in `flake.nix`, so that `nix flake update` will work
        # We could also achieve this by manually writing the final `flake.nix` and writing rev/narHash into the `flake.lock`.
        # However, I don't know how to compute the narHash, so I will do this instead.
        # I also think that flake.lock is technically not part of the "public interface" of flakes, so it might change its format.
        # I don't think Nix developers intend users to set that directly.
        (self.resource_path / "flake.nix").write_text(
            (root / "flake.nix.template")
            .read_text()
            .replace("INPUTS_HERE", ("\n" + 4 * " ").join(input_lines_with_rev)) # NOT input_lines
            .replace("PACKAGES_HERE", ("\n" + 14 * " ").join(package_lines))
            .replace("NAME_EQUALS_PACKAGE_HERE", ("\n" + 10 * " ").join(name_equals_package_lines))
        )
        NixFlake.lock(self.resource_path)
        (self.resource_path / "flake.nix").write_text(
            (root / "flake.nix.template")
            .read_text()
            .replace("INPUTS_HERE", ("\n" + 4 * " ").join(input_lines)) # NOT input_lines_with_rev
            .replace("PACKAGES_HERE", ("\n" + 14 * " ").join(package_lines))
            .replace("NAME_EQUALS_PACKAGE_HERE", ("\n" + 10 * " ").join(name_equals_package_lines))
        )

    def add_source(self, source: NixSource) -> None:
        if source.alias in self.sources:
            raise ZilchError(
                f"Cannot add {source}: "
                "A source with that alias already exists"
            )
        if source.rev is None:
            self.sources[source.alias] = source
            self._write_flake()
            rev = NixFlake.get_rev(self.resource_path, source.alias)
            source.rev = rev
            expect_type(TomlAoT, self.toml_doc["sources"]).append({
                "url": source.url,
                "alias": source.alias,
                "rev": source.rev,
            })
        else:
            self.sources[source.alias] = source
            expect_type(TomlAoT, self.toml_doc["sources"]).append({
                "url": source.url,
                "alias": source.alias,
                "rev": source.rev,
            })

    def remove_source(self, source_alias) -> None:
        if source_alias not in self.sources:
            raise ZilchError(
                f"Cannot remove {source_alias}: "
                "No source with that alias exists"
            )
        del self.sources[source_alias]
        toml_sources = expect_type(TomlAoT, self.toml_doc["sources"])
        for i in range(len(toml_sources)):
            if toml_sources[i]["alias"] == source_alias:
                del toml_sources[i]
                break

    def add_package(self, package: NixPackage) -> None:
        if package.source.alias in self.sources:
            if package.source != self.sources[package.source.alias]:
                raise ZilchError(
                    f"Cannot add {package} from {package.source}: "
                    f"The alias {package.source.alias} already exists"
                )
        else:
            self.add_source(package.source)
        for existing_package in self.packages:
            if existing_package == package:
                raise ZilchError(
                    f"Cannot add {package}: Already installed"
                )
        self.packages.append(package)
        expect_type(TomlAoT, self.toml_doc["packages"]).append({
            "name": package.name,
            "source": package.source.alias,
        })

    def _get_package(self, package: NixPackage, any_source: bool) -> tuple[NixPackage, int]:
        for i, existing_package in enumerate(self.packages):
            if (existing_package.name == package.name
                and (any_source or package.source.alias == existing_package.source.alias)):
                return (package, i)
        raise KeyError()

    def remove_package(self, package: NixPackage, any_source: bool) -> None:
        try:
            _, i = self._get_package(package, any_source)
        except KeyError:
            raise ZilchError(
                f"Cannot remove {package}{' (any source)' if any_source else ''}: "
                f"{package} not added"
            )
        else:
            del self.packages[i]
            del expect_type(TomlAoT, self.toml_doc["packages"])[i]

    def status(self, package: NixPackage, any_source: bool) -> str:
        try:
            package, i = self._get_package(package, any_source)
        except KeyError:
            return "Not added"
        else:
            attr = f"{package.source.alias}-{package.name}"
            if NixFlake.get_store_path(self.resource_path, attr).exists():
                return f"Added from {package.source} & installed"
            else:
                return f"Added from {package.source} but not installed"

    def autoremove(self) -> None:
        subprocess.run(
            ["nix", "store", "gc"],
            check=True,
            capture_output=False,
            # This output can get propagated to the user
        )

    def sync(self) -> None:
        self._write_toml()
        self._write_flake()
        NixFlake.build(self.resource_path, ".#zilch-env")

    def get_env_vars(self) -> typing.Mapping[str, str]:
        return NixFlake.env_vars(self.resource_path, ".#zilch-env")


@dataclasses.dataclass
class NixPackage:
    """A uniquely identified package."""
    attribute: str
    source: NixSource
    version: str | None = None
    description: str | None = None

    @staticmethod
    def from_name(name: str, source: NixSource) -> NixPackage:
        return NixPackage(
            f"legacyPackages.{get_system()}.{name}",
            source,
            None,
        )

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


@dataclasses.dataclass
class NixSource:
    """Nix package source, at a specific revision."""
    url: str
    alias: str
    rev: str | None


class NixFlake:
    """A wrapper around a Nix Flake"""

    @staticmethod
    def env_vars(path: pathlib.Path, pkg: str) -> typing.Mapping[str, str]:
        """Returns the environment variables that turn a shell into a Nix shell"""
        # Direnv uses `nix print-dev-env --profile <profile_path> --json <flake path>`
        # to set their shells set up
        # https://github.com/direnv/direnv/blob/4da566cee14dbd8e75f3cd04622e5983c02a0c1c/stdlib.sh#L1274k
        # Unfortunately, that method gets many unrelated environment variables, like TMP and TEMP set to random things
        # We will simply call env in a subshell
        script = "import os, json; print(json.dumps(dict(os.environ)))"
        inner_env = json.loads(subprocess.run(
            ["nix", "shell", pkg, "--command", sys.executable, "-c", script],
            cwd=str(path),
            check=True,
            text=True,
            capture_output=True,
        ).stdout)
        outer_env = dict(os.environ)
        return {
            key: value
            for key, value in inner_env.items()
            if outer_env[key] != value
        }

    @staticmethod
    def lock(path: pathlib.Path) -> None:
        subprocess.run(
            ["nix", "flake", "lock"],
            cwd=str(path),
            check=True,
            capture_output=True,
        )

    @staticmethod
    def get_rev(path: pathlib.Path, source_alias: str) -> str:
        NixFlake.lock(path)
        return json.loads((path / "flake.lock").read_text())["nodes"][source_alias]["locked"]["rev"]

    @staticmethod
    def get_store_path(path: pathlib.Path, pkg: str) -> pathlib.Path:
        return pathlib.Path(subprocess.run(
            ["nix", "eval", "--raw", "pkg"],
            cwd=str(path),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip())

    @staticmethod
    def build(path: pathlib.Path, pkg: str) -> None:
        subprocess.run(
            ["nix", "build", pkg],
            cwd=str(path),
            capture_output=True,
            check=True,
        )


DEFAULT_SOURCE = NixSource("github:NixOS/nixpkgs", "nixpkgs", None)

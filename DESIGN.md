# Zilch

Nix could be a useful package manager for power users, developers, and administrators, but it is notoriously difficult to learn.
This work provides a CLI wrapper, simplifying the initial part of the learning curve.

_I am open to suggestions for better names._

## Why use Nix package manager?

Nix is a cross-platform package manager that emphasizes reproducibility. Except for a small set of bootstrap sources, every Nix package, including the transitive dependencies of those packages, can be compiled from source. Compiling from source enables portability, ease of patching, reproducibility, and other important qualities. Compiling from source can be slow, but commonly used packages are compiled into a package cache. Most Nix builds are bit-wise reproducible[^bitwise-reproducible], so Nix can transparently "switch" between cached and built-on-your-machine packages. The binary cache is verifiable. This gives Nix the customizability of source-based package mangaers like Portage with the speed of binary package managers like Apt-get.

Features of Nix that a power user would like:

- Works on any Linux distro, MacOS, Windows with WSL2, or others.
- Does not need root
- Has many more packages and is more up-to-date than other package repositories according to [Repology].
- Can roll back or forward any package transaction

Features of Nix that a developer would like:

- Can "reproduce"[^defn-reproducible] the software environment on other machines from a small manifest
- Detects when malicious or compromised package repositories feed a different package than the one seen before
- Can manage project-specific or user-level software environment
- Simplifies using a custom fork or patch for compiled dependencies

Features of Nix that a system administrator would like:

- Can roll back or forward any package transaction
- Reproducible deterministic builds
- Declarative configuration

## Why does Nix need a wrapper?

The difficulty in learning or deploying Nix comes from many sources including:

1. Nix represents a new way of thinking about package management
2. Nix uses a functional, lazy language with idiosyncratic syntax, the Nix language
3. The Nix CLI is unlike other package manager CLI's, such as `apt`, `dnf`, `cargo`, and `pip`

This work aims to provide a wrapper CLI for Nix addressing points two and three. Our CLI is similar to other package managers that the user may already be familiar with. Also, use of our CLI would obviate the need for the user to interact directly with the Nix language for simple operations.

Nix has two "official" CLIs:

- The stable interface consisting of set of binaries named `nix-shell`, `nix-store`, `nix-env`, etc., and
- The experimental interface consisting of a single binary named `nix` with subcommands for `nix shell`, `nix store`, and `nix profile`

The stable interface uses hard-to-remember shortcuts. For example, [search.nixos.org] suggests installing firefox with `nix-env -iA nixpkgs.firefox`. The flag `-i` stands for "install", but `-A` stands for "attr". What exactly does that mean? Why must we write `nixpkgs.` before `firefox`?

How does one search for packages from the command-line? `nix-env -qaP firefox`. Why is this a `nix-env ...` command? Does it manipulate the environment?

The experimental interface is somewhat better. It uses `nix profile install nixpkgs#firefox` or `nix search nixpkgs firefox`, at the cost of not being enabled by default. However, it shares these same problems with the stable interface:
- It is still too verbose.
- It is _imperative_ rather than _declarative_; the result is not easily sharable with others[^manifest].
- It has so many subcommands it is hard to get an overview of which subcommands are most relevant (see [nix cli docs]).

## How to make a better wrapper

- Look like Cargo. Cargo is the package manager for Rust. Operations have simple and predictable translation into Cargo commands and vice versa. The interface for most users is `cargo add $package` and `cargo remove $package`. All of these commands modify a spec-file (`Cargo.toml`) and a lock-file (`Cargo.lock`).
- Prevent users from needing to use the Nix expression language and Nix CLI.
  - There is an inherent tradeoff between simplicity and power; a table saw requires more knowledge to use than a hand saw. zilch is a simpler/less-powerful balance-point than the original Nix CLI. Even when Nix is hidden behind a simple interface, the virtues of its design should still yield a more powerful package manager than a system-level package manager. _All_ of the points raised in "Why use Nix?" should still be achievable. It gives users an "advance" on some of the features of Nix without requiring "upfront payment" learning Nix.
  - However, zilch _does not preclude_ using the underlying Nix CLI or writing custom Nix expressions. There is still a single source of truth, but it can be manipulated by either automated tools, the underlying Nix CLI, or by hand. Perhaps even advanced Nix users will use zilch because it automates the editing they would do by hand in common cases. This is also an escape-hatch for limitations of zilch, allowing zilch to focus on simple but common cases.

<!-- Learning curve figure, shows time invested on the X and features on the Y. Nix is useless unless you invest a lot of time, then you get a pretty powerful set of features that grow linearly as you invest more time. zilch provides a point where you invest very little time, but you still get some features. zilch smoothly transitions to Nix's curve itself. Using zilch does not preclude the user from also using underlying Nix. -->

## The design

### Files:

- `$NIX_HELPER_PATH` is a directory containing the following files. If unset, it defaults to `$XDG_CONFIG_HOME/zilch`, which is under Git control.
- `flake.nix` contains Nix expressions that read from `packages.toml` (generated by zilch). The user may edit this as they please so long as they don't touch the expression which reads from `packages.toml` (unless of course, they know what they're doing).
- `flake.lock` is a lockfile for the remote inputs of `flake.nix` (generated by Nix).
- `packages.toml` is a TOML description of packages and versions the user wants installed. [Devshell.toml] takes a similar approach.
- `$NIX_HELPER_CONFIG_FILE` is a configuration file for `$NIX_HELPER`, defaulting to `$XDG_CONFIG_HOME/zilch/settings.toml`.

### Commands

#### Install/Add

```
zilch install firefox
zilch install firefox==1.2.3
zilch install firefox --source=flakehub
# folder containing flake.nix
zilch install path/to/firefox
# FIXME
zilch install firefox==1.2.3 --source=flakehub --system=arm7
```

```
# Here be Issues
> zilch install passhole
fail
> zilch install python311Packages.passhole
> passhole -h
Python not found
> zilch install python311

```


- `zilch add $package`: Adds `$package` to `packages.toml`.
  - `$package` and variants will be searched in Nixpkgs and possibly others such as NUR, [Nix Flake search], or [flakehub]. User can specify `$package=$version`, and the tool will attempt a strategy similar to [the search tool on Marcelo Lazaroni's website][lazamar].
  - If `$package` is part of a package set the zilch will "do the commonly expected thing", e.g., if the package request was Python's `requests`, zilch will add it to the Python package's environment.
  - zilch will give a preview of the changes (list of packages/versions to be installed) and confirm with the user, like `apt`.
  - If the user set up shell integration, this command will modify the _current_ shell environment, which is a departure from the original Nix CLI, but more similar to `apt` and `cargo`. Otherwise, the tool may start a new shell or exec a new shell with the package in the environment. zilch will work with [direnv]'s auto updating.
  
#### Search

Search available packages

```
zilch search firefox
zilch search firefox --source=flakehub
# should also say whether a package is installed
```

- `zilch search $package`: Searches names and titles for `$package` over all repositories available to `zilch add`.

```
shadowfox (2.2.0)
  Universal dark theme for Firefox while adhering to the modern design principles set by Mozilla
  Installed: (2.1.0) from flakehub
  Installed: (2.0.0) from https://..../foo/bar
```

#### List

List installed packages

```
zilch list
zilch list --all
# list installed packages
```

#### Remove/Uninstall

```
zilch remove firefox
zilch remove firefox==1.2.3
zilch remove firefox==1.2.3 --source=flakehub
# packages.toml needs to store the source
```

- `zilch remove $package`: Removes `package` from `packages.toml`. However, this will not run garbage collection unless a flag is passed. Like `zilch add`, this command will preview the changes, prompt for acceptance, and modify the current shell.

#### Upgrade and Update

```
zilch upgrade
zilch upgrade firefox
  - same as (zilch update, zilch install firefox)
zilch upgrade firefox --source=flakehub
```
- `zilch upgrade`: Tries to upgrade all packages (without changing which repo the package comes from). Like `zilch add`, this command will preview the changes, prompt for acceptance, and modify the current shell.

#### History

Install/Uninstall history

```
zilch history
```

- optional rollback?

#### Modify

```
zilch modify firefox
zilch modify firefox==1.2.3
zilch modify firefox==1.2.3 --source=flakehub
```

- `zilch modify $package`: Downloads the source code and build recipe for a package, and lets the user modify it. They may later use `zilch add $path_to_modified_package`. The modified package may be distributed in whole or by patch in the current repository or a new repository, or it may not be distributed at all, but in that case, `zil` would warn the user that their system is irreproducible.

#### Info

Print information about a specific installed package
Maybe support uninstalled packages in the future

```
zilch info firefox
zilch info firefox --source=flakehub
```

#### Activate/Shell

Activate a zilch environment.  Mutate current environment

```
zilch activate path/to/dir
zilch activate path/to/dir/zilch.toml
```

Start a new shell or program in a zilch environment.

```
zilch shell path/to/dir
zilch exec path/to/dir/zilch.toml PROGRAM
```

#### Others

- `zilch run $package`: Similar semantics as `zilch add`, but just runs a command or a shell without modifying `packages.toml`.
- `zilch reload`: Re-evaluate `flake.nix` in light of changes to it or `packages.toml`. Like `zilch add`, this command will preview the changes, prompt for acceptance, and modify the current shell.
- `zilch run $package`: Similar semantics as `zilch add`, but just runs a command or a shell without modifying `packages.toml`.
- `zilch modify $package`: Downloads the source code and build recipe for a package, and lets the user modify it. They may later use `zilch add $path_to_modified_package`. The modified package may be distributed in whole or by patch in the current repository or a new repository, or it may not be distributed at all, but in that case, `zilch` would warn the user that their system is irreproducible.

Rather than implement history and rollback directly in the CLI, as the official Nix CLI does, `flake.{nix,lock}` and `packages.toml` can be tracked in Git, and redeployed from that.

## Acknowledgements

- [Evan Widlosky](http://evan.widloski.com/) suggested this idea. Evan also revised the CLI interface design.
- [Nathan Somers](https://en.wikipedia.org/wiki/User:Pngdeity) gave copy-editing and valuable discussion involving the motivation and value of Zilch.
- [J.T. Parrish](https://github.com/jtparrish) suggested a clarification on when Nix builds from source.

[^defn-reproducible]: Acording to the [ACM][ACM-repr], reproducibility means the ability for _another_ user/system to get the _same_ result. "Sameness" can be evaluated at many different levels; Nix can guarantee that the initial source codes fed into the build toolchain are identical. Nix disables certain features, like datestamping, that are known to create non-reproducible builds. Often "same source" + "disabling known non-reproducible features" is enough to get a bitwise identical output from the build toolchain, but not always.

[^bitwise-reproducible]: In some package sets tested by [R13Y], more than 95% of the package builds compiled with Nix are bitwise identical.

[^manifest]: `nix-env` and `nix profile` do manipulate `manifest.nix` or `manifest.json`, respectively. However, this is hidden from the user, and there is no documentation on how to share these between machines or users. They are also global-scope, not amenable to usage with direnvs.

# Futher reading

## Imperative vs declarative management

- <https://jade.fyi/blog/flakes-arent-real/>
- <https://stop-using-nix-env.privatevoid.net/>
- <https://discourse.nixos.org/t/transitioning-from-imperative-to-declarative-package-management-with-nix-alone/28728>

## Suitability of Flakes

- <https://jade.fyi/blog/flakes-arent-real/>
- <https://nix.dev/concepts/flakes.html#why-are-flakes-controversial>
- <https://samuel.dionne-riel.com/blog/2023/09/06/flakes-is-an-experiment-that-did-too-much-at-once.html>
- <https://determinate.systems/posts/experimental-does-not-mean-unstable/>

## Getting old versions

- <https://github.com/NixOS/nixpkgs/issues/9682>
  - <https://github.com/NixOS/nixpkgs/issues/9682#issuecomment-658424656>
  - <https://github.com/NixOS/nixpkgs/issues/9682#issuecomment-658429316>
- <https://www.haskellforall.com/2022/05/the-golden-rule-of-software.html>
- <https://github.com/NixOS/nixpkgs/issues/93327>
  - <https://github.com/NixOS/nixpkgs/issues/93327#issuecomment-661986395>
- <https://matthewbauer.us/blog/all-the-versions.html>
- <https://lazamar.github.io/download-specific-package-version-with-nix/>
- <https://history.nix-packages.com/>
- Also consider just changing the source version (not getting an older rev of "flake source")
- <https://news.ycombinator.com/item?id=28593823>
- <https://www.nixhub.io/>

## Similar tools

- <https://www.jetpack.io/devbox/>
- <https://github.com/lf-/flakey-profile>
- <https://numtide.github.io/devshell/getting_started.html>
- <https://devenv.sh/>
- <https://github.com/nmattia/niv>
- <https://flox.dev/>

### Similar Non-Nix tools

- <https://zap.srev.in/>

## Package mangaer CLI UX

- <https://github.com/srevinsaju/zap/issues/66>
- <https://github.com/NixOS/nix/issues/7966>

## Nix flake sources

- <https://flakehub.com/>
- <https://search.nixos.org/flakes

[Repology]: https://repology.org/repositories/graphs
[ACM-repr]: https://www.acm.org/publications/policies/artifact-review-and-badging-current
[R13Y]: https://r13y.com/
[forum-discussion]: https://news.ycombinator.com/item?id=30384121
[search.nixos.org]: https://search.nixos.org/packages?channel=23.11&show=firefox&from=0&size=50&sort=relevance&type=packages&query=firefox
[nix cli docs]: https://nixos.org/manual/nix/unstable/command-ref/experimental-commands
[devshell.toml]: https://numtide.github.io/devshell/intro.html
[flakehub]: https://determinate.systems/posts/introducing-flakehub
[Nix Flake search]: https://search.nixos.org/flakes?
[lazamar]: https://lazamar.co.uk/nix-versions/
[direnv]: https://direnv.net/

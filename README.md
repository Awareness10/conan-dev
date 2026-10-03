# conan-dev

A sandbox for developing and testing [conan_config](../conan_config): its hooks,
custom commands, profiles and recipes. Each demo exercises one part of that
config against real Conan runs.

## Setup

```bash
uv sync    # .venv with Conan (>= 2.33.0, see pyproject.toml)
```

The demos expect the conan_config working copy next to this repo
(`../conan_config`), so you test your uncommitted changes. Use `--config <path>`
to point them somewhere else.

**Your own Conan home is never touched:**

- Scripted demos (`run.py`) use an isolated `CONAN_HOME` in `~/.cache/<demo>`.
- They set `CONAN_CONFIG_SYNC_SKIP=1`, so the config's auto-sync doesn't replace the
  working copy with the remote `main`.
- They install the working copy with `conan config install`, and delete the work
  folder afterwards unless you pass `--keep`.

## Layout

| Path | What it is |
|------|------------|
| `demo/` | fmt packaged from a tarball, zip or git clone: source download and extraction progress |
| `large-demo/` | Extracts a generated ~640 MiB bzip2 tarball: a long extraction progress bar |
| `parallel-demo/` | Parallel uploads and downloads against a local, rate-limited server |
| `libdatachannel-demo/` | A full from-source build of libdatachannel and its dependencies, then upload and removal |
| `win64-cross-demo/` | Cross-compiles a Windows program on Linux with the `windows-x64-clangcl` profile and runs its test under wine |
| `win64-game-demo/` | Breakout with raylib, cross-built into a standalone Windows `.exe` |
| `demo_remote.py` | Shared helpers for the scripted demos: an isolated Conan home and the local demo remote |

## The demos

### `demo/`: fmt from tarball, zip or git

A recipe that packages fmt 11.1.4. It exercises the progress hook for downloads,
archive extraction and `git clone`, plus the step-timing hook. Run it with your
normal Conan home:

```bash
conan create demo                       # tarball (default)
DEMO_SOURCE=zip conan create demo
DEMO_SOURCE=git conan create demo
```

Sources are cached per recipe revision. Run `conan remove "demo/*" -c` before
switching `DEMO_SOURCE`. `demo/test_package` builds a small fmt program.

### `large-demo/`: long extraction

`source()` unpacks a ~640 MiB bzip2 tarball of text, which takes about 12 s, long
enough to watch the extraction bar. The archive is generated once (~30 s) into
`~/.cache/conan-large-demo/` and reused.

```bash
conan create large-demo
conan remove "large-demo/*" -c          # to watch the extraction again
LARGE_DEMO_MIB=200 conan create large-demo
```

### `parallel-demo/`: parallel transfers

Starts the demo remote (see [`demo_remote.py`](#demo_remotepy)). It then creates
packages of random, incompressible bytes, uploads them in parallel, deletes them
locally and installs them again. You see compression, upload, download and
unpacking bars. The parallelism comes from conan_config's `global.conf`
(`core.upload:parallel`, `core.download:parallel`).

```bash
uv run parallel-demo/run.py                          # 1 x 3500 MiB + 7 x 400 MiB, ~20 GB of disk
uv run parallel-demo/run.py --big-mib 1000 --mib 100 # quicker
uv run parallel-demo/run-3.12.7.py                   # same, with Conan on Python 3.12.7
```

`run-3.12.7.py` runs the same script in a throwaway `uv` environment, with the
project's Conan version on Python 3.12.7. That exercises the pre-3.14 archive
path: Python before 3.14 can't write `.tzst`. Try `CONAN_PROGRESS_THEME=btop`, a
small terminal, or `| cat` for CI-style output.

### `libdatachannel-demo/`: everything in one run

Every conan_config hook in one realistic run:

1. **Empty cache:** removes everything, so nothing is reused.
2. **Build:** `conan install --requires=libdatachannel/0.24.0 --build=missing` builds
   openssl, zlib, usrsctp, libsrtp, libjuice and libdatachannel from source, with
   cmake as a `tool_requires`.
3. **Upload:** uploads everything to the demo remote.
4. **Clean up:** lists the packages on the remote, removes them, and lists again.

```bash
uv run libdatachannel-demo/run.py
uv run libdatachannel-demo/run.py --rate 20   # faster uploads (MB/s per connection)
```

### `win64-cross-demo/`: Windows cross-compiling

Tests conan_config's `windows-x64-clangcl` profile, where Conan provides every
tool. It builds Windows x64 programs (MSVC ABI) on Linux with clang-cl and runs
their tests under wine.

```bash
uv run win64-cross-demo/run.py --accept-msvc-license
uv run win64-cross-demo/run.py --accept-msvc-license --keep   # keep the Conan home
```

What it does:

1. Installs conan_config. The first conan command adds its `index/` recipes as the
   `conan_config` remote; `conan recipes:index` shows them.
2. Runs `conan build win64-cross-demo -pr:h windows-x64-clangcl --build=missing --update`:
   - builds the tool packages from conan_config's recipes:

     | Package | Contents |
     |---------|----------|
     | `llvm` | official LLVM 23.1.2 release, with ICU 70 bundled |
     | `msvc-sysroot` | MSVC CRT 14.44 + Windows SDK 10.0.26100, unpacked by `xwin` |
     | `clang-cl-cross` | the CMake toolchain |
     | `wine` | 11.18 |

     `cmake` and `ninja` come from ConanCenter.
   - cross-builds fmt and zlib from ConanCenter with clang-cl
   - builds `hello.exe`; `ctest` runs its self-test through wine
     (`CMAKE_CROSSCOMPILING_EMULATOR`)
3. Runs `hello.exe` with `conan wine:run`. It prints the Windows version wine reports,
   the clang-cl version and the MSVC ABI version (1944).

Notes:

- **Microsoft license:** `--accept-msvc-license` is required. The `msvc-sysroot`
  package downloads the Microsoft CRT and Windows SDK, which are covered by
  [Microsoft's license](https://go.microsoft.com/fwlink/?LinkId=2086102); the flag
  passes `-c:a user.msvc_sysroot:accept_license=True`.
- **Downloads:** the first run downloads about 3 GB (CRT/SDK 1.7 GB, LLVM 1.1 GB,
  wine 100 MB), cached in `~/.cache/conan-win64-cross-demo-downloads`. Later runs
  reuse them even without `--keep`: about 30 s plus the ICU build. Delete that
  folder to reclaim the space.
- **`--update`** makes Conan re-export the conan_config recipes, so edits to
  `../conan_config/index` are picked up even with `--keep`.
- **The demo's own recipe** shows the one thing a consumer has to do differently:
  `cmake.test(env="conanbuild")`. The default `cmake.test()` tries to combine the
  Linux build environment (`.sh`) with the Windows run environment (`.bat`), and
  Conan refuses.

See conan_config's README ("Cross-compiling for Windows") for the profile, the
recipes and where each download comes from.

### `win64-game-demo/`: a Windows game

Breakout written in C with [raylib](https://www.raylib.com) 6.0 from ConanCenter,
cross-built with the same profile. It has particles, screen shake, score and lives.

- **Move:** arrow keys, A/D, or the mouse.
- **Launch:** Space or click.
- **Restart:** R. **Quit:** Esc.

Run it with your normal Conan home:

```bash
cd win64-game-demo
conan build . -pr:h windows-x64-clangcl -s:h compiler.runtime=static --build=missing \
    -c:a user.msvc_sysroot:accept_license=True
conan wine:run --wayland build/Release/breakout.exe   # play it on Linux
```

**A standalone `.exe`:**

- `compiler.runtime=static` puts the C runtime into the `.exe`, so it imports
  only DLLs that ship with Windows (`KERNEL32`, `USER32`, `GDI32`, `SHELL32`,
  `WINMM`). No Visual C++ redistributable is needed; copy `breakout.exe` (~680 KB)
  to any Windows 10/11 machine.
- It's linked as a GUI program, so it opens no console window.

**Why `--wayland`:** under XWayland on Hyprland, the window opened off-screen,
because XWayland and Hyprland disagreed on the monitor order. `--wayland` makes
wine use its native Wayland driver, so the compositor places the window. See
conan_config's README (`conan wine:run`).

## `demo_remote.py`

Shared by `parallel-demo` and `libdatachannel-demo`; `win64-cross-demo` uses only
its `Conan` class. It depends on the standard library only, so it also works under
`run-3.12.7.py`.

- **`Conan`** runs `conan` with `CONAN_HOME=<work>/home` and the config auto-sync
  turned off. It uses this venv's `conan` when there is one.
- **`demo_remote()`** starts a local `conan_server`, in a throwaway
  `uv run --with conan-server` environment, behind a proxy that limits each
  connection to `--rate` MB/s, so transfers last long enough to watch. The server
  uses a multi-threaded WSGI server, so parallel transfers really run in parallel.
  - ports: `--port` (default 9300) and `--port + 1` for the proxy
  - login: `demo` / `demo`, remote name: `demo`
- **`add_arguments()`** adds the options the scripted demos share: `--rate`,
  `--port`, `--config`, `--work` and `--keep`.

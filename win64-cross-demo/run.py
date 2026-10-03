"""Cross-compile a Windows program on Linux with the conan_config
windows-x64-clangcl profile, where Conan provides every tool, and run its tests
under wine.

    uv run win64-cross-demo/run.py --accept-msvc-license
    uv run win64-cross-demo/run.py --accept-msvc-license --keep   # keep the Conan home

In ~/.cache/conan-win64-cross-demo (an isolated CONAN_HOME, your own is not
touched), with the conan_config working copy (--config, default ../conan_config):

1. `conan config install`: profiles, extensions and the recipes in index/;
   the first conan command adds them as the "conan_config" remote
2. `conan build win64-cross-demo -pr:h windows-x64-clangcl --build=missing`:
   - builds the tool packages from the conan_config recipes: xwin, msvc-sysroot
     (MSVC CRT + Windows SDK), llvm-mingw (clang-cl, lld-link), clang-cl-cross
     (the CMake toolchain) and wine; cmake and ninja come from ConanCenter
   - cross-builds fmt and zlib from ConanCenter for Windows with clang-cl
   - builds hello.exe, and ctest runs its self-test through wine
3. runs hello.exe under wine (`conan-wine` from the wine package)

Downloads (~2 GB the first time: the Microsoft CRT/SDK is ~1.7 GB, LLVM 80 MB,
wine 100 MB) are cached in ~/.cache/conan-win64-cross-demo-downloads and reused by
later runs, even without --keep. --accept-msvc-license is required because the
msvc-sysroot package downloads the Microsoft CRT and Windows SDK:
https://go.microsoft.com/fwlink/?LinkId=2086102
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from demo_remote import Conan


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--accept-msvc-license",
        action="store_true",
        help="accept the Microsoft CRT/SDK license (required)",
    )
    parser.add_argument("--config", default=str(HERE.parent.parent / "conan_config"))
    parser.add_argument(
        "--work", default=str(Path.home() / ".cache" / "conan-win64-cross-demo")
    )
    parser.add_argument(
        "--downloads",
        default=str(Path.home() / ".cache" / "conan-win64-cross-demo-downloads"),
    )
    parser.add_argument("--keep", action="store_true", help="keep the work folder")
    args = parser.parse_args()
    if not args.accept_msvc_license:
        parser.error(
            "pass --accept-msvc-license to accept the Microsoft CRT/SDK license: "
            "https://go.microsoft.com/fwlink/?LinkId=2086102"
        )

    work = Path(args.work)
    downloads = Path(args.downloads)
    work.mkdir(parents=True, exist_ok=True)
    (downloads / "xwin").mkdir(parents=True, exist_ok=True)
    conan = Conan(work)
    print(conan.version())
    try:
        print(f"Installing {args.config} into {conan.home}", flush=True)
        conan("config", "install", args.config)
        # core.* confs are only read from global.conf
        conf = conan.home / "global.conf"
        lines = [
            l
            for l in conf.read_text().splitlines()
            if not l.startswith("core.sources:download_cache")
        ]
        lines.append(f"core.sources:download_cache={downloads / 'sources'}")
        conf.write_text("\n".join(lines) + "\n")
        conan(
            "remote", "list", show=True
        )  # "conan_config" is added on the next command
        conan("recipes:index", show=True)

        output = work / "build"
        conan(
            "build",
            str(HERE),
            "-pr:h=windows-x64-clangcl",
            "--build=missing",
            "--update",  # pick up edits to the conan_config recipes (with --keep)
            "-of",
            str(output),
            "-c:a",
            "user.msvc_sysroot:accept_license=True",
            "-c:a",
            f"user.msvc_sysroot:cache_dir={downloads / 'xwin'}",
            show=True,
        )

        exe = next(output.rglob("hello.exe"))
        wine = next(conan.home.rglob("bin/conan-wine"))  # from the wine package
        print(f"\n$ conan-wine {exe.relative_to(work)}", flush=True)
        subprocess.run([str(wine), str(exe)], check=True)
    finally:
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()

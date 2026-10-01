"""Parallel uploads and downloads against the demo remote, to watch the progress hook.

    uv run parallel-demo/run.py                 # 1 x 3500 MiB + 7 x 400 MiB packages
    uv run parallel-demo/run.py --big-mib 1000 --mib 100   # quicker
    uv run parallel-demo/run.py --keep          # keep the ~20 GB work folder

What it does, in ~/.cache/conan-parallel-demo (an isolated CONAN_HOME, your own is
not touched):

1. starts the demo remote (../demo_remote.py): conan_server behind a proxy that
   limits every connection to --rate MB/s, so transfers take long enough to watch
2. installs the conan_config working copy (--config, default ../conan_config),
   so core.upload:parallel / core.download:parallel come from its global.conf
3. creates --count packages blob0..blobN of random bytes (blob0 is --big-mib)
4. `conan upload`: compression + upload bars, in parallel
5. removes them from the cache, then `conan install`: download + unpack bars

Steps 4 and 5 run in your terminal, so you see the live output. Try
CONAN_PROGRESS_THEME=btop, a small terminal, or `| cat` for CI-style output.
"""

import argparse
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from demo_remote import REMOTE, Conan, add_arguments, demo_remote


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--count", type=int, default=8, help="packages (default 8)")
    parser.add_argument("--big-mib", type=int, default=3500, help="blob0 size")
    parser.add_argument("--mib", type=int, default=400, help="size of the others")
    add_arguments(parser, work="conan-parallel-demo", rate=100)
    args = parser.parse_args()

    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    conan = Conan(work)
    names = [f"blob{i}" for i in range(args.count)]
    print(conan.version())
    try:
        with demo_remote(work, args.port, args.rate) as url:
            conan.setup(args.config, url)
            conan("config", "show", "core.*:parallel", show=True, check=False)
            conan("remove", "blob*", "-c")
            conan("remove", "blob*", "-r", REMOTE, "-c")

            for i, name in enumerate(names):
                mib = args.big_mib if i == 0 else args.mib
                print(f"Creating {name}/0.1 ({mib} MiB)", flush=True)
                conan.env["PARALLEL_DEMO_MIB"] = str(mib)
                conan("create", str(HERE), "--name", name)

            conan("upload", "blob*", "-r", REMOTE, "-c", show=True)
            conan("remove", "blob*", "-c")
            requires = [f"--requires={name}/0.1" for name in names]
            output = str(work / "install")
            conan("install", *requires, "-r", REMOTE, "-of", output, show=True)
    finally:
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()

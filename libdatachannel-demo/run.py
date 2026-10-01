"""libdatachannel and its dependencies built from source, uploaded to the demo
remote and deleted from it again: every step of the conan_config hooks in one run.

    uv run libdatachannel-demo/run.py
    uv run libdatachannel-demo/run.py --keep    # keep the Conan home and remote data
    uv run libdatachannel-demo/run.py --rate 20 # faster uploads (MB/s per connection)

In ~/.cache/conan-libdatachannel-demo (an isolated CONAN_HOME, your own is not
touched), with the conan_config working copy (--config, default ../conan_config):

1. `conan remove "*"` and `conan cache clean`: an empty cache, so nothing is reused
2. `conan install --requires=libdatachannel/... --build=missing -r conancenter`,
   with the default profile plus cmake as a tool_requires (no system cmake needed):
   recipe and source downloads, source extraction, cmake download and unpacking,
   colored Ninja builds of openssl, zlib, usrsctp, libsrtp, libjuice and
   libdatachannel, and the step times summary (ConanCenter has no binaries for
   this toolchain, so they're built)
3. `conan upload "*" -r demo`: compression and upload bars, in parallel
4. `conan list "*" -r demo`, `conan remove "*" -r demo`, `conan list` again:
   the packages on the demo remote (../demo_remote.py), then gone

The demo remote's default rate is low (--rate 5) so the uploads of these
few-MB packages take long enough to watch.
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
    parser.add_argument("--version", default="0.24.0", help="libdatachannel version")
    add_arguments(parser, work="conan-libdatachannel-demo", rate=5)
    args = parser.parse_args()

    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    conan = Conan(work)
    print(conan.version())
    try:
        with demo_remote(work, args.port, args.rate) as url:
            conan.setup(args.config, url)

            conan("remove", "*", "-c", show=True)
            conan("cache", "clean", "*", show=True)

            # libjuice and others run cmake from PATH; give every package Conan's
            profile = work / "cmake.profile"
            profile.write_text("[tool_requires]\n!cmake/*: cmake/[>=3.27 <4]\n")
            default = conan.output("config", "show", "core:default_profile")
            default = default.partition(": ")[2] or "default"
            conan(
                "install",
                f"--requires=libdatachannel/{args.version}",
                "--build=missing",
                "-r",
                "conancenter",
                f"-pr:h={default}",
                f"-pr:h={profile}",
                "-of",
                str(work / "install"),
                show=True,
            )

            conan("upload", "*", "-r", REMOTE, "-c", show=True)
            conan("list", "*", "-r", REMOTE, show=True)
            conan("remove", "*", "-r", REMOTE, "-c", show=True)
            conan("list", "*", "-r", REMOTE, show=True)
    finally:
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()

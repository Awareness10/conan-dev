import os
import random
import shutil
import tarfile
import time
from io import BytesIO
from pathlib import Path

from conan import ConanFile
from conan.tools.files import copy, save, unzip

# ~640 MiB of text extracts in 12-13 s with Python's bz2, long enough to watch the bar
SIZE_MIB = int(os.environ.get("LARGE_DEMO_MIB", "640"))
FILE_MIB = 10
CACHE_DIR = (
    Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "conan-large-demo"
)


class LargeDemoConan(ConanFile):
    """Extracts a large, heavily compressed tarball in source() to show the progress bar.

    The archive is generated once (~30 s) into ~/.cache/conan-large-demo/ and reused.
    Sources are cached per recipe revision: run `conan remove "large-demo/*" -c` to
    watch the extraction again. LARGE_DEMO_MIB=<n> changes the uncompressed size.
    """

    name = "large-demo"
    version = "0.1"
    license = "MIT"
    description = (
        "Large bzip2 tarball extraction, to test the conan_config progress hook"
    )
    no_copy_source = True
    package_type = "unknown"

    def source(self):
        payload = self._payload()
        unzip(self, str(payload), strip_root=True)
        # Keep only a summary: the extracted text is ~SIZE_MIB MiB of nothing useful
        files = [p for p in Path(self.source_folder).rglob("*.txt") if p.is_file()]
        total = sum(p.stat().st_size for p in files)
        save(self, "manifest.txt", f"{len(files)} files, {total / 2**20:.0f} MiB\n")
        for entry in Path(self.source_folder).iterdir():
            if entry.is_dir():
                shutil.rmtree(entry)

    def _payload(self):
        path = CACHE_DIR / f"payload-{SIZE_MIB}MiB.tar.bz2"
        if path.exists():
            return path
        self.output.info(f"Generating {path} ({SIZE_MIB} MiB of text, one time, ~30 s)")
        start = time.monotonic()
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        rng = random.Random(42)
        letters = "abcdefghijklmnopqrstuvwxyz"
        words = [
            "".join(rng.choices(letters, k=rng.randint(2, 10))) for _ in range(5000)
        ]
        tmp = path.with_suffix(".tmp")
        with tarfile.open(tmp, "w:bz2") as tar:
            for i in range(max(1, SIZE_MIB // FILE_MIB)):
                lines, size = [], 0
                while size < FILE_MIB * 2**20:
                    line = " ".join(rng.choices(words, k=12)) + "\n"
                    lines.append(line)
                    size += len(line)
                data = "".join(lines).encode()
                info = tarfile.TarInfo(f"payload/part{i // 16:02d}/file{i:03d}.txt")
                info.size, info.mtime = len(data), 0
                tar.addfile(info, BytesIO(data))
        tmp.rename(path)
        mib = path.stat().st_size / 2**20
        self.output.info(
            f"Generated {mib:.0f} MiB archive in {time.monotonic() - start:.0f} s"
        )
        return path

    def package(self):
        copy(self, "manifest.txt", self.source_folder, self.package_folder)

    def package_info(self):
        self.cpp_info.includedirs = []
        self.cpp_info.libdirs = []
        self.cpp_info.bindirs = []

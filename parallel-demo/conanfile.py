import os

from conan import ConanFile


class BlobConan(ConanFile):
    """A package holding PARALLEL_DEMO_MIB MiB of random bytes, for run.py.

    Random bytes don't compress, so the .tgz is as big as the package: a transfer of
    known size. The name comes from `conan create --name blobN`.
    """

    version = "0.1"
    license = "MIT"
    description = "Incompressible blob, to test the conan_config progress hook"
    settings = "os", "arch"

    def package(self):
        left = int(os.environ.get("PARALLEL_DEMO_MIB", "100")) * 2**20
        with open(os.path.join(self.package_folder, "blob.bin"), "wb") as f:
            while left:
                n = min(left, 64 * 2**20)
                f.write(os.urandom(n))
                left -= n

import os

from conan import ConanFile
from conan.tools.files import load


class TestPackageConan(ConanFile):
    def requirements(self):
        self.requires(self.tested_reference_str)

    def test(self):
        package_folder = self.dependencies["large-demo"].package_folder
        manifest = load(self, os.path.join(package_folder, "manifest.txt")).strip()
        self.output.info(f"large-demo test_package: extracted {manifest}")

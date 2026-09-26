import os

from conan import ConanFile
from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout
from conan.tools.files import copy, get
from conan.tools.scm import Git

FMT_VERSION = "11.1.4"


class DemoConan(ConanFile):
    """fmt packaged from a tarball, zip or git clone, to exercise the conan_config hooks.

    DEMO_SOURCE=tar|zip|git selects how source() fetches fmt (default: tar). Sources are
    cached per recipe revision, so run `conan remove "demo/*" -c` before switching.
    """

    name = "demo"
    version = "0.1"
    license = "MIT"
    description = f"fmt {FMT_VERSION} for testing conan_config hooks"
    settings = "os", "arch", "compiler", "build_type"
    options = {"shared": [True, False], "fPIC": [True, False]}  # noqa: RUF012 - Conan idiom
    default_options = {"shared": False, "fPIC": True}  # noqa: RUF012

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def layout(self):
        cmake_layout(self, src_folder="src")

    def build_requirements(self):
        self.tool_requires("cmake/[>=3.27 <4]")

    def source(self):
        mode = os.environ.get("DEMO_SOURCE", "tar")
        base = "https://github.com/fmtlib/fmt"
        if mode == "git":
            Git(self).clone(
                f"{base}.git",
                target=".",
                args=["--branch", FMT_VERSION, "--depth", "1"],
            )
        elif mode == "zip":
            get(
                self,
                f"{base}/releases/download/{FMT_VERSION}/fmt-{FMT_VERSION}.zip",
                strip_root=True,
            )
        else:
            get(self, f"{base}/archive/refs/tags/{FMT_VERSION}.tar.gz", strip_root=True)

    def generate(self):
        tc = CMakeToolchain(self)
        tc.cache_variables["FMT_DOC"] = False
        tc.cache_variables["FMT_TEST"] = False
        tc.cache_variables["FMT_INSTALL"] = True
        tc.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def package(self):
        copy(
            self,
            "LICENSE*",
            self.source_folder,
            os.path.join(self.package_folder, "licenses"),
        )
        CMake(self).install()

    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "fmt")
        self.cpp_info.set_property("cmake_target_name", "fmt::fmt")
        self.cpp_info.libs = ["fmtd" if self.settings.build_type == "Debug" else "fmt"]

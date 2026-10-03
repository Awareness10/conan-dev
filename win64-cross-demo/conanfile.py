from conan import ConanFile
from conan.tools.cmake import CMake, cmake_layout


class Win64CrossDemoConan(ConanFile):
    """A small consumer cross-built for Windows: fmt (C++) and zlib (C) from
    ConanCenter are built with clang-cl too, and the tests run under wine."""

    settings = "os", "arch", "compiler", "build_type"
    generators = "CMakeDeps", "CMakeToolchain"

    def requirements(self):
        self.requires("fmt/11.1.4")
        self.requires("zlib/[>=1.3 <2]")

    def layout(self):
        cmake_layout(self)

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()
        # ctest runs the Windows test binary through wine (CMAKE_CROSSCOMPILING_EMULATOR).
        # Only the build env: the host (Windows) run env is a .bat, which can't be
        # combined with the Linux .sh one; the dependencies are static, so it's not needed.
        cmake.test(env="conanbuild")

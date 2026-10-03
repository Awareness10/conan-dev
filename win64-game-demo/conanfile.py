from conan import ConanFile
from conan.tools.cmake import CMake, cmake_layout


class BreakoutConan(ConanFile):
    """Breakout with raylib, cross-built for Windows. Build with the static runtime
    (-s compiler.runtime=static) for a single .exe that runs on any Windows 10/11."""

    settings = "os", "arch", "compiler", "build_type"
    generators = "CMakeDeps", "CMakeToolchain"

    def requirements(self):
        self.requires("raylib/6.0")

    def layout(self):
        cmake_layout(self)

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

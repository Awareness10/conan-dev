cmake_minimum_required(VERSION 3.27)
project(win64_cross_demo LANGUAGES CXX)

find_package(fmt REQUIRED CONFIG)
find_package(ZLIB REQUIRED)

add_executable(hello src/main.cpp)
target_compile_features(hello PRIVATE cxx_std_20)
target_link_libraries(hello PRIVATE fmt::fmt ZLIB::ZLIB)

enable_testing()
# With a cross toolchain, CMAKE_CROSSCOMPILING_EMULATOR (wine) runs this.
add_test(NAME hello_selftest COMMAND hello --self-test)

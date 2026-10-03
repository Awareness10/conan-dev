cmake_minimum_required(VERSION 3.27)
project(breakout LANGUAGES C)

find_package(raylib REQUIRED CONFIG)

add_executable(breakout src/main.c)
target_link_libraries(breakout PRIVATE raylib)
if(WIN32)
    # A windowed program: no console window, but keep the standard main().
    target_link_options(breakout PRIVATE /SUBSYSTEM:WINDOWS /ENTRY:mainCRTStartup)
endif()

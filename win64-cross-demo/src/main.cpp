#include <fmt/format.h>
#include <zlib.h>

#include <string>
#include <string_view>
#include <vector>

#if defined(_WIN32)
#  include <windows.h>
#endif

namespace {

std::string platform() {
#if defined(_MSC_VER) && defined(__clang__)
    std::string compiler = fmt::format("clang-cl {} (MSVC ABI {})", __clang_version__, _MSC_VER);
#elif defined(_MSC_VER)
    std::string compiler = fmt::format("MSVC {}", _MSC_VER);
#else
    std::string compiler = "non-MSVC compiler";
#endif
#if defined(_WIN32)
    // RtlGetVersion reports the real version (GetVersionEx is deprecated and lies).
    using RtlGetVersionFn = LONG(WINAPI*)(OSVERSIONINFOW*);
    OSVERSIONINFOW info{};
    info.dwOSVersionInfoSize = sizeof(info);
    const auto rtlGetVersion = reinterpret_cast<RtlGetVersionFn>(
        reinterpret_cast<void*>(GetProcAddress(GetModuleHandleW(L"ntdll.dll"), "RtlGetVersion")));
    if (rtlGetVersion == nullptr || rtlGetVersion(&info) != 0) {
        return compiler;
    }
    return fmt::format("Windows {}.{} build {}, {}", info.dwMajorVersion, info.dwMinorVersion,
                       info.dwBuildNumber, compiler);
#else
    return compiler;
#endif
}

bool zlibRoundTrip() {
    const std::string text(1000, 'x');
    std::vector<Bytef> packed(compressBound(static_cast<uLong>(text.size())));
    uLongf packedSize = static_cast<uLongf>(packed.size());
    if (compress(packed.data(), &packedSize, reinterpret_cast<const Bytef*>(text.data()),
                 static_cast<uLong>(text.size())) != Z_OK) {
        return false;
    }
    std::string unpacked(text.size(), '\0');
    uLongf unpackedSize = static_cast<uLongf>(unpacked.size());
    if (uncompress(reinterpret_cast<Bytef*>(unpacked.data()), &unpackedSize, packed.data(),
                   packedSize) != Z_OK) {
        return false;
    }
    fmt::print("zlib {}: {} -> {} -> {} bytes\n", zlibVersion(), text.size(), packedSize,
               unpackedSize);
    return unpacked == text;
}

} // namespace

int main(int argc, char** argv) {
    fmt::print("Hello from {}\n", platform());
    const bool selfTest = argc > 1 && std::string_view(argv[1]) == "--self-test";
    if (!selfTest) {
        return 0;
    }
    const bool ok = zlibRoundTrip() && fmt::format("{:>5}|{:#x}", 42, 255) == "   42|0xff";
    fmt::print("self-test: {}\n", ok ? "PASSED" : "FAILED");
    return ok ? 0 : 1;
}

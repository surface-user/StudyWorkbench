#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <string>

// Diagnostic for pinned LibreOffice 26.8.1 x64 exports only; never linked into the product.
struct String { std::int32_t refs, length; wchar_t data[1]; };
struct JavaInfo { String *vendor, *location, *version; std::uint64_t requirements; void *data; };
struct EmptyVector { void *first = nullptr, *last = nullptr, *end = nullptr; };
using Select = int (*)(JavaInfo**);
using Start = int (*)(const JavaInfo*, const EmptyVector&, void**, void**);

void check(bool ok, const char* why) {
    if (!ok) { std::fprintf(stderr, "%s; Win32=%lu\n", why, GetLastError()); ExitProcess(1); }
}
void show(const char* label, String* s) {
    check(s && s->length > 0 && s->length < 8192, "Invalid returned string");
    std::wprintf(L"%hs=%.*s\n", label, s->length, s->data);
}
int wmain(int argc, wchar_t** argv) {
    check(argc == 2 && sizeof(void*) == 8, "Need pinned x64 runtime root");
    std::wstring root = argv[1], program = root + L"\\program";
    check(SetDllDirectoryW(program.c_str()), "Set diagnostic process DLL directory");
    HMODULE framework = LoadLibraryExW((program + L"\\jvmfwklo.dll").c_str(), nullptr, LOAD_WITH_ALTERED_SEARCH_PATH);
    check(framework != nullptr, "Load pinned Office framework");
    auto select = reinterpret_cast<Select>(GetProcAddress(framework,
        "?jfw_getSelectedJRE@@YA?AW4javaFrameworkError@@PEAV?$unique_ptr@UJavaInfo@@U?$default_delete@UJavaInfo@@@std@@@std@@@Z"));
    auto start = reinterpret_cast<Start>(GetProcAddress(framework,
        "?jfw_startVM@@YA?AW4javaFrameworkError@@PEBUJavaInfo@@AEBV?$vector@VOUString@rtl@@V?$allocator@VOUString@rtl@@@std@@@std@@PEAPEAUJavaVM_@@PEAPEAUJNIEnv_@@@Z"));
    check(select && start, "Pinned framework exports");
    JavaInfo* selected = nullptr;
    int selected_result = select(&selected);
    std::printf("office_select=%d\n", selected_result);
    check(selected_result == 0 && selected, "Office must recognize selected JRE");
    show("vendor", selected->vendor); show("location", selected->location); show("version", selected->version);
    EmptyVector options;
    void *vm = nullptr, *env = nullptr;
    int started = start(nullptr, options, &vm, &env);
    std::printf("office_start_vm=%d\n", started);
    check(started == 0 && vm && env, "Office framework must start JVM");
    check(LoadLibraryW((program + L"\\officebean.dll").c_str()) != nullptr, "Office Java AWT bridge");
    for (auto name : {L"jvm.dll", L"jawt.dll", L"awt.dll", L"officebean.dll", L"msvcp140.dll", L"vcruntime140.dll", L"vcruntime140_1.dll"}) {
        auto module = GetModuleHandleW(name);
        check(module != nullptr, "Expected module must be loaded");
        wchar_t path[32768];
        auto count = GetModuleFileNameW(module, path, 32768);
        check(count > 0 && count < 32768, "Module location");
        std::wstring actual(path);
        check(actual.size() > root.size() && _wcsnicmp(actual.c_str(), root.c_str(), root.size()) == 0
              && actual[root.size()] == L'\\', "Must not borrow host module");
        std::wprintf(L"module %s=%s\n", name, actual.substr(root.size() + 1).c_str());
    }
    using Destroy = int (*)(void*);
    int destroyed = reinterpret_cast<Destroy>((*reinterpret_cast<void***>(vm))[3])(vm);
    std::printf("destroy_vm=%d\n", destroyed);
    check(destroyed == 0, "Destroy JVM");
    // Process exit frees the framework-owned JavaInfo; no cross-CRT deallocation.
    return 0;
}

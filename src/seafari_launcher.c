#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shellapi.h>

int WINAPI wWinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPWSTR lpCmdLine, int nShowCmd) {
    // 1.5-second startup hold before launching browser
    Sleep(1500);

    wchar_t exePath[MAX_PATH];
    GetModuleFileNameW(NULL, exePath, MAX_PATH);
    wchar_t* lastSlash = wcsrchr(exePath, L'\\');
    if (lastSlash) {
        *(lastSlash + 1) = L'\0';
    }
    wchar_t ffPath[MAX_PATH];
    wcscpy_s(ffPath, MAX_PATH, exePath);
    wcscat_s(ffPath, MAX_PATH, L"firefox.exe");

    HINSTANCE res = ShellExecuteW(NULL, L"open", ffPath, lpCmdLine, exePath, nShowCmd > 0 ? nShowCmd : SW_SHOWNORMAL);
    return ((INT_PTR)res > 32) ? 0 : 1;
}

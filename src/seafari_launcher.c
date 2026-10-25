#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shellapi.h>
#include <wchar.h>
#include <stdio.h>

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

    // Prepare dedicated profile directory under %APPDATA%\Seafari\profile
    wchar_t args[32768];
    args[0] = L'\0';

    if (lpCmdLine && (wcsstr(lpCmdLine, L"-profile") || wcsstr(lpCmdLine, L"--profile") || wcsstr(lpCmdLine, L"-P"))) {
        wcscpy_s(args, 32768, lpCmdLine);
    } else {
        wchar_t appData[MAX_PATH];
        DWORD len = GetEnvironmentVariableW(L"APPDATA", appData, MAX_PATH);
        if (len > 0 && len < MAX_PATH) {
            wchar_t seafariDir[MAX_PATH];
            wchar_t profileDir[MAX_PATH];
            swprintf_s(seafariDir, MAX_PATH, L"%ls\\Seafari", appData);
            swprintf_s(profileDir, MAX_PATH, L"%ls\\Seafari\\profile", appData);
            CreateDirectoryW(seafariDir, NULL);
            CreateDirectoryW(profileDir, NULL);

            if (lpCmdLine && wcslen(lpCmdLine) > 0) {
                swprintf_s(args, 32768, L"-no-remote -profile \"%ls\" %ls", profileDir, lpCmdLine);
            } else {
                swprintf_s(args, 32768, L"-no-remote -profile \"%ls\"", profileDir);
            }
        } else {
            if (lpCmdLine && wcslen(lpCmdLine) > 0) {
                wcscpy_s(args, 32768, lpCmdLine);
            }
        }
    }

    HINSTANCE res = ShellExecuteW(NULL, L"open", ffPath, args[0] ? args : NULL, exePath, nShowCmd > 0 ? nShowCmd : SW_SHOWNORMAL);
    return ((INT_PTR)res > 32) ? 0 : 1;
}

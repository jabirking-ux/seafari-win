#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shellapi.h>
#include <urlmon.h>
#include <stdlib.h>

#pragma comment(lib, "shell32.lib")
#pragma comment(lib, "urlmon.lib")
#pragma comment(lib, "user32.lib")

int WINAPI wWinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPWSTR lpCmdLine, int nShowCmd) {
    int argc = 0;
    LPWSTR* argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (!argv || argc < 2) {
        if (argv) LocalFree(argv);
        return 1;
    }

    wchar_t ownDir[MAX_PATH];
    GetModuleFileNameW(NULL, ownDir, MAX_PATH);
    wchar_t* lastSlash = wcsrchr(ownDir, L'\\');
    if (lastSlash) {
        *lastSlash = L'\0';
    }

    LPCWSTR installerPath = NULL;
    DWORD targetPid = 0;
    LPCWSTR installDir = ownDir;

    if (wcscmp(argv[1], L"--apply") == 0 && argc >= 3) {
        installerPath = argv[2];
        if (argc >= 4) {
            targetPid = (DWORD)_wtoi(argv[3]);
        }
        if (argc >= 5 && wcslen(argv[4]) > 0) {
            installDir = argv[4];
        }
    } else if (wcscmp(argv[1], L"--download-and-apply") == 0 && argc >= 3) {
        LPCWSTR downloadUrl = argv[2];
        if (argc >= 4) {
            targetPid = (DWORD)_wtoi(argv[3]);
        }
        if (argc >= 5 && wcslen(argv[4]) > 0) {
            installDir = argv[4];
        }

        wchar_t tempPath[MAX_PATH];
        GetTempPathW(MAX_PATH, tempPath);
        static wchar_t tempInstaller[MAX_PATH];
        wsprintfW(tempInstaller, L"%sseafari_update_%u.exe", tempPath, (unsigned int)GetTickCount());

        HRESULT hr = URLDownloadToFileW(NULL, downloadUrl, tempInstaller, 0, NULL);
        if (hr != S_OK) {
            LocalFree(argv);
            return 2;
        }
        installerPath = tempInstaller;
    } else {
        LocalFree(argv);
        return 1;
    }

    // 1. Wait for parent browser process to fully terminate
    if (targetPid > 0) {
        HANDLE hProc = OpenProcess(SYNCHRONIZE, FALSE, targetPid);
        if (hProc != NULL) {
            WaitForSingleObject(hProc, 30000);
            CloseHandle(hProc);
        }
    }

    // Small delay for OS to release all DLL file locks
    Sleep(1000);

    // 2. Execute NSIS silent installation
    if (installerPath && GetFileAttributesW(installerPath) != INVALID_FILE_ATTRIBUTES) {
        wchar_t params[MAX_PATH * 3];
        wsprintfW(params, L"/S /D=%s", installDir);

        SHELLEXECUTEINFOW sei = { sizeof(sei) };
        sei.cbSize = sizeof(sei);
        sei.fMask = SEE_MASK_NOCLOSEPROCESS;
        sei.lpVerb = L"open";
        sei.lpFile = installerPath;
        sei.lpParameters = params;
        sei.nShow = SW_HIDE;

        if (ShellExecuteExW(&sei) && sei.hProcess != NULL) {
            WaitForSingleObject(sei.hProcess, 90000);
            CloseHandle(sei.hProcess);
        }

        // Delete temporary installer
        DeleteFileW(installerPath);
    }

    // 3. Relaunch Seafari
    wchar_t seafariExe[MAX_PATH];
    wsprintfW(seafariExe, L"%s\\seafari.exe", installDir);
    ShellExecuteW(NULL, L"open", seafariExe, NULL, installDir, SW_SHOWNORMAL);

    LocalFree(argv);
    return 0;
}

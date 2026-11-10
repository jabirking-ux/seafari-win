#define WIN32_LEAN_AND_MEAN
#define _CRT_SECURE_NO_WARNINGS

#include <windows.h>
#include <initguid.h>
#include <shellapi.h>
#include <shlobj.h>
#include <shlwapi.h>
#include <tlhelp32.h>
#include <commctrl.h>
#include <dwmapi.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "miniz.h"

#pragma comment(lib, "shell32.lib")
#pragma comment(lib, "ole32.lib")
#pragma comment(lib, "comctl32.lib")
#pragma comment(lib, "advapi32.lib")
#pragma comment(lib, "shlwapi.lib")
#pragma comment(lib, "dwmapi.lib")
#pragma comment(lib, "user32.lib")
#pragma comment(lib, "gdi32.lib")

#ifndef DWMWA_USE_IMMERSIVE_DARK_MODE
#define DWMWA_USE_IMMERSIVE_DARK_MODE 20
#endif

// Version definition with macro stringification
#define SEAFARI_STR2(x) L#x
#define SEAFARI_STR(x) SEAFARI_STR2(x)
#ifdef SEAFARI_VERSION
#define SEAFARI_VERSION_STR SEAFARI_STR(SEAFARI_VERSION)
#else
#define SEAFARI_VERSION_STR L"158.0.13"
#endif

static HWND g_hWnd = NULL;
static HWND g_hProgress = NULL;
static HWND g_hStatus = NULL;
static BOOL g_bSilent = FALSE;
static BOOL g_bNoStart = FALSE;
static BOOL g_bUninstall = FALSE;
static wchar_t g_szInstallDir[MAX_PATH] = { 0 };
static wchar_t g_szOwnExePath[MAX_PATH] = { 0 };

static void CreateDirectoryRecursive(LPCWSTR path) {
    wchar_t folder[MAX_PATH];
    wcsncpy(folder, path, MAX_PATH - 1);
    folder[MAX_PATH - 1] = L'\0';
    wchar_t* p = folder;
    if (p[0] && p[1] == L':') p += 2;
    while (*p == L'\\') p++;
    while ((p = wcschr(p, L'\\')) != NULL) {
        *p = L'\0';
        CreateDirectoryW(folder, NULL);
        *p = L'\\';
        p++;
    }
    CreateDirectoryW(folder, NULL);
}

static void TerminateExistingProcesses() {
    HANDLE hSnap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (hSnap != INVALID_HANDLE_VALUE) {
        PROCESSENTRY32W pe;
        pe.dwSize = sizeof(pe);
        if (Process32FirstW(hSnap, &pe)) {
            do {
                if (_wcsicmp(pe.szExeFile, L"seafari.exe") == 0 || _wcsicmp(pe.szExeFile, L"firefox.exe") == 0) {
                    HANDLE hProc = OpenProcess(PROCESS_TERMINATE, FALSE, pe.th32ProcessID);
                    if (hProc) {
                        TerminateProcess(hProc, 0);
                        CloseHandle(hProc);
                    }
                }
            } while (Process32NextW(hSnap, &pe));
        }
        CloseHandle(hSnap);
    }
    Sleep(200);
}

static HRESULT CreateShortcut(LPCWSTR targetPath, LPCWSTR shortcutPath, LPCWSTR iconPath, LPCWSTR workingDir) {
    IShellLinkW* psl = NULL;
    HRESULT hr = CoCreateInstance(&CLSID_ShellLink, NULL, CLSCTX_INPROC_SERVER, &IID_IShellLinkW, (void**)&psl);
    if (SUCCEEDED(hr)) {
        psl->lpVtbl->SetPath(psl, targetPath);
        if (workingDir) psl->lpVtbl->SetWorkingDirectory(psl, workingDir);
        if (iconPath) psl->lpVtbl->SetIconLocation(psl, iconPath, 0);

        IPersistFile* ppf = NULL;
        hr = psl->lpVtbl->QueryInterface(psl, &IID_IPersistFile, (void**)&ppf);
        if (SUCCEEDED(hr)) {
            hr = ppf->lpVtbl->Save(ppf, shortcutPath, TRUE);
            ppf->lpVtbl->Release(ppf);
        }
        psl->lpVtbl->Release(psl);
    }
    return hr;
}

static void WriteRegistryKeyStr(HKEY hRoot, LPCWSTR subKey, LPCWSTR valueName, LPCWSTR value) {
    HKEY hKey;
    if (RegCreateKeyExW(hRoot, subKey, 0, NULL, REG_OPTION_NON_VOLATILE, KEY_WRITE, NULL, &hKey, NULL) == ERROR_SUCCESS) {
        if (value) {
            RegSetValueExW(hKey, valueName, 0, REG_SZ, (const BYTE*)value, (DWORD)((wcslen(value) + 1) * sizeof(wchar_t)));
        }
        RegCloseKey(hKey);
    }
}

static void WriteRegistryKeyDword(HKEY hRoot, LPCWSTR subKey, LPCWSTR valueName, DWORD value) {
    HKEY hKey;
    if (RegCreateKeyExW(hRoot, subKey, 0, NULL, REG_OPTION_NON_VOLATILE, KEY_WRITE, NULL, &hKey, NULL) == ERROR_SUCCESS) {
        RegSetValueExW(hKey, valueName, 0, REG_DWORD, (const BYTE*)&value, sizeof(DWORD));
        RegCloseKey(hKey);
    }
}

static void RegisterSystemIntegration() {
    wchar_t seafariExe[MAX_PATH];
    wchar_t seafariIco[MAX_PATH];
    wchar_t uninstallExe[MAX_PATH];
    wsprintfW(seafariExe, L"%s\\seafari.exe", g_szInstallDir);
    wsprintfW(seafariIco, L"%s\\seafari.ico", g_szInstallDir);
    wsprintfW(uninstallExe, L"%s\\uninstall.exe", g_szInstallDir);

    // 1. InledGroup\Seafari
    WriteRegistryKeyStr(HKEY_CURRENT_USER, L"Software\\InledGroup\\Seafari", L"Install_Dir", g_szInstallDir);

    // 2. Add/Remove Programs (Uninstall)
    LPCWSTR uninstKey = L"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Seafari";
    WriteRegistryKeyStr(HKEY_CURRENT_USER, uninstKey, L"DisplayName", L"Seafari Browser");
    WriteRegistryKeyStr(HKEY_CURRENT_USER, uninstKey, L"DisplayVersion", SEAFARI_VERSION_STR);
    WriteRegistryKeyStr(HKEY_CURRENT_USER, uninstKey, L"Publisher", L"Inled Group");
    WriteRegistryKeyStr(HKEY_CURRENT_USER, uninstKey, L"DisplayIcon", seafariIco);

    wchar_t uninstCmd[MAX_PATH + 8];
    wsprintfW(uninstCmd, L"\"%s\"", uninstallExe);
    WriteRegistryKeyStr(HKEY_CURRENT_USER, uninstKey, L"UninstallString", uninstCmd);
    WriteRegistryKeyDword(HKEY_CURRENT_USER, uninstKey, L"NoModify", 1);
    WriteRegistryKeyDword(HKEY_CURRENT_USER, uninstKey, L"NoRepair", 1);

    // 3. AppUserModelID
    LPCWSTR aumidKey = L"Software\\Classes\\AppUserModelId\\InledGroup.Seafari";
    WriteRegistryKeyStr(HKEY_CURRENT_USER, aumidKey, L"DisplayName", L"Seafari");
    WriteRegistryKeyStr(HKEY_CURRENT_USER, aumidKey, L"IconUri", seafariIco);
    WriteRegistryKeyDword(HKEY_CURRENT_USER, aumidKey, L"IconBackgroundColor", 0);
    WriteRegistryKeyDword(HKEY_CURRENT_USER, aumidKey, L"ShowInNewInstall", 1);

    // 4. StartMenuInternet
    LPCWSTR smiKey = L"Software\\Clients\\StartMenuInternet\\Seafari";
    WriteRegistryKeyStr(HKEY_CURRENT_USER, smiKey, L"", L"Seafari");
    WriteRegistryKeyStr(HKEY_CURRENT_USER, L"Software\\Clients\\StartMenuInternet\\Seafari\\Capabilities", L"ApplicationDescription", L"Seafari Browser");
    WriteRegistryKeyStr(HKEY_CURRENT_USER, L"Software\\Clients\\StartMenuInternet\\Seafari\\Capabilities", L"ApplicationName", L"Seafari");

    wchar_t iconRef[MAX_PATH + 8];
    wsprintfW(iconRef, L"%s,0", seafariExe);
    WriteRegistryKeyStr(HKEY_CURRENT_USER, L"Software\\Clients\\StartMenuInternet\\Seafari\\Capabilities", L"ApplicationIcon", iconRef);
    WriteRegistryKeyStr(HKEY_CURRENT_USER, L"Software\\Clients\\StartMenuInternet\\Seafari\\DefaultIcon", L"", iconRef);

    wchar_t openCmd[MAX_PATH + 8];
    wsprintfW(openCmd, L"\"%s\"", seafariExe);
    WriteRegistryKeyStr(HKEY_CURRENT_USER, L"Software\\Clients\\StartMenuInternet\\Seafari\\shell\\open\\command", L"", openCmd);

    // 5. Shortcuts
    wchar_t startMenu[MAX_PATH];
    if (SUCCEEDED(SHGetFolderPathW(NULL, CSIDL_PROGRAMS, NULL, 0, startMenu))) {
        // Purge legacy Firefox shortcuts
        wchar_t legacyLnk[MAX_PATH];
        wsprintfW(legacyLnk, L"%s\\Firefox.lnk", startMenu);
        DeleteFileW(legacyLnk);
        wsprintfW(legacyLnk, L"%s\\Firefox Private Browsing.lnk", startMenu);
        DeleteFileW(legacyLnk);

        wchar_t seaMenu[MAX_PATH];
        wsprintfW(seaMenu, L"%s\\Seafari", startMenu);
        CreateDirectoryW(seaMenu, NULL);

        wchar_t lnkSeafari[MAX_PATH];
        wsprintfW(lnkSeafari, L"%s\\Seafari.lnk", seaMenu);
        CreateShortcut(seafariExe, lnkSeafari, seafariIco, g_szInstallDir);

        wsprintfW(lnkSeafari, L"%s\\Seafari.lnk", startMenu);
        CreateShortcut(seafariExe, lnkSeafari, seafariIco, g_szInstallDir);

        wchar_t lnkUninst[MAX_PATH];
        wsprintfW(lnkUninst, L"%s\\Uninstall Seafari.lnk", seaMenu);
        CreateShortcut(uninstallExe, lnkUninst, seafariIco, g_szInstallDir);
    }

    wchar_t desktop[MAX_PATH];
    if (SUCCEEDED(SHGetFolderPathW(NULL, CSIDL_DESKTOPDIRECTORY, NULL, 0, desktop))) {
        wchar_t legacyLnk[MAX_PATH];
        wsprintfW(legacyLnk, L"%s\\Firefox.lnk", desktop);
        DeleteFileW(legacyLnk);
        wsprintfW(legacyLnk, L"%s\\Firefox Private Browsing.lnk", desktop);
        DeleteFileW(legacyLnk);

        wchar_t lnkDesktop[MAX_PATH];
        wsprintfW(lnkDesktop, L"%s\\Seafari.lnk", desktop);
        CreateShortcut(seafariExe, lnkDesktop, seafariIco, g_szInstallDir);
    }
}

static void PerformUninstall() {
    if (!g_bSilent) {
        int resp = MessageBoxW(NULL,
            L"Are you sure you want to completely uninstall Seafari Browser and remove all of its components?",
            L"Uninstall Seafari",
            MB_YESNO | MB_ICONQUESTION);
        if (resp != IDYES) return;
    }

    TerminateExistingProcesses();

    // Remove shortcuts
    wchar_t startMenu[MAX_PATH];
    if (SUCCEEDED(SHGetFolderPathW(NULL, CSIDL_PROGRAMS, NULL, 0, startMenu))) {
        wchar_t seaMenu[MAX_PATH];
        wsprintfW(seaMenu, L"%s\\Seafari", startMenu);
        wchar_t f[MAX_PATH];
        wsprintfW(f, L"%s\\Seafari.lnk", seaMenu);
        DeleteFileW(f);
        wsprintfW(f, L"%s\\Uninstall Seafari.lnk", seaMenu);
        DeleteFileW(f);
        RemoveDirectoryW(seaMenu);

        wsprintfW(f, L"%s\\Seafari.lnk", startMenu);
        DeleteFileW(f);
    }

    wchar_t desktop[MAX_PATH];
    if (SUCCEEDED(SHGetFolderPathW(NULL, CSIDL_DESKTOPDIRECTORY, NULL, 0, desktop))) {
        wchar_t f[MAX_PATH];
        wsprintfW(f, L"%s\\Seafari.lnk", desktop);
        DeleteFileW(f);
    }

    // Clean registry keys
    RegDeleteTreeW(HKEY_CURRENT_USER, L"Software\\InledGroup\\Seafari");
    RegDeleteTreeW(HKEY_CURRENT_USER, L"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Seafari");
    RegDeleteTreeW(HKEY_CURRENT_USER, L"Software\\Classes\\AppUserModelId\\InledGroup.Seafari");
    RegDeleteTreeW(HKEY_CURRENT_USER, L"Software\\Clients\\StartMenuInternet\\Seafari");

    // Spawn self-deleting command to wipe install dir after process exit
    wchar_t cmd[MAX_PATH * 3];
    wsprintfW(cmd, L"/c timeout /t 1 /nobreak >nul & rmdir /s /q \"%s\"", g_szInstallDir);
    ShellExecuteW(NULL, L"open", L"cmd.exe", cmd, NULL, SW_HIDE);

    if (!g_bSilent) {
        MessageBoxW(NULL, L"Seafari Browser has been successfully removed from your computer.", L"Uninstall Seafari", MB_OK | MB_ICONINFORMATION);
    }
}

static DWORD WINAPI ExtractionWorker(LPVOID lpParam) {
    CoInitializeEx(NULL, COINIT_APARTMENTTHREADED);

    TerminateExistingProcesses();
    CreateDirectoryRecursive(g_szInstallDir);

    FILE* pFile = _wfopen(g_szOwnExePath, L"rb");
    if (!pFile) {
        if (!g_bSilent) MessageBoxW(g_hWnd, L"Failed to open installer package file.", L"Error", MB_OK | MB_ICONERROR);
        PostMessageW(g_hWnd, WM_CLOSE, 0, 0);
        return 1;
    }

    mz_zip_archive zip;
    memset(&zip, 0, sizeof(zip));
    if (!mz_zip_reader_init_cfile(&zip, pFile, 0, 0)) {
        fclose(pFile);
        if (!g_bSilent) MessageBoxW(g_hWnd, L"Corrupted or invalid installer package payload.", L"Error", MB_OK | MB_ICONERROR);
        PostMessageW(g_hWnd, WM_CLOSE, 0, 0);
        return 2;
    }

    mz_uint numFiles = mz_zip_reader_get_num_files(&zip);
    if (g_hProgress) {
        SendMessageW(g_hProgress, PBM_SETRANGE32, 0, numFiles);
        SendMessageW(g_hProgress, PBM_SETPOS, 0, 0);
    }

    for (mz_uint i = 0; i < numFiles; i++) {
        mz_zip_archive_file_stat stat;
        if (!mz_zip_reader_file_stat(&zip, i, &stat)) continue;

        wchar_t relPath[MAX_PATH];
        MultiByteToWideChar(CP_UTF8, 0, stat.m_filename, -1, relPath, MAX_PATH);

        // Standardize slashes and prevent directory traversal
        for (wchar_t* p = relPath; *p; p++) {
            if (*p == L'/') *p = L'\\';
        }
        if (wcsstr(relPath, L"..") != NULL) continue;

        wchar_t fullPath[MAX_PATH];
        wsprintfW(fullPath, L"%s\\%s", g_szInstallDir, relPath);

        if (g_hStatus && (i % 8 == 0 || i == numFiles - 1)) {
            wchar_t statusBuf[MAX_PATH + 32];
            wchar_t* fname = wcsrchr(relPath, L'\\');
            wsprintfW(statusBuf, L"Extracting: %s", fname ? (fname + 1) : relPath);
            SetWindowTextW(g_hStatus, statusBuf);
        }

        if (stat.m_is_directory || relPath[wcslen(relPath) - 1] == L'\\') {
            CreateDirectoryRecursive(fullPath);
        } else {
            wchar_t parent[MAX_PATH];
            wcscpy(parent, fullPath);
            wchar_t* lastSlash = wcsrchr(parent, L'\\');
            if (lastSlash) {
                *lastSlash = L'\0';
                CreateDirectoryRecursive(parent);
            }

            void* pBuf = malloc((size_t)stat.m_uncomp_size + 1);
            if (pBuf) {
                if (mz_zip_reader_extract_to_mem(&zip, i, pBuf, (size_t)stat.m_uncomp_size, 0)) {
                    HANDLE hOut = CreateFileW(fullPath, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL | FILE_FLAG_SEQUENTIAL_SCAN, NULL);
                    if (hOut != INVALID_HANDLE_VALUE) {
                        DWORD written = 0;
                        WriteFile(hOut, pBuf, (DWORD)stat.m_uncomp_size, &written, NULL);
                        CloseHandle(hOut);
                    }
                }
                free(pBuf);
            }
        }

        if (g_hProgress) {
            SendMessageW(g_hProgress, PBM_SETPOS, i + 1, 0);
        }
    }

    mz_zip_reader_end(&zip);
    fclose(pFile);

    // Copy own executable as uninstaller
    wchar_t uninstDst[MAX_PATH];
    wsprintfW(uninstDst, L"%s\\uninstall.exe", g_szInstallDir);
    CopyFileW(g_szOwnExePath, uninstDst, FALSE);

    if (g_hStatus) SetWindowTextW(g_hStatus, L"Configuring system integration and shortcuts...");
    RegisterSystemIntegration();

    if (!g_bNoStart) {
        wchar_t seafariExe[MAX_PATH];
        wsprintfW(seafariExe, L"%s\\seafari.exe", g_szInstallDir);
        ShellExecuteW(NULL, L"open", seafariExe, NULL, g_szInstallDir, SW_SHOWNORMAL);
    }

    CoUninitialize();

    if (g_hWnd) {
        Sleep(350);
        PostMessageW(g_hWnd, WM_CLOSE, 0, 0);
    }
    return 0;
}

static LRESULT CALLBACK WndProc(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    static HFONT hFontTitle = NULL;
    static HFONT hFontRegular = NULL;
    static HBRUSH hBkBrush = NULL;

    switch (msg) {
    case WM_CREATE: {
        BOOL darkMode = TRUE;
        DwmSetWindowAttribute(hWnd, DWMWA_USE_IMMERSIVE_DARK_MODE, &darkMode, sizeof(darkMode));

        hBkBrush = CreateSolidBrush(RGB(30, 30, 30));
        hFontTitle = CreateFontW(20, 0, 0, 0, FW_SEMIBOLD, FALSE, FALSE, FALSE, DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
        hFontRegular = CreateFontW(14, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE, DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");

        HWND hTitle = CreateWindowExW(0, L"STATIC", L"Installing Seafari", WS_CHILD | WS_VISIBLE | SS_LEFT, 36, 26, 380, 26, hWnd, NULL, ((LPCREATESTRUCT)lParam)->hInstance, NULL);
        SendMessageW(hTitle, WM_SETFONT, (WPARAM)hFontTitle, TRUE);

        HWND hSub = CreateWindowExW(0, L"STATIC", L"The authentic macOS Safari experience for Windows", WS_CHILD | WS_VISIBLE | SS_LEFT, 36, 54, 400, 20, hWnd, NULL, ((LPCREATESTRUCT)lParam)->hInstance, NULL);
        SendMessageW(hSub, WM_SETFONT, (WPARAM)hFontRegular, TRUE);

        g_hProgress = CreateWindowExW(0, PROGRESS_CLASSW, NULL, WS_CHILD | WS_VISIBLE | PBS_SMOOTH, 36, 96, 408, 14, hWnd, NULL, ((LPCREATESTRUCT)lParam)->hInstance, NULL);

        g_hStatus = CreateWindowExW(0, L"STATIC", L"Preparing installation...", WS_CHILD | WS_VISIBLE | SS_LEFTNOWORDWRAP, 36, 122, 408, 20, hWnd, NULL, ((LPCREATESTRUCT)lParam)->hInstance, NULL);
        SendMessageW(g_hStatus, WM_SETFONT, (WPARAM)hFontRegular, TRUE);

        CreateThread(NULL, 0, ExtractionWorker, NULL, 0, NULL);
        return 0;
    }
    case WM_CTLCOLORSTATIC: {
        HDC hdcStatic = (HDC)wParam;
        SetTextColor(hdcStatic, RGB(235, 235, 235));
        SetBkColor(hdcStatic, RGB(30, 30, 30));
        return (INT_PTR)hBkBrush;
    }
    case WM_ERASEBKGND: {
        HDC hdc = (HDC)wParam;
        RECT rc;
        GetClientRect(hWnd, &rc);
        FillRect(hdc, &rc, hBkBrush);
        return 1;
    }
    case WM_DESTROY:
        if (hFontTitle) DeleteObject(hFontTitle);
        if (hFontRegular) DeleteObject(hFontRegular);
        if (hBkBrush) DeleteObject(hBkBrush);
        PostQuitMessage(0);
        return 0;
    default:
        return DefWindowProcW(hWnd, msg, wParam, lParam);
    }
}

int WINAPI wWinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPWSTR lpCmdLine, int nShowCmd) {
    INITCOMMONCONTROLSEX icex;
    icex.dwSize = sizeof(icex);
    icex.dwICC = ICC_PROGRESS_CLASS;
    InitCommonControlsEx(&icex);

    GetModuleFileNameW(NULL, g_szOwnExePath, MAX_PATH);

    // Default target: %LOCALAPPDATA%\Programs\Seafari
    wchar_t localAppData[MAX_PATH];
    if (SUCCEEDED(SHGetFolderPathW(NULL, CSIDL_LOCAL_APPDATA, NULL, 0, localAppData))) {
        wsprintfW(g_szInstallDir, L"%s\\Programs\\Seafari", localAppData);
    } else {
        wcscpy(g_szInstallDir, L"C:\\Seafari");
    }

    int argc = 0;
    LPWSTR* argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (argv) {
        for (int i = 1; i < argc; i++) {
            if (_wcsicmp(argv[i], L"/S") == 0 || _wcsicmp(argv[i], L"-s") == 0 || _wcsicmp(argv[i], L"--silent") == 0) {
                g_bSilent = TRUE;
            } else if (_wcsnicmp(argv[i], L"/D=", 3) == 0) {
                wcscpy(g_szInstallDir, argv[i] + 3);
            } else if (_wcsnicmp(argv[i], L"--dir=", 6) == 0) {
                wcscpy(g_szInstallDir, argv[i] + 6);
            } else if (_wcsicmp(argv[i], L"/NOSTART") == 0 || _wcsicmp(argv[i], L"--no-launch") == 0) {
                g_bNoStart = TRUE;
            } else if (_wcsicmp(argv[i], L"/UNINSTALL") == 0 || _wcsicmp(argv[i], L"-u") == 0 || _wcsicmp(argv[i], L"--uninstall") == 0) {
                g_bUninstall = TRUE;
            }
        }
        LocalFree(argv);
    }

    // Auto-detect uninstaller mode from executable leaf name
    wchar_t* leafName = wcsrchr(g_szOwnExePath, L'\\');
    if (leafName && wcsstr(leafName, L"uninstall") != NULL) {
        g_bUninstall = TRUE;
        // In uninstaller mode, default install directory is own folder
        wchar_t ownDir[MAX_PATH];
        wcscpy(ownDir, g_szOwnExePath);
        wchar_t* slash = wcsrchr(ownDir, L'\\');
        if (slash) *slash = L'\0';
        wcscpy(g_szInstallDir, ownDir);
    }

    if (g_bUninstall) {
        PerformUninstall();
        return 0;
    }

    if (g_bSilent) {
        ExtractionWorker(NULL);
        return 0;
    }

    // Register modern window class
    WNDCLASSEXW wc = { sizeof(wc) };
    wc.lpfnWndProc = WndProc;
    wc.hInstance = hInstance;
    wc.hCursor = LoadCursorW(NULL, (LPCWSTR)IDC_ARROW);
    wc.lpszClassName = L"SeafariSetupClass";
    wc.hIcon = LoadIconW(hInstance, MAKEINTRESOURCEW(1));
    RegisterClassExW(&wc);

    int winW = 480;
    int winH = 200;
    int scrW = GetSystemMetrics(SM_CXSCREEN);
    int scrH = GetSystemMetrics(SM_CYSCREEN);
    int posX = (scrW - winW) / 2;
    int posY = (scrH - winH) / 2;

    g_hWnd = CreateWindowExW(
        0,
        L"SeafariSetupClass",
        L"Seafari Setup",
        WS_POPUP | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX | WS_VISIBLE,
        posX, posY, winW, winH,
        NULL, NULL, hInstance, NULL
    );

    if (!g_hWnd) {
        ExtractionWorker(NULL);
        return 0;
    }

    ShowWindow(g_hWnd, SW_SHOW);
    UpdateWindow(g_hWnd);

    MSG msg;
    while (GetMessageW(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }

    return 0;
}

/* Minimal Windows GUI launcher. Starts the bundled interpreter without a console. */
typedef unsigned short WCHAR;
typedef unsigned int DWORD;
typedef void *HANDLE;
typedef int BOOL;

typedef struct {
    DWORD cb;
    WCHAR *reserved, *desktop, *title;
    DWORD x, y, x_size, y_size, x_chars, y_chars, fill, flags;
    unsigned short show, reserved_size;
    unsigned char *reserved_data;
    HANDLE input, output, error;
} StartupInfo;
typedef struct { HANDLE process, thread; DWORD pid, tid; } ProcessInfo;

#define WINAPI __attribute__((ms_abi))
#define DLLIMPORT __attribute__((dllimport))
extern DLLIMPORT DWORD WINAPI GetModuleFileNameW(HANDLE, WCHAR *, DWORD);
extern DLLIMPORT BOOL WINAPI CreateProcessW(const WCHAR *, WCHAR *, void *, void *,
    BOOL, DWORD, void *, const WCHAR *, StartupInfo *, ProcessInfo *);
extern DLLIMPORT BOOL WINAPI CloseHandle(HANDLE);
extern DLLIMPORT void WINAPI ExitProcess(DWORD) __attribute__((noreturn));
extern DLLIMPORT int WINAPI MessageBoxW(HANDLE, const WCHAR *, const WCHAR *, unsigned int);

static WCHAR executable[32768], command[32768], directory[32768];
static StartupInfo startup;
static ProcessInfo process;

static WCHAR *append(WCHAR *dest, const WCHAR *source) {
    while (*source) *dest++ = *source++;
    *dest = 0;
    return dest;
}

void WINAPI start(void) {
    DWORD length = GetModuleFileNameW(0, directory, 32768);
    if (length && length < 32000) {
        while (length && directory[length - 1] != '\\') length--;
        directory[length] = 0;
        append(append(executable, directory), L"runtime\\pythonw.exe");
        WCHAR *tail = append(append(command, L"\""), executable);
        append(tail, L"\" -I -m app");
        startup.cb = sizeof(startup);
        if (CreateProcessW(executable, command, 0, 0, 0, 0, 0, directory, &startup, &process)) {
            CloseHandle(process.thread);
            CloseHandle(process.process);
            ExitProcess(0);
        }
    }
    MessageBoxW(0, L"无法启动光标工坊。请完整解压 ZIP 后再打开 CursorStudio.exe。",
                L"光标工坊", 0x10);
    ExitProcess(1);
}

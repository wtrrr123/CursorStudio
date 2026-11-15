"""Apply runtime-only changes and recover the user's Windows cursor scheme."""
import ctypes
from ctypes import wintypes
from pathlib import Path
from tempfile import TemporaryDirectory

from cursor_files import ROLES, cursor_bytes


class WindowsCursors:
    def __init__(self, marker):
        self.marker = marker
        dll = ctypes.WinDLL("user32", use_last_error=True)
        self.load_image = dll.LoadImageW
        self.load_image.argtypes = (wintypes.HINSTANCE, wintypes.LPCWSTR,
                                    wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.UINT)
        self.load_image.restype = wintypes.HANDLE
        self.set_cursor = dll.SetSystemCursor
        self.set_cursor.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        self.set_cursor.restype = wintypes.BOOL
        self.destroy_cursor = dll.DestroyCursor
        self.destroy_cursor.argtypes = (wintypes.HANDLE,)
        self.destroy_cursor.restype = wintypes.BOOL
        self.system_parameters = dll.SystemParametersInfoW
        self.system_parameters.argtypes = (wintypes.UINT, wintypes.UINT,
                                           ctypes.c_void_p, wintypes.UINT)
        self.system_parameters.restype = wintypes.BOOL

        self.monitor_from_window = dll.MonitorFromWindow
        self.monitor_from_window.argtypes = (wintypes.HWND, wintypes.DWORD)
        self.monitor_from_window.restype = wintypes.HANDLE
        self.get_metrics = dll.GetSystemMetrics
        self.get_metrics.argtypes = (ctypes.c_int,)
        self.get_metrics.restype = ctypes.c_int
        self.get_metrics_for_dpi = getattr(dll, "GetSystemMetricsForDpi", None)
        if self.get_metrics_for_dpi:
            self.get_metrics_for_dpi.argtypes = (ctypes.c_int, wintypes.UINT)
            self.get_metrics_for_dpi.restype = ctypes.c_int
        self.scaling = ctypes.WinDLL("shcore")
        self.monitor_scale = self.scaling.GetScaleFactorForMonitor
        self.monitor_scale.argtypes = (wintypes.HANDLE, ctypes.POINTER(ctypes.c_int))
        self.monitor_scale.restype = ctypes.c_long

    def nominal_size(self, hwnd):
        # Obtain the monitor's scale independently of Tk's DPI awareness.
        scale = ctypes.c_int()
        monitor = self.monitor_from_window(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
        if self.get_metrics_for_dpi and monitor and self.monitor_scale(monitor, ctypes.byref(scale)) == 0:
            size = self.get_metrics_for_dpi(13, round(96 * scale.value / 100))
        else:
            size = self.get_metrics(13)  # SM_CXCURSOR
        return min(size, 256) if size > 0 else 32

    def restore(self):
        if not self.system_parameters(0x0057, 0, None, 0):  # SPI_SETCURSORS
            raise ctypes.WinError(ctypes.get_last_error())
        self.marker.unlink(missing_ok=True)

    def apply(self, slots):
        if not slots:
            if self.marker.exists():
                self.restore()
            return
        handles = {}
        try:
            with TemporaryDirectory() as temp:
                for key, slot in slots.items():
                    path = Path(temp) / f"{key}.cur"
                    path.write_bytes(cursor_bytes(slot))
                    handle = self.load_image(None, str(path), 2, 0, 0, 0x10)
                    if not handle:
                        raise ctypes.WinError(ctypes.get_last_error())
                    handles[key] = handle

            # Reset roles from the previous pack before applying this pack.
            if self.marker.exists():
                self.restore()
            self.marker.write_text("reload Windows cursor scheme\n", encoding="ascii")
            try:
                for key in slots:
                    # SetSystemCursor consumes the non-shared cursor handle.
                    if not self.set_cursor(handles.pop(key), ROLES[key][1]):
                        raise ctypes.WinError(ctypes.get_last_error())
            except OSError as error:
                try:
                    self.restore()
                except OSError as recovery_error:
                    raise OSError(f"套装应用失败（{error}）。恢复也失败（{recovery_error}）。") from error
                raise
        finally:
            for handle in handles.values():
                self.destroy_cursor(handle)

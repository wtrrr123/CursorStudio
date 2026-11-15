"""Cursor Studio desktop entry point."""
import os
import sys
import tkinter as tk
from pathlib import Path
from tempfile import TemporaryDirectory
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from cursor_files import (
    ROLES, SIZES, Slot, cursor_bytes, demo_pack, load_pack, read_image, save_pack,
)
from eraser import EraserDialog
from windows_cursors import WindowsCursors

PREVIEW = 320
BG = "#F5F6FA"
CARD = "#FFFFFF"
INK = "#202442"
MUTED = "#515974"
ACCENT = "#5445B8"
TEST_WIDTH, TEST_HEIGHT = 192, 84
TEST_X, TEST_Y = TEST_WIDTH // 2, TEST_HEIGHT // 2
BACKGROUNDS = {"棋盘格": ("#EDF0F6", "#D7DEEB"), "浅色": ("#FFFFFF",),
               "深色": ("#252A3C",)}


class Studio:
    def __init__(self, root, system, preview_dir):
        self.root = root
        self.system = system
        self.preview_dir = Path(preview_dir)
        self.preview_path = None
        self.preview_version = 0
        self.slots = {}
        self.demo_roles = set()
        self.match_system = tk.BooleanVar(value=True)
        self.output = tk.StringVar()
        self.size = tk.IntVar(value=32)
        self.crop = tk.BooleanVar()
        self.status = tk.StringVar(value="选择状态后导入图片，或打开内置示例。")
        self.position = tk.StringVar()
        self.details = tk.StringVar()
        self.active_role = tk.StringVar()
        self.background = tk.StringVar(value="棋盘格")
        self.count = tk.StringVar()
        root.title("光标工坊 2.2")
        root.configure(bg=BG)
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<Escape>", lambda event: self.restore())

        style = ttk.Style(root)
        style.theme_use("clam")
        families = set(root.tk.call("font", "families"))
        font = next((name for name in ("Microsoft YaHei UI", "Noto Sans CJK SC")
                     if name in families), "TkDefaultFont")
        root.option_add("*Font", (font, 10))
        style.configure(".", font=(font, 10))
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=INK)
        style.configure("Card.TFrame", background=CARD)
        style.configure("Card.TLabel", background=CARD, foreground=INK)
        style.configure("Muted.TLabel", background=CARD, foreground=MUTED)
        style.configure("TCheckbutton", background=CARD, foreground=INK)
        style.configure("TButton", padding=(10, 6), background="#FFFFFF",
                        foreground=INK, bordercolor="#DAD3E5")
        style.map("TButton", background=[("active", "#F0EAF9")])
        style.configure("Accent.TButton", background=ACCENT, foreground="white")
        style.map("Accent.TButton", background=[("active", "#523396")])

        shell = ttk.Frame(root, padding=(22, 18, 22, 16))
        shell.pack()
        header = ttk.Frame(shell)
        header.pack(fill="x", pady=(0, 16))
        ttk.Label(header, text="光标工坊", font=(font, 23, "bold")).pack(side="left")
        ttk.Label(header, textvariable=self.count, foreground=MUTED).pack(side="right")

        menu = tk.Menu(root)
        packs = tk.Menu(menu, tearoff=False)
        packs.add_command(label="新建空白", command=self.new_pack)
        packs.add_command(label="打开套装…", command=self.open_pack)
        packs.add_command(label="保存套装…", command=self.save_pack)
        packs.add_separator()
        packs.add_command(label="加载内置示例", command=self.load_demo)
        packs.add_command(label="导出 .cur…", command=self.export)
        menu.add_cascade(label="套装", menu=packs)
        root.configure(menu=menu)

        body = ttk.Frame(shell)
        body.pack(fill="x")
        roles = ttk.Frame(body, style="Card.TFrame", padding=12)
        roles.pack(side="left", fill="y")
        ttk.Label(roles, text="光标状态", style="Card.TLabel",
                  font=(font, 11, "bold")).pack(anchor="w", pady=(0, 10))
        self.role_list = tk.Listbox(roles, width=13, height=len(ROLES),
                                    activestyle="none", exportselection=False,
                                    font=(font, 11), borderwidth=0, highlightthickness=0,
                                    fg=INK, bg=CARD, selectbackground=ACCENT,
                                    selectforeground="white")
        self.role_list.pack(fill="x")
        self.role_list.bind("<<ListboxSelect>>", lambda event: self.refresh())
        ttk.Button(roles, text="加载示例", command=self.load_demo).pack(fill="x", pady=(15, 0))

        editor = ttk.Frame(body, style="Card.TFrame", padding=12)
        editor.pack(side="left", padx=12, fill="y")
        editor_header = ttk.Frame(editor, style="Card.TFrame")
        editor_header.pack(fill="x", pady=(0, 8))
        ttk.Label(editor_header, textvariable=self.active_role, style="Card.TLabel",
                  font=(font, 11, "bold")).pack(side="left")
        background = ttk.Combobox(editor_header, state="readonly", width=7,
                                  values=tuple(BACKGROUNDS), textvariable=self.background)
        background.pack(side="right")
        background.bind("<<ComboboxSelected>>", lambda event: self.refresh())
        self.editor = tk.Canvas(editor, width=PREVIEW, height=PREVIEW, highlightthickness=0)
        self.editor.pack()
        self.editor.bind("<Button-1>", self.set_hotspot)
        self.editor.bind("<B1-Motion>", self.set_hotspot)
        self.editor.bind("<ButtonRelease-1>", lambda event: self.update_test_cursor())
        ttk.Label(editor, textvariable=self.position, style="Muted.TLabel").pack(anchor="w", pady=(8, 0))

        settings = ttk.Frame(body, style="Card.TFrame", padding=12)
        settings.pack(side="left", fill="y")
        ttk.Button(settings, text="导入图片…", command=self.import_image).pack(fill="x")
        ttk.Label(settings, textvariable=self.details, style="Muted.TLabel",
                  wraplength=TEST_WIDTH).pack(anchor="w", pady=(6, 9))
        ttk.Checkbutton(settings, text="匹配系统光标尺寸", variable=self.match_system,
                        command=self.refresh).pack(anchor="w", pady=(0, 4))
        ttk.Label(settings, textvariable=self.output, style="Card.TLabel").pack(anchor="w")
        self.size_box = ttk.Combobox(settings, state="readonly", width=12,
                                     values=SIZES, textvariable=self.size)
        self.size_box.pack(fill="x", pady=(4, 4))
        self.size_box.bind("<<ComboboxSelected>>", self.change_options)
        self.crop_box = ttk.Checkbutton(settings, text="居中裁剪填满", variable=self.crop,
                                       command=self.change_options)
        self.crop_box.pack(anchor="w", pady=(0, 12))
        ttk.Label(settings, text="试用光标 · 点击圆心", style="Card.TLabel").pack(anchor="w")
        self.test = tk.Canvas(settings, width=TEST_WIDTH, height=TEST_HEIGHT,
                              bg="#EFECFC", highlightthickness=0)
        self.test.pack(pady=(6, 10))
        self.test.create_oval(TEST_X-8, TEST_Y-8, TEST_X+8, TEST_Y+8, outline=ACCENT, width=2)
        self.test.create_oval(TEST_X-2, TEST_Y-2, TEST_X+2, TEST_Y+2, fill=ACCENT, width=0)
        self.test.bind("<Button-1>", self.test_click)
        image_actions = ttk.Frame(settings, style="Card.TFrame")
        image_actions.pack(fill="x")
        self.erase_button = ttk.Button(image_actions, text="透明橡皮擦…", command=self.erase)
        self.erase_button.pack(side="left")
        self.remove_button = ttk.Button(image_actions, text="移除图片", command=self.remove_image)
        self.remove_button.pack(side="right")

        actions = ttk.Frame(shell)
        actions.pack(fill="x", pady=(14, 6))
        ttk.Button(actions, text="应用套装", style="Accent.TButton",
                   command=self.apply).pack(side="right")
        ttk.Button(actions, text="恢复光标", command=self.restore).pack(side="right", padx=(0, 8))
        ttk.Label(actions, textvariable=self.status, foreground=MUTED,
                  wraplength=410).pack(side="left", padx=(0, 12))
        self.update_list()
        self.refresh()

    def key(self):
        selected = self.role_list.curselection()
        return tuple(ROLES)[selected[0] if selected else 0]

    def update_list(self):
        key = self.key()
        self.role_list.delete(0, tk.END)
        for role, (label, _) in ROLES.items():
            prefix = "○" if role in self.demo_roles else "●" if role in self.slots else " "
            self.role_list.insert(tk.END, f" {prefix}  {label}")
        self.role_list.selection_set(tuple(ROLES).index(key))
        self.count.set(f"已配置 {len(self.custom_slots())} / {len(ROLES)} 个光标状态")

    def custom_slots(self):
        return {key: slot for key, slot in self.slots.items() if key not in self.demo_roles}

    def display_slot(self, slot, size):
        return slot.at_size(size if size is not None else slot.size)

    def system_size(self):
        if self.match_system.get():
            return self.system.nominal_size(self.root.winfo_id()) if self.system else 32
        return None

    def refresh(self):
        self.editor.delete("all")
        palette = BACKGROUNDS[self.background.get()]
        self.editor.configure(bg=palette[0])
        if len(palette) > 1:
            for row in range(16):
                for col in range((row + 1) % 2, 16, 2):
                    x, y = col * 20, row * 20
                    self.editor.create_rectangle(x, y, x + 20, y + 20, fill=palette[1], width=0)
        slot = self.slots.get(self.key())
        can_erase = slot is not None and self.key() not in self.demo_roles
        self.erase_button.state(["!disabled" if can_erase else "disabled"])
        self.active_role.set(ROLES[self.key()][0])
        state = "!disabled" if slot else "disabled"
        target = self.system_size()
        self.size_box.state(["disabled" if not slot or target else "!disabled"])
        self.output.set(f"系统输出：{target} × {target} px" if target else "手动输出尺寸（像素）")
        for widget in (self.crop_box, self.remove_button):
            widget.state([state])
        if not slot:
            self.size.set(32)
            self.editor.configure(cursor="")
            self.crop.set(False)
            self.details.set("沿用原系统光标")
            self.position.set("导入后点击图像，设置实际点击点")
            self.editor.create_text(PREVIEW / 2, PREVIEW / 2, text="暂无图片",
                                    fill="white" if self.background.get() == "深色" else INK)
        else:
            self.size.set(slot.size)
            if self.editor.cget("cursor") != "crosshair":
                self.editor.configure(cursor="crosshair")
            self.crop.set(slot.crop)
            rendered = self.display_slot(slot, target).render()
            transparent = rendered.getchannel("A").getextrema()[0] < 255
            width, height = slot.image.size
            kind = "示例 · 仅预览" if self.key() in self.demo_roles else (
                "含透明区域" if transparent else "不透明输出")
            self.details.set(f"源图 {width} × {height} · {kind}")
            scaled = rendered.resize((PREVIEW, PREVIEW), Image.Resampling.NEAREST)
            self.large = ImageTk.PhotoImage(scaled)
            self.editor.create_image(0, 0, image=self.large, anchor="nw")
            self.draw_hotspot(slot)
        self.update_test_cursor()

    def draw_hotspot(self, slot):
        self.editor.delete("hotspot")
        effective = self.display_slot(slot, self.system_size())
        output_x, output_y = effective.hotspot
        self.position.set(f"输出点击点 ({output_x}, {output_y})  ·  点击或拖动调整")
        display_x = (output_x + 0.5) * PREVIEW / effective.size
        display_y = (output_y + 0.5) * PREVIEW / effective.size
        for color, width in (("white", 5), (ACCENT, 2)):
            self.editor.create_line(display_x - 10, display_y, display_x + 10, display_y,
                                    fill=color, width=width, tags="hotspot")
            self.editor.create_line(display_x, display_y - 10, display_x, display_y + 10,
                                    fill=color, width=width, tags="hotspot")

    def update_test_cursor(self):
        self.test.configure(cursor="")
        if self.preview_path:
            self.preview_path.unlink(missing_ok=True)
            self.preview_path = None
        slot = self.slots.get(self.key())
        if not slot or sys.platform != "win32":
            return
        self.preview_version += 1
        self.preview_path = self.preview_dir / f"preview-{self.preview_version}.cur"
        try:
            self.preview_path.write_bytes(cursor_bytes(self.display_slot(slot, self.system_size())))
            self.test.configure(cursor=(f"@{self.preview_path.as_posix()}",))
        except (OSError, tk.TclError):
            self.status.set("试用区无法加载当前光标。仍可查看预览和导出。")

    def set_hotspot(self, event):
        slot = self.slots.get(self.key())
        if not slot:
            return
        size = self.system_size() or slot.size
        point = tuple(max(0, min(size - 1, coord * size // PREVIEW))
                      for coord in (event.x, event.y))
        slot.anchor = tuple((coordinate + 0.5) / size for coordinate in point)
        slot.hotspot = slot.at_size(slot.size).hotspot
        self.draw_hotspot(slot)

    def test_click(self, event):
        if self.key() not in self.slots:
            self.status.set("为当前状态导入图片后即可试点。")
        else:
            distance = ((event.x - TEST_X) ** 2 + (event.y - TEST_Y) ** 2) ** 0.5
            self.status.set("已点中目标。" if distance <= 8
                            else f"落点距离目标中心约 {round(distance)} 像素。")

    def change_options(self, event=None):
        slot = self.slots.get(self.key())
        if not slot:
            return
        size = self.size.get()
        slot = slot.at_size(size)
        slot.crop = self.crop.get()
        self.slots[self.key()] = slot
        self.refresh()

    def import_image(self):
        path = filedialog.askopenfilename(filetypes=[("图片", "*.png *.webp *.gif *.jpg *.jpeg")])
        if path:
            def action():
                image = read_image(path)
                key = self.key()
                current = self.custom_slots().get(key)
                size = current.size if current else 32
                hotspot = current.hotspot if current else (size // 2, size // 2)
                self.slots[key] = Slot(image, size, hotspot, self.crop.get(),
                                       current.anchor if current else None)
                self.demo_roles.discard(key)
                self.changed("图片已导入。请设置点击点。")
            self.run(action)

    def erase(self):
        key = self.key()
        slot = self.slots.get(key)
        if slot is None or key in self.demo_roles:
            return

        def save(image):
            slot.image = image
            self.changed("已保存透明区域。点击「应用套装」更新系统光标。")

        EraserDialog(self.root, slot.image, save)

    def remove_image(self):
        self.slots.pop(self.key(), None)
        self.demo_roles.discard(self.key())
        self.changed("已移除图片。重新应用时该状态将使用系统光标。")

    def changed(self, status):
        self.update_list()
        self.status.set(status)
        self.refresh()

    def replace_pack(self, slots, status, *, demo=False):
        if self.custom_slots() and not messagebox.askyesno(
            "替换编辑中的套装", "替换会丢弃当前编辑内容。继续吗？", parent=self.root
        ):
            return
        self.slots = slots
        self.demo_roles = set(slots) if demo else set()
        self.changed(status)

    def new_pack(self):
        self.replace_pack({}, "已新建空白套装。")

    def load_demo(self):
        self.replace_pack(demo_pack(), "示例仅供预览。导入自己的图片后即可应用。", demo=True)

    def open_pack(self):
        path = filedialog.askopenfilename(filetypes=[("光标套装", "*.cursorpack")])
        if path:
            self.run(lambda: self.replace_pack(load_pack(path), "套装已打开。"))

    def save_pack(self):
        path = filedialog.asksaveasfilename(defaultextension=".cursorpack",
                                            filetypes=[("光标套装", "*.cursorpack")])
        if path:
            def action():
                save_pack(path, self.custom_slots())
                self.status.set("套装已保存，图片与点击点都包含在文件中。")
            self.run(action)

    def export(self):
        slots = self.custom_slots()
        if not slots:
            self.status.set("请先导入光标图片。")
            return
        folder = filedialog.askdirectory()
        if folder:
            def action():
                size = self.system_size()
                paths = {Path(folder) / f"{key}.cur": cursor_bytes(self.display_slot(slot, size))
                         for key, slot in slots.items()}
                if any(path.exists() for path in paths) and not messagebox.askyesno(
                    "覆盖文件", "目标文件夹内已有同名光标。覆盖吗？", parent=self.root
                ):
                    return
                for path, data in paths.items():
                    path.write_bytes(data)
                self.status.set(f"已导出 {len(paths)} 个 .cur 文件。")
            self.run(action)

    def apply(self):
        def action():
            slots = self.custom_slots()
            size = self.system_size()
            self.system.apply({key: self.display_slot(slot, size) for key, slot in slots.items()})
            self.status.set(f"已应用 {len(slots)} 个光标。其余沿用系统光标。" if slots
                            else "当前所有状态均使用系统光标。")
        self.run(action)

    def restore(self):
        def action():
            if self.system.marker.exists():
                self.system.restore()
            self.status.set("Windows 光标方案已恢复。")
        self.run(action)

    def close(self):
        try:
            if self.system.marker.exists():
                self.system.restore()
        except OSError as error:
            messagebox.showerror("恢复失败", f"{error}\n请重试，或在 Windows 鼠标设置中重新应用方案。",
                                 parent=self.root)
            return
        self.root.destroy()

    def run(self, action):
        try:
            action()
        except (OSError, ValueError, KeyError, TypeError, Image.DecompressionBombError) as error:
            messagebox.showerror("操作失败", str(error), parent=self.root)


def main():
    if sys.platform != "win32":
        raise SystemExit("此应用需要在 Windows 10 或 11 中运行。")
    import msvcrt

    runtime = Path(sys.executable).parent
    tcl = runtime / "tcl"
    if (tcl / "tcl8.6" / "init.tcl").is_file():
        os.environ["TCL_LIBRARY"] = str(tcl / "tcl8.6")
        os.environ["TK_LIBRARY"] = str(tcl / "tk8.6")
    root = tk.Tk()
    root.withdraw()
    app_data = Path(os.environ["LOCALAPPDATA"]) / "CursorStudio"
    try:
        app_data.mkdir(parents=True, exist_ok=True)
        with (app_data / "instance.lock").open("a+b") as lock:
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                messagebox.showinfo("光标工坊", "应用已在运行。", parent=root)
                root.destroy()
                return
            system = WindowsCursors(app_data / "restore.pending")
            if system.marker.exists():
                system.restore()
            with TemporaryDirectory(prefix="cursor-studio-") as preview_dir:
                Studio(root, system, preview_dir)
                root.deiconify()
                root.mainloop()
    except OSError as error:
        messagebox.showerror("光标工坊启动失败", str(error), parent=root)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        if sys.platform != "win32":
            raise
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, str(error), "光标工坊启动失败", 0x10)

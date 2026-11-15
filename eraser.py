"""Edit the source alpha channel with a round, continuous eraser brush."""
import tkinter as tk
from collections import deque
from tkinter import ttk

from PIL import Image, ImageDraw, ImageTk

CANVAS_SIZE = 448
BRUSH_HINT = "拖动鼠标擦除，露出的棋盘格代表透明。"


class EraserDialog:
    def __init__(self, parent, image, on_save):
        self.window = window = tk.Toplevel(parent)
        window.title("透明橡皮擦")
        window.transient(parent)
        window.resizable(False, False)
        self.image = image.copy()
        self.alpha = self.image.getchannel("A")
        self.history = deque(maxlen=8)
        self.last = None
        self.paint_job = None
        self.diameter = tk.IntVar(master=window, value=28)
        self.hint = tk.StringVar(master=window, value=BRUSH_HINT)

        width, height = self.image.size
        factor = CANVAS_SIZE / max(width, height)
        self.preview_size = (max(1, round(width * factor)), max(1, round(height * factor)))
        self.offset = tuple((CANVAS_SIZE - length) // 2 for length in self.preview_size)

        frame = ttk.Frame(window, padding=14)
        frame.pack()
        ttk.Label(frame, textvariable=self.hint, wraplength=CANVAS_SIZE).pack(anchor="w", pady=(0, 8))
        self.canvas = tk.Canvas(frame, width=CANVAS_SIZE, height=CANVAS_SIZE,
                                bg="#EEF0F5", highlightthickness=0, cursor="crosshair")
        self.canvas.pack()
        left, top = self.offset
        right, bottom = left + self.preview_size[0], top + self.preview_size[1]
        self.canvas.create_rectangle(left, top, right, bottom, fill="#EDF0F6", width=0)
        for y in range(top, bottom, 16):
            for x in range(left, right, 16):
                if ((y - top) // 16 + (x - left) // 16) % 2:
                    self.canvas.create_rectangle(x, y, min(x + 16, right), min(y + 16, bottom),
                                                 fill="#CFD7E7", width=0)
        self.preview = self.canvas.create_image(left, top, anchor="nw")
        self.canvas.bind("<Button-1>", self.start)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<ButtonRelease-1>", self.finish)
        self.canvas.bind("<Motion>", self.move)
        self.canvas.bind("<Leave>", lambda event: self.canvas.delete("brush"))

        controls = ttk.Frame(frame)
        controls.pack(fill="x", pady=(10, 0))
        ttk.Label(controls, text="笔刷大小").pack(side="left")
        ttk.Scale(controls, from_=4, to=100, variable=self.diameter,
                  length=130).pack(side="left", padx=6)
        ttk.Label(controls, textvariable=self.diameter, width=3).pack(side="left")
        ttk.Button(controls, text="撤销上一笔", command=self.undo).pack(side="right")
        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(actions, text="保存擦除", style="Accent.TButton",
                   command=lambda: self.save(on_save)).pack(side="right")
        ttk.Button(actions, text="取消", command=self.close).pack(side="right", padx=(0, 8))
        window.bind("<Escape>", lambda event: self.close())
        window.bind("<Control-z>", lambda event: self.undo())
        window.protocol("WM_DELETE_WINDOW", self.close)
        self.redraw()
        window.update_idletasks()
        window.wait_visibility()
        window.grab_set()
        window.focus_set()

    def source_point(self, event):
        return tuple((coordinate - offset) * length // preview
                     for coordinate, offset, length, preview in
                     zip((event.x, event.y), self.offset, self.image.size, self.preview_size))

    def start(self, event):
        x, y = self.source_point(event)
        if not (0 <= x < self.image.width and 0 <= y < self.image.height):
            return
        self.hint.set(BRUSH_HINT)
        self.history.append(self.alpha.copy())
        self.last = (x, y)
        self.drag(event)

    def drag(self, event):
        if self.last is None:
            return
        point = self.source_point(event)
        diameter = max(1, round(self.diameter.get() * max(self.image.size) / CANVAS_SIZE))
        radius = diameter // 2
        draw = ImageDraw.Draw(self.alpha)
        draw.line((self.last, point), fill=0, width=diameter)
        for x, y in (self.last, point):
            draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill=0)
        self.last = point
        self.move(event)
        if self.paint_job is None:
            self.paint_job = self.window.after(24, self.redraw)

    def finish(self, event):
        if self.last is not None and self.source_point(event) != self.last:
            self.drag(event)
        self.last = None

    def move(self, event):
        self.canvas.delete("brush")
        radius = self.diameter.get() / 2
        bounds = (event.x-radius, event.y-radius, event.x+radius, event.y+radius)
        self.canvas.create_oval(*bounds, outline="white", width=3, tags="brush")
        self.canvas.create_oval(*bounds, outline="#34315F", width=1, tags="brush")

    def redraw(self):
        self.paint_job = None
        self.image.putalpha(self.alpha)
        scaled = self.image.resize(self.preview_size, Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(scaled, master=self.window)
        self.canvas.itemconfigure(self.preview, image=self.photo)

    def undo(self):
        if self.history and self.last is None:
            self.alpha = self.history.pop()
            self.schedule_cancel()
            self.redraw()
            self.hint.set("已撤销上一笔。")

    def schedule_cancel(self):
        if self.paint_job is not None:
            self.window.after_cancel(self.paint_job)
            self.paint_job = None

    def save(self, on_save):
        if self.alpha.getbbox() is None:
            self.hint.set("图片已完全透明，请先撤销一笔，保留要显示的图案。")
            return
        self.image.putalpha(self.alpha)
        on_save(self.image)
        self.close()

    def close(self):
        self.schedule_cancel()
        self.window.destroy()

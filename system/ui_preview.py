"""Experimental dark UI built on desktop_app.QuoteApp.

Opened from the UI切替 button (or the trial bat). Only the layout differs;
quote generation methods on QuoteApp are called as they are.
"""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from pathlib import Path

import tkinter as tk
import tkinter.font as tkfont

from desktop_app import UI_PREVIEW, QuoteApp, run_app
from quote_system.config import (
    APP_DISPLAY_NAME,
    APP_VERSION,
    EDITION_LABEL,
    FORCED_DEPARTMENT,
    IS_SPECIAL_EDITION,
    QUOTE_OUTPUT_DIRNAME,
    QUOTE_OUTPUT_DIRNAME_24,
    QUOTE_OUTPUT_DIRNAME_36,
    app_window_title,
)

BG = "#121214"
CARD = "#2c2c2e"
CARD_SOFT = "#1c1c1e"
TRACK = "#3a3a3c"
TEXT = "#f5f5f7"
TEXT_DIM = "#aeaeb2"
TEXT_MUTED = "#8e8e93"
ACCENT = "#0a84ff"
ACCENT_HOVER = "#409cff"
ACCENT_PRESS = "#0060df"
WARN = "#ff9f0a"
DANGER = "#ff453a"
LOG_BG = "#0c0c0e"
WHITE = "#ffffff"

FONT = "Yu Gothic UI"
TITLE_SUFFIX = "  ［試験UI］"


def _mix(start: str, end: str, t: float) -> str:
    t = max(0.0, min(1.0, t))
    a = start.lstrip("#")
    b = end.lstrip("#")
    channels = []
    for i in (0, 2, 4):
        av = int(a[i : i + 2], 16)
        bv = int(b[i : i + 2], 16)
        channels.append(int(av + (bv - av) * t))
    return "#{:02x}{:02x}{:02x}".format(*channels)


def _draw_round_rect(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs) -> None:
    r = int(min(radius, max(0, (x2 - x1) / 2), max(0, (y2 - y1) / 2)))
    if r <= 0:
        canvas.create_rectangle(x1, y1, x2, y2, **kwargs)
        return
    style = {"style": "pieslice", **kwargs}
    canvas.create_arc(x1, y1, x1 + 2 * r, y1 + 2 * r, start=90, extent=90, **style)
    canvas.create_arc(x2 - 2 * r, y1, x2, y1 + 2 * r, start=0, extent=90, **style)
    canvas.create_arc(x1, y2 - 2 * r, x1 + 2 * r, y2, start=180, extent=90, **style)
    canvas.create_arc(x2 - 2 * r, y2 - 2 * r, x2, y2, start=270, extent=90, **style)
    canvas.create_rectangle(x1 + r, y1, x2 - r, y2, **kwargs)
    canvas.create_rectangle(x1, y1 + r, x2, y2 - r, **kwargs)


class PillButton(tk.Canvas):
    """Rounded button. Hover and press ease between colors. state matches ttk."""

    def __init__(
        self,
        parent: tk.Widget,
        text: str,
        command,
        *,
        kind: str = "secondary",
        canvas_bg: str = CARD,
    ) -> None:
        self._text = text
        self._command = command
        self._kind = kind
        self._state = "normal"
        self._pressed = False
        self._hover = False
        self._anim_job: str | None = None
        weight = "bold" if kind == "primary" else "normal"
        size = 12 if kind == "primary" else 11
        self._font = tkfont.Font(family=FONT, size=size, weight=weight)
        self._bw = self._font.measure(text) + (36 if kind == "primary" else 28)
        self._bh = 40 if kind == "primary" else 36
        super().__init__(
            parent,
            width=self._bw,
            height=self._bh,
            bg=canvas_bg,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self._fill = self._target_fill()
        self._fg = self._target_fg()
        self._paint()
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def configure(self, cnf=None, **kwargs):  # type: ignore[override]
        if isinstance(cnf, dict):
            kwargs = {**cnf, **kwargs}
        state = kwargs.pop("state", None)
        result = super().configure(**kwargs) if kwargs else None
        if state is not None and state != self._state:
            self._state = state
            self.configure(cursor="hand2" if state == "normal" else "arrow")
            self._animate_to(self._target_fill(), self._target_fg())
        return result

    config = configure  # type: ignore[assignment]

    def _palette(self) -> tuple[str, str]:
        if self._state != "normal":
            return (TRACK, TEXT_MUTED)
        if self._kind == "primary":
            if self._pressed:
                return (ACCENT_PRESS, WHITE)
            if self._hover:
                return (ACCENT_HOVER, WHITE)
            return (ACCENT, WHITE)
        if self._pressed:
            return ("#5a5a5e", TEXT)
        if self._hover:
            return ("#48484a", TEXT)
        return (TRACK, TEXT)

    def _target_fill(self) -> str:
        return self._palette()[0]

    def _target_fg(self) -> str:
        return self._palette()[1]

    def _paint(self) -> None:
        self.delete("all")
        _draw_round_rect(self, 1, 1, self._bw - 1, self._bh - 1, 12, fill=self._fill, outline="")
        self.create_text(self._bw / 2, self._bh / 2, text=self._text, fill=self._fg, font=self._font)

    def _animate_to(self, fill: str, fg: str) -> None:
        if self._anim_job is not None:
            self.after_cancel(self._anim_job)
            self._anim_job = None
        start_fill, start_fg = self._fill, self._fg
        steps = 6

        def step(i: int = 1) -> None:
            if not self.winfo_exists():
                return
            t = i / steps
            self._fill = _mix(start_fill, fill, t)
            self._fg = _mix(start_fg, fg, t)
            self._paint()
            if i < steps:
                self._anim_job = self.after(16, lambda: step(i + 1))

        step()

    def _on_enter(self, _event: tk.Event) -> None:
        self._hover = True
        if self._state == "normal":
            self._animate_to(self._target_fill(), self._target_fg())

    def _on_leave(self, _event: tk.Event) -> None:
        self._hover = False
        self._pressed = False
        if self._state == "normal":
            self._animate_to(self._target_fill(), self._target_fg())

    def _on_press(self, _event: tk.Event) -> None:
        if self._state != "normal":
            return
        self._pressed = True
        self._animate_to(self._target_fill(), self._target_fg())

    def _on_release(self, event: tk.Event) -> None:
        was_pressed = self._pressed
        self._pressed = False
        inside = 0 <= event.x <= self._bw and 0 <= event.y <= self._bh
        if self._state == "normal":
            self._animate_to(self._target_fill(), self._target_fg())
        if was_pressed and inside and self._state == "normal" and self._command:
            self._command()


class Toggle(tk.Canvas):
    """iOS-style switch bound to the existing BooleanVar."""

    def __init__(self, parent: tk.Widget, variable: tk.BooleanVar, *, bg: str = CARD) -> None:
        self.variable = variable
        self._bw, self._bh = 48, 28
        self._knob = 1.0 if variable.get() else 0.0
        self._job: str | None = None
        super().__init__(
            parent,
            width=self._bw,
            height=self._bh,
            bg=bg,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self._paint()
        self.bind("<Button-1>", self._on_click)
        variable.trace_add("write", self._on_var)

    def _on_click(self, _event: tk.Event) -> None:
        self.variable.set(not bool(self.variable.get()))

    def _on_var(self, *_args) -> None:
        self._animate()

    def _animate(self) -> None:
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None
        target = 1.0 if self.variable.get() else 0.0

        def step() -> None:
            if not self.winfo_exists():
                return
            self._knob += (target - self._knob) * 0.45
            if abs(target - self._knob) < 0.02:
                self._knob = target
                self._paint()
                return
            self._paint()
            self._job = self.after(16, step)

        step()

    def _paint(self) -> None:
        self.delete("all")
        track = _mix(TRACK, ACCENT, self._knob)
        _draw_round_rect(self, 1, 1, self._bw - 1, self._bh - 1, 14, fill=track, outline="")
        pad = 3
        knob_d = self._bh - pad * 2
        travel = self._bw - pad * 2 - knob_d
        x = pad + travel * self._knob
        self.create_oval(x, pad, x + knob_d, pad + knob_d, fill=WHITE, outline="")


class Segmented(tk.Frame):
    """Two-choice control. The selected side uses the accent color."""

    def __init__(
        self,
        parent: tk.Widget,
        variable: tk.StringVar,
        options: list[tuple[str, str]],
        command,
        *,
        bg: str = CARD,
    ) -> None:
        super().__init__(parent, bg=bg)
        self.variable = variable
        self.command = command
        self._labels: dict[str, tk.Label] = {}
        track = tk.Frame(self, bg=CARD_SOFT)
        track.pack(anchor="w")
        for value, label in options:
            item = tk.Label(
                track,
                text=label,
                font=(FONT, 11),
                padx=18,
                pady=8,
                cursor="hand2",
            )
            item.pack(side="left", padx=3, pady=3)
            item.bind("<Button-1>", lambda _e, v=value: self._pick(v))
            self._labels[value] = item
        self._paint()
        variable.trace_add("write", lambda *_: self._paint())

    def _pick(self, value: str) -> None:
        if self.variable.get() == value:
            return
        self.variable.set(value)
        if self.command:
            self.command()

    def _paint(self) -> None:
        current = self.variable.get()
        for value, label in self._labels.items():
            if value == current:
                label.configure(bg=ACCENT, fg=WHITE)
            else:
                label.configure(bg=CARD_SOFT, fg=TEXT_DIM)


class LineProgress(tk.Canvas):
    """Thin bar. configure(maximum=, value=) matches the production progress bar."""

    def __init__(self, parent: tk.Widget, *, bg: str = CARD) -> None:
        super().__init__(parent, height=8, bg=bg, highlightthickness=0, bd=0)
        self._max = 1.0
        self._value = 0.0
        self.bind("<Configure>", lambda _e: self._paint())

    def configure(self, cnf=None, **kwargs):  # type: ignore[override]
        if isinstance(cnf, dict):
            kwargs = {**cnf, **kwargs}
        maximum = kwargs.pop("maximum", None)
        value = kwargs.pop("value", None)
        result = super().configure(**kwargs) if kwargs else None
        if maximum is not None:
            self._max = max(float(maximum), 1.0)
        if value is not None:
            self._value = max(0.0, float(value))
        if maximum is not None or value is not None:
            self._paint()
        return result

    config = configure  # type: ignore[assignment]

    def _paint(self) -> None:
        self.delete("all")
        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)
        _draw_round_rect(self, 0, 0, width, height, 4, fill=TRACK, outline="")
        frac = max(0.0, min(1.0, self._value / self._max))
        fill_w = int(width * frac)
        if fill_w > 0:
            _draw_round_rect(self, 0, 0, max(fill_w, 8), height, 4, fill=ACCENT, outline="")


class WinFileDrop:
    """Optional Windows file drop for this trial window only."""

    WM_DROPFILES = 0x0233
    GWLP_WNDPROC = -4

    def __init__(self, root: tk.Tk, on_files) -> None:
        self._root = root
        self._on_files = on_files
        self._hwnd: int | None = None
        self._old: int | None = None
        self._proc = None
        self._set_long = None
        self.installed = False

    def install(self) -> bool:
        if os.name != "nt" or self.installed:
            return self.installed
        try:
            self._root.update_idletasks()
            user32 = ctypes.windll.user32
            child = int(self._root.winfo_id())
            parent = int(user32.GetParent(child) or 0)
            hwnd = parent or child
            pointer = ctypes.c_ssize_t
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                get_long = user32.GetWindowLongPtrW
                set_long = user32.SetWindowLongPtrW
            else:
                get_long = user32.GetWindowLongW
                set_long = user32.SetWindowLongW
            get_long.argtypes = [wintypes.HWND, ctypes.c_int]
            get_long.restype = pointer
            set_long.argtypes = [wintypes.HWND, ctypes.c_int, pointer]
            set_long.restype = pointer
            call_proc = user32.CallWindowProcW
            call_proc.argtypes = [pointer, wintypes.HWND, ctypes.c_uint, pointer, pointer]
            call_proc.restype = pointer
            query = ctypes.windll.shell32.DragQueryFileW
            query.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint]
            query.restype = ctypes.c_uint
            wndproc = ctypes.WINFUNCTYPE(pointer, wintypes.HWND, ctypes.c_uint, pointer, pointer)
            old = int(get_long(hwnd, self.GWLP_WNDPROC))

            @wndproc
            def proc(h, msg, wp, lp):
                if msg == self.WM_DROPFILES:
                    try:
                        count = int(query(wp, 0xFFFFFFFF, None, 0))
                        files: list[str] = []
                        for index in range(count):
                            needed = int(query(wp, index, None, 0))
                            buf = ctypes.create_unicode_buffer(needed + 1)
                            query(wp, index, buf, needed + 1)
                            files.append(buf.value)
                        ctypes.windll.shell32.DragFinish(wp)
                        self._root.after(0, lambda paths=files: self._on_files(paths))
                    except Exception:
                        ctypes.windll.shell32.DragFinish(wp)
                    return 0
                return call_proc(old, h, msg, wp, lp)

            self._proc = proc
            set_long(hwnd, self.GWLP_WNDPROC, ctypes.cast(proc, ctypes.c_void_p).value)
            ctypes.windll.shell32.DragAcceptFiles(hwnd, True)
            self._hwnd = hwnd
            self._old = old
            self._set_long = set_long
            self.installed = True
            return True
        except Exception:
            self.installed = False
            return False

    def uninstall(self) -> None:
        if not self.installed or self._hwnd is None or self._old is None or self._set_long is None:
            return
        try:
            self._set_long(self._hwnd, self.GWLP_WNDPROC, self._old)
            ctypes.windll.shell32.DragAcceptFiles(self._hwnd, False)
        except Exception:
            pass
        self.installed = False


class PreviewQuoteApp(QuoteApp):
    """Same QuoteApp behavior, with a trial dark layout."""

    UI_MODE = UI_PREVIEW

    def __init__(self, *, ui_snapshot: dict | None = None) -> None:
        super().__init__(ui_snapshot=ui_snapshot)
        self.title(app_window_title() + TITLE_SUFFIX)

    def destroy(self) -> None:
        drop = getattr(self, "_file_drop", None)
        if drop is not None:
            drop.uninstall()
        super().destroy()

    def _fit_window_to_content(self) -> None:
        self.update_idletasks()
        screen_w = max(self.winfo_screenwidth(), 900)
        screen_h = max(self.winfo_screenheight(), 700)
        win_w = min(980, int(screen_w * 0.92))
        win_h = min(880, int(screen_h * 0.90))
        self.minsize(780, 640)
        x = max(0, (screen_w - win_w) // 2)
        y = max(0, (screen_h - win_h) // 2)
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")

    def _set_running_ui(self, running: bool) -> None:
        super()._set_running_ui(running)
        self._sync_steps()

    def _on_installment_mode_changed(self) -> None:
        super()._on_installment_mode_changed()
        if getattr(self, "drop_title", None) is not None:
            self._sync_drop()
            self._sync_steps()

    def _build_ui(self) -> None:
        self.configure(bg=BG)
        self._wheel_bound: set[int] = set()
        self._details_open = False
        self.drop_title = tk.StringVar(value="PDFをドロップ、またはクリックして選択")
        self.drop_path = tk.StringVar(value="対応しているファイルは .pdf です")

        shell = tk.Frame(self, bg=BG)
        shell.pack(fill="both", expand=True, padx=22, pady=8)

        self._build_header(shell)
        self._build_steps(shell)

        log_wrap = tk.Frame(shell, bg=BG)
        log_wrap.pack(side="bottom", fill="x", pady=(12, 0))
        self._build_log(log_wrap)

        mid = tk.Frame(shell, bg=BG)
        mid.pack(fill="both", expand=True, pady=(12, 0))
        self._scroll = tk.Canvas(mid, bg=BG, highlightthickness=0, bd=0)
        self._scroll.pack(side="left", fill="both", expand=True)
        scroll_bar = tk.Scrollbar(
            mid,
            command=self._scroll.yview,
            bg=BG,
            troughcolor=BG,
            activebackground=TRACK,
            relief="flat",
            width=10,
        )
        scroll_bar.pack(side="right", fill="y")
        self._scroll.configure(yscrollcommand=scroll_bar.set)
        self._scroll_inner = tk.Frame(self._scroll, bg=BG)
        self._scroll_win = self._scroll.create_window((0, 0), window=self._scroll_inner, anchor="nw")
        self._scroll_inner.bind("<Configure>", self._on_scroll_inner)
        self._scroll.bind("<Configure>", self._on_scroll_canvas)

        self._columns = tk.Frame(self._scroll_inner, bg=BG)
        self._columns.pack(fill="x")
        self._col_left = tk.Frame(self._columns, bg=BG)
        self._col_right = tk.Frame(self._columns, bg=BG)
        self._col_left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self._col_right.pack(side="left", fill="both", expand=True, padx=(8, 0))

        self._build_type_card()
        self._build_file_card()
        self._build_condition_card()
        self._build_run_card()

        self.pdf_var.trace_add("write", self._on_pdf_changed)
        self._sync_drop()
        self._sync_steps()
        self._bind_tree_wheel(self._scroll_inner)
        self._file_drop = WinFileDrop(self, self._on_files_dropped)
        self.after(120, self._install_drop)
        self.after(80, self._use_dark_titlebar)
        self.title(app_window_title() + TITLE_SUFFIX)

    def _install_drop(self) -> None:
        if not self.winfo_exists() or self._file_drop.installed:
            return
        if self._file_drop.install():
            self._write_log("試験UI：PDFは上の枠へドロップするか、クリックして選べます。")

    def _use_dark_titlebar(self) -> None:
        if os.name != "nt" or not self.winfo_exists():
            return
        try:
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id()) or self.winfo_id()
            value = ctypes.c_int(1)
            for attr in (20, 19):
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    attr,
                    ctypes.byref(value),
                    ctypes.sizeof(value),
                )
        except Exception:
            return

    def _on_scroll_inner(self, _event: tk.Event) -> None:
        self._scroll.configure(scrollregion=self._scroll.bbox("all"))

    def _on_scroll_canvas(self, event: tk.Event) -> None:
        self._scroll.itemconfigure(self._scroll_win, width=event.width)

    def _on_preview_wheel(self, event: tk.Event) -> str:
        self._scroll.yview_scroll(int(-event.delta / 120), "units")
        return "break"

    def _bind_tree_wheel(self, widget: tk.Widget) -> None:
        ident = id(widget)
        if ident not in self._wheel_bound:
            self._wheel_bound.add(ident)
            widget.bind("<MouseWheel>", self._on_preview_wheel)
        for child in widget.winfo_children():
            self._bind_tree_wheel(child)

    def _card(self, title: str, subtitle: str = "", parent: tk.Widget | None = None) -> tk.Frame:
        outer = tk.Frame(parent or self._scroll_inner, bg=BG)
        outer.pack(fill="x", pady=(0, 8))
        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0, bd=0)
        canvas.pack(fill="x")
        body = tk.Frame(canvas, bg=CARD)
        window_id = canvas.create_window(0, 0, window=body, anchor="nw")

        def layout(_event: tk.Event | None = None) -> None:
            if not canvas.winfo_exists() or getattr(canvas, "_laying", False):
                return
            canvas._laying = True
            try:
                width = canvas.winfo_width()
                if width < 40:
                    return
                inset = 16
                canvas.itemconfigure(window_id, width=max(width - inset * 2, 10))
                body.update_idletasks()
                height = max(body.winfo_reqheight() + inset * 2, 48)
                canvas.coords(window_id, inset, inset)
                if int(float(canvas.cget("height"))) != int(height):
                    canvas.configure(height=height)
                canvas.delete("shape")
                _draw_round_rect(canvas, 1, 1, width - 2, height - 2, inset, fill=CARD, outline="")
                canvas.tag_lower("shape")
            finally:
                canvas._laying = False

        body.bind("<Configure>", layout)
        canvas.bind("<Configure>", layout)
        tk.Label(body, text=title, bg=CARD, fg=TEXT, font=(FONT, 14, "bold"), anchor="w").pack(anchor="w")
        if subtitle:
            tk.Label(
                body,
                text=subtitle,
                bg=CARD,
                fg=TEXT_DIM,
                font=(FONT, 10),
                anchor="w",
                justify="left",
                wraplength=400,
            ).pack(anchor="w", pady=(4, 0))
        return body

    def _build_header(self, parent: tk.Frame) -> None:
        header = tk.Frame(parent, bg=BG)
        header.pack(fill="x")
        title_row = tk.Frame(header, bg=BG)
        title_row.pack(fill="x")
        tk.Label(
            title_row,
            text=APP_DISPLAY_NAME,
            bg=BG,
            fg=TEXT,
            font=(FONT, 22, "bold"),
        ).pack(side="left", anchor="w")
        ver = f"ver.{APP_VERSION}"
        if IS_SPECIAL_EDITION:
            ver = f"{EDITION_LABEL}   {ver}"
        tk.Label(title_row, text=ver, bg=BG, fg=TEXT_DIM, font=(FONT, 12)).pack(
            side="left", anchor="s", padx=(12, 0), pady=(0, 4)
        )
        self._build_info_button(title_row).pack(side="right", anchor="ne")
        self.switch_ui_button = PillButton(
            title_row, "UI切替（いつもの画面へ）", self._switch_ui, canvas_bg=BG
        )
        self.switch_ui_button.pack(side="right", anchor="ne", padx=(0, 8))
        tk.Label(
            header,
            text="試験用の画面です。右上の［UI切替］でいつもの画面に戻せます。",
            bg=BG,
            fg=TEXT_MUTED,
            font=(FONT, 10),
            anchor="w",
        ).pack(anchor="w", pady=(6, 0))

    def _build_steps(self, parent: tk.Frame) -> None:
        bar = tk.Frame(parent, bg=BG)
        bar.pack(fill="x", pady=(14, 0))
        self._step_labels: list[tk.Label] = []
        names = ("1   ファイル", "2   条件", "3   実行")
        for index, name in enumerate(names):
            if index:
                tk.Label(bar, text=">", bg=BG, fg=TEXT_MUTED, font=(FONT, 12)).pack(side="left", padx=8)
            label = tk.Label(bar, text=name, bg=BG, fg=TEXT_MUTED, font=(FONT, 12, "bold"))
            label.pack(side="left")
            self._step_labels.append(label)

    def _sync_steps(self) -> None:
        if not getattr(self, "_step_labels", None):
            return
        has_pdf = bool(self.pdf_var.get().strip())
        if self._is_running:
            states = ("done", "done", "now")
        elif has_pdf:
            states = ("done", "now", "wait")
        else:
            states = ("now", "wait", "wait")
        colors = {"done": TEXT, "now": ACCENT, "wait": TEXT_MUTED}
        for label, state in zip(self._step_labels, states):
            label.configure(fg=colors[state])
        if getattr(self, "_run_dot", None) is not None:
            self._run_dot.configure(fg=ACCENT if self._is_running else "#30d158")

    def _on_pdf_changed(self, *_args) -> None:
        self._sync_drop()
        self._sync_steps()

    def _build_type_card(self) -> None:
        body = self._card("作成タイプ", "48回と36回はここで切り替えます。24回は個別の見積だけ、別の窓で作ります。", self._col_left)
        Segmented(
            body,
            self.installment_mode_var,
            [("48", "通常（48回）"), ("36", "36回割賦")],
            self._on_installment_mode_changed,
            bg=CARD,
        ).pack(anchor="w", pady=(12, 0))
        row = tk.Frame(body, bg=CARD)
        row.pack(fill="x", pady=(12, 0))
        tk.Label(row, text="24回割賦", bg=CARD, fg=TEXT, font=(FONT, 11)).pack(side="left")
        PillButton(
            row,
            "個別作成を開く",
            lambda: self._open_individual_window(24),
            canvas_bg=CARD,
        ).pack(side="right")
        tk.Label(
            body,
            text=(
                "出力先  48回  output/"
                + QUOTE_OUTPUT_DIRNAME
                + "    36回  output/"
                + QUOTE_OUTPUT_DIRNAME_36
                + "    24回  output/"
                + QUOTE_OUTPUT_DIRNAME_24
            ),
            bg=CARD,
            fg=TEXT_MUTED,
            font=(FONT, 9),
            anchor="w",
            justify="left",
            wraplength=400,
        ).pack(anchor="w", pady=(10, 0))
        if IS_SPECIAL_EDITION:
            tk.Label(
                body,
                text=f"このパッケージは{EDITION_LABEL}です。一括は通常ルール、個別だけ制限を外しています。",
                bg=CARD,
                fg=WARN,
                font=(FONT, 10),
                anchor="w",
                justify="left",
                wraplength=400,
            ).pack(anchor="w", pady=(6, 0))

    def _build_file_card(self) -> None:
        body = self._card("ファイル", "機種代金表のPDFを読み取ります。", self._col_left)
        drop = tk.Frame(body, bg=CARD_SOFT, cursor="hand2", padx=16, pady=12)
        drop.pack(fill="x", pady=(12, 0))
        badge = tk.Label(drop, text="PDF", bg=CARD_SOFT, fg=ACCENT, font=(FONT, 11, "bold"))
        badge.pack()
        title = tk.Label(
            drop,
            textvariable=self.drop_title,
            bg=CARD_SOFT,
            fg=TEXT,
            font=(FONT, 13),
            wraplength=400,
            justify="center",
        )
        title.pack(pady=(8, 0))
        path = tk.Label(
            drop,
            textvariable=self.drop_path,
            bg=CARD_SOFT,
            fg=TEXT_MUTED,
            font=(FONT, 9),
            wraplength=400,
            justify="center",
        )
        path.pack(pady=(4, 0))
        self._drop_widgets = (drop, badge, title, path)
        for widget in self._drop_widgets:
            widget.bind("<Button-1>", lambda _e: self._choose_pdf())
            widget.bind("<Enter>", lambda _e: self._paint_drop(TRACK))
            widget.bind("<Leave>", lambda _e: self._paint_drop(CARD_SOFT))
        tools = tk.Frame(body, bg=CARD)
        tools.pack(fill="x", pady=(10, 0))
        PillButton(tools, "価格表フォルダを開く", self._open_price_folder, canvas_bg=CARD).pack(side="left")
        quote_row = tk.Frame(body, bg=CARD)
        quote_row.pack(fill="x", pady=(8, 0))
        self.individual_button = PillButton(
            quote_row,
            "個別見積作成",
            lambda: self._open_individual_window(48),
            canvas_bg=CARD,
        )
        self.individual_button.pack(side="left")
        self.individual36_button = PillButton(
            quote_row,
            "個別見積（36回）",
            lambda: self._open_individual_window(36),
            canvas_bg=CARD,
        )
        self.individual36_button.pack(side="left", padx=(8, 0))

    def _paint_drop(self, color: str) -> None:
        for widget in self._drop_widgets:
            widget.configure(bg=color)

    def _sync_drop(self) -> None:
        raw = self.pdf_var.get().strip()
        if not raw:
            self.drop_title.set("PDFをドロップ、またはクリックして選択")
            if self.installment_mode_var.get() == "36":
                self.drop_path.set("36回は「機種代金一覧表 / 36回割賦」のPDFを使います")
            else:
                self.drop_path.set("「機種代金一覧表」フォルダのPDF、または選んだPDFを使います")
            return
        path = Path(raw)
        self.drop_title.set(path.name)
        self.drop_path.set(str(path).replace(chr(92), "/"))

    def _on_files_dropped(self, paths: list[str]) -> None:
        pdfs = [item for item in paths if item.lower().endswith(".pdf")]
        if not pdfs:
            self._write_log("PDF以外は受け取れませんでした。")
            self.status_var.set("ドロップされたファイルはPDFではありません。")
            return
        self.pdf_var.set(pdfs[0])
        self._write_log("ファイルを受け取りました：" + Path(pdfs[0]).name)
        if len(pdfs) > 1:
            self._write_log("複数ドロップされたため、先頭のPDFだけを使います。")

    def _build_condition_card(self) -> None:
        body = self._card("条件", "プランやSB光は、いままでのルールで自動で分かれます。", self._col_right)
        if not FORCED_DEPARTMENT:
            dep = tk.Frame(body, bg=CARD)
            dep.pack(fill="x", pady=(12, 0))
            tk.Label(dep, text="見積書に表示する部署", bg=CARD, fg=TEXT_DIM, font=(FONT, 10)).pack(anchor="w")
            choices = list(self.departments) or [self.department_var.get() or "TM"]
            current = self.department_var.get()
            if current and current not in choices:
                choices.insert(0, current)
            menu = tk.OptionMenu(dep, self.department_var, *choices)
            menu.configure(
                bg=TRACK,
                fg=TEXT,
                activebackground=ACCENT,
                activeforeground=WHITE,
                relief="flat",
                highlightthickness=0,
                font=(FONT, 11),
            )
            menu["menu"].configure(bg=CARD, fg=TEXT, activebackground=ACCENT, font=(FONT, 11))
            menu.pack(anchor="w", pady=(4, 0))
            tk.Label(
                body,
                text="見積の右上に出ます。",
                bg=CARD,
                fg=TEXT_MUTED,
                font=(FONT, 9),
                anchor="w",
                justify="left",
                wraplength=400,
            ).pack(anchor="w", pady=(4, 0))

        self._toggle_row(body, "値段が変わっていない機種も、もう一度すべて作り直す", self.force_all_var, "オフのときは、値段が変わった機種だけ作り直します。最初の1回は、オンでもオフでも全部作ります。")
        picker = tk.Frame(body, bg=CARD)
        picker.pack(fill="x", pady=(14, 0))
        self.exclude_button = PillButton(
            picker,
            "作成する機種",
            self._open_exclude_window,
            kind="primary",
            canvas_bg=CARD,
        )
        self.exclude_button.pack(side="left")
        tk.Label(
            picker,
            textvariable=self.exclude_status_var,
            bg=CARD,
            fg=WARN,
            font=(FONT, 10),
            anchor="w",
            justify="left",
            wraplength=280,
        ).pack(side="left", padx=(12, 0))

        toggle_head = tk.Frame(body, bg=CARD, cursor="hand2")
        toggle_head.pack(fill="x", pady=(16, 0))
        self._chevron = tk.StringVar(value="詳細設定")
        chevron = tk.Label(
            toggle_head,
            textvariable=self._chevron,
            bg=CARD,
            fg=TEXT,
            font=(FONT, 12, "bold"),
            cursor="hand2",
        )
        chevron.pack(side="left")
        hint = tk.Label(
            toggle_head,
            text="事務手数料・ライトプラン・IPS など",
            bg=CARD,
            fg=TEXT_MUTED,
            font=(FONT, 10),
            cursor="hand2",
        )
        hint.pack(side="left", padx=(10, 0))
        for widget in (toggle_head, chevron, hint):
            widget.bind("<Button-1>", lambda _e: self._toggle_details())

        self._details = tk.Frame(body, bg=CARD)
        self._toggle_row(self._details, "事務手数料あり（税抜4,500円）版も作成", self.standard_fee_var)
        self._toggle_row(self._details, "通常IPSプランも作成", self.upfront_var)
        mode = tk.Frame(self._details, bg=CARD)
        mode.pack(anchor="w", padx=(8, 0), pady=(8, 0))
        Segmented(
            mode,
            self.upfront_mode_var,
            [("lump", "一括表記"), ("monthly_as_running", "ランニングコスト表記")],
            None,
            bg=CARD,
        ).pack(anchor="w")
        self._toggle_row(self._details, "新規／MNPでもスーパー／ハイパー（IRSあり・割引セット）を作成", self.mnp_shinki_irs_var)
        self._toggle_row(self._details, "ライトプランも作成（IRSなし）", self.light_plan_var, "PDFの枚数と処理時間が、かなり増えることがあります。", hint_color=DANGER)
        self._toggle_row(self._details, "IPSなしの特別対応版も作成", self.no_ips_var)

    def _toggle_row(
        self,
        parent: tk.Frame,
        title: str,
        variable: tk.BooleanVar,
        hint: str = "",
        hint_color: str = TEXT_MUTED,
    ) -> None:
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x", pady=(12, 0))
        text = tk.Frame(row, bg=CARD)
        text.pack(side="left", fill="x", expand=True)
        tk.Label(
            text,
            text=title,
            bg=CARD,
            fg=TEXT,
            font=(FONT, 11),
            anchor="w",
            justify="left",
            wraplength=340,
        ).pack(anchor="w")
        if hint:
            tk.Label(
                text,
                text=hint,
                bg=CARD,
                fg=hint_color,
                font=(FONT, 9),
                anchor="w",
                justify="left",
                wraplength=340,
            ).pack(anchor="w", pady=(2, 0))
        Toggle(row, variable, bg=CARD).pack(side="right", anchor="n", padx=(12, 0))

    def _toggle_details(self) -> None:
        self._details_open = not self._details_open
        if self._details_open:
            self._details.pack(fill="x", pady=(4, 0))
            self._chevron.set("詳細設定を閉じる")
        else:
            self._details.pack_forget()
            self._chevron.set("詳細設定")
        self.update_idletasks()
        self._bind_tree_wheel(self._scroll_inner)
        self._scroll.configure(scrollregion=self._scroll.bbox("all"))

    def _build_run_card(self) -> None:
        body = self._card("実行", "途中で止めて、あとから続けます。", self._col_right)
        row = tk.Frame(body, bg=CARD)
        row.pack(fill="x", pady=(12, 0))
        self.run_button = PillButton(row, "見積もりを作成", self._start, kind="primary", canvas_bg=CARD)
        self.run_button.pack(side="left")
        self.cancel_button = PillButton(row, "中断", self._cancel_batch, canvas_bg=CARD)
        self.cancel_button.pack(side="left", padx=(8, 0))
        self.cancel_button.configure(state="disabled")
        self.resume_button = PillButton(row, "再開", self._resume_batch, canvas_bg=CARD)
        self.resume_button.pack(side="left", padx=(8, 0))
        self.resume_button.configure(state="disabled")

        nav = tk.Frame(body, bg=CARD)
        nav.pack(fill="x", pady=(8, 0))
        PillButton(nav, "出力フォルダを開く", self._open_output_folder, canvas_bg=CARD).pack(side="left")

    def _build_log(self, parent: tk.Frame) -> None:
        self.progress = LineProgress(parent, bg=BG)
        self.progress.pack(fill="x", pady=(0, 6))
        tk.Label(
            parent,
            textvariable=self.status_var,
            bg=BG,
            fg=TEXT_DIM,
            font=(FONT, 10),
            anchor="w",
            justify="left",
            wraplength=860,
        ).pack(anchor="w", pady=(0, 6))
        head = tk.Frame(parent, bg=LOG_BG)
        head.pack(fill="x")
        self._run_dot = tk.Label(head, text="*", bg=LOG_BG, fg="#30d158", font=(FONT, 9))
        self._run_dot.pack(side="left", padx=(12, 4), pady=6)
        tk.Label(head, text="ログ", bg=LOG_BG, fg=TEXT_DIM, font=(FONT, 10)).pack(side="left")
        self.log = tk.Text(
            parent,
            height=3,
            bg=LOG_BG,
            fg="#d1d1d6",
            insertbackground=TEXT,
            relief="flat",
            highlightthickness=0,
            bd=0,
            font=(FONT, 10),
            padx=12,
            pady=4,
            wrap="word",
        )
        self.log.pack(fill="x")
        self.log.configure(state="disabled")


if __name__ == "__main__":
    run_app(UI_PREVIEW)

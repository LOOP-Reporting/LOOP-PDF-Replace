import os
import sys
import json
import tempfile
import fitz
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_NAME = "Loop PDF Replace All"
BRAND = "Loop Structural Automation"
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".loop_pdf_replace_all.json")


def resource_path(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
    except Exception:
        pass


# --------------------------------------------------------------------------
# Core PDF logic (unchanged behaviour)
# --------------------------------------------------------------------------
def replace_pdf(src, dst, pairs, progress_cb=None):
    doc = fitz.open(src)
    counts = {old: 0 for old, _ in pairs}
    total_pages = len(doc)
    for page_index, page in enumerate(doc):
        for old, new in pairs:
            if not old:
                continue
            rects = page.search_for(old)
            if not rects:
                continue

            font_size = 8.0
            try:
                data = page.get_text("dict")
                found = False
                for block in data.get("blocks", []):
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            if old in span.get("text", ""):
                                font_size = float(span.get("size", 8.0))
                                found = True
                                break
                        if found:
                            break
                    if found:
                        break
            except Exception:
                pass

            for rect in rects:
                page.add_redact_annot(rect, fill=(1, 1, 1))
            page.apply_redactions()

            for rect in rects:
                y = rect.y1 - max(1.5, font_size * 0.18)
                page.insert_text(
                    (rect.x0, y),
                    new,
                    fontsize=font_size,
                    fontname="helv",
                    color=(0, 0, 0),
                    overlay=True
                )
                counts[old] += 1

        if progress_cb:
            progress_cb(page_index + 1, total_pages)

    # Save to a temporary file in the destination folder first, then swap it
    # into place. This works whether dst is a brand-new file or the same
    # path as src ("overwrite original") — PyMuPDF only allows saving over
    # the currently-open file using an incremental save, which is
    # incompatible with the garbage-collection/compression options below.
    # Writing to a temp file and replacing sidesteps that restriction
    # safely for both cases.
    dst_dir = os.path.dirname(os.path.abspath(dst)) or "."
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".pdf", dir=dst_dir)
    os.close(tmp_fd)
    try:
        doc.save(tmp_path, garbage=4, deflate=True)
    finally:
        doc.close()
    os.replace(tmp_path, dst)
    return counts


# --------------------------------------------------------------------------
# Theme definitions
# --------------------------------------------------------------------------
LIGHT = {
    "bg": "#f4f5f7",
    "surface": "#ffffff",
    "surface_alt": "#f8f9fb",
    "border": "#e2e5ea",
    "text": "#14181f",
    "text_muted": "#6b7280",
    "text_faint": "#98a0ab",
    "accent": "#2563eb",
    "accent_hover": "#1d4ed8",
    "accent_soft": "#e8effe",
    "danger": "#e5484d",
    "danger_hover": "#c43e42",
    "danger_soft": "#fdecec",
    "success": "#1a9d5c",
    "input_bg": "#ffffff",
    "input_border": "#d8dce2",
    "input_focus": "#2563eb",
    "header_bg": "#ffffff",
    "status_bg": "#ffffff",
    "shadow": "#e6e8ec",
    "track_off": "#d5d9e0",
    "track_on": "#2563eb",
    "knob": "#ffffff",
    "row_alt": "#fafbfd",
}

DARK = {
    "bg": "#14161c",
    "surface": "#1c1f27",
    "surface_alt": "#20232c",
    "border": "#2b2f3a",
    "text": "#eef0f4",
    "text_muted": "#9aa1ae",
    "text_faint": "#6b7280",
    "accent": "#4d8dff",
    "accent_hover": "#6fa1ff",
    "accent_soft": "#1f2a41",
    "danger": "#f2666b",
    "danger_hover": "#f68387",
    "danger_soft": "#33191c",
    "success": "#37c07f",
    "input_bg": "#20232c",
    "input_border": "#343947",
    "input_focus": "#4d8dff",
    "header_bg": "#1c1f27",
    "status_bg": "#1c1f27",
    "shadow": "#0e1015",
    "track_off": "#3a3f4c",
    "track_on": "#4d8dff",
    "knob": "#ffffff",
    "row_alt": "#20232c",
}


class ToggleSwitch(tk.Canvas):
    """A small pill-shaped animated theme toggle (sun / moon)."""

    def __init__(self, parent, app, width=54, height=28, **kw):
        super().__init__(parent, width=width, height=height,
                          highlightthickness=0, bd=0, cursor="hand2", **kw)
        self.app = app
        self.w = width
        self.h = height
        self.bind("<Button-1>", lambda e: self.app.toggle_theme())
        self.draw()

    def draw(self):
        t = self.app.theme
        self.configure(bg=t["surface"])
        self.delete("all")
        is_dark = self.app.dark_mode
        track_color = t["track_on"] if is_dark else t["track_off"]
        r = self.h / 2
        self.create_oval(0, 0, self.h, self.h, fill=track_color, outline="")
        self.create_rectangle(r, 0, self.w - r, self.h, fill=track_color, outline="")
        self.create_oval(self.w - self.h, 0, self.w, self.h, fill=track_color, outline="")

        pad = 3
        knob_d = self.h - pad * 2
        knob_x = (self.w - knob_d - pad) if is_dark else pad
        self.create_oval(knob_x, pad, knob_x + knob_d, pad + knob_d,
                          fill=t["knob"], outline="")
        icon = "🌙" if is_dark else "☀"
        icon_x = knob_x + knob_d / 2
        self.create_text(icon_x, self.h / 2, text=icon, font=("Segoe UI", 10))


class HoverButton(tk.Button):
    """A flat button with hover/press colors driven by the current theme."""

    def __init__(self, parent, bg, hover, fg="white", active_fg=None, **kw):
        self._bg = bg
        self._hover = hover
        super().__init__(
            parent, bg=bg, fg=fg, activebackground=hover,
            activeforeground=active_fg or fg, relief="flat", bd=0,
            cursor="hand2", highlightthickness=0, **kw
        )
        self.bind("<Enter>", lambda e: self.config(bg=self._hover))
        self.bind("<Leave>", lambda e: self.config(bg=self._bg))

    def restyle(self, bg, hover, fg="white"):
        self._bg = bg
        self._hover = hover
        self.config(bg=bg, fg=fg, activebackground=hover)


def _rounded_rect(canvas, x0, y0, x1, y1, r, **kw):
    points = [
        x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r,
        x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1,
        x0, y1, x0, y1 - r, x0, y0 + r, x0, y0,
    ]
    return canvas.create_polygon(points, smooth=True, **kw)


class IconButton(tk.Canvas):
    """A small bordered square button with a hand-drawn vector icon
    (trash / chevron-up / chevron-down) that always renders crisply,
    independent of the system's emoji/symbol font coverage."""

    def __init__(self, parent, app, kind, command, size=32, **kw):
        super().__init__(parent, width=size, height=size,
                          highlightthickness=0, bd=0, cursor="hand2", **kw)
        self.app = app
        self.kind = kind
        self.command = command
        self.size = size
        self._hover = False
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.redraw()

    def _on_click(self, _event):
        if str(self.cget("state")) == "disabled":
            return
        self.command()

    def _on_enter(self, _event):
        self._hover = True
        self.redraw()

    def _on_leave(self, _event):
        self._hover = False
        self.redraw()

    def redraw(self):
        t = self.app.theme
        try:
            parent_bg = self.master.cget("bg")
        except Exception:
            parent_bg = t["surface"]
        self.configure(bg=parent_bg)
        self.delete("all")

        s = self.size
        pad = 2.5
        is_delete = self.kind == "delete"

        if is_delete:
            border = t["danger"] if self._hover else t["border"]
            fill = t["danger_soft"] if self._hover else parent_bg
            icon_color = t["danger"]
        else:
            border = t["input_focus"] if self._hover else t["border"]
            fill = t["surface_alt"] if self._hover else parent_bg
            icon_color = t["text"] if self._hover else t["text_muted"]

        _rounded_rect(self, pad, pad, s - pad, s - pad, 7,
                      outline=border, fill=fill, width=1.3)

        cx, cy = s / 2, s / 2
        if self.kind == "up":
            self.create_line(cx - 5, cy + 3, cx, cy - 4, cx + 5, cy + 3,
                              fill=icon_color, width=2, capstyle="round",
                              joinstyle="round", smooth=False)
        elif self.kind == "down":
            self.create_line(cx - 5, cy - 3, cx, cy + 4, cx + 5, cy - 3,
                              fill=icon_color, width=2, capstyle="round",
                              joinstyle="round", smooth=False)
        elif is_delete:
            self.create_line(cx - 6, cy - 5, cx + 6, cy - 5,
                              fill=icon_color, width=2, capstyle="round")
            self.create_line(cx - 2.5, cy - 7.5, cx + 2.5, cy - 7.5,
                              fill=icon_color, width=2, capstyle="round")
            self.create_rectangle(cx - 5, cy - 4, cx + 5, cy + 7,
                                   outline=icon_color, width=1.5)
            self.create_line(cx - 2, cy - 1.5, cx - 2, cy + 5,
                              fill=icon_color, width=1.2)
            self.create_line(cx + 2, cy - 1.5, cx + 2, cy + 5,
                              fill=icon_color, width=1.2)


class App:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("1080x780")
        self.root.minsize(920, 640)

        cfg = load_config()
        self.dark_mode = bool(cfg.get("dark_mode", False))
        self.theme = DARK if self.dark_mode else LIGHT

        self.pdf_var = tk.StringVar(value="")
        self.output_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Ready")
        self.rows = []
        self._themed_widgets = []   # (widget, kind) registered for live re-theming
        self._buttons = []          # HoverButton instances registered for re-theming
        self._icon_buttons = []     # IconButton (row action) instances registered for re-theming

        self.setup_style()
        self.build_ui()
        self.apply_theme()

        self.add_row("Engg_1", "Engg_II")
        for _ in range(4):
            self.add_row()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ------------------------------------------------------------------
    # Theming
    # ------------------------------------------------------------------
    def setup_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        self.ttk_style = style

    def register(self, widget, kind, **extra):
        """kind: 'frame_bg', 'label_bg', 'label_muted', 'label_faint', 'entry', 'card'"""
        self._themed_widgets.append((widget, kind, extra))

    def register_button(self, btn, variant="primary"):
        self._buttons.append((btn, variant))

    def apply_theme(self):
        t = self.theme
        self.root.configure(bg=t["bg"])

        style = self.ttk_style
        style.configure("TEntry",
                         fieldbackground=t["input_bg"],
                         foreground=t["text"],
                         bordercolor=t["input_border"],
                         lightcolor=t["input_border"],
                         darkcolor=t["input_border"],
                         insertcolor=t["text"],
                         padding=6)
        style.map("TEntry",
                  bordercolor=[("focus", t["input_focus"])],
                  lightcolor=[("focus", t["input_focus"])],
                  darkcolor=[("focus", t["input_focus"])])

        style.configure("TRadiobutton",
                         background=t["surface"],
                         foreground=t["text"],
                         font=("Segoe UI", 10))
        style.map("TRadiobutton", background=[("active", t["surface"])])

        style.configure("TCheckbutton",
                         background=t["surface"],
                         foreground=t["text"])

        style.configure("TScrollbar", background=t["surface_alt"],
                         troughcolor=t["bg"], bordercolor=t["border"],
                         arrowcolor=t["text_muted"])

        style.configure("TProgressbar", background=t["accent"],
                         troughcolor=t["surface_alt"], bordercolor=t["border"])

        for widget, kind, extra in self._themed_widgets:
            try:
                if kind == "frame_bg":
                    widget.configure(bg=t["bg"])
                elif kind == "surface":
                    widget.configure(bg=t["surface"])
                elif kind == "surface_alt":
                    widget.configure(bg=t["surface_alt"])
                elif kind == "border_frame":
                    widget.configure(bg=t["border"])
                elif kind == "label_title":
                    widget.configure(bg=extra.get("parentbg", t["surface"]), fg=t["text"])
                elif kind == "label_muted":
                    widget.configure(bg=extra.get("parentbg", t["surface"]), fg=t["text_muted"])
                elif kind == "label_faint":
                    widget.configure(bg=extra.get("parentbg", t["surface"]), fg=t["text_faint"])
                elif kind == "canvas_card":
                    widget.configure(bg=t["surface"], highlightbackground=t["border"],
                                      highlightcolor=t["border"])
                elif kind == "row_num":
                    idx = extra.get("index", 0)
                    bg = t["row_alt"] if idx % 2 else t["surface"]
                    widget.configure(bg=bg, fg=t["text_faint"])
                elif kind == "row_frame":
                    idx = extra.get("index", 0)
                    bg = t["row_alt"] if idx % 2 else t["surface"]
                    widget.configure(bg=bg)
                elif kind == "status_bar":
                    widget.configure(bg=t["status_bg"])
                elif kind == "status_text":
                    widget.configure(bg=t["status_bg"], fg=t["text_muted"])
            except Exception:
                pass

        for btn, variant in self._buttons:
            try:
                if variant == "primary":
                    btn.restyle(t["accent"], t["accent_hover"], "#ffffff")
                elif variant == "danger":
                    btn.restyle(t["danger_soft"], t["danger"], t["danger"])
                elif variant in ("ghost", "neutral"):
                    btn.restyle(t["surface_alt"], t["border"], t["text"])
            except Exception:
                pass

        for ibtn in self._icon_buttons:
            try:
                ibtn.redraw()
            except Exception:
                pass

        if hasattr(self, "toggle"):
            self.toggle.draw()
        if hasattr(self, "header"):
            self.header.configure(bg=t["header_bg"])
        if hasattr(self, "logo_holder"):
            self.logo_holder.configure(bg=t["header_bg"])
        if hasattr(self, "title_frame"):
            self.title_frame.configure(bg=t["header_bg"])
        if hasattr(self, "help_box"):
            self.help_box.configure(bg=t["header_bg"])
        if hasattr(self, "theme_wrap"):
            self.theme_wrap.configure(bg=t["header_bg"])
        if hasattr(self, "divider"):
            self.divider.configure(bg=t["border"])
        if hasattr(self, "app_title_lbl"):
            self.app_title_lbl.configure(bg=t["header_bg"], fg=t["text"])
        if hasattr(self, "app_sub_lbl"):
            self.app_sub_lbl.configure(bg=t["header_bg"], fg=t["text_muted"])
        if hasattr(self, "brand_lbl"):
            self.brand_lbl.configure(bg=t["header_bg"], fg=t["accent"])
        if hasattr(self, "theme_label"):
            self.theme_label.configure(bg=t["header_bg"], fg=t["text_faint"])

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.theme = DARK if self.dark_mode else LIGHT
        save_config({"dark_mode": self.dark_mode})
        self.apply_theme()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def card(self, parent, title, subtitle=None):
        """A themed 'card' section with a title row, returns the inner content frame."""
        t = self.theme
        outer = tk.Frame(parent, bg=t["bg"])
        card = tk.Frame(outer, bg=t["surface"], highlightthickness=1,
                         highlightbackground=t["border"], highlightcolor=t["border"])
        card.pack(fill="both", expand=True)
        self.register(card, "canvas_card")

        head = tk.Frame(card, bg=t["surface"])
        head.pack(fill="x", padx=18, pady=(14, 6))
        self.register(head, "surface")
        lbl = tk.Label(head, text=title, font=("Segoe UI", 11, "bold"),
                        bg=t["surface"], fg=t["text"])
        lbl.pack(anchor="w")
        self.register(lbl, "label_title")
        if subtitle:
            sub = tk.Label(head, text=subtitle, font=("Segoe UI", 9),
                            bg=t["surface"], fg=t["text_faint"])
            sub.pack(anchor="w")
            self.register(sub, "label_faint")

        body = tk.Frame(card, bg=t["surface"])
        body.pack(fill="both", expand=True, padx=18, pady=(0, 16))
        self.register(body, "surface")
        return outer, body

    def build_ui(self):
        t = self.theme

        # ---------------- Header ----------------
        self.header = tk.Frame(self.root, bg=t["header_bg"], height=118)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)

        self.logo_holder = tk.Frame(self.header, bg=t["header_bg"], width=250)
        self.logo_holder.pack(side="left", fill="y", padx=(24, 12), pady=12)
        self.logo_holder.pack_propagate(False)

        try:
            self.logo = tk.PhotoImage(file=resource_path("loop_logo.png"))
            # Logo ships pre-sized with a transparent background, so it
            # blends into the header regardless of light/dark theme.
            # Scale down only if it's noticeably larger than the header slot.
            target_h = 88
            if self.logo.height() > target_h * 1.6:
                factor = max(1, round(self.logo.height() / target_h))
                self.logo = self.logo.subsample(factor, factor)
            logo_lbl = tk.Label(self.logo_holder, image=self.logo, bg=t["header_bg"], bd=0)
            logo_lbl.pack(anchor="w", expand=True)
            self.register(logo_lbl, "surface")
        except Exception:
            self.brand_lbl = tk.Label(
                self.logo_holder, text="LOOP",
                font=("Segoe UI", 24, "bold"),
                bg=t["header_bg"], fg=t["accent"]
            )
            self.brand_lbl.pack(anchor="w", expand=True)

        self.divider = tk.Frame(self.header, bg=t["border"], width=1)
        self.divider.pack(side="left", fill="y", pady=20)

        self.title_frame = tk.Frame(self.header, bg=t["header_bg"])
        self.title_frame.pack(side="left", fill="both", expand=True, padx=24)
        self.app_title_lbl = tk.Label(
            self.title_frame, text="PDF Replace All",
            font=("Segoe UI", 22, "bold"),
            bg=t["header_bg"], fg=t["text"]
        )
        self.app_title_lbl.pack(anchor="w", pady=(28, 0))
        self.app_sub_lbl = tk.Label(
            self.title_frame, text="Find and replace multiple texts across an entire PDF",
            font=("Segoe UI", 10), bg=t["header_bg"], fg=t["text_muted"]
        )
        self.app_sub_lbl.pack(anchor="w", pady=(4, 0))

        self.help_box = tk.Frame(self.header, bg=t["header_bg"])
        self.help_box.pack(side="right", padx=24)

        self.theme_wrap = tk.Frame(self.help_box, bg=t["header_bg"])
        self.theme_wrap.pack(side="left", padx=(0, 16))
        self.theme_label = tk.Label(self.theme_wrap, text="Theme", font=("Segoe UI", 9),
                                     bg=t["header_bg"], fg=t["text_faint"])
        self.theme_label.pack()
        self.toggle = ToggleSwitch(self.theme_wrap, self)
        self.toggle.pack(pady=(2, 0))

        about_btn = self.make_pill_button(self.help_box, "i  About", self.about, variant="ghost")
        about_btn.pack(side="left", padx=4)
        help_btn = self.make_pill_button(self.help_box, "?  Help", self.help, variant="ghost")
        help_btn.pack(side="left", padx=4)

        # ---------------- Main scroll area ----------------
        main_outer = tk.Frame(self.root, bg=t["bg"])
        main_outer.pack(fill="both", expand=True)
        self.register(main_outer, "frame_bg")

        canvas = tk.Canvas(main_outer, bg=t["bg"], highlightthickness=0)
        vscroll = ttk.Scrollbar(main_outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vscroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        main = tk.Frame(canvas, bg=t["bg"])
        self.register(main, "frame_bg")
        win_id = canvas.create_window((0, 0), window=main, anchor="nw")

        def on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(win_id, width=event.width)
        canvas.bind("<Configure>", on_configure)
        main.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        def on_mousewheel(event):
            delta = -1 * (event.delta // 120) if event.delta else 0
            canvas.yview_scroll(delta, "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        # ----- Section 1: Select PDF -----
        sec1_outer, sec1_body = self.card(main, "1. Select PDF File",
                                           "Choose the PDF you want to update")
        sec1_outer.pack(fill="x", padx=22, pady=(20, 12))

        pdf_row = tk.Frame(sec1_body, bg=t["surface"])
        pdf_row.pack(fill="x")
        self.register(pdf_row, "surface")
        self.pdf_entry = ttk.Entry(pdf_row, textvariable=self.pdf_var, font=("Segoe UI", 10))
        self.pdf_entry.pack(side="left", fill="x", expand=True, ipady=8)
        browse_pdf_btn = self.make_pill_button(pdf_row, "Browse PDF", self.browse_pdf, variant="neutral")
        browse_pdf_btn.pack(side="left", padx=(10, 6))
        self.open_btn = self.make_pill_button(pdf_row, "Open PDF", self.open_pdf, variant="neutral")
        self.open_btn.pack(side="left")
        self.open_btn.config(state="disabled")

        self.selected_file_lbl = tk.Label(sec1_body, text="No file selected",
                                           font=("Segoe UI", 9), bg=t["surface"], fg=t["text_faint"])
        self.selected_file_lbl.pack(anchor="w", pady=(8, 0))
        self.register(self.selected_file_lbl, "label_faint")

        # ----- Section 2: Find & Replace entries -----
        sec2_outer, sec2_body = self.card(
            main, "2. Find and Replace Entries",
            "Add as many entries as you want — they run in order, top to bottom"
        )
        sec2_outer.pack(fill="both", expand=True, padx=22, pady=12)

        table_wrap = tk.Frame(sec2_body, bg=t["surface"], highlightthickness=1,
                               highlightbackground=t["border"])
        table_wrap.pack(fill="both", expand=True)
        self.register(table_wrap, "canvas_card")

        thead = tk.Frame(table_wrap, bg=t["surface_alt"])
        thead.pack(fill="x")
        self.register(thead, "surface_alt")
        num_h = tk.Label(thead, text="#", bg=t["surface_alt"], fg=t["text_muted"],
                          width=4, font=("Segoe UI", 9, "bold"))
        num_h.pack(side="left", pady=10)
        self.register(num_h, "label_muted", parentbg=t["surface_alt"])
        find_h = tk.Label(thead, text="FIND (text to search)", bg=t["surface_alt"],
                           fg=t["text_muted"], font=("Segoe UI", 9, "bold"))
        find_h.pack(side="left", fill="x", expand=True, pady=10)
        self.register(find_h, "label_muted", parentbg=t["surface_alt"])
        repl_h = tk.Label(thead, text="REPLACE WITH (new text)", bg=t["surface_alt"],
                           fg=t["text_muted"], font=("Segoe UI", 9, "bold"))
        repl_h.pack(side="left", fill="x", expand=True, pady=10)
        self.register(repl_h, "label_muted", parentbg=t["surface_alt"])
        act_h = tk.Label(thead, text="ACTIONS", bg=t["surface_alt"], fg=t["text_muted"],
                          width=16, font=("Segoe UI", 9, "bold"))
        act_h.pack(side="left", pady=10, padx=(0, 12))
        self.register(act_h, "label_muted", parentbg=t["surface_alt"])

        self.rows_frame = tk.Frame(table_wrap, bg=t["surface"])
        self.rows_frame.pack(fill="both", expand=True)
        self.register(self.rows_frame, "surface")

        add_bar = tk.Frame(sec2_body, bg=t["surface"])
        add_bar.pack(fill="x", pady=(12, 0))
        self.register(add_bar, "surface")
        add_btn = self.make_pill_button(add_bar, "+  Add Entry", lambda: self.add_row(), variant="ghost")
        add_btn.pack(side="left")
        clear_btn = self.make_pill_button(add_bar, "Clear All", self.clear_rows, variant="ghost")
        clear_btn.pack(side="left", padx=8)

        # ----- Section 3: Output + Action -----
        bottom = tk.Frame(main, bg=t["bg"])
        bottom.pack(fill="x", padx=22, pady=(0, 20))
        self.register(bottom, "frame_bg")

        out_outer, out_body = self.card(bottom, "3. Output Settings",
                                         "Choose how the result is saved")
        out_outer.pack(side="left", fill="both", expand=True, padx=(0, 14))

        mode_row = tk.Frame(out_body, bg=t["surface"])
        mode_row.pack(fill="x", pady=(0, 10))
        self.register(mode_row, "surface")
        mode_lbl = tk.Label(mode_row, text="Save As", font=("Segoe UI", 10, "bold"),
                             bg=t["surface"], fg=t["text"])
        mode_lbl.pack(side="left")
        self.register(mode_lbl, "label_title")
        self.mode_var = tk.StringVar(value="new")
        ttk.Radiobutton(mode_row, text="Create new file (recommended)",
                        variable=self.mode_var, value="new").pack(side="left", padx=(16, 12))
        ttk.Radiobutton(mode_row, text="Overwrite original file",
                        variable=self.mode_var, value="overwrite").pack(side="left")

        outrow = tk.Frame(out_body, bg=t["surface"])
        outrow.pack(fill="x")
        self.register(outrow, "surface")
        outfile_lbl = tk.Label(outrow, text="Output File", bg=t["surface"], fg=t["text_muted"],
                                font=("Segoe UI", 10))
        outfile_lbl.pack(side="left")
        self.register(outfile_lbl, "label_muted")
        ttk.Entry(outrow, textvariable=self.output_var).pack(
            side="left", fill="x", expand=True, padx=14, ipady=7
        )
        out_browse_btn = self.make_pill_button(outrow, "Browse", self.browse_output, variant="neutral")
        out_browse_btn.pack(side="left")

        action = tk.Frame(bottom, bg=t["bg"], width=270)
        action.pack(side="right", fill="y")
        action.pack_propagate(False)
        self.register(action, "frame_bg")

        self.replace_btn = HoverButton(
            action, bg=t["accent"], hover=t["accent_hover"],
            text="\u27F3   REPLACE ALL\nProcess entire PDF",
            command=self.run,
            font=("Segoe UI", 13, "bold"),
        )
        self.replace_btn.pack(fill="both", expand=True)
        self.register_button(self.replace_btn, "primary")

        self.progress = ttk.Progressbar(action, mode="determinate")
        # placed on demand during processing

        # ---------------- Status bar ----------------
        self.status = tk.Frame(self.root, bg=t["status_bg"], height=34)
        self.status.pack(fill="x", side="bottom")
        self.register(self.status, "status_bar")
        self.status_lbl = tk.Label(self.status, textvariable=self.status_var, bg=t["status_bg"],
                                    fg=t["text_muted"], anchor="w")
        self.status_lbl.pack(side="left", padx=18)
        self.register(self.status_lbl, "status_text")
        brand_status = tk.Label(self.status, text=f"By {BRAND}", bg=t["status_bg"],
                                 fg=t["text_muted"], anchor="e")
        brand_status.pack(side="right", padx=18)
        self.register(brand_status, "status_text")

    def make_pill_button(self, parent, text, command, variant="neutral"):
        t = self.theme
        if variant == "primary":
            bg, hover, fg = t["accent"], t["accent_hover"], "#ffffff"
        elif variant == "danger":
            bg, hover, fg = t["danger_soft"], t["danger"], t["danger"]
        else:  # neutral / ghost
            bg, hover, fg = t["surface_alt"], t["border"], t["text"]
        btn = HoverButton(parent, bg=bg, hover=hover, fg=fg,
                           text=text, command=command,
                           font=("Segoe UI", 10), padx=12, pady=7)
        self.register_button(btn, variant)
        return btn

    # ------------------------------------------------------------------
    # Rows
    # ------------------------------------------------------------------
    def add_row(self, old="", new=""):
        t = self.theme
        index = len(self.rows)
        bg = t["row_alt"] if index % 2 else t["surface"]

        row = tk.Frame(self.rows_frame, bg=bg, height=50)
        row.pack(fill="x")
        row.pack_propagate(False)
        self.register(row, "row_frame", index=index)

        num = tk.Label(row, text=str(index + 1), width=4, bg=bg, fg=t["text_faint"],
                        font=("Segoe UI", 9))
        num.pack(side="left")
        self.register(num, "row_num", index=index)

        find_var = tk.StringVar(value=old)
        repl_var = tk.StringVar(value=new)

        find_entry = ttk.Entry(row, textvariable=find_var, font=("Segoe UI", 10))
        repl_entry = ttk.Entry(row, textvariable=repl_var, font=("Segoe UI", 10))
        find_entry.pack(side="left", fill="x", expand=True, padx=(4, 6), pady=6, ipady=6)
        repl_entry.pack(side="left", fill="x", expand=True, padx=(0, 6), pady=6, ipady=6)

        actions = tk.Frame(row, bg=bg, width=150, height=50)
        actions.pack(side="left", padx=(0, 10))
        actions.pack_propagate(False)
        self.register(actions, "row_frame", index=index)

        del_btn = IconButton(actions, self, "delete",
                              command=lambda r=row: self.delete_row(r))
        del_btn.pack(side="left", padx=3, pady=9)
        self._icon_buttons.append(del_btn)

        up_btn = IconButton(actions, self, "up",
                             command=lambda r=row: self.move_row(r, -1))
        up_btn.pack(side="left", padx=3, pady=9)
        self._icon_buttons.append(up_btn)

        down_btn = IconButton(actions, self, "down",
                               command=lambda r=row: self.move_row(r, 1))
        down_btn.pack(side="left", padx=3, pady=9)
        self._icon_buttons.append(down_btn)

        self.rows.append({
            "row": row, "num": num, "find_var": find_var, "repl_var": repl_var,
            "actions": actions, "buttons": [del_btn, up_btn, down_btn]
        })
        self.renumber()

    def clear_rows(self):
        if not messagebox.askyesno(APP_NAME, "Remove all entries and start with a single blank row?"):
            return
        for item in self.rows:
            for b in item["buttons"]:
                if b in self._icon_buttons:
                    self._icon_buttons.remove(b)
            item["row"].destroy()
        self.rows = []
        self.add_row()

    def delete_row(self, row):
        if len(self.rows) <= 1:
            return
        for item in self.rows:
            if item["row"] is row:
                for b in item["buttons"]:
                    if b in self._icon_buttons:
                        self._icon_buttons.remove(b)
                row.destroy()
                self.rows.remove(item)
                break
        self.renumber()

    def move_row(self, row, direction):
        idx = next((i for i, x in enumerate(self.rows) if x["row"] is row), None)
        if idx is None:
            return
        new_idx = idx + direction
        if not 0 <= new_idx < len(self.rows):
            return
        self.rows[idx], self.rows[new_idx] = self.rows[new_idx], self.rows[idx]
        self.refresh_rows()

    def refresh_rows(self):
        for item in self.rows:
            item["row"].pack_forget()
        for item in self.rows:
            item["row"].pack(fill="x")
        self.renumber()

    def renumber(self):
        t = self.theme
        for i, item in enumerate(self.rows):
            item["num"].config(text=str(i + 1))
            bg = t["row_alt"] if i % 2 else t["surface"]
            item["row"].configure(bg=bg)
            item["num"].configure(bg=bg)
            item["actions"].configure(bg=bg)
            for w_idx, (widget, kind, extra) in enumerate(self._themed_widgets):
                if widget in (item["row"], item["num"], item["actions"]):
                    self._themed_widgets[w_idx] = (widget, kind, {"index": i})
            for b in item["buttons"]:
                b.redraw()

    # ------------------------------------------------------------------
    # File actions
    # ------------------------------------------------------------------
    def browse_pdf(self):
        p = filedialog.askopenfilename(
            title="Select PDF",
            filetypes=[("PDF files", "*.pdf")]
        )
        if p:
            self.pdf_var.set(p)
            base, ext = os.path.splitext(p)
            self.output_var.set(base + "_replaced.pdf")
            self.open_btn.config(state="normal")
            self.status_var.set("PDF selected")
            self.selected_file_lbl.config(text=os.path.basename(p))

    def browse_output(self):
        p = filedialog.asksaveasfilename(
            title="Save output PDF",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")]
        )
        if p:
            self.output_var.set(p)

    def open_pdf(self):
        p = self.pdf_var.get()
        if os.path.isfile(p):
            try:
                os.startfile(p)
            except AttributeError:
                import subprocess
                subprocess.Popen(["xdg-open", p])

    def get_pairs(self):
        pairs = []
        for item in self.rows:
            old = item["find_var"].get()
            new = item["repl_var"].get()
            if old.strip():
                pairs.append((old, new))
        return pairs

    def run(self):
        src = self.pdf_var.get().strip()
        if not os.path.isfile(src):
            messagebox.showwarning(APP_NAME, "Please select a PDF file first.")
            return

        pairs = self.get_pairs()
        if not pairs:
            messagebox.showwarning(APP_NAME, "Please enter at least one Find entry.")
            return

        if self.mode_var.get() == "overwrite":
            dst = src
        else:
            dst = self.output_var.get().strip()
            if not dst:
                base, _ = os.path.splitext(src)
                dst = base + "_replaced.pdf"

        if os.path.abspath(dst) == os.path.abspath(src):
            if not messagebox.askyesno(
                APP_NAME,
                "You selected overwrite original file.\n\nContinue?"
            ):
                return

        self.replace_btn.config(state="disabled")
        self.progress.pack(fill="x", pady=(10, 0))
        self.progress["value"] = 0
        self.status_var.set("Processing entire PDF...")
        self.root.update_idletasks()

        def progress_cb(done, total):
            self.progress["maximum"] = max(total, 1)
            self.progress["value"] = done
            self.status_var.set(f"Processing page {done} of {total}...")
            self.root.update_idletasks()

        try:
            counts = replace_pdf(src, dst, pairs, progress_cb=progress_cb)
            total = sum(counts.values())
            details = "\n".join(
                f"{old}  \u2192  {new}: {counts[old]}"
                for old, new in pairs
            )
            self.status_var.set(f"Completed \u2014 {total} occurrence(s) replaced")
            messagebox.showinfo(
                "Replacement Complete",
                f"Successfully processed the PDF.\n\n"
                f"Total replacements: {total}\n\n{details}\n\n"
                f"Output:\n{dst}"
            )
        except Exception as e:
            self.status_var.set("Error")
            messagebox.showerror(APP_NAME, f"Could not process the PDF:\n\n{e}")
        finally:
            self.replace_btn.config(state="normal")
            self.progress.pack_forget()

    def on_close(self):
        save_config({"dark_mode": self.dark_mode})
        self.root.destroy()

    def about(self):
        messagebox.showinfo(
            "About",
            "Loop PDF Replace All\n\n"
            "A PDF text replacement utility by\n"
            "Loop Structural Automation.\n\n"
            "Replace multiple entries across an entire PDF in one operation."
        )

    def help(self):
        messagebox.showinfo(
            "Help",
            "1. Browse and select your PDF.\n"
            "2. Enter the text to find and its replacement.\n"
            "3. Add as many replacement entries as required.\n"
            "4. Reorder entries with the \u2191 / \u2193 buttons if order matters.\n"
            "5. Choose a new output file or overwrite the original.\n"
            "6. Click REPLACE ALL.\n\n"
            "Tip: use the sun/moon switch in the top right to change "
            "between light and dark mode \u2014 your choice is remembered.\n\n"
            "Best results are obtained with selectable/vector PDF text."
        )


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()

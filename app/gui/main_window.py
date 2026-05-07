"""Main application window for Webex Connect Message Sender."""

from __future__ import annotations

import re
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any, Dict, List, Optional

import customtkinter as ctk

from ..core.api_sender import APISender
from ..core.file_parser import FileParser

# ──────────────────────────────────────────────────────────────
# Colour palette
# ──────────────────────────────────────────────────────────────
_ACCENT = "#2563eb"
_ACCENT_HOVER = "#1d4ed8"
_SUCCESS = "#16a34a"
_SUCCESS_HOVER = "#15803d"
_DANGER = "#dc2626"
_CHIP_COLORS = [
    "#2563eb", "#7c3aed", "#0891b2", "#059669",
    "#d97706", "#db2777", "#dc2626", "#0d9488",
]


# ══════════════════════════════════════════════════════════════
# Drag-and-drop chip widget
# ══════════════════════════════════════════════════════════════

class DragChip(ctk.CTkButton):
    """A pill-shaped button that can be dragged onto a text field."""

    # Shared registry of drop targets (container_widget → inner_text_widget)
    _drop_targets: List[tuple] = []

    @classmethod
    def register_drop_target(cls, container: tk.Widget, inner: tk.Widget) -> None:
        cls._drop_targets.append((container, inner))

    @classmethod
    def clear_drop_targets(cls) -> None:
        cls._drop_targets.clear()

    def __init__(
        self,
        master: tk.Widget,
        header: str,
        color: str = _ACCENT,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            master,
            text=header,
            width=0,
            height=28,
            corner_radius=14,
            fg_color=color,
            hover_color=_darken(color),
            text_color="white",
            font=ctk.CTkFont(size=11, weight="bold"),
            cursor="hand2",
            **kwargs,
        )
        self.header = header
        self._ghost: Optional[tk.Toplevel] = None

        self.bind("<ButtonPress-1>", self._on_press, add=True)
        self.bind("<B1-Motion>", self._on_motion, add=True)
        self.bind("<ButtonRelease-1>", self._on_release, add=True)

    # ── drag lifecycle ─────────────────────────────────────────

    def _on_press(self, event: tk.Event) -> str:
        self._ghost = tk.Toplevel()
        self._ghost.overrideredirect(True)
        self._ghost.attributes("-alpha", 0.80, "-topmost", True)
        fg = self.cget("fg_color")
        bg = fg[0] if isinstance(fg, (list, tuple)) else fg
        lbl = tk.Label(
            self._ghost,
            text=f"  {{{{{self.header}}}}}  ",
            bg=bg,
            fg="white",
            padx=8,
            pady=4,
            font=("Segoe UI", 11, "bold"),
            relief="flat",
            bd=0,
        )
        lbl.pack()
        self._move_ghost(event.x_root, event.y_root)
        return "break"

    def _on_motion(self, event: tk.Event) -> None:
        if self._ghost and self._ghost.winfo_exists():
            self._move_ghost(event.x_root, event.y_root)

    def _on_release(self, event: tk.Event) -> None:
        if self._ghost and self._ghost.winfo_exists():
            self._ghost.destroy()
            self._ghost = None

        inner = self._find_drop_target(event.x_root, event.y_root)
        if inner is None:
            # Fallback: try winfo_containing
            inner = self._walk_for_text(
                self.winfo_containing(event.x_root, event.y_root)
            )

        if inner is not None:
            self._insert(inner)

    # ── helpers ────────────────────────────────────────────────

    def _move_ghost(self, x: int, y: int) -> None:
        if self._ghost:
            self._ghost.geometry(f"+{x + 12}+{y + 8}")

    def _find_drop_target(self, x: int, y: int) -> Optional[tk.Widget]:
        """Check registered drop targets using bounding-box hit testing."""
        for container, inner in self._drop_targets:
            try:
                rx = container.winfo_rootx()
                ry = container.winfo_rooty()
                rw = container.winfo_width()
                rh = container.winfo_height()
                if rx <= x <= rx + rw and ry <= y <= ry + rh:
                    return inner
            except Exception:
                pass
        return None

    @staticmethod
    def _walk_for_text(widget: Optional[tk.Widget]) -> Optional[tk.Widget]:
        """Walk up the widget tree to find a tk.Text or tk.Entry."""
        w = widget
        visited: set = set()
        while w is not None and id(w) not in visited:
            visited.add(id(w))
            if isinstance(w, (tk.Text, tk.Entry)):
                return w
            try:
                w = w.master
            except Exception:
                break
        return None

    @staticmethod
    def _insert(widget: tk.Widget) -> None:
        """Insert the variable placeholder at the cursor position."""
        # We need the header; the chip that called this knows it.
        # This method is called from _on_release where self is available.
        pass  # replaced per-instance below


# Patch _insert to use self.header at call time
def _chip_insert(self: DragChip, widget: tk.Widget) -> None:
    token = f"{{{{{self.header}}}}}"
    if isinstance(widget, tk.Text):
        try:
            widget.insert("insert", token)
            widget.see("insert")
        except Exception:
            pass
    elif isinstance(widget, tk.Entry):
        try:
            widget.insert(tk.INSERT, token)
        except Exception:
            pass


DragChip._insert = _chip_insert  # type: ignore[assignment]


def _darken(hex_color: str) -> str:
    """Return a slightly darker shade of a hex colour (best-effort)."""
    try:
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        r = max(0, r - 30)
        g = max(0, g - 30)
        b = max(0, b - 30)
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return hex_color


# ══════════════════════════════════════════════════════════════
# Helper: labelled drop-target text box
# ══════════════════════════════════════════════════════════════

def _make_label(parent: tk.Widget, text: str, row: int, **grid_kw: Any) -> None:
    ctk.CTkLabel(
        parent,
        text=text,
        font=ctk.CTkFont(size=12, weight="bold"),
        anchor="w",
    ).grid(row=row, column=0, sticky="w", padx=12, pady=(6, 2), **grid_kw)


def _make_hint(parent: tk.Widget, text: str, row: int, **grid_kw: Any) -> None:
    ctk.CTkLabel(
        parent,
        text=text,
        font=ctk.CTkFont(size=10),
        text_color="gray",
        anchor="w",
        wraplength=500,
    ).grid(row=row, column=0, sticky="w", padx=12, pady=(0, 6), **grid_kw)


# ══════════════════════════════════════════════════════════════
# Main Window
# ══════════════════════════════════════════════════════════════

class MainWindow(ctk.CTk):
    """Top-level application window."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Webex Connect — Message Sender")
        self.geometry("1180x780")
        self.minsize(960, 640)

        # ── state ────────────────────────────────────────────
        self.file_parser = FileParser()
        self.api_sender = APISender()
        self.headers: List[str] = []
        self.rows: List[Dict[str, str]] = []
        self._sending = False

        # ── tkinter vars ─────────────────────────────────────
        self.file_info_var = tk.StringVar(value="Nenhum arquivo selecionado")
        self.msisdn_field_var = tk.StringVar()
        self.campaign_var = tk.StringVar()

        # SMS vars
        self.sms_from_var = tk.StringVar()
        self.sms_type_var = tk.StringVar(value="text")

        # MMS vars
        self.mms_from_var = tk.StringVar()
        self.mms_subject_var = tk.StringVar()
        self.mms_media_url_var = tk.StringVar()
        self.mms_caption_var = tk.StringVar()

        # RCS vars
        self.rcs_from_var = tk.StringVar()
        self.rcs_content_type_var = tk.StringVar(value="text")
        self.rcs_media_url_var = tk.StringVar()
        self.rcs_richcard_title_var = tk.StringVar()
        self.rcs_carousel_width_var = tk.StringVar(value="MEDIUM")
        # Carousel cards stored as list of dicts with StringVars
        self._carousel_cards: List[Dict[str, tk.StringVar]] = []
        # Suggestions stored as list of dicts {type_var, displayText_var, extra1_var, extra2_var}
        self._suggestions: List[Dict[str, tk.StringVar]] = []
        self.rcs_fallback_var = tk.BooleanVar(value=False)
        # Debounce timers for URL thumbnail loading
        self._pending_after: Dict[str, Any] = {}
        # Keep CTkImage references alive
        self._thumb_refs: List[Any] = []
        self.rcs_fallback_sender_var = tk.StringVar()
        self.rcs_fallback_text_var = tk.StringVar()

        DragChip.clear_drop_targets()
        self._build_ui()

    # ──────────────────────────────────────────────────────────
    # UI construction
    # ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=0, minsize=340)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Left panel
        left = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(12, 4), pady=12)
        left.grid_rowconfigure(2, weight=1)
        left.grid_columnconfigure(0, weight=1)
        self._build_left(left)

        # Right panel (scrollable)
        right = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 12), pady=12)
        right.grid_columnconfigure(0, weight=1)
        self._build_right(right)

    # ── left panel ────────────────────────────────────────────

    def _build_left(self, parent: ctk.CTkFrame) -> None:
        # App title
        ctk.CTkLabel(
            parent,
            text="Message Sender",
            font=ctk.CTkFont(size=22, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 10))

        # ── File upload card ──────────────────────────────────
        card = ctk.CTkFrame(parent, corner_radius=10)
        card.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text="1.  Carregar Arquivo",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))

        ctk.CTkLabel(
            card,
            text="CSV ou TXT com cabeçalhos (MSISDN, NOME, …)",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 6))

        ctk.CTkButton(
            card,
            text="📂   Selecionar Arquivo",
            command=self._load_file,
            fg_color=_ACCENT,
            hover_color=_ACCENT_HOVER,
            height=38,
            corner_radius=8,
            font=ctk.CTkFont(size=13),
        ).grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))

        ctk.CTkLabel(
            card,
            textvariable=self.file_info_var,
            font=ctk.CTkFont(size=10),
            text_color="gray",
            anchor="w",
            wraplength=290,
        ).grid(row=3, column=0, sticky="w", padx=12, pady=(0, 10))

        # ── Chips card ────────────────────────────────────────
        chips_card = ctk.CTkFrame(parent, corner_radius=10)
        chips_card.grid(row=2, column=0, sticky="nsew", pady=(0, 0))
        chips_card.grid_columnconfigure(0, weight=1)
        chips_card.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            chips_card,
            text="Campos disponíveis",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))

        ctk.CTkLabel(
            chips_card,
            text="Arraste para os campos de texto →",
            font=ctk.CTkFont(size=10),
            text_color="gray",
            anchor="w",
        ).grid(row=0, column=0, sticky="e", padx=12, pady=(10, 2))

        self.chips_scroll = ctk.CTkScrollableFrame(
            chips_card, label_text="", height=240
        )
        self.chips_scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=(4, 10))
        self.chips_scroll.grid_columnconfigure((0, 1), weight=1)

        self._chips_placeholder = ctk.CTkLabel(
            self.chips_scroll,
            text="Carregue um arquivo para ver\nos campos disponíveis",
            font=ctk.CTkFont(size=11),
            text_color="gray",
        )
        self._chips_placeholder.grid(row=0, column=0, columnspan=2, pady=30)

    # ── right panel ───────────────────────────────────────────

    def _build_right(self, parent: ctk.CTkScrollableFrame) -> None:
        # ── Recipient field ───────────────────────────────────
        recip = self._section(parent, "Campo Destinatário (MSISDN)", row=0)
        recip.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            recip,
            text="Nome do campo com o número de telefone (arraste o chip ou digite):",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=12, pady=(2, 4))

        msisdn_entry = ctk.CTkEntry(
            recip,
            textvariable=self.msisdn_field_var,
            placeholder_text="ex: MSISDN  ou  PHONE",
            height=36,
            font=ctk.CTkFont(size=12),
            border_color=_ACCENT,
            border_width=2,
        )
        msisdn_entry.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))
        # Register as drop target
        DragChip.register_drop_target(recip, msisdn_entry._entry)  # type: ignore[attr-defined]

        # ── Campaign name ─────────────────────────────────────
        camp = self._section(parent, "Nome da Campanha", row=1)
        camp.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            camp,
            text="Identificador da campanha (enviado como correlationId na API):",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=12, pady=(2, 4))

        ctk.CTkEntry(
            camp,
            textvariable=self.campaign_var,
            placeholder_text="ex: Black Friday 2026",
            height=36,
            font=ctk.CTkFont(size=12),
        ).grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))

        # ── Channel tabs ──────────────────────────────────────
        tabs_frame = self._section(parent, "Canal de Envio", row=2)
        tabs_frame.grid_columnconfigure(0, weight=1)

        self.tab_view = ctk.CTkTabview(tabs_frame, height=420)
        self.tab_view.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 10))
        self.tab_view.grid_columnconfigure(0, weight=1)

        # Add tabs
        sms_tab = self.tab_view.add("SMS")
        mms_tab = self.tab_view.add("MMS")
        rcs_tab = self.tab_view.add("RCS")

        for tab in (sms_tab, mms_tab, rcs_tab):
            tab.grid_columnconfigure(0, weight=1)

        self._build_sms_tab(sms_tab)
        self._build_mms_tab(mms_tab)
        self._build_rcs_tab(rcs_tab)

        # ── Action buttons ────────────────────────────────────
        actions = ctk.CTkFrame(parent, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", pady=(4, 8))
        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)

        self.preview_btn = ctk.CTkButton(
            actions,
            text="👁   Preview",
            command=self._show_preview,
            fg_color="#6366f1",
            hover_color="#4f46e5",
            height=42,
            corner_radius=10,
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.preview_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.send_btn = ctk.CTkButton(
            actions,
            text="🚀   Enviar Mensagens",
            command=self._start_sending,
            fg_color=_SUCCESS,
            hover_color=_SUCCESS_HOVER,
            height=42,
            corner_radius=10,
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.send_btn.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        # ── Progress section ──────────────────────────────────
        prog = self._section(parent, "Progresso", row=3)
        prog.grid_columnconfigure(0, weight=1)

        self.progress_status = ctk.CTkLabel(
            prog,
            text="Aguardando…",
            font=ctk.CTkFont(size=12),
            anchor="w",
        )
        self.progress_status.grid(row=1, column=0, sticky="w", padx=12, pady=(4, 4))

        self.progress_bar = ctk.CTkProgressBar(
            prog, mode="determinate", height=14, corner_radius=7
        )
        self.progress_bar.set(0)
        self.progress_bar.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 6))

        self.log_box = ctk.CTkTextbox(
            prog,
            height=140,
            font=ctk.CTkFont(family="Courier New", size=11),
            state="disabled",
        )
        self.log_box.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))

    # ──────────────────────────────────────────────────────────
    # Tab builders
    # ──────────────────────────────────────────────────────────

    def _build_sms_tab(self, parent: tk.Widget) -> None:
        parent.grid_columnconfigure(0, weight=1)

        _make_label(parent, "Shortcode / Alphatag (from) *", row=0)
        sms_from = ctk.CTkEntry(
            parent,
            textvariable=self.sms_from_var,
            placeholder_text="ex: 55119XXXXXXX  ou  MINHA_EMPRESA",
            height=36,
        )
        sms_from.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        DragChip.register_drop_target(parent, sms_from._entry)  # type: ignore[attr-defined]

        # Content type
        type_row = ctk.CTkFrame(parent, fg_color="transparent")
        type_row.grid(row=2, column=0, sticky="w", padx=12, pady=(0, 6))
        ctk.CTkLabel(type_row, text="Tipo:", font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=(0, 12))
        ctk.CTkRadioButton(type_row, text="text", variable=self.sms_type_var, value="text").grid(row=0, column=1, padx=(0, 12))
        ctk.CTkRadioButton(type_row, text="unicode (emoji/especiais)", variable=self.sms_type_var, value="unicode").grid(row=0, column=2)

        _make_label(parent, "Texto da Mensagem *", row=3)
        self.sms_text = ctk.CTkTextbox(
            parent, height=130, font=ctk.CTkFont(size=12), border_color=_ACCENT, border_width=2
        )
        self.sms_text.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 4))
        DragChip.register_drop_target(parent, self.sms_text._textbox)  # type: ignore[attr-defined]

        _make_hint(parent, "Use {{CAMPO}} para personalizar (ex: Olá {{NOME}}, seu código é {{CODIGO}})", row=5)

    def _build_mms_tab(self, parent: tk.Widget) -> None:
        parent.grid_columnconfigure(0, weight=1)

        _make_label(parent, "Número de Origem MMS (from) *", row=0)
        mms_from = ctk.CTkEntry(
            parent, textvariable=self.mms_from_var,
            placeholder_text="ex: +15551234567", height=36,
        )
        mms_from.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        DragChip.register_drop_target(parent, mms_from._entry)  # type: ignore[attr-defined]

        _make_label(parent, "Assunto (Subject) *", row=2)
        ctk.CTkEntry(
            parent, textvariable=self.mms_subject_var,
            placeholder_text="Assunto do MMS (máx. 80 caracteres)", height=36,
        ).grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 8))

        _make_label(parent, "Texto / Legenda", row=4)
        self.mms_text = ctk.CTkTextbox(
            parent, height=90, font=ctk.CTkFont(size=12), border_color=_ACCENT, border_width=2
        )
        self.mms_text.grid(row=5, column=0, sticky="ew", padx=12, pady=(0, 4))
        DragChip.register_drop_target(parent, self.mms_text._textbox)  # type: ignore[attr-defined]

        _make_hint(parent, "Use {{CAMPO}} para personalizar", row=6)

        self._make_media_url_input(parent, self.mms_media_url_var, "URL da Imagem / Mídia *", row_start=7)
        # helper uses rows 7, 8, 9

        _make_label(parent, "Legenda da imagem", row=10)
        ctk.CTkEntry(
            parent, textvariable=self.mms_caption_var,
            placeholder_text="Descrição / alt-text da imagem", height=36,
        ).grid(row=11, column=0, sticky="ew", padx=12, pady=(0, 12))

    def _build_rcs_tab(self, parent: tk.Widget) -> None:
        parent.grid_columnconfigure(0, weight=1)

        _make_label(parent, "Agent App ID / rcsAppId (from) *", row=0)
        rcs_from = ctk.CTkEntry(
            parent, textvariable=self.rcs_from_var,
            placeholder_text="App ID do asset RCS na plataforma", height=36,
        )
        rcs_from.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        DragChip.register_drop_target(parent, rcs_from._entry)  # type: ignore[attr-defined]

        # Content type selector
        ctype_row = ctk.CTkFrame(parent, fg_color="transparent")
        ctype_row.grid(row=2, column=0, sticky="w", padx=12, pady=(0, 8))
        ctk.CTkLabel(ctype_row, text="Tipo de conteúdo:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, padx=(0, 12))
        for col, (val, lbl) in enumerate([("text", "Texto"), ("media", "Mídia"), ("standalone", "Rich Card"), ("carousel", "Carrossel")]):
            ctk.CTkRadioButton(
                ctype_row, text=lbl, variable=self.rcs_content_type_var, value=val,
                command=self._on_rcs_content_type_change,
            ).grid(row=0, column=col + 1, padx=(0, 14))

        # ── Dynamic area inside a container ──────────────────
        self.rcs_dynamic = ctk.CTkFrame(parent, fg_color="transparent")
        self.rcs_dynamic.grid(row=3, column=0, sticky="ew")
        self.rcs_dynamic.grid_columnconfigure(0, weight=1)
        self._build_rcs_dynamic_fields(self.rcs_dynamic)

        # ── SMS Fallback ──────────────────────────────────────
        sep = ctk.CTkFrame(parent, height=1, fg_color="gray30")
        sep.grid(row=4, column=0, sticky="ew", padx=12, pady=(8, 6))

        fb_toggle = ctk.CTkCheckBox(
            parent,
            text="Ativar fallback para SMS se RCS não for suportado",
            variable=self.rcs_fallback_var,
            command=self._toggle_rcs_fallback,
            font=ctk.CTkFont(size=12),
        )
        fb_toggle.grid(row=5, column=0, sticky="w", padx=12, pady=(0, 4))

        self.rcs_fallback_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.rcs_fallback_frame.grid(row=6, column=0, sticky="ew")
        self.rcs_fallback_frame.grid_columnconfigure(0, weight=1)
        self._build_rcs_fallback_fields(self.rcs_fallback_frame)
        self.rcs_fallback_frame.grid_remove()  # hidden by default

    # ── RCS dynamic content area ──────────────────────────────

    def _build_rcs_dynamic_fields(self, parent: tk.Widget) -> None:
        """Rebuild the dynamic content area based on the selected content type."""
        for w in parent.winfo_children():
            w.destroy()
        parent.grid_columnconfigure(0, weight=1)
        ct = self.rcs_content_type_var.get()

        next_row = [0]  # mutable counter

        def row() -> int:
            r = next_row[0]
            next_row[0] += 1
            return r

        if ct in ("text", "standalone"):
            _make_label(parent, "Texto da Mensagem *", row=row())
            self.rcs_text = ctk.CTkTextbox(
                parent, height=90, font=ctk.CTkFont(size=12),
                border_color=_ACCENT, border_width=2,
            )
            self.rcs_text.grid(row=row(), column=0, sticky="ew", padx=12, pady=(0, 4))
            DragChip.register_drop_target(parent, self.rcs_text._textbox)  # type: ignore[attr-defined]
            _make_hint(parent, "Use {{CAMPO}} para personalizar", row=row())

        if ct in ("media", "standalone"):
            r = next_row[0]
            next_row[0] = self._make_media_url_input(parent, self.rcs_media_url_var, "URL da Mídia (imagem/vídeo) *", row_start=r)

        if ct == "standalone":
            _make_label(parent, "Título do Rich Card *", row=row())
            ctk.CTkEntry(
                parent, textvariable=self.rcs_richcard_title_var,
                placeholder_text="Título exibido no card", height=36,
            ).grid(row=row(), column=0, sticky="ew", padx=12, pady=(0, 8))

        if ct == "carousel":
            self._build_rcs_carousel_fields(parent, next_row)
            return  # carousel has its own suggestions per card

        # ── Suggestions (for text / media / standalone) ───────
        self._build_rcs_suggestions_section(parent, next_row)

    # ── Carousel ──────────────────────────────────────────────

    def _build_rcs_carousel_fields(self, parent: tk.Widget, next_row: List[int]) -> None:
        """Build carousel card list UI."""
        def row() -> int:
            r = next_row[0]; next_row[0] += 1; return r

        # Width
        w_row = ctk.CTkFrame(parent, fg_color="transparent")
        w_row.grid(row=row(), column=0, sticky="w", padx=12, pady=(4, 8))
        ctk.CTkLabel(w_row, text="Largura dos cards:", font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=(0, 8))
        ctk.CTkRadioButton(w_row, text="SMALL", variable=self.rcs_carousel_width_var, value="SMALL").grid(row=0, column=1, padx=(0, 8))
        ctk.CTkRadioButton(w_row, text="MEDIUM", variable=self.rcs_carousel_width_var, value="MEDIUM").grid(row=0, column=2)

        # Cards container
        _make_label(parent, "Cards do Carrossel (mín. 2) *", row=row())
        _make_hint(parent, "Cada card tem título, descrição e imagem obrigatórios. Adicione até 4 suggestions por card.", row=row())

        self._carousel_cards_frame = ctk.CTkScrollableFrame(parent, height=300, label_text="")
        self._carousel_cards_frame.grid(row=row(), column=0, sticky="ew", padx=8, pady=(0, 4))
        self._carousel_cards_frame.grid_columnconfigure(0, weight=1)

        # Add card button
        ctk.CTkButton(
            parent, text="＋  Adicionar Card",
            command=self._add_carousel_card,
            height=32, fg_color=_ACCENT, hover_color=_ACCENT_HOVER,
            font=ctk.CTkFont(size=12),
        ).grid(row=row(), column=0, sticky="w", padx=12, pady=(0, 8))

        # Init with 2 cards if empty
        if not self._carousel_cards:
            self._carousel_cards = []
            self._carousel_card_frames: List[tk.Widget] = []
        else:
            self._carousel_card_frames = []

        self._rebuild_carousel_cards_ui()

    def _add_carousel_card(self) -> None:
        self._carousel_cards.append({
            "title": tk.StringVar(),
            "description": tk.StringVar(),
            "media_url": tk.StringVar(),
            "suggestions": [],  # list of dicts {type_var, text_var, extra_var}
        })
        self._rebuild_carousel_cards_ui()

    def _remove_carousel_card(self, idx: int) -> None:
        if len(self._carousel_cards) <= 2:
            return
        self._carousel_cards.pop(idx)
        self._rebuild_carousel_cards_ui()

    def _rebuild_carousel_cards_ui(self) -> None:
        if not hasattr(self, "_carousel_cards_frame") or not self._carousel_cards_frame.winfo_exists():
            return
        for w in self._carousel_cards_frame.winfo_children():
            w.destroy()
        self._carousel_card_frames = []

        # Ensure at least 2 cards
        while len(self._carousel_cards) < 2:
            self._carousel_cards.append({
                "title": tk.StringVar(),
                "description": tk.StringVar(),
                "media_url": tk.StringVar(),
                "suggestions": [],
            })

        for idx, card in enumerate(self._carousel_cards):
            card_frame = ctk.CTkFrame(self._carousel_cards_frame, corner_radius=8, border_width=1, border_color="gray40")
            card_frame.grid(row=idx, column=0, sticky="ew", padx=4, pady=4)
            card_frame.grid_columnconfigure(0, weight=1)
            self._carousel_card_frames.append(card_frame)

            # Header row
            hdr = ctk.CTkFrame(card_frame, fg_color="gray25", corner_radius=6)
            hdr.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 2))
            hdr.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(hdr, text=f"Card {idx + 1}", font=ctk.CTkFont(size=12, weight="bold"), anchor="w").grid(row=0, column=0, padx=8, pady=4, sticky="w")
            if len(self._carousel_cards) > 2:
                ctk.CTkButton(hdr, text="✕", width=28, height=24, fg_color=_DANGER, hover_color="#b91c1c",
                              command=lambda i=idx: self._remove_carousel_card(i)).grid(row=0, column=1, padx=4, pady=2)

            ctk.CTkLabel(card_frame, text="Título *", font=ctk.CTkFont(size=11), anchor="w", text_color="gray70").grid(row=1, column=0, sticky="w", padx=8, pady=(4, 0))
            ctk.CTkEntry(card_frame, textvariable=card["title"], placeholder_text="Ex: Crédito pré-aprovado", height=30).grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 2))
            ctk.CTkLabel(card_frame, text="Descrição", font=ctk.CTkFont(size=11), anchor="w", text_color="gray70").grid(row=3, column=0, sticky="w", padx=8, pady=(2, 0))
            ctk.CTkEntry(card_frame, textvariable=card["description"], placeholder_text="Ex: Contrate em até 5 minutos (opcional)", height=30).grid(row=4, column=0, sticky="ew", padx=8, pady=(0, 2))

            self._make_media_url_input(card_frame, card["media_url"], "URL da Mídia *", row_start=5, padx=8, height=70)

            # Per-card suggestions (rows 5,6,7 used by media url widget → start at 8)
            self._build_card_suggestions(card_frame, card, idx, sug_row=8)

    def _build_card_suggestions(self, parent: tk.Widget, card: Dict, card_idx: int, sug_row: int = 4) -> None:
        """Build per-card suggestions. Rebuilds the whole frame content to avoid empty space."""
        outer = ctk.CTkFrame(parent, fg_color="gray20", corner_radius=6)
        outer.grid(row=sug_row, column=0, sticky="ew", padx=8, pady=(2, 6))
        outer.grid_columnconfigure(0, weight=1)

        def rebuild_card_sug() -> None:
            for w in outer.winfo_children():
                w.destroy()

            hdr_frame = ctk.CTkFrame(outer, fg_color="transparent")
            hdr_frame.grid(row=0, column=0, sticky="ew", padx=6, pady=(4, 2))
            hdr_frame.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(hdr_frame, text="Suggestions do card (máx. 2)",
                         font=ctk.CTkFont(size=11, weight="bold"), anchor="w").grid(row=0, column=0, sticky="w")

            sugs = card.get("suggestions", [])
            for i, sug in enumerate(sugs):
                self._render_suggestion_row(outer, sug, i + 1, sugs, rebuild_card_sug)

            if len(sugs) < 2:
                ctk.CTkButton(
                    outer, text="＋ Suggestion", width=120, height=26,
                    fg_color="gray40", hover_color="gray30", font=ctk.CTkFont(size=11),
                    command=lambda: self._add_suggestion_to(card["suggestions"], rebuild_card_sug, max_count=2),
                ).grid(row=len(sugs) + 1, column=0, sticky="w", padx=8, pady=(2, 6))
            else:
                ctk.CTkFrame(outer, height=4, fg_color="transparent").grid(row=3, column=0)

        rebuild_card_sug()

    # ── Suggestions section (for text/media/standalone) ───────

    def _build_rcs_suggestions_section(self, parent: tk.Widget, next_row: List[int]) -> None:
        """Build the global suggestions section below the content fields."""
        def row() -> int:
            r = next_row[0]; next_row[0] += 1; return r

        sep = ctk.CTkFrame(parent, height=1, fg_color="gray35")
        sep.grid(row=row(), column=0, sticky="ew", padx=12, pady=(6, 4))

        sug_header = ctk.CTkFrame(parent, fg_color="transparent")
        sug_header.grid(row=row(), column=0, sticky="ew", padx=12)
        sug_header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(sug_header, text="Suggestions (opcional, máx. 10)", font=ctk.CTkFont(size=12, weight="bold"), anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkButton(sug_header, text="＋ Adicionar", height=28, width=110,
                      fg_color=_ACCENT, hover_color=_ACCENT_HOVER, font=ctk.CTkFont(size=11),
                      command=lambda: self._add_global_suggestion()).grid(row=0, column=1, sticky="e")

        _make_hint(parent, "Reply, URL, Localização, Telefone, Agenda", row=row())

        self._sug_list_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._sug_list_frame.grid(row=row(), column=0, sticky="ew", padx=8, pady=(0, 8))
        self._sug_list_frame.grid_columnconfigure(0, weight=1)

        self._rebuild_global_suggestions_ui()

    def _rebuild_global_suggestions_ui(self) -> None:
        if not hasattr(self, "_sug_list_frame") or not self._sug_list_frame.winfo_exists():
            return
        for w in self._sug_list_frame.winfo_children():
            w.destroy()
        for i, sug in enumerate(self._suggestions):
            self._render_suggestion_row(self._sug_list_frame, sug, i, self._suggestions, self._rebuild_global_suggestions_ui)

    def _add_global_suggestion(self) -> None:
        if len(self._suggestions) >= 10:
            return
        self._suggestions.append({"type_var": tk.StringVar(value="reply"), "text_var": tk.StringVar(), "extra_var": tk.StringVar(), "extra2_var": tk.StringVar()})
        self._rebuild_global_suggestions_ui()

    def _add_suggestion_to(self, sug_list: List, rebuild_fn: Any, max_count: int = 10) -> None:
        if len(sug_list) >= max_count:
            return
        sug_list.append({"type_var": tk.StringVar(value="reply"), "text_var": tk.StringVar(), "extra_var": tk.StringVar(), "extra2_var": tk.StringVar()})
        rebuild_fn()
        # Rebuild entire carousel UI so the add button visibility updates
        if hasattr(self, "_carousel_cards_frame"):
            self._rebuild_carousel_cards_ui()

    def _render_suggestion_row(self, parent: tk.Widget, sug: Dict, idx: int, sug_list: List, rebuild_fn: Any) -> None:
        """Render a single suggestion row (type selector + fields + remove button)."""
        row_frame = ctk.CTkFrame(parent, fg_color="gray25", corner_radius=6)
        row_frame.grid(row=idx, column=0, sticky="ew", padx=4, pady=2)
        row_frame.grid_columnconfigure(1, weight=1)

        # Type dropdown
        type_menu = ctk.CTkOptionMenu(
            row_frame,
            variable=sug["type_var"],
            values=["reply", "openUrl", "dialPhone", "viewLocation", "shareLocation", "calendarEvent"],
            width=130, height=28, font=ctk.CTkFont(size=11),
            command=lambda _v: rebuild_fn(),
        )
        type_menu.grid(row=0, column=0, padx=(6, 4), pady=4)

        stype = sug["type_var"].get()
        ctk.CTkEntry(row_frame, textvariable=sug["text_var"], placeholder_text="displayText *", height=28).grid(row=0, column=1, sticky="ew", padx=(0, 4), pady=4)

        if stype == "openUrl":
            ctk.CTkEntry(row_frame, textvariable=sug["extra_var"], placeholder_text="URL *", height=28).grid(row=0, column=2, sticky="ew", padx=(0, 4), pady=4)
            row_frame.grid_columnconfigure(2, weight=1)
        elif stype == "dialPhone":
            ctk.CTkEntry(row_frame, textvariable=sug["extra_var"], placeholder_text="Telefone *", height=28, width=120).grid(row=0, column=2, padx=(0, 4), pady=4)
        elif stype == "viewLocation":
            ctk.CTkEntry(row_frame, textvariable=sug["extra_var"], placeholder_text="lat,lon ex: -23.5,-46.6", height=28).grid(row=0, column=2, sticky="ew", padx=(0, 4), pady=4)
            row_frame.grid_columnconfigure(2, weight=1)
        elif stype == "calendarEvent":
            ctk.CTkEntry(row_frame, textvariable=sug["extra_var"], placeholder_text="startTime ISO8601", height=28).grid(row=0, column=2, sticky="ew", padx=(0, 4), pady=4)
            ctk.CTkEntry(row_frame, textvariable=sug["extra2_var"], placeholder_text="endTime ISO8601", height=28).grid(row=0, column=3, sticky="ew", padx=(0, 4), pady=4)
            row_frame.grid_columnconfigure(2, weight=1)
            row_frame.grid_columnconfigure(3, weight=1)

        ctk.CTkButton(row_frame, text="✕", width=26, height=26, fg_color=_DANGER, hover_color="#b91c1c",
                      command=lambda i=idx: (sug_list.pop(i), rebuild_fn())).grid(row=0, column=4, padx=(0, 4), pady=4)

    # ── old alias kept for on_rcs_content_type_change ─────────

    def _build_rcs_text_fields(self, parent: tk.Widget) -> None:
        """Alias kept for compatibility — delegates to _build_rcs_dynamic_fields."""
        self._build_rcs_dynamic_fields(parent)

    def _build_rcs_fallback_fields(self, parent: tk.Widget) -> None:
        parent.grid_columnconfigure(0, weight=1)
        _make_label(parent, "Sender ID SMS (fallback)", row=0)
        ctk.CTkEntry(
            parent, textvariable=self.rcs_fallback_sender_var,
            placeholder_text="Shortcode ou alphatag SMS", height=34,
        ).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 6))
        _make_label(parent, "Texto SMS de fallback", row=2)
        ctk.CTkEntry(
            parent, textvariable=self.rcs_fallback_text_var,
            placeholder_text="Mensagem enviada caso RCS falhe", height=34,
        ).grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 10))

    # ──────────────────────────────────────────────────────────
    # Event handlers
    # ──────────────────────────────────────────────────────────

    def _on_rcs_content_type_change(self) -> None:
        # Reset suggestions and carousel state when type changes
        self._suggestions = []
        self._carousel_cards = []
        # Re-register drop targets after rebuild
        DragChip.clear_drop_targets()
        self._re_register_static_targets()
        self._build_rcs_dynamic_fields(self.rcs_dynamic)

    def _re_register_static_targets(self) -> None:
        """Re-register the static drop targets (MSISDN entry and tab entries)."""
        # This is called after clearing targets; we must walk the already-created widgets.
        # Instead of re-building, we can register by traversing known refs.
        pass  # Targets for the currently shown tab will re-register when _build_rcs_text_fields runs.

    def _toggle_rcs_fallback(self) -> None:
        if self.rcs_fallback_var.get():
            self.rcs_fallback_frame.grid()
        else:
            self.rcs_fallback_frame.grid_remove()

    # ──────────────────────────────────────────────────────────
    # File loading
    # ──────────────────────────────────────────────────────────

    def _load_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Selecionar arquivo",
            filetypes=[
                ("CSV / TXT", "*.csv *.txt"),
                ("CSV", "*.csv"),
                ("TXT", "*.txt"),
                ("Todos os arquivos", "*.*"),
            ],
        )
        if not path:
            return
        try:
            headers, rows = self.file_parser.parse(path)
        except ValueError as exc:
            messagebox.showerror("Erro ao carregar arquivo", str(exc))
            return

        self.headers = headers
        self.rows = rows
        fname = Path(path).name
        self.file_info_var.set(
            f"✓  {fname}   ({len(rows)} linhas · {len(headers)} campos)"
        )
        self._populate_chips()

        # Auto-select MSISDN field
        for h in headers:
            if h.upper() in ("MSISDN", "PHONE", "TELEFONE", "NUMERO", "NUMBER", "CEL"):
                self.msisdn_field_var.set(h)
                break

    def _populate_chips(self) -> None:
        """Destroy old chips and create new ones from self.headers."""
        self._chips_placeholder.grid_remove()
        for w in self.chips_scroll.winfo_children():
            if w is not self._chips_placeholder:
                w.destroy()

        for idx, header in enumerate(self.headers):
            color = _CHIP_COLORS[idx % len(_CHIP_COLORS)]
            chip = DragChip(self.chips_scroll, header=header, color=color)
            row, col = divmod(idx, 2)
            chip.grid(row=row, column=col, padx=4, pady=4, sticky="ew")

        self.chips_scroll.grid_columnconfigure(0, weight=1)
        self.chips_scroll.grid_columnconfigure(1, weight=1)

    # ──────────────────────────────────────────────────────────
    # Media browse
    # ──────────────────────────────────────────────────────────

    def _browse_media(self, target_var: tk.StringVar) -> None:
        """Legacy — kept for compatibility but no longer used in UI."""
        pass

    def _make_media_url_input(
        self,
        parent: tk.Widget,
        url_var: tk.StringVar,
        label_text: str,
        row_start: int,
        padx: int = 12,
        height: int = 86,
    ) -> int:
        """Build a URL entry + live image thumbnail preview.

        Uses rows row_start (label), row_start+1 (entry), row_start+2 (thumb).
        Returns row_start + 3 (next available row).
        """
        _make_label(parent, label_text, row=row_start)

        entry = ctk.CTkEntry(
            parent,
            textvariable=url_var,
            placeholder_text="Cole a URL da imagem gerada pelo Webex (ex: https://aws…/foto.jpg)",
            height=34,
            font=ctk.CTkFont(size=11),
        )
        entry.grid(row=row_start + 1, column=0, sticky="ew", padx=padx, pady=(0, 4))

        # Thumbnail container
        thumb_outer = ctk.CTkFrame(parent, fg_color="gray18", corner_radius=8, height=height)
        thumb_outer.grid(row=row_start + 2, column=0, sticky="ew", padx=padx, pady=(0, 6))
        thumb_outer.grid_propagate(False)
        thumb_outer.grid_columnconfigure(0, weight=1)

        thumb_lbl = ctk.CTkLabel(
            thumb_outer,
            text="🖼  Cole a URL acima para visualizar a imagem",
            font=ctk.CTkFont(size=11),
            text_color="gray50",
        )
        thumb_lbl.place(relx=0.5, rely=0.5, anchor="center")

        # Debounced URL watcher
        key = str(id(url_var))

        def _schedule(*_: Any) -> None:
            if key in self._pending_after:
                try:
                    self.after_cancel(self._pending_after[key])
                except Exception:
                    pass
            self._pending_after[key] = self.after(
                700, self._load_url_thumb, url_var, thumb_lbl, thumb_outer
            )

        url_var.trace_add("write", _schedule)
        # Also trigger immediately if var already has a value (e.g. tab rebuild)
        if url_var.get().strip():
            self.after(100, self._load_url_thumb, url_var, thumb_lbl, thumb_outer)

        return row_start + 3

    def _load_url_thumb(self, url_var: tk.StringVar, label: ctk.CTkLabel, container: ctk.CTkFrame) -> None:
        url = url_var.get().strip()
        if not url:
            try:
                label.configure(image=None, text="🖼  Cole a URL acima para visualizar a imagem")
            except Exception:
                pass
            return
        label.configure(image=None, text="⏳  Carregando…")
        import threading as _th
        _th.Thread(target=self._fetch_thumb, args=(url, label, container), daemon=True).start()

    def _fetch_thumb(self, url: str, label: ctk.CTkLabel, container: ctk.CTkFrame) -> None:
        try:
            import requests as _req
            from PIL import Image as _Img
            from io import BytesIO
            resp = _req.get(url, timeout=8, stream=True)
            resp.raise_for_status()
            img = _Img.open(BytesIO(resp.content)).convert("RGB")
            # Fit to container width (~280px) keeping aspect ratio
            max_w = 280
            max_h = container.winfo_reqheight() or 86
            img.thumbnail((max_w, max_h), _Img.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(img.width, img.height))
            self._thumb_refs.append(ctk_img)  # prevent GC
            self.after(0, lambda i=ctk_img: label.configure(image=i, text=""))
        except Exception:
            self.after(0, lambda: label.configure(image=None, text="⚠  Não foi possível carregar a imagem"))

    # ──────────────────────────────────────────────────────────
    # Payload builder
    # ──────────────────────────────────────────────────────────

    def _active_channel(self) -> str:
        tab = self.tab_view.get()
        return tab.lower()  # "sms", "mms" or "rcs"

    def _apply_subs(self, text: str, row: Dict[str, str]) -> str:
        """Replace {{FIELD}} tokens with row values (case-insensitive match)."""
        for key, value in row.items():
            text = re.sub(
                re.escape(f"{{{{{key}}}}}"),
                lambda v=str(value): v,
                text,
                flags=re.IGNORECASE,
            )
        return text

    def _build_suggestions_payload(self, sug_list: List[Dict], row: Dict[str, str]) -> List[Dict[str, Any]]:
        """Convert suggestion tkvar dicts to API payload objects."""
        result: List[Dict[str, Any]] = []
        for s in sug_list:
            stype = s["type_var"].get()
            dtext = self._apply_subs(s["text_var"].get().strip(), row)
            extra = s.get("extra_var", tk.StringVar()).get().strip()
            extra2 = s.get("extra2_var", tk.StringVar()).get().strip()
            if not dtext:
                continue
            if stype == "reply":
                result.append({"type": "reply", "displayText": dtext})
            elif stype == "openUrl" and extra:
                result.append({"type": "openUrl", "displayText": dtext, "url": extra})
            elif stype == "dialPhone" and extra:
                result.append({"type": "dialPhone", "displayText": dtext, "phone": extra})
            elif stype == "shareLocation":
                result.append({"type": "shareLocation", "displayText": dtext})
            elif stype == "viewLocation" and extra:
                parts = extra.split(",")
                if len(parts) >= 2:
                    try:
                        result.append({"type": "viewLocation", "displayText": dtext,
                                       "latitude": float(parts[0]), "longitude": float(parts[1])})
                    except ValueError:
                        pass
            elif stype == "calendarEvent" and extra and extra2:
                result.append({"type": "calendarEvent", "displayText": dtext,
                               "startTime": extra, "endTime": extra2, "meetingTitle": dtext})
        return result

    def _get_textbox(self, widget: ctk.CTkTextbox) -> str:
        try:
            return widget.get("1.0", "end-1c").strip()
        except Exception:
            return ""

    def build_payload(self, row: Dict[str, str]) -> Dict[str, Any]:
        """Build the API payload for a single row dict."""
        channel = self._active_channel()
        msisdn_field = self.msisdn_field_var.get().strip()
        msisdn = str(row.get(msisdn_field, "")).strip()

        campaign = self.campaign_var.get().strip()

        if channel == "sms":
            p: Dict[str, Any] = {
                "channel": "sms",
                "from": self.sms_from_var.get().strip(),
                "to": [{"msisdn": [msisdn]}],
                "content": {
                    "type": self.sms_type_var.get(),
                    "text": self._apply_subs(self._get_textbox(self.sms_text), row),
                },
            }
            if campaign:
                p["correlationId"] = campaign
            return p

        if channel == "mms":
            text = self._apply_subs(self._get_textbox(self.mms_text), row)
            campaign = self.campaign_var.get().strip()
            payload: Dict[str, Any] = {
                "channel": "mms",
                "from": self.mms_from_var.get().strip(),
                "to": [{"msisdn": [msisdn]}],
                "content": {
                    "subject": self.mms_subject_var.get().strip(),
                    "fallbacktext": text,
                    "name": "Message",
                },
            }
            if campaign:
                payload["correlationId"] = campaign
            media_url = self.mms_media_url_var.get().strip()
            attachments: List[Dict[str, Any]] = []
            if media_url:
                attachments.append({"type": "image", "messageText": text, "mediaUrl": media_url, "duration": 5})
            elif text:
                attachments.append({"type": "text", "messageText": text})
            if attachments:
                payload["content"]["attachments"] = attachments
            return payload

        # rcs
        ct = self.rcs_content_type_var.get()
        options: Dict[str, Any] = {}
        if self.rcs_fallback_var.get():
            options = {
                "smsFallback": True,
                "smsSenderId": self.rcs_fallback_sender_var.get().strip(),
                "text": self._apply_subs(self.rcs_fallback_text_var.get().strip(), row),
            }

        base: Dict[str, Any] = {
            "channel": "rcs",
            "from": self.rcs_from_var.get().strip(),
            "to": [{"msisdn": [msisdn]}],
        }
        if campaign:
            base["correlationId"] = campaign
        if options:
            base["options"] = options

        if ct == "text":
            base["content"] = {
                "type": "text",
                "text": self._apply_subs(self._get_textbox(self.rcs_text), row),
            }
            sugs = self._build_suggestions_payload(self._suggestions, row)
            if sugs:
                base["content"]["suggestions"] = sugs
        elif ct == "media":
            base["content"] = {
                "type": "media",
                "mediaContentUrl": self.rcs_media_url_var.get().strip(),
            }
            sugs = self._build_suggestions_payload(self._suggestions, row)
            if sugs:
                base["content"]["suggestions"] = sugs
        elif ct == "standalone":  # standalone richcard
            text = self._apply_subs(self._get_textbox(self.rcs_text), row)
            rc: Dict[str, Any] = {
                "title": self.rcs_richcard_title_var.get().strip() or "Mensagem",
                "description": text,
                "orientation": "VERTICAL",
                "thumbnailAlignment": "LEFT",
                "media": {
                    "url": self.rcs_media_url_var.get().strip(),
                    "height": "MEDIUM",
                },
            }
            sugs = self._build_suggestions_payload(self._suggestions, row)
            if sugs:
                rc["suggestions"] = sugs
            base["content"] = {"type": "standalone", "richCard": rc}
        else:  # carousel
            cards_payload: List[Dict[str, Any]] = []
            for card in self._carousel_cards:
                c: Dict[str, Any] = {
                    "title": card["title"].get().strip(),
                    "description": card["description"].get().strip(),
                    "media": {"url": card["media_url"].get().strip(), "height": "MEDIUM"},
                }
                card_sugs = self._build_suggestions_payload(card.get("suggestions", []), row)
                if card_sugs:
                    c["suggestions"] = card_sugs
                cards_payload.append(c)
            base["content"] = {
                "type": "carousel",
                "width": self.rcs_carousel_width_var.get(),
                "cards": cards_payload,
            }
            sugs = self._build_suggestions_payload(self._suggestions, row)
            if sugs:
                base["content"]["suggestions"] = sugs
        return base

    # ──────────────────────────────────────────────────────────
    # Validation
    # ──────────────────────────────────────────────────────────

    def _validate(self) -> List[str]:
        errs: List[str] = []
        channel = self._active_channel()
        msisdn_field = self.msisdn_field_var.get().strip()

        if not self.rows:
            errs.append("• Carregue um arquivo CSV/TXT primeiro.")
        if not msisdn_field:
            errs.append("• Informe o nome do campo destinatário (MSISDN).")
        elif self.rows and msisdn_field not in self.headers:
            errs.append(f"• Campo '{msisdn_field}' não encontrado no arquivo.")

        if channel == "sms":
            if not self.sms_from_var.get().strip():
                errs.append("• SMS: preencha o campo 'From' (shortcode/alphatag).")
            if not self._get_textbox(self.sms_text):
                errs.append("• SMS: preencha o texto da mensagem.")
        elif channel == "mms":
            if not self.mms_from_var.get().strip():
                errs.append("• MMS: preencha o número de origem.")
            if not self.mms_subject_var.get().strip():
                errs.append("• MMS: preencha o assunto.")
            if not self.mms_media_url_var.get().strip():
                errs.append("• MMS: informe a URL da mídia.")
        else:  # rcs
            if not self.rcs_from_var.get().strip():
                errs.append("• RCS: preencha o App ID (rcsAppId).")
            ct = self.rcs_content_type_var.get()
            if ct in ("text", "standalone"):
                if not hasattr(self, "rcs_text") or not self._get_textbox(self.rcs_text):
                    errs.append("• RCS: preencha o texto da mensagem.")
            if ct in ("media", "standalone") and not self.rcs_media_url_var.get().strip():
                errs.append("• RCS: informe a URL da mídia.")
            if ct == "carousel":
                if len(self._carousel_cards) < 2:
                    errs.append("• RCS Carrossel: adicione ao menos 2 cards.")
                else:
                    for i, card in enumerate(self._carousel_cards):
                        if not card["title"].get().strip():
                            errs.append(f"• RCS Carrossel: card {i+1} precisa de título.")
                        if not card["media_url"].get().strip():
                            errs.append(f"• RCS Carrossel: card {i+1} precisa de URL de mídia.")
            if self.rcs_fallback_var.get():
                if not self.rcs_fallback_sender_var.get().strip():
                    errs.append("• RCS Fallback: informe o Sender ID SMS.")
                if not self.rcs_fallback_text_var.get().strip():
                    errs.append("• RCS Fallback: informe o texto SMS.")
        return errs

    # ──────────────────────────────────────────────────────────
    # Preview
    # ──────────────────────────────────────────────────────────

    def _show_preview(self) -> None:
        if not self.rows and not self._has_content():
            messagebox.showwarning("Preview", "Preencha ao menos a mensagem antes de visualizar.")
            return
        preview_row = self.rows[0] if self.rows else {}
        try:
            payload = self.build_payload(preview_row)
        except Exception as exc:
            messagebox.showerror("Erro no preview", str(exc))
            return

        # Import here to avoid circular
        from .preview_dialog import PreviewDialog  # noqa: PLC0415
        dlg = PreviewDialog(self, payload, self._active_channel())
        dlg.grab_set()
        dlg.focus_set()

    def _has_content(self) -> bool:
        ch = self._active_channel()
        if ch == "sms":
            return bool(self._get_textbox(self.sms_text))
        if ch == "mms":
            return bool(self.mms_subject_var.get())
        return bool(self.rcs_from_var.get())

    # ──────────────────────────────────────────────────────────
    # Sending
    # ──────────────────────────────────────────────────────────

    def _start_sending(self) -> None:
        if self._sending:
            return
        errs = self._validate()
        if errs:
            messagebox.showerror("Campos obrigatórios", "\n".join(errs))
            return

        channel = self._active_channel().upper()
        if not messagebox.askyesno(
            "Confirmar envio",
            f"Enviar {channel} para {len(self.rows)} destinatário(s)?\n\nContinuar?",
        ):
            return

        self._sending = True
        self.send_btn.configure(state="disabled", text="Enviando…")
        self.preview_btn.configure(state="disabled")
        self.progress_bar.set(0)
        self._log_clear()
        self._log("▶ Iniciando envio…")

        threading.Thread(target=self._send_all_rows, daemon=True).start()

    def _send_all_rows(self) -> None:
        total = len(self.rows)
        ok = 0
        fail = 0

        for i, row in enumerate(self.rows):
            try:
                payload = self.build_payload(row)
                result = self.api_sender.send(payload)
            except Exception as exc:
                result = {"success": False, "error": str(exc)}

            msisdn_field = self.msisdn_field_var.get().strip()
            msisdn = row.get(msisdn_field, "?")

            if result.get("success"):
                ok += 1
                mid = result.get("messageId") or ""
                self.after(0, self._log, f"✓  [{i+1}/{total}]  {msisdn}  →  {mid}")
            else:
                fail += 1
                err = result.get("error") or "Erro desconhecido"
                self.after(0, self._log, f"✗  [{i+1}/{total}]  {msisdn}  →  {err}")

            progress = (i + 1) / total
            self.after(0, self.progress_bar.set, progress)
            self.after(0, self.progress_status.configure, {"text": f"Enviando {i+1} de {total}…"})

        summary = f"Concluído  ✓ {ok} sucesso  ✗ {fail} falha  (total: {total})"
        self.after(0, self.progress_status.configure, {"text": summary})
        self.after(0, self._log, f"\n{summary}")
        self.after(0, self._on_send_done, summary, fail > 0)

    def _on_send_done(self, summary: str, had_errors: bool) -> None:
        self._sending = False
        self.send_btn.configure(state="normal", text="🚀   Enviar Mensagens")
        self.preview_btn.configure(state="normal")
        if had_errors:
            messagebox.showwarning("Envio concluído", summary)
        else:
            messagebox.showinfo("Envio concluído", summary)

    # ──────────────────────────────────────────────────────────
    # Log helpers
    # ──────────────────────────────────────────────────────────

    def _log(self, text: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _log_clear(self) -> None:
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    # ──────────────────────────────────────────────────────────
    # Utility
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _section(parent: tk.Widget, title: str, row: int) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent, corner_radius=10)
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        frame.grid_columnconfigure(0, weight=1)
        if title:
            ctk.CTkLabel(
                frame,
                text=title,
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w",
            ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))
        return frame

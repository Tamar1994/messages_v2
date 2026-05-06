"""Phone-mockup preview dialog."""

from __future__ import annotations

import textwrap
import threading
from io import BytesIO
from typing import Any, Dict, List

import customtkinter as ctk
import tkinter as tk


class PreviewDialog(ctk.CTkToplevel):
    """Modal window that renders a simplified phone mockup for the message."""

    _PHONE_W = 320
    _PHONE_H = 560

    def __init__(
        self,
        parent: tk.Widget,
        payload: Dict[str, Any],
        channel: str,
    ) -> None:
        super().__init__(parent)
        self.title(f"Preview — {channel.upper()}")
        self.resizable(False, False)
        self._img_refs: List[Any] = []  # keep CTkImage refs alive

        # Center relative to parent
        self.after(10, self._center, parent)

        self._payload = payload
        self._channel = channel.lower()
        self._build_ui()

    # ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.grid(row=0, column=0, padx=20, pady=20)

        # Phone body
        phone = ctk.CTkFrame(
            outer,
            width=self._PHONE_W,
            height=self._PHONE_H,
            corner_radius=36,
            fg_color="#111827",
            border_color="#374151",
            border_width=3,
        )
        phone.pack()
        phone.pack_propagate(False)

        # Status bar
        status = ctk.CTkFrame(phone, fg_color="#111827", height=36, corner_radius=0)
        status.pack(fill="x", padx=0)
        ctk.CTkLabel(
            status,
            text="9:41",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="white",
            anchor="w",
        ).pack(side="left", padx=16)
        ctk.CTkLabel(
            status,
            text="▲ ● ▌▌",
            font=ctk.CTkFont(size=10),
            text_color="#9ca3af",
            anchor="e",
        ).pack(side="right", padx=12)

        # App header bar
        header = ctk.CTkFrame(phone, fg_color="#1f2937", height=44, corner_radius=0)
        header.pack(fill="x")
        channel_label = self._channel.upper()
        ctk.CTkLabel(
            header,
            text=f"◀   {channel_label} · {self._from_str()}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="white",
            anchor="w",
        ).pack(side="left", padx=12, pady=8)

        # Scrollable message area
        msg_area = ctk.CTkScrollableFrame(
            phone,
            fg_color="#1f2937",
            label_text="",
            height=390,
        )
        msg_area.pack(fill="both", expand=True, padx=0, pady=0)
        msg_area.grid_columnconfigure(0, weight=1)

        self._render_message(msg_area)

        # Input bar (decorative)
        input_bar = ctk.CTkFrame(phone, fg_color="#111827", height=48, corner_radius=0)
        input_bar.pack(fill="x", side="bottom")
        ctk.CTkLabel(
            input_bar, text="Aa",
            font=ctk.CTkFont(size=12),
            text_color="#6b7280",
        ).pack(side="left", padx=16, pady=10)
        ctk.CTkLabel(
            input_bar, text="⊕  📷  🎤",
            font=ctk.CTkFont(size=12),
            text_color="#6b7280",
        ).pack(side="right", padx=12)

        # Home bar indicator
        ctk.CTkFrame(outer, width=100, height=4, corner_radius=2, fg_color="#374151").pack(pady=(6, 0))

        # Close button below phone
        ctk.CTkButton(
            outer,
            text="Fechar",
            command=self.destroy,
            width=120,
            height=34,
            fg_color="gray40",
            hover_color="gray30",
        ).pack(pady=(12, 0))

    # ──────────────────────────────────────────────────────────

    def _render_message(self, parent: tk.Widget) -> None:
        """Render message bubble(s) based on channel/payload content."""
        channel = self._channel
        content = self._payload.get("content", {})

        if channel == "sms":
            text = content.get("text", "")
            self._bubble(parent, text, row=0)

        elif channel == "mms":
            subject = content.get("subject", "")
            fallback = content.get("fallbacktext", "")
            attachments = content.get("attachments", [])

            if subject:
                self._bubble(parent, f"📌 {subject}", row=0, accent=True)

            for i, att in enumerate(attachments):
                mtype = att.get("type", "")
                url = att.get("mediaUrl", "")
                caption = att.get("messageText", "")
                icon = {"image": "🖼", "video": "🎬", "audio": "🎵", "pdf": "📄"}.get(mtype, "📎")
                self._media_tile(parent, icon, url, caption, row=i + 1)

            if fallback:
                self._bubble(parent, fallback, row=len(attachments) + 1)

        else:  # rcs
            ct = content.get("type", "text")

            if ct == "text":
                self._bubble(parent, content.get("text", ""), row=0)
                self._render_suggestions(parent, content.get("suggestions", []), base_row=1)

            elif ct == "media":
                url = content.get("mediaContentUrl", "")
                self._media_tile(parent, "🖼", url, "", row=0)
                self._render_suggestions(parent, content.get("suggestions", []), base_row=1)

            elif ct == "standalone":
                rc = content.get("richCard", {})
                title = rc.get("title", "")
                desc = rc.get("description", "")
                media = rc.get("media", {})
                media_url = media.get("url", "")
                self._richcard(parent, title, desc, media_url, row=0, suggestions=rc.get("suggestions", []))

            elif ct == "carousel":
                cards = content.get("cards", [])
                for i, card in enumerate(cards):
                    self._richcard(
                        parent,
                        card.get("title", ""),
                        card.get("description", ""),
                        card.get("media", {}).get("url", ""),
                        row=i,
                        suggestions=card.get("suggestions", []),
                        compact=True,
                    )
                self._render_suggestions(parent, content.get("suggestions", []), base_row=len(cards))

    def _bubble(
        self,
        parent: tk.Widget,
        text: str,
        row: int,
        accent: bool = False,
    ) -> None:
        """Render a chat bubble."""
        bg = "#2563eb" if accent else "#374151"
        wrapped = textwrap.fill(text, width=34) if text else "(mensagem vazia)"
        frame = ctk.CTkFrame(
            parent,
            fg_color=bg,
            corner_radius=16,
        )
        frame.grid(row=row, column=0, sticky="e", padx=(40, 10), pady=(6, 2))
        ctk.CTkLabel(
            frame,
            text=wrapped,
            font=ctk.CTkFont(size=12),
            text_color="white",
            wraplength=220,
            justify="left",
            anchor="w",
        ).pack(padx=12, pady=8)
        ctk.CTkLabel(
            parent,
            text="✓✓",
            font=ctk.CTkFont(size=9),
            text_color="#6b7280",
            anchor="e",
        ).grid(row=row, column=0, sticky="e", padx=(0, 12))

    def _media_tile(
        self,
        parent: tk.Widget,
        icon: str,
        url: str,
        caption: str,
        row: int,
    ) -> None:
        """Render a media attachment tile (image fills the card)."""
        frame = ctk.CTkFrame(parent, fg_color="#2d3748", corner_radius=14)
        frame.grid(row=row, column=0, sticky="ew", padx=(10, 10), pady=(4, 2))
        frame.grid_columnconfigure(0, weight=1)

        # Image area with fixed height; replaced by real image on load
        img_container = ctk.CTkFrame(frame, fg_color="#1a2535", corner_radius=10, height=120)
        img_container.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 3))
        img_container.grid_propagate(False)
        img_container.grid_columnconfigure(0, weight=1)

        img_lbl = ctk.CTkLabel(
            img_container,
            text="⏳",
            font=ctk.CTkFont(size=24),
            text_color="#4b5563",
        )
        img_lbl.place(relx=0.5, rely=0.5, anchor="center")

        if url:
            self._async_load_image(url, img_lbl, icon, target_w=240, target_h=118)

        if caption:
            ctk.CTkLabel(
                frame,
                text=caption,
                font=ctk.CTkFont(size=11),
                text_color="#e5e7eb",
                wraplength=230,
                anchor="w",
                justify="left",
            ).grid(row=1, column=0, sticky="w", padx=10, pady=(0, 8))
        else:
            ctk.CTkFrame(frame, height=4, fg_color="transparent").grid(row=1, column=0)

    def _richcard(
        self,
        parent: tk.Widget,
        title: str,
        desc: str,
        media_url: str,
        row: int,
        suggestions: list = None,
        compact: bool = False,
    ) -> None:
        """Render an RCS rich card."""
        if suggestions is None:
            suggestions = []
        frame = ctk.CTkFrame(parent, fg_color="#1e3a5f", corner_radius=14)
        padx = (4, 4) if compact else (10, 10)
        frame.grid(row=row, column=0, sticky="ew", padx=padx, pady=(4, 2))
        frame.grid_columnconfigure(0, weight=1)

        # Media area
        media_h = 70 if compact else 100
        media_ph = ctk.CTkFrame(frame, fg_color="#0f2a47", corner_radius=10, height=media_h)
        media_ph.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 4))
        media_ph.grid_propagate(False)
        media_ph.grid_columnconfigure(0, weight=1)

        img_lbl = ctk.CTkLabel(
            media_ph,
            text="⏳",
            font=ctk.CTkFont(size=22 if not compact else 16),
            text_color="#2d4a6e",
        )
        img_lbl.place(relx=0.5, rely=0.5, anchor="center")

        if media_url:
            ph_w = 250 if not compact else 200
            self._async_load_image(media_url, img_lbl, "🖼", target_w=ph_w, target_h=media_h - 6)

        # Title
        ctk.CTkLabel(
            frame,
            text=title or "Título do Card",
            font=ctk.CTkFont(size=12 if compact else 13, weight="bold"),
            text_color="white",
            anchor="w",
            wraplength=230,
            justify="left",
        ).grid(row=1, column=0, sticky="w", padx=10, pady=(2, 1))

        # Description
        if desc:
            ctk.CTkLabel(
                frame,
                text=desc,
                font=ctk.CTkFont(size=10 if compact else 11),
                text_color="#93c5fd",
                anchor="w",
                wraplength=220,
                justify="left",
            ).grid(row=2, column=0, sticky="w", padx=10, pady=(0, 4))

        # Suggestions
        if suggestions:
            sug_frame = ctk.CTkFrame(frame, fg_color="#163050", corner_radius=8)
            sug_frame.grid(row=3, column=0, sticky="ew", padx=6, pady=(0, 6))
            sug_frame.grid_columnconfigure(0, weight=1)
            for si, sug in enumerate(suggestions[:4]):
                ctk.CTkButton(
                    sug_frame,
                    text=sug.get("displayText", ""),
                    height=26,
                    width=0,
                    corner_radius=13,
                    fg_color="#1e40af",
                    hover_color="#1d4ed8",
                    font=ctk.CTkFont(size=10),
                ).grid(row=si, column=0, sticky="ew", padx=6, pady=2)
            ctk.CTkFrame(sug_frame, height=2, fg_color="transparent").grid(row=len(suggestions[:4]), column=0)
        else:
            ctk.CTkFrame(frame, height=4, fg_color="transparent").grid(row=3, column=0)

    def _render_suggestions(self, parent: tk.Widget, suggestions: list, base_row: int) -> None:
        """Render a row of suggestion chips below a message."""
        if not suggestions:
            return
        chips_frame = ctk.CTkFrame(parent, fg_color="transparent")
        chips_frame.grid(row=base_row, column=0, sticky="ew", padx=10, pady=(2, 6))
        for i, sug in enumerate(suggestions):
            ctk.CTkButton(
                chips_frame,
                text=sug.get("displayText", ""),
                height=28,
                width=0,
                corner_radius=14,
                fg_color="#1e40af",
                hover_color="#1d4ed8",
                font=ctk.CTkFont(size=11),
            ).grid(row=0, column=i, padx=3, pady=2)

    # ──────────────────────────────────────────────────────────

    def _async_load_image(
        self,
        url: str,
        label: ctk.CTkLabel,
        fallback_icon: str,
        target_w: int = 240,
        target_h: int = 90,
        container: Any = None,
    ) -> None:
        """Load image from URL in a background thread and update label."""
        threading.Thread(
            target=self._fetch_preview_image,
            args=(url, label, fallback_icon, target_w, target_h, container),
            daemon=True,
        ).start()

    def _fetch_preview_image(
        self,
        url: str,
        label: ctk.CTkLabel,
        fallback_icon: str,
        target_w: int,
        target_h: int,
        container: Any,
    ) -> None:
        try:
            import requests as _req
            from PIL import Image as _Img
            resp = _req.get(url, timeout=8, stream=True)
            resp.raise_for_status()
            img = _Img.open(BytesIO(resp.content)).convert("RGB")
            img.thumbnail((target_w, target_h), _Img.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(img.width, img.height))
            self._img_refs.append(ctk_img)
            # Use lambda so kwargs are passed correctly to CTkLabel.configure
            self.after(0, lambda i=ctk_img: label.configure(image=i, text=""))
        except Exception:
            self.after(0, lambda: label.configure(image=None, text=f"{fallback_icon}  (indisponível)"))

    # ──────────────────────────────────────────────────────────

    def _from_str(self) -> str:
        return str(self._payload.get("from", ""))

    def _center(self, parent: tk.Widget) -> None:
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_x()
        py = parent.winfo_y()
        w = self.winfo_width()
        h = self.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"+{x}+{y}")

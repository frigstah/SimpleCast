from __future__ import annotations

import logging
import math
import os
import platform
import ctypes
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .audio import (
    AUDIO_SYSTEMS,
    AudioDevice,
    AudioEngine,
    GainControl,
    list_input_devices,
)
from .config_store import ConfigStore
from .diagnostics import DiagnosticStep, run_server_diagnostic
from .logging_setup import configure_logging
from .listener_stats import fetch_listener_count
from .metadata import (
    METADATA_FORMATS,
    MetadataDeliveryEngine,
    MetadataFileWatcher,
    format_manual_now_playing,
    sanitized_server_json,
)
from .models import AppConfig, ServerProfile
from .processing import (
    PROCESSING_PRESETS,
    process_test_file,
)
from .recording import (
    RECORDING_BITRATE,
    RecordingEngine,
    RecordingState,
    default_recording_folder,
    next_recording_path,
)
from .readiness import ReadinessCheck, run_readiness_checks
from .streaming import (
    BroadcastState,
    MultiStreamEngine,
    QUALITY_PRESETS,
    StreamDestination,
)
from .startup import set_start_with_windows
from .support import sanitize_support_text
from .tray import TrayController
from .updater import (
    UpdateRelease,
    check_for_update,
    download_installer,
)
from .windows import SleepPreventer


THEMES = {
    "Modern & sleek": {
        "description": (
            "A restrained charcoal interface with crisp cyan highlights "
            "and compact controls."
        ),
        "font_size": 10,
        "button_padding": (13, 7),
        "colors": {
            "bg": "#0b0f14",
            "surface": "#141a22",
            "surface_alt": "#202833",
            "surface_hover": "#2b3644",
            "input": "#0d131a",
            "input_hover": "#17202a",
            "disabled": "#1a2028",
            "disabled_text": "#697583",
            "line": "#344253",
            "text": "#f6f8fa",
            "muted": "#aab5c1",
            "accent": "#4dd7e5",
            "accent_hover": "#79e4ee",
            "accent_dark": "#12383e",
            "warning": "#f6c85f",
            "error": "#ff6b7a",
            "offline": "#8d9aa8",
            "sidebar": "#080c11",
            "sidebar_text": "#f6f8fa",
            "sidebar_muted": "#9eabb8",
            "sidebar_accent": "#4dd7e5",
            "accent_text": "#071d17",
            "error_text": "#2d0710",
        },
    },
    "Classic SimpleCast": {
        "description": (
            "The familiar SimpleCast navy design used in earlier beta releases."
        ),
        "font_size": 10,
        "button_padding": (14, 8),
        "colors": {
            "bg": "#0b1422",
            "surface": "#142238",
            "surface_alt": "#1c2f49",
            "surface_hover": "#263d5b",
            "input": "#0d1b2d",
            "input_hover": "#132842",
            "disabled": "#17263a",
            "disabled_text": "#71839a",
            "line": "#355170",
            "text": "#f5f7fb",
            "muted": "#adbed2",
            "accent": "#55ddb0",
            "accent_hover": "#73e9c2",
            "accent_dark": "#123a34",
            "warning": "#f6c85f",
            "error": "#ff6b7a",
            "offline": "#93a4b8",
            "sidebar": "#0a1828",
            "sidebar_text": "#f5f7fb",
            "sidebar_muted": "#adbed2",
            "sidebar_accent": "#55ddb0",
            "accent_text": "#09201a",
            "error_text": "#2d0710",
        },
    },
    "Beginner friendly": {
        "description": (
            "A bright, high-contrast layout with larger text and roomier controls."
        ),
        "font_size": 11,
        "button_padding": (15, 10),
        "colors": {
            "bg": "#edf3f8",
            "surface": "#ffffff",
            "surface_alt": "#dce8f2",
            "surface_hover": "#cbddea",
            "input": "#f8fbfd",
            "input_hover": "#ffffff",
            "disabled": "#e4e9ee",
            "disabled_text": "#788592",
            "line": "#8da5b8",
            "text": "#152332",
            "muted": "#4d6274",
            "accent": "#168d72",
            "accent_hover": "#20a987",
            "accent_dark": "#c8eee4",
            "warning": "#b57900",
            "error": "#c8364b",
            "offline": "#617487",
            "sidebar": "#17324b",
            "sidebar_text": "#ffffff",
            "sidebar_muted": "#c8d8e6",
            "sidebar_accent": "#79e4c5",
            "accent_text": "#ffffff",
            "error_text": "#ffffff",
        },
    },
}

CLASSIC_THEMES = (
    "Modern & sleek",
    "Classic SimpleCast",
    "Beginner friendly",
)

SKINS = {
    "Classic SimpleCast": {
        "description": (
            "The familiar SimpleCast dashboard with its existing appearance "
            "variations and sidebar navigation."
        ),
    },
    "Broadcast Console": {
        "description": (
            "A compact dark broadcast console with a slim navigation rail, "
            "large meters, and a focused two-column workflow."
        ),
    },
    "Studio Workspace": {
        "description": (
            "A bright, highly legible studio organized from Source to Signal "
            "to On air, with navigation across the top."
        ),
    },
    "Studio Dark": {
        "description": (
            "The Source–Signal–On air studio workflow in a restrained charcoal "
            "broadcasting palette."
        ),
    },
}

STUDIO_DARK_PROFILE = {
    "description": SKINS["Studio Dark"]["description"],
    "font_size": 10,
    "button_padding": (13, 8),
    "colors": {
        "bg": "#0a1016",
        "surface": "#111b24",
        "surface_alt": "#1a2834",
        "surface_hover": "#263a49",
        "input": "#0b141c",
        "input_hover": "#13222d",
        "disabled": "#17222b",
        "disabled_text": "#687b88",
        "line": "#304756",
        "text": "#f3f7f8",
        "muted": "#a4b5bf",
        "accent": "#44d3df",
        "accent_hover": "#70e1e9",
        "accent_dark": "#11383d",
        "warning": "#f0c45c",
        "error": "#ff6878",
        "offline": "#8ca0ad",
        "sidebar": "#070d12",
        "sidebar_text": "#f3f7f8",
        "sidebar_muted": "#9aacb7",
        "sidebar_accent": "#44d3df",
        "accent_text": "#061b1e",
        "error_text": "#2b060d",
    },
}

STUDIO_LIGHT_PROFILE = {
    "description": SKINS["Studio Workspace"]["description"],
    "font_size": 10,
    "button_padding": (14, 9),
    "colors": dict(THEMES["Beginner friendly"]["colors"]),
}

SKIN_PROFILES = {
    "Broadcast Console": THEMES["Modern & sleek"],
    "Studio Workspace": STUDIO_LIGHT_PROFILE,
    "Studio Dark": STUDIO_DARK_PROFILE,
}

SKIN_WINDOW_SIZES = {
    "Classic SimpleCast": (1180, 800, 880, 620),
    "Broadcast Console": (1220, 820, 980, 650),
    "Studio Workspace": (1320, 900, 1100, 720),
    "Studio Dark": (1320, 900, 1100, 720),
}

COLORS = dict(THEMES["Classic SimpleCast"]["colors"])

SAMPLE_RATES = {
    "32 kHz": 32000,
    "44.1 kHz": 44100,
    "48 kHz": 48000,
}

STARTUP_DELAYS = {
    "5 seconds": 5,
    "10 seconds": 10,
    "30 seconds": 30,
    "60 seconds": 60,
}


def _appearance_profile(config: AppConfig) -> dict[str, object]:
    if config.ui_skin == "Classic SimpleCast":
        return THEMES[config.ui_theme]
    return SKIN_PROFILES[config.ui_skin]


def _resource_path(*parts: str) -> Path:
    base = Path(
        getattr(
            sys,
            "_MEIPASS",
            Path(__file__).resolve().parent.parent,
        )
    )
    return base.joinpath(*parts)


def _enable_windows_dpi_awareness() -> None:
    if platform.system() != "Windows":
        return
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def _fit_window(
    window: tk.Tk | tk.Toplevel,
    preferred_width: int,
    preferred_height: int,
    minimum_width: int,
    minimum_height: int,
) -> None:
    window.update_idletasks()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    width = min(max(preferred_width, window.winfo_reqwidth()), screen_width - 40)
    height = min(max(preferred_height, window.winfo_reqheight()), screen_height - 70)
    width = max(420, width)
    height = max(420, height)
    x = max(0, (screen_width - width) // 2)
    y = max(0, (screen_height - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")
    window.minsize(
        min(minimum_width, width),
        min(minimum_height, height),
    )


class LevelMeter(tk.Canvas):
    def __init__(self, master: tk.Misc, **kwargs: object) -> None:
        height = kwargs.pop("height", 18)
        super().__init__(
            master,
            height=height,
            background=COLORS["surface_alt"],
            highlightthickness=0,
            **kwargs,
        )
        self.level = 0.0
        self.bind("<Configure>", lambda _event: self.redraw())

    def set_level(self, level: float) -> None:
        self.level = max(0.0, min(1.0, level))
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        width = self.winfo_width()
        height = self.winfo_height()
        fill_width = int(width * self.level)
        color = (
            COLORS["error"]
            if self.level >= 0.94
            else COLORS["warning"]
            if self.level >= 0.78
            else COLORS["accent"]
        )
        if fill_width:
            self.create_rectangle(0, 0, fill_width, height, fill=color, outline="")
        self.create_line(width * 0.78, 0, width * 0.78, height, fill="#d3a94d")
        self.create_line(width * 0.94, 0, width * 0.94, height, fill="#d95b68")


class VerticalLevelMeter(tk.Canvas):
    def __init__(self, master: tk.Misc, **kwargs: object) -> None:
        super().__init__(
            master,
            width=30,
            height=165,
            background=COLORS["surface"],
            highlightthickness=0,
            **kwargs,
        )
        self.level = 0.0
        self.bind("<Configure>", lambda _event: self.redraw())

    def set_level(self, level: float) -> None:
        self.level = max(0.0, min(1.0, level))
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        width = self.winfo_width()
        height = self.winfo_height()
        segments = 24
        gap = 2
        segment_height = max(2, (height - gap * (segments - 1)) / segments)
        active_segments = int(round(self.level * segments))
        for index in range(segments):
            y2 = height - index * (segment_height + gap)
            y1 = y2 - segment_height
            if index < active_segments:
                ratio = (index + 1) / segments
                color = (
                    COLORS["error"]
                    if ratio >= 0.9
                    else COLORS["warning"]
                    if ratio >= 0.72
                    else COLORS["accent"]
                )
            else:
                color = COLORS["input"]
            self.create_rectangle(0, y1, width, y2, fill=color, outline="")


class ServerDialog(tk.Toplevel):
    SERVER_TYPES = {
        "Icecast 2": "icecast2",
        "SHOUTcast 1": "shoutcast1",
        "SHOUTcast 2 (compatible source)": "shoutcast2",
    }

    def __init__(
        self,
        parent: tk.Misc,
        profile: ServerProfile | None,
        password: str,
        on_save: callable,
    ) -> None:
        super().__init__(parent)
        self.title("Edit station" if profile else "Add station")
        self.geometry("620x680")
        self.configure(background=COLORS["bg"])
        self.transient(parent)
        self.grab_set()
        self.profile = profile or ServerProfile()
        self.on_save = on_save
        self.variables = {
            "name": tk.StringVar(value=self.profile.name),
            "server_type": tk.StringVar(
                value=next(
                    (
                        label
                        for label, value in self.SERVER_TYPES.items()
                        if value == self.profile.server_type
                    ),
                    "Icecast 2",
                )
            ),
            "host": tk.StringVar(value=self.profile.host),
            "port": tk.StringVar(value=str(self.profile.port)),
            "mount": tk.StringVar(value=self.profile.mount),
            "username": tk.StringVar(value=self.profile.username),
            "stream_id": tk.StringVar(value=str(self.profile.stream_id)),
            "port_plus_one": tk.BooleanVar(
                value=self.profile.shoutcast_port_plus_one
            ),
            "password": tk.StringVar(value=password),
            "tls": tk.BooleanVar(value=self.profile.use_tls),
            "station_name": tk.StringVar(value=self.profile.station_name),
            "description": tk.StringVar(value=self.profile.description),
            "genre": tk.StringVar(value=self.profile.genre),
            "website": tk.StringVar(value=self.profile.website),
        }
        self._build()
        _fit_window(self, 620, 680, 540, 560)

    def _build(self) -> None:
        frame = ttk.Frame(self, padding=22)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Station connection", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text="Use the connection details provided by your radio host.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(4, 12))

        ttk.Label(frame, text="Server type").pack(anchor="w", pady=(9, 4))
        server_type = ttk.Combobox(
            frame,
            textvariable=self.variables["server_type"],
            values=list(self.SERVER_TYPES),
            state="readonly",
        )
        server_type.pack(fill="x", ipady=4)
        server_type.bind("<<ComboboxSelected>>", self._server_type_changed)

        connection = ttk.Frame(frame)
        connection.pack(fill="x")
        connection.columnconfigure(1, weight=1)
        self.connection_rows: dict[str, tuple[ttk.Label, ttk.Entry]] = {}
        fields = [
            ("Profile name", "name"),
            ("Server address", "host"),
            ("Port", "port"),
            ("Stream path", "mount"),
            ("Source username", "username"),
            ("Stream ID (SID)", "stream_id"),
            ("Source password", "password"),
        ]
        for row_number, (label, key) in enumerate(fields):
            label_widget = ttk.Label(connection, text=label)
            label_widget.grid(
                row=row_number,
                column=0,
                sticky="w",
                padx=(0, 14),
                pady=(6, 0),
            )
            entry = ttk.Entry(
                connection,
                textvariable=self.variables[key],
                show="●" if key == "password" else "",
            )
            entry.grid(
                row=row_number,
                column=1,
                sticky="ew",
                ipady=5,
                pady=(6, 0),
            )
            self.connection_rows[key] = (label_widget, entry)

        self.port_plus_one = ttk.Checkbutton(
            frame,
            text="Use port + 1 for the source connection (SHOUTcast standard)",
            variable=self.variables["port_plus_one"],
        )
        self.port_plus_one.pack(anchor="w", pady=(8, 0))
        self.tls_check = ttk.Checkbutton(
            frame,
            text="Use a secure TLS connection (only if your host supports it)",
            variable=self.variables["tls"],
        )
        self.tls_check.pack(anchor="w", pady=(5, 2))

        details = ttk.LabelFrame(frame, text="Station information (optional)", padding=14)
        details.pack(fill="x", pady=(10, 2))
        for label, key in [
            ("Public station name", "station_name"),
            ("Description", "description"),
            ("Genre", "genre"),
            ("Website", "website"),
        ]:
            row = ttk.Frame(details)
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=label, width=21).pack(side="left")
            ttk.Entry(row, textvariable=self.variables[key]).pack(
                side="left", fill="x", expand=True
            )

        self.error = ttk.Label(frame, text="", style="Error.TLabel", wraplength=510)
        self.error.pack(anchor="w", pady=(8, 0))
        actions = ttk.Frame(frame)
        actions.pack(side="bottom", fill="x", pady=(12, 0))
        ttk.Button(actions, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(
            actions,
            text="Save station",
            style="Accent.TButton",
            command=self._save,
        ).pack(side="right", padx=(0, 10))
        self._server_type_changed()

    def _server_type_changed(self, _event: object = None) -> None:
        server_type = self.SERVER_TYPES[self.variables["server_type"].get()]
        if _event is not None:
            if (
                server_type.startswith("shoutcast")
                and self.variables["username"].get().strip() == "source"
            ):
                self.variables["username"].set("")
            elif (
                server_type == "icecast2"
                and not self.variables["username"].get().strip()
            ):
                self.variables["username"].set("source")
        visible = {"name", "host", "port", "password"}
        if server_type == "icecast2":
            visible.update({"mount", "username"})
            self.port_plus_one.pack_forget()
        elif server_type == "shoutcast2":
            visible.update({"username", "stream_id"})
            if not self.port_plus_one.winfo_manager():
                self.port_plus_one.pack(before=self.tls_check, anchor="w", pady=(8, 0))
        else:
            if not self.port_plus_one.winfo_manager():
                self.port_plus_one.pack(before=self.tls_check, anchor="w", pady=(8, 0))
        for key, widgets in self.connection_rows.items():
            for widget in widgets:
                if key in visible:
                    widget.grid()
                else:
                    widget.grid_remove()

    def _save(self) -> None:
        try:
            port = int(self.variables["port"].get())
            stream_id = int(self.variables["stream_id"].get())
        except ValueError:
            self.error.configure(text="Port and Stream ID must be whole numbers.")
            return
        profile = ServerProfile(
            id=self.profile.id,
            name=self.variables["name"].get(),
            server_type=self.SERVER_TYPES[self.variables["server_type"].get()],
            host=self.variables["host"].get(),
            port=port,
            mount=self.variables["mount"].get(),
            username=self.variables["username"].get(),
            stream_id=stream_id,
            shoutcast_port_plus_one=self.variables["port_plus_one"].get(),
            use_tls=self.variables["tls"].get(),
            station_name=self.variables["station_name"].get(),
            description=self.variables["description"].get(),
            genre=self.variables["genre"].get(),
            website=self.variables["website"].get(),
            personal_listener_peak=self.profile.personal_listener_peak,
        ).normalized()
        errors = profile.validate()
        if errors:
            self.error.configure(text=" ".join(errors))
            return
        self.on_save(profile, self.variables["password"].get())
        self.destroy()


class ServerManager(tk.Toplevel):
    def __init__(self, parent: "SimpleCastApp") -> None:
        super().__init__(parent)
        self.app = parent
        self.title("Manage stations")
        self.geometry("880x470")
        self.configure(background=COLORS["bg"])
        self.transient(parent)
        self._build()
        self.refresh()
        _fit_window(self, 880, 470, 660, 400)

    def _build(self) -> None:
        frame = ttk.Frame(self, padding=24)
        frame.pack(fill="both", expand=True)
        heading = ttk.Frame(frame)
        heading.pack(fill="x")
        ttk.Label(heading, text="Your stations", style="Title.TLabel").pack(side="left")
        ttk.Button(
            heading,
            text="+ Add station",
            style="Accent.TButton",
            command=lambda: ServerDialog(self, None, "", self._save),
        ).pack(side="right")
        ttk.Label(
            frame,
            text="Include one or more stations in the next broadcast.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(4, 16))
        self.tree = ttk.Treeview(
            frame,
            columns=(
                "name",
                "favorite",
                "type",
                "address",
                "listeners",
                "status",
            ),
            show="headings",
            selectmode="browse",
        )
        self.tree.heading("name", text="STATION")
        self.tree.heading("favorite", text="FAVORITE")
        self.tree.heading("type", text="CONNECTION")
        self.tree.heading("address", text="ADDRESS")
        self.tree.heading("listeners", text="PERSONAL HIGH")
        self.tree.heading("status", text="BROADCAST")
        self.tree.column("name", width=145)
        self.tree.column("favorite", width=78, anchor="center")
        self.tree.column("type", width=105)
        self.tree.column("address", width=205)
        self.tree.column("listeners", width=105, anchor="center")
        self.tree.column("status", width=95, anchor="center")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda _event: self.edit())

        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=(14, 0))
        ttk.Button(
            actions,
            text="Include / exclude",
            command=self.toggle_enabled,
        ).pack(side="left")
        ttk.Button(
            actions,
            text="★ Favorite",
            command=self.toggle_favorite,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Edit", command=self.edit).pack(side="left", padx=8)
        ttk.Button(actions, text="Test", command=self.test).pack(side="left")
        ttk.Button(actions, text="Delete", command=self.delete).pack(side="left", padx=8)
        ttk.Button(actions, text="Close", command=self.destroy).pack(side="right")

    def selected_profile(self) -> ServerProfile | None:
        selection = self.tree.selection()
        if not selection:
            return None
        server_id = selection[0]
        return next((item for item in self.app.config.servers if item.id == server_id), None)

    def refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for server in self.app.config.servers:
            connection_names = {
                "icecast2": "Icecast 2",
                "shoutcast1": "SHOUTcast 1",
                "shoutcast2": "SHOUTcast 2",
            }
            connection = connection_names.get(server.server_type, "Icecast 2")
            if server.use_tls:
                connection += " + TLS"
            address = f"{server.host}:{server.port}"
            if server.server_type == "icecast2":
                address += server.mount
            elif server.server_type == "shoutcast2":
                address += f" · SID {server.stream_id}"
            selected = (
                "☑ Included"
                if server.id in self.app.config.enabled_server_ids
                else "☐ Excluded"
            )
            favorite = (
                "★ Yes"
                if server.id in self.app.config.favorite_server_ids
                else "☆ No"
            )
            self.tree.insert(
                "",
                "end",
                iid=server.id,
                values=(
                    server.name,
                    favorite,
                    connection,
                    address,
                    server.personal_listener_peak,
                    selected,
                ),
            )
        if self.app.config.selected_server_id in self.tree.get_children():
            self.tree.selection_set(self.app.config.selected_server_id)

    def _save(self, profile: ServerProfile, password: str) -> None:
        existing = next(
            (item for item in self.app.config.servers if item.id == profile.id), None
        )
        if existing:
            index = self.app.config.servers.index(existing)
            self.app.config.servers[index] = profile
        else:
            self.app.config.servers.append(profile)
            if not self.app.config.selected_server_id:
                self.app.config.selected_server_id = profile.id
            if profile.id not in self.app.config.enabled_server_ids:
                self.app.config.enabled_server_ids.append(profile.id)
        self.app.store.set_password(profile.id, password)
        self.app.save_config()
        self.refresh()
        self.app.refresh_station()

    def edit(self) -> None:
        profile = self.selected_profile()
        if not profile:
            messagebox.showinfo("Choose a station", "Select a station to edit.", parent=self)
            return
        ServerDialog(
            self,
            profile,
            self.app.store.get_password(profile.id),
            self._save,
        )

    def toggle_enabled(self) -> None:
        profile = self.selected_profile()
        if not profile:
            messagebox.showinfo("Choose a station", "Select a station first.", parent=self)
            return
        self.app.config.selected_server_id = profile.id
        if profile.id in self.app.config.enabled_server_ids:
            self.app.config.enabled_server_ids.remove(profile.id)
        else:
            self.app.config.enabled_server_ids.append(profile.id)
        self.app.save_config()
        self.refresh()
        self.app.refresh_station()

    def toggle_favorite(self) -> None:
        profile = self.selected_profile()
        if not profile:
            messagebox.showinfo("Choose a station", "Select a station first.", parent=self)
            return
        if profile.id in self.app.config.favorite_server_ids:
            self.app.config.favorite_server_ids.remove(profile.id)
        else:
            if len(self.app.config.favorite_server_ids) >= 6:
                messagebox.showinfo(
                    "Six favorites already selected",
                    (
                        "SimpleCast shows up to six favorite stations on the "
                        "dashboard. Remove one favorite before adding another."
                    ),
                    parent=self,
                )
                return
            self.app.config.favorite_server_ids.append(profile.id)
        self.app.save_config()
        self.refresh()
        self.app.refresh_station()

    def test(self) -> None:
        profile = self.selected_profile()
        if profile:
            self.app.test_server(profile, parent=self)

    def delete(self) -> None:
        profile = self.selected_profile()
        if not profile:
            return
        if not messagebox.askyesno(
            "Delete station?",
            f"Remove “{profile.name}” from SimpleCast?",
            parent=self,
        ):
            return
        self.app.config.servers.remove(profile)
        if profile.id in self.app.config.enabled_server_ids:
            self.app.config.enabled_server_ids.remove(profile.id)
        if profile.id in self.app.config.favorite_server_ids:
            self.app.config.favorite_server_ids.remove(profile.id)
        self.app.store.delete_password(profile.id)
        if self.app.config.selected_server_id == profile.id:
            self.app.config.selected_server_id = (
                self.app.config.servers[0].id if self.app.config.servers else ""
            )
        self.app.save_config()
        self.refresh()
        self.app.refresh_station()


class SimpleCastApp(tk.Tk):
    SHUTDOWN_GRACE_MS = 5000
    FORCE_EXIT_SECONDS = 8.0

    def __init__(self) -> None:
        super().__init__()
        self.log_path = configure_logging()
        self.store = ConfigStore()
        self.config = self.store.load()
        self.active_skin = self.config.ui_skin
        COLORS.clear()
        COLORS.update(_appearance_profile(self.config)["colors"])
        try:
            self.iconbitmap(
                default=str(
                    _resource_path("assets", "simplecast.ico")
                )
            )
        except tk.TclError:
            pass
        self.title(f"SimpleCast {__version__}")
        preferred_width, preferred_height, minimum_width, minimum_height = (
            SKIN_WINDOW_SIZES[self.active_skin]
        )
        self.geometry(f"{preferred_width}x{preferred_height}")
        self.minsize(minimum_width, minimum_height)
        self.configure(background=COLORS["bg"])
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.gain = GainControl(self.config.input_volume_percent)
        self.audio = AudioEngine(self.gain)
        self.devices: list[AudioDevice] = []
        self.current_device: AudioDevice | None = None
        self._meter_levels = (0.0, 0.0)
        self._meter_peak = 0.0
        self.last_test_path = Path(tempfile.gettempdir()) / "simplecast_sound_test.wav"
        self.processed_test_path = (
            Path(tempfile.gettempdir()) / "simplecast_sound_test_processed.wav"
        )
        self._test_ready = False
        self._last_clip_warning = 0.0
        self.state = BroadcastState.OFFLINE
        self.sleep_preventer = SleepPreventer()
        self.stream = MultiStreamEngine(
            self._on_stream_state,
            self._on_server_stream_state,
            self._on_level,
            self.gain,
            self._resolve_device,
            self._on_broadcast_recording,
        )
        self.recording = RecordingEngine(
            self._on_recording_state,
            self._on_level,
            self.gain,
            self._resolve_device,
        )
        self.metadata_watcher = MetadataFileWatcher(
            self._on_metadata_file_title,
            self._on_metadata_watcher_status,
        )
        self.metadata_delivery = MetadataDeliveryEngine(
            self._on_metadata_delivery_result
        )
        self.auto_metadata_title = ""
        self.metadata_generation = 0
        self.metadata_delivery_results: dict[str, bool | None] = {}
        self.listener_counts: dict[str, int] = {}
        self.listener_errors: dict[str, str] = {}
        self._listener_polling: set[str] = set()
        self._available_update: UpdateRelease | None = None
        self._update_download_active = False
        self.tray = TrayController(
            lambda: self.after(0, self.show_window),
            lambda: self.after(0, self._tray_toggle_broadcast),
            lambda: self.after(0, self.close),
            lambda: self.stream.active,
        )
        self._volume_save_job: str | None = None
        self._closing = False
        self._restart_requested = False
        self._launched_by_windows = "--startup" in sys.argv[1:]
        self._auto_start_active = False
        self._auto_start_job: str | None = None
        self._auto_start_remaining = 0
        self._shutdown_clean = threading.Event()
        self._shutdown_steps: dict[str, threading.Event] = {}
        self._configure_styles()
        self._build()
        if self._launched_by_windows and self.config.start_minimized:
            self.withdraw()
        self.update_idletasks()
        _fit_window(
            self,
            preferred_width,
            preferred_height,
            minimum_width,
            minimum_height,
        )
        self.refresh_devices()
        self.refresh_station()
        self.after(200, self._sync_metadata_watcher)
        self.bind("<Unmap>", self._on_unmap)
        try:
            self.tray.start()
        except Exception:
            logging.exception("Could not start the Windows tray icon")
        self.after(500, self._update_timer)
        self.after(50, self._poll_meter_levels)
        self.after(1200, self._poll_listener_stats)
        self.after(400, self._apply_launch_automation)

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        theme = (
            THEMES[self.config.ui_theme]
            if self.active_skin == "Classic SimpleCast"
            else SKIN_PROFILES[self.active_skin]
        )
        font_size = int(theme["font_size"])
        button_padding = theme["button_padding"]

        # The combobox popup is a classic Tk Listbox, not a ttk widget. Its
        # palette must be configured separately or Windows can use light system
        # colors that conflict with the dark readonly field.
        self.option_add("*TCombobox*Listbox.background", COLORS["input"])
        self.option_add("*TCombobox*Listbox.foreground", COLORS["text"])
        self.option_add(
            "*TCombobox*Listbox.selectBackground",
            COLORS["accent"],
        )
        self.option_add(
            "*TCombobox*Listbox.selectForeground",
            COLORS["accent_text"],
        )
        self.option_add("*TCombobox*Listbox.font", ("Segoe UI", font_size))
        self.option_add("*TCombobox*Listbox.relief", "flat")
        self.option_add("*TCombobox*Listbox.borderWidth", 0)

        style.configure(".", font=("Segoe UI", font_size), background=COLORS["bg"])
        style.configure("TFrame", background=COLORS["bg"])
        style.configure("Card.TFrame", background=COLORS["surface"])
        style.configure("Sidebar.TFrame", background=COLORS["sidebar"])
        style.configure(
            "TLabel", background=COLORS["bg"], foreground=COLORS["text"]
        )
        style.configure(
            "Sidebar.TLabel",
            background=COLORS["sidebar"],
            foreground=COLORS["sidebar_text"],
        )
        style.configure(
            "SidebarMuted.TLabel",
            background=COLORS["sidebar"],
            foreground=COLORS["sidebar_muted"],
        )
        style.configure(
            "Card.TLabel", background=COLORS["surface"], foreground=COLORS["text"]
        )
        style.configure(
            "Muted.TLabel", background=COLORS["bg"], foreground=COLORS["muted"]
        )
        style.configure(
            "CardMuted.TLabel",
            background=COLORS["surface"],
            foreground=COLORS["muted"],
        )
        style.configure(
            "Title.TLabel",
            background=COLORS["bg"],
            foreground=COLORS["text"],
            font=("Segoe UI Semibold", 19),
        )
        style.configure(
            "CardTitle.TLabel",
            background=COLORS["surface"],
            foreground=COLORS["text"],
            font=("Segoe UI Semibold", 12),
        )
        style.configure(
            "Hero.TLabel",
            background=COLORS["bg"],
            foreground=COLORS["text"],
            font=("Segoe UI Semibold", 26),
        )
        style.configure(
            "PageTitle.TLabel",
            background=COLORS["bg"],
            foreground=COLORS["text"],
            font=("Segoe UI Semibold", 22),
        )
        style.configure(
            "Status.TLabel",
            background=COLORS["bg"],
            foreground=COLORS["offline"],
            font=("Segoe UI Semibold", 10),
        )
        style.configure(
            "Error.TLabel", background=COLORS["bg"], foreground=COLORS["error"]
        )
        style.configure(
            "TButton",
            background=COLORS["surface_alt"],
            foreground=COLORS["text"],
            borderwidth=0,
            padding=button_padding,
            relief="flat",
        )
        style.map(
            "TButton",
            background=[
                ("disabled", COLORS["disabled"]),
                ("pressed", COLORS["input"]),
                ("active", COLORS["surface_hover"]),
            ],
            foreground=[
                ("disabled", COLORS["disabled_text"]),
                ("!disabled", COLORS["text"]),
            ],
        )
        style.configure(
            "Compact.TButton",
            background=COLORS["surface_alt"],
            foreground=COLORS["text"],
            borderwidth=0,
            padding=(5, 7),
            font=("Segoe UI", 9),
        )
        style.map(
            "Compact.TButton",
            background=[
                ("disabled", COLORS["disabled"]),
                ("active", COLORS["surface_hover"]),
            ],
            foreground=[
                ("disabled", COLORS["disabled_text"]),
                ("!disabled", COLORS["text"]),
            ],
        )
        style.configure(
            "Nav.TButton",
            background=COLORS["sidebar"],
            foreground=COLORS["sidebar_muted"],
            anchor="w",
            font=("Segoe UI Semibold", 11),
            padding=(18, 13),
        )
        style.map(
            "Nav.TButton",
            background=[
                ("active", COLORS["surface_alt"]),
                ("pressed", COLORS["surface_alt"]),
            ],
            foreground=[
                ("active", COLORS["sidebar_accent"]),
                ("!disabled", COLORS["sidebar_muted"]),
            ],
        )
        style.configure(
            "NavActive.TButton",
            background=COLORS["surface_alt"],
            foreground=COLORS["sidebar_accent"],
            anchor="w",
            font=("Segoe UI Semibold", 11),
            padding=(18, 13),
        )
        style.map(
            "NavActive.TButton",
            background=[("active", COLORS["surface_hover"])],
            foreground=[("!disabled", COLORS["sidebar_accent"])],
        )
        style.configure(
            "TopNav.TButton",
            background=COLORS["bg"],
            foreground=COLORS["muted"],
            font=("Segoe UI Semibold", 10),
            padding=(18, 12),
            borderwidth=0,
        )
        style.map(
            "TopNav.TButton",
            background=[("active", COLORS["surface_alt"])],
            foreground=[("active", COLORS["accent"])],
        )
        style.configure(
            "TopNavActive.TButton",
            background=COLORS["bg"],
            foreground=COLORS["accent"],
            font=("Segoe UI Semibold", 10),
            padding=(18, 12),
            borderwidth=0,
        )
        style.map(
            "TopNavActive.TButton",
            background=[("active", COLORS["surface_alt"])],
            foreground=[("!disabled", COLORS["accent"])],
        )
        style.configure(
            "Favorite.TButton",
            background=COLORS["input"],
            foreground=COLORS["text"],
            anchor="w",
            font=("Segoe UI Semibold", 10),
            padding=(12, 8),
            borderwidth=1,
            bordercolor=COLORS["line"],
        )
        style.map(
            "Favorite.TButton",
            background=[
                ("disabled", COLORS["disabled"]),
                ("active", COLORS["surface_hover"]),
            ],
            foreground=[
                ("disabled", COLORS["disabled_text"]),
                ("!disabled", COLORS["text"]),
            ],
            bordercolor=[("active", COLORS["accent"])],
        )
        style.configure(
            "FavoriteSelected.TButton",
            background=COLORS["accent_dark"],
            foreground=COLORS["accent"],
            anchor="w",
            font=("Segoe UI Semibold", 10),
            padding=(12, 8),
            borderwidth=2,
            bordercolor=COLORS["accent"],
        )
        style.map(
            "FavoriteSelected.TButton",
            background=[("active", "#194941")],
            foreground=[("!disabled", COLORS["accent"])],
        )
        style.configure(
            "Accent.TButton",
            background=COLORS["accent"],
            foreground=COLORS["accent_text"],
            font=("Segoe UI Semibold", 10),
        )
        style.map(
            "Accent.TButton",
            background=[
                ("disabled", COLORS["disabled"]),
                ("pressed", COLORS["accent"]),
                ("active", COLORS["accent_hover"]),
            ],
            foreground=[
                ("disabled", COLORS["disabled_text"]),
                ("!disabled", COLORS["accent_text"]),
            ],
        )
        style.configure(
            "Broadcast.TButton",
            background=COLORS["accent"],
            foreground=COLORS["accent_text"],
            font=("Segoe UI Semibold", 15),
            padding=(20, 12),
        )
        style.map(
            "Broadcast.TButton",
            background=[
                ("disabled", COLORS["disabled"]),
                ("pressed", COLORS["accent"]),
                ("active", COLORS["accent_hover"]),
            ],
            foreground=[
                ("disabled", COLORS["disabled_text"]),
                ("!disabled", COLORS["accent_text"]),
            ],
        )
        style.configure(
            "Stop.TButton",
            background=COLORS["error"],
            foreground=COLORS["error_text"],
            font=("Segoe UI Semibold", 15),
            padding=(20, 12),
        )
        style.configure(
            "TEntry",
            fieldbackground=COLORS["input"],
            foreground=COLORS["text"],
            insertcolor=COLORS["text"],
            bordercolor=COLORS["line"],
            lightcolor=COLORS["line"],
            darkcolor=COLORS["line"],
            borderwidth=1,
            padding=(9, 7),
        )
        style.map(
            "TEntry",
            fieldbackground=[
                ("disabled", COLORS["disabled"]),
                ("focus", COLORS["input_hover"]),
                ("!disabled", COLORS["input"]),
            ],
            foreground=[
                ("disabled", COLORS["disabled_text"]),
                ("!disabled", COLORS["text"]),
            ],
            bordercolor=[
                ("focus", COLORS["accent"]),
                ("!focus", COLORS["line"]),
            ],
            lightcolor=[
                ("focus", COLORS["accent"]),
                ("!focus", COLORS["line"]),
            ],
            darkcolor=[
                ("focus", COLORS["accent"]),
                ("!focus", COLORS["line"]),
            ],
        )
        style.configure(
            "TCombobox",
            fieldbackground=COLORS["input"],
            background=COLORS["surface_alt"],
            foreground=COLORS["text"],
            arrowcolor=COLORS["text"],
            bordercolor=COLORS["line"],
            lightcolor=COLORS["line"],
            darkcolor=COLORS["line"],
            borderwidth=1,
            arrowsize=16,
            padding=(9, 7),
        )
        style.map(
            "TCombobox",
            fieldbackground=[
                ("disabled", COLORS["disabled"]),
                ("focus", COLORS["input_hover"]),
                ("readonly", COLORS["input"]),
            ],
            background=[
                ("disabled", COLORS["disabled"]),
                ("pressed", COLORS["accent_dark"]),
                ("active", COLORS["surface_hover"]),
                ("readonly", COLORS["surface_alt"]),
            ],
            foreground=[
                ("disabled", COLORS["disabled_text"]),
                ("readonly", COLORS["text"]),
            ],
            arrowcolor=[
                ("disabled", COLORS["disabled_text"]),
                ("readonly", COLORS["text"]),
            ],
            bordercolor=[
                ("focus", COLORS["accent"]),
                ("!focus", COLORS["line"]),
            ],
            lightcolor=[
                ("focus", COLORS["accent"]),
                ("!focus", COLORS["line"]),
            ],
            darkcolor=[
                ("focus", COLORS["accent"]),
                ("!focus", COLORS["line"]),
            ],
        )
        style.configure(
            "TCheckbutton",
            background=COLORS["bg"],
            foreground=COLORS["text"],
        )
        style.configure(
            "Card.TCheckbutton",
            background=COLORS["surface"],
            foreground=COLORS["text"],
        )
        style.configure(
            "Horizontal.TScale",
            background=COLORS["surface"],
            troughcolor=COLORS["input"],
            bordercolor=COLORS["input"],
            lightcolor=COLORS["accent"],
            darkcolor=COLORS["accent"],
            sliderlength=18,
            sliderthickness=18,
        )
        style.configure(
            "TLabelframe",
            background=COLORS["bg"],
            foreground=COLORS["muted"],
            bordercolor=COLORS["line"],
        )
        style.configure(
            "TLabelframe.Label",
            background=COLORS["bg"],
            foreground=COLORS["muted"],
        )
        style.configure(
            "Treeview",
            background=COLORS["surface"],
            fieldbackground=COLORS["surface"],
            foreground=COLORS["text"],
            rowheight=36,
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            background=COLORS["surface_alt"],
            foreground=COLORS["muted"],
            borderwidth=0,
        )
        style.map(
            "Treeview",
            background=[("selected", COLORS["accent_dark"])],
            foreground=[("selected", COLORS["text"])],
        )

    def _card(self, parent: tk.Misc) -> ttk.Frame:
        return ttk.Frame(parent, padding=16, style="Card.TFrame")

    def _build(self) -> None:
        if self.active_skin in {"Studio Workspace", "Studio Dark"}:
            self._build_top_shell()
        else:
            self._build_sidebar_shell()

    def _build_sidebar_shell(self) -> None:
        shell = ttk.Frame(self)
        shell.pack(fill="both", expand=True)
        compact = self.active_skin == "Broadcast Console"
        sidebar_width = 176 if compact else 218
        sidebar = ttk.Frame(
            shell,
            width=sidebar_width,
            style="Sidebar.TFrame",
        )
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        content = ttk.Frame(shell)
        content.pack(side="left", fill="both", expand=True)

        brand = ttk.Frame(
            sidebar,
            style="Sidebar.TFrame",
            padding=((16, 20) if compact else (22, 24)),
        )
        brand.pack(fill="x")
        ttk.Label(
            brand,
            text="SIMP" if compact else "◉  SimpleCast",
            style="Sidebar.TLabel",
            font=("Segoe UI Semibold", 16 if compact else 18),
        ).pack(anchor="w")

        self.nav_buttons: dict[str, ttk.Button] = {}
        for page_name, icon in (
            ("Dashboard", "⌂"),
            ("Stations", "⌁"),
            ("Recordings", "●"),
            ("Settings", "⚙"),
        ):
            command = (
                self.manage_servers
                if page_name == "Stations"
                else lambda name=page_name: self._show_page(name)
            )
            button = ttk.Button(
                sidebar,
                text=(
                    f"{icon}  {page_name}"
                    if compact
                    else f"{icon}   {page_name}"
                ),
                style="Nav.TButton",
                command=command,
            )
            button.pack(fill="x", padx=12, pady=2)
            self.nav_buttons[page_name] = button

        sidebar_footer = ttk.Frame(
            sidebar,
            style="Sidebar.TFrame",
            padding=((16, 16) if compact else (22, 18)),
        )
        sidebar_footer.pack(side="bottom", fill="x")
        ttk.Separator(sidebar_footer).pack(fill="x", pady=(0, 15))
        self.sidebar_connection_label = ttk.Label(
            sidebar_footer,
            text="●  Connection ready",
            style="Sidebar.TLabel",
        )
        self.sidebar_connection_label.pack(anchor="w")
        self.recording_status_label = ttk.Label(
            sidebar_footer,
            text="●  Recording off",
            style="SidebarMuted.TLabel",
            wraplength=140 if compact else 175,
        )
        self.recording_status_label.pack(anchor="w", pady=(9, 15))
        ttk.Label(
            sidebar_footer,
            text="By Doversoft,\nthank you for trying it out",
            style="SidebarMuted.TLabel",
            justify="left",
            wraplength=135 if compact else 175,
        ).pack(anchor="w")
        ttk.Label(
            sidebar_footer,
            text=f"SimpleCast {__version__}",
            style="SidebarMuted.TLabel",
        ).pack(anchor="w", pady=(7, 0))

        header = ttk.Frame(content, padding=(30, 14, 30, 8))
        header.pack(fill="x")
        title_group = ttk.Frame(header)
        title_group.pack(side="left")
        ttk.Label(title_group, text="SimpleCast", style="Hero.TLabel").pack(anchor="w")
        ttk.Label(
            title_group,
            text="Broadcasting without all the fuzz",
            style="Muted.TLabel",
        ).pack(anchor="w")
        status_group = ttk.Frame(header)
        status_group.pack(side="right")
        self.status_label = ttk.Label(
            status_group,
            text="● OFFLINE",
            style="Status.TLabel",
        )
        self.status_label.pack(anchor="e")
        self.timer_label = ttk.Label(status_group, text="", style="Muted.TLabel")
        self.timer_label.pack(anchor="e", pady=(3, 0))

        viewport = ttk.Frame(content)
        viewport.pack(fill="both", expand=True)
        self.content_canvas = tk.Canvas(
            viewport,
            background=COLORS["bg"],
            highlightthickness=0,
            borderwidth=0,
        )
        scrollbar = ttk.Scrollbar(
            viewport,
            orient="vertical",
            command=self.content_canvas.yview,
        )
        self.content_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.content_canvas.pack(side="left", fill="both", expand=True)
        self.page_host = ttk.Frame(self.content_canvas, padding=(30, 8, 22, 6))
        self.content_window = self.content_canvas.create_window(
            (0, 0),
            window=self.page_host,
            anchor="nw",
        )
        self.page_host.bind(
            "<Configure>",
            lambda _event: self.content_canvas.configure(
                scrollregion=self.content_canvas.bbox("all")
            ),
        )
        self.content_canvas.bind(
            "<Configure>",
            lambda event: self.content_canvas.itemconfigure(
                self.content_window,
                width=event.width,
            ),
        )
        self.bind_all("<MouseWheel>", self._scroll_content, add="+")
        # Tk's default TCombobox class binding changes the selected value when
        # the wheel is used over a closed field. Replace that binding entirely.
        # An open dropdown is a separate Listbox window, so its own normal
        # wheel scrolling remains available for long lists.
        self.bind_class(
            "TCombobox",
            "<MouseWheel>",
            self._ignore_closed_combobox_wheel,
        )

        self.pages = {
            "Dashboard": ttk.Frame(self.page_host),
            "Recordings": ttk.Frame(self.page_host),
            "Settings": ttk.Frame(self.page_host),
        }
        self.content_frame = self.pages["Dashboard"]
        self._build_dashboard(self.pages["Dashboard"])
        self._build_recordings_page(self.pages["Recordings"])
        self._build_settings_page(self.pages["Settings"])
        self._show_page("Dashboard")

    def _build_top_shell(self) -> None:
        shell = ttk.Frame(self)
        shell.pack(fill="both", expand=True)

        topbar = ttk.Frame(shell, padding=(24, 10))
        topbar.pack(fill="x")
        brand = ttk.Frame(topbar)
        brand.pack(side="left")
        ttk.Label(
            brand,
            text="SIMP",
            style="Title.TLabel",
            foreground=COLORS["accent"],
            font=("Segoe UI Semibold", 16),
        ).pack(side="left")
        ttk.Label(
            brand,
            text="SimpleCast",
            style="Title.TLabel",
            font=("Segoe UI Semibold", 16),
        ).pack(side="left", padx=(16, 0))

        navigation = ttk.Frame(topbar)
        navigation.pack(side="left", padx=(52, 0))
        self.nav_buttons = {}
        for page_name, label in (
            ("Dashboard", "Broadcast"),
            ("Recordings", "Recordings"),
            ("Settings", "Settings"),
        ):
            button = ttk.Button(
                navigation,
                text=label,
                style="TopNav.TButton",
                command=lambda name=page_name: self._show_page(name),
            )
            button.pack(side="left", padx=2)
            self.nav_buttons[page_name] = button
        station_button = ttk.Button(
            navigation,
            text="Stations",
            style="TopNav.TButton",
            command=self.manage_servers,
        )
        station_button.pack(side="left", padx=2)
        self.nav_buttons["Stations"] = station_button

        status_group = ttk.Frame(topbar)
        status_group.pack(side="right")
        self.status_label = ttk.Label(
            status_group,
            text="● OFFLINE",
            style="Status.TLabel",
        )
        self.status_label.pack(side="left", padx=(0, 14))
        self.sidebar_connection_label = ttk.Label(
            status_group,
            text="●  Connection ready",
            style="Muted.TLabel",
        )
        self.sidebar_connection_label.pack(side="left", padx=(0, 14))
        self.recording_status_label = ttk.Label(
            status_group,
            text="●  Recording off",
            style="Muted.TLabel",
        )
        self.recording_status_label.pack(side="left")
        self.timer_label = ttk.Label(
            status_group,
            text="",
            style="Muted.TLabel",
        )
        self.timer_label.pack(side="left", padx=(12, 0))

        ttk.Separator(shell).pack(fill="x")
        content = ttk.Frame(shell)
        content.pack(fill="both", expand=True)
        viewport = ttk.Frame(content)
        viewport.pack(fill="both", expand=True)
        self.content_canvas = tk.Canvas(
            viewport,
            background=COLORS["bg"],
            highlightthickness=0,
            borderwidth=0,
        )
        scrollbar = ttk.Scrollbar(
            viewport,
            orient="vertical",
            command=self.content_canvas.yview,
        )
        self.content_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.content_canvas.pack(side="left", fill="both", expand=True)
        self.page_host = ttk.Frame(
            self.content_canvas,
            padding=(28, 14, 20, 8),
        )
        self.content_window = self.content_canvas.create_window(
            (0, 0),
            window=self.page_host,
            anchor="nw",
        )
        self.page_host.bind(
            "<Configure>",
            lambda _event: self.content_canvas.configure(
                scrollregion=self.content_canvas.bbox("all")
            ),
        )
        self.content_canvas.bind(
            "<Configure>",
            lambda event: self.content_canvas.itemconfigure(
                self.content_window,
                width=event.width,
            ),
        )
        self.bind_all("<MouseWheel>", self._scroll_content, add="+")
        self.bind_class(
            "TCombobox",
            "<MouseWheel>",
            self._ignore_closed_combobox_wheel,
        )

        self.pages = {
            "Dashboard": ttk.Frame(self.page_host),
            "Recordings": ttk.Frame(self.page_host),
            "Settings": ttk.Frame(self.page_host),
        }
        self.content_frame = self.pages["Dashboard"]
        self._build_dashboard(self.pages["Dashboard"])
        self._build_recordings_page(self.pages["Recordings"])
        self._build_settings_page(self.pages["Settings"])
        footer = ttk.Frame(shell, padding=(24, 5))
        footer.pack(fill="x")
        ttk.Label(
            footer,
            text=(
                "By Doversoft, thank you for trying it out"
                f"   ·   SimpleCast {__version__}"
            ),
            style="Muted.TLabel",
        ).pack()
        self._show_page("Dashboard")

    def _build_dashboard(self, root: ttk.Frame) -> None:
        if self.active_skin == "Classic SimpleCast":
            self._build_dashboard_classic(root)
        elif self.active_skin == "Broadcast Console":
            self._build_dashboard_console(root)
        else:
            self._build_dashboard_studio(root)

    def _build_dashboard_classic(self, root: ttk.Frame) -> None:
        self.favorite_columns = 3
        self.startup_banner = self._card(root)
        startup_banner_row = ttk.Frame(self.startup_banner, style="Card.TFrame")
        startup_banner_row.pack(fill="x")
        self.startup_status_label = ttk.Label(
            startup_banner_row,
            text="Preparing automatic broadcast…",
            style="Card.TLabel",
        )
        self.startup_status_label.pack(side="left", fill="x", expand=True)
        ttk.Button(
            startup_banner_row,
            text="Cancel automatic start",
            command=self.cancel_automatic_start,
        ).pack(side="right", padx=(12, 0))

        favorites = ttk.Frame(root, padding=14, style="Card.TFrame")
        favorites.pack(fill="x", pady=(0, 10))
        favorite_top = ttk.Frame(favorites, style="Card.TFrame")
        favorite_top.pack(fill="x")
        ttk.Label(
            favorite_top,
            text="Broadcast to",
            style="CardTitle.TLabel",
        ).pack(side="left")

        server_controls = ttk.Frame(favorites, style="Card.TFrame")
        server_controls.pack(fill="x", pady=(9, 0))
        server_controls.columnconfigure(0, weight=1)
        self.server_choice_var = tk.StringVar()
        self.server_choice_combo = ttk.Combobox(
            server_controls,
            textvariable=self.server_choice_var,
            state="readonly",
            width=24,
        )
        self.server_choice_combo.grid(row=0, column=0, sticky="ew")
        self.server_choice_combo.bind(
            "<<ComboboxSelected>>",
            self._server_choice_selected,
        )
        self.add_server_button = ttk.Button(
            server_controls,
            text="Add server",
            command=self.add_server,
        )
        self.add_server_button.grid(row=0, column=1, padx=(8, 0))
        self.edit_server_button = ttk.Button(
            server_controls,
            text="Edit",
            command=self.edit_selected_server,
        )
        self.edit_server_button.grid(row=0, column=2, padx=(8, 0))
        self.delete_server_button = ttk.Button(
            server_controls,
            text="Delete",
            command=self.delete_selected_server,
        )
        self.delete_server_button.grid(row=0, column=3, padx=(8, 0))
        self.manage_servers_button = ttk.Button(
            server_controls,
            text="Manage stations",
            command=self.manage_servers,
        )
        self.manage_servers_button.grid(row=0, column=4, padx=(8, 0))
        self.server_control_widgets = (
            self.server_choice_combo,
            self.add_server_button,
            self.edit_server_button,
            self.delete_server_button,
            self.manage_servers_button,
        )
        self.favorite_grid = ttk.Frame(favorites, style="Card.TFrame")
        self.favorite_grid.pack(fill="x", pady=(8, 0))
        for column in range(3):
            self.favorite_grid.columnconfigure(column, weight=1)
        self.favorite_buttons: list[ttk.Button] = []

        self.dashboard_body = ttk.Frame(root)
        self.dashboard_body.pack(fill="both", expand=True)
        self.dashboard_body.columnconfigure(0, weight=3, uniform="dashboard")
        self.dashboard_body.columnconfigure(1, weight=2, uniform="dashboard")
        self.dashboard_body.rowconfigure(1, weight=1)

        sound = self._card(self.dashboard_body)
        self.sound_card = sound
        sound.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 6))
        top = ttk.Frame(sound, style="Card.TFrame")
        top.pack(fill="x")
        ttk.Label(top, text="Audio Input", style="CardTitle.TLabel").pack(side="left")
        ttk.Button(top, text="Refresh", command=self.refresh_devices).pack(side="right")
        audio_body = ttk.Frame(sound, style="Card.TFrame")
        audio_body.pack(fill="both", expand=True, pady=(8, 0))
        audio_body.columnconfigure(0, weight=1)
        controls = ttk.Frame(audio_body, style="Card.TFrame")
        controls.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        meters = ttk.Frame(audio_body, style="Card.TFrame")
        meters.grid(row=0, column=1, sticky="ns")

        ttk.Label(controls, text="Device", style="CardMuted.TLabel").pack(anchor="w")
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(
            controls,
            textvariable=self.device_var,
            state="readonly",
        )
        self.device_combo.pack(fill="x", pady=(3, 6))
        self.device_combo.bind("<<ComboboxSelected>>", self._device_selected)

        audio_system_row = ttk.Frame(controls, style="Card.TFrame")
        audio_system_row.pack(fill="x", pady=(0, 6))
        ttk.Label(
            audio_system_row,
            text="Audio system",
            style="CardMuted.TLabel",
        ).pack(anchor="w")
        self.audio_system_var = tk.StringVar(value=self.config.audio_system)
        self.audio_system_combo = ttk.Combobox(
            audio_system_row,
            textvariable=self.audio_system_var,
            values=AUDIO_SYSTEMS,
            state="readonly",
        )
        self.audio_system_combo.pack(fill="x", pady=(3, 0))
        self.audio_system_combo.bind(
            "<<ComboboxSelected>>",
            self._audio_system_selected,
        )
        self.audio_api_status = ttk.Label(
            controls,
            text="Checking active audio system…",
            style="CardMuted.TLabel",
            wraplength=330,
        )
        self.audio_api_status.pack(anchor="w", pady=(0, 6))

        ttk.Label(controls, text="Input volume", style="CardMuted.TLabel").pack(anchor="w")
        volume_row = ttk.Frame(controls, style="Card.TFrame")
        volume_row.pack(fill="x", pady=(3, 6))
        self.volume_var = tk.DoubleVar(value=self.config.input_volume_percent)
        self.volume_slider = ttk.Scale(
            volume_row,
            from_=0,
            to=200,
            variable=self.volume_var,
            command=self._volume_changed,
        )
        self.volume_slider.pack(side="left", fill="x", expand=True)
        self.volume_label = ttk.Label(
            volume_row,
            text=f"{self.config.input_volume_percent}%",
            width=6,
            anchor="e",
            style="Card.TLabel",
        )
        self.volume_label.pack(side="left", padx=(8, 0))
        ttk.Button(
            volume_row,
            text="Reset",
            command=self._reset_volume,
        ).pack(side="left", padx=(8, 0))

        ttk.Label(controls, text="Processing", style="CardMuted.TLabel").pack(anchor="w")
        self.processing_var = tk.StringVar(value=self.config.processing_preset)
        self.processing_combo = ttk.Combobox(
            controls,
            textvariable=self.processing_var,
            values=list(PROCESSING_PRESETS),
            state="readonly",
        )
        self.processing_combo.pack(fill="x", pady=(3, 3))
        self.processing_combo.bind(
            "<<ComboboxSelected>>",
            self._processing_selected,
        )
        self.processing_detail = ttk.Label(
            controls,
            text=PROCESSING_PRESETS[self.config.processing_preset].description,
            style="CardMuted.TLabel",
            wraplength=330,
        )
        self.processing_detail.pack(anchor="w")
        self.sound_hint = ttk.Label(
            controls,
            text="Aim for healthy green movement without red peaks.",
            style="CardMuted.TLabel",
            wraplength=330,
        )
        self.sound_hint.pack(anchor="w", pady=(6, 0))

        ttk.Label(meters, text="L", style="CardMuted.TLabel").grid(row=0, column=0)
        ttk.Label(meters, text="R", style="CardMuted.TLabel").grid(row=0, column=1)
        self.left_meter = VerticalLevelMeter(meters)
        self.left_meter.grid(row=1, column=0, padx=(0, 8), pady=(5, 0))
        self.right_meter = VerticalLevelMeter(meters)
        self.right_meter.grid(row=1, column=1, pady=(5, 0))

        stream = self._card(self.dashboard_body)
        stream.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=(0, 6))
        ttk.Label(stream, text="Stream Settings", style="CardTitle.TLabel").pack(anchor="w")
        self.quality_var = tk.StringVar(value=self.config.quality)
        self.quality_combo = ttk.Combobox(
            stream,
            textvariable=self.quality_var,
            values=list(QUALITY_PRESETS),
            state="readonly",
        )
        self.quality_combo.pack(fill="x", pady=(8, 3))
        self.quality_combo.bind("<<ComboboxSelected>>", self._quality_selected)
        self.quality_detail = ttk.Label(
            stream,
            text=self._quality_description(self.config.quality),
            style="CardMuted.TLabel",
        )
        self.quality_detail.pack(anchor="w")
        sample_rate_label = next(
            (
                label
                for label, rate in SAMPLE_RATES.items()
                if rate == self.config.output_sample_rate
            ),
            "44.1 kHz",
        )
        self.sample_rate_var = tk.StringVar(value=sample_rate_label)
        self.sample_rate_combo = ttk.Combobox(
            stream,
            textvariable=self.sample_rate_var,
            values=list(SAMPLE_RATES),
            state="readonly",
        )
        self.sample_rate_combo.pack(fill="x", pady=(6, 3))
        self.sample_rate_combo.bind(
            "<<ComboboxSelected>>",
            self._sample_rate_selected,
        )
        self.station_name = ttk.Label(
            stream,
            text="No station added",
            style="Card.TLabel",
            font=("Segoe UI Semibold", 11),
        )
        self.station_detail = ttk.Label(
            stream,
            text="Add a station to continue.",
            style="CardMuted.TLabel",
            wraplength=370,
        )
        self.server_status_frame = ttk.Frame(stream, style="Card.TFrame")
        self.server_status_frame.pack(fill="x", pady=(6, 0))
        self.server_status_labels: dict[str, tuple[ttk.Label, ttk.Label]] = {}
        self.listener_status_labels: dict[str, ttk.Label] = {}
        self.test_server_button = ttk.Button(
            stream,
            text="Test connection",
            command=lambda: self.test_server(self.config.selected_server()),
        )
        self.test_server_button.pack(anchor="e", pady=(6, 0))

        metadata = self._card(self.dashboard_body)
        metadata.grid(row=1, column=1, sticky="nsew", padx=(6, 0), pady=(6, 0))
        ttk.Label(metadata, text="Now Playing", style="CardTitle.TLabel").pack(anchor="w")
        self.song_var = tk.StringVar()
        self.artist_var = tk.StringVar()
        self.title_var = tk.StringVar()
        ttk.Label(metadata, text="Artist", style="CardMuted.TLabel").pack(
            anchor="w", pady=(7, 2)
        )
        self.artist_entry = ttk.Entry(metadata, textvariable=self.artist_var)
        self.artist_entry.pack(fill="x")
        ttk.Label(metadata, text="Title", style="CardMuted.TLabel").pack(
            anchor="w", pady=(5, 2)
        )
        self.title_entry = ttk.Entry(metadata, textvariable=self.title_var)
        self.title_entry.pack(fill="x")
        self.metadata_button = ttk.Button(
            metadata,
            text="SEND NOW PLAYING",
            command=self.send_metadata,
        )
        self.metadata_button.pack(anchor="e", pady=(7, 0))

        action_row = ttk.Frame(root)
        action_row.pack(fill="x", pady=(6, 0))
        preview_actions = ttk.Frame(action_row)
        preview_actions.pack(side="left")
        self.sound_button = ttk.Button(
            preview_actions,
            text="🔊  Test my sound",
            command=self.test_sound,
        )
        self.sound_button.pack(side="left")
        self.play_original_button = ttk.Button(
            preview_actions,
            text="Play original",
            command=lambda: self._play_test_file(self.last_test_path),
            state="disabled",
        )
        self.play_original_button.pack(side="left", padx=(8, 0))
        self.play_processed_button = ttk.Button(
            preview_actions,
            text="Play processed",
            command=lambda: self._play_test_file(self.processed_test_path),
            state="disabled",
        )
        self.play_processed_button.pack(side="left", padx=(8, 0))
        self.broadcast_button = ttk.Button(
            action_row,
            text="▶  START BROADCAST",
            style="Broadcast.TButton",
            command=self.toggle_broadcast,
        )
        self.broadcast_button.pack(side="right", fill="x", expand=True, padx=(30, 0))
        self.detail_label = ttk.Label(
            root,
            text="Ready to broadcast",
            style="Muted.TLabel",
            anchor="e",
        )

    def _build_alt_startup_banner(self, root: ttk.Frame) -> None:
        self.startup_banner = self._card(root)
        row = ttk.Frame(self.startup_banner, style="Card.TFrame")
        row.pack(fill="x")
        self.startup_status_label = ttk.Label(
            row,
            text="Preparing automatic broadcast…",
            style="Card.TLabel",
        )
        self.startup_status_label.pack(side="left", fill="x", expand=True)
        ttk.Button(
            row,
            text="Cancel automatic start",
            command=self.cancel_automatic_start,
        ).pack(side="right", padx=(12, 0))

    def _build_alt_station_strip(self, root: ttk.Frame) -> None:
        self.favorite_columns = 6
        station = self._card(root)
        station.pack(fill="x", pady=(0, 10))
        controls = ttk.Frame(station, style="Card.TFrame")
        controls.pack(fill="x")
        controls.columnconfigure(0, weight=1)
        self.server_choice_var = tk.StringVar()
        self.server_choice_combo = ttk.Combobox(
            controls,
            textvariable=self.server_choice_var,
            state="readonly",
            width=28,
        )
        self.server_choice_combo.grid(row=0, column=0, sticky="ew")
        self.server_choice_combo.bind(
            "<<ComboboxSelected>>",
            self._server_choice_selected,
        )
        self.add_server_button = ttk.Button(
            controls,
            text="+  Add server",
            style="Accent.TButton",
            command=self.add_server,
        )
        self.add_server_button.grid(row=0, column=1, padx=(10, 0))
        self.edit_server_button = ttk.Button(
            controls,
            text="Edit",
            command=self.edit_selected_server,
        )
        self.edit_server_button.grid(row=0, column=2, padx=(8, 0))
        self.delete_server_button = ttk.Button(
            controls,
            text="Delete",
            command=self.delete_selected_server,
        )
        self.delete_server_button.grid(row=0, column=3, padx=(8, 0))
        self.manage_servers_button = ttk.Button(
            controls,
            text="Manage stations",
            command=self.manage_servers,
        )
        self.manage_servers_button.grid(row=0, column=4, padx=(8, 0))
        self.server_control_widgets = (
            self.server_choice_combo,
            self.add_server_button,
            self.edit_server_button,
            self.delete_server_button,
            self.manage_servers_button,
        )
        self.favorite_grid = ttk.Frame(station, style="Card.TFrame")
        self.favorite_grid.pack(fill="x", pady=(9, 0))
        for column in range(self.favorite_columns):
            self.favorite_grid.columnconfigure(column, weight=1)
        self.favorite_buttons = []

    def _build_alt_source_panel(
        self,
        parent: tk.Misc,
        *,
        include_meters: bool,
    ) -> ttk.Frame:
        panel = self._card(parent)
        self.sound_card = panel
        heading = ttk.Frame(panel, style="Card.TFrame")
        heading.pack(fill="x")
        ttk.Label(
            heading,
            text="Source" if not include_meters else "Audio Input",
            style="CardTitle.TLabel",
        ).pack(side="left")
        ttk.Button(
            heading,
            text="Refresh",
            command=self.refresh_devices,
        ).pack(side="right")

        ttk.Label(
            panel,
            text="Recording device",
            style="CardMuted.TLabel",
        ).pack(anchor="w", pady=(12, 3))
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(
            panel,
            textvariable=self.device_var,
            state="readonly",
        )
        self.device_combo.pack(fill="x")
        self.device_combo.bind("<<ComboboxSelected>>", self._device_selected)

        ttk.Label(
            panel,
            text="Audio system",
            style="CardMuted.TLabel",
        ).pack(anchor="w", pady=(9, 3))
        self.audio_system_var = tk.StringVar(value=self.config.audio_system)
        self.audio_system_combo = ttk.Combobox(
            panel,
            textvariable=self.audio_system_var,
            values=AUDIO_SYSTEMS,
            state="readonly",
        )
        self.audio_system_combo.pack(fill="x")
        self.audio_system_combo.bind(
            "<<ComboboxSelected>>",
            self._audio_system_selected,
        )
        self.audio_api_status = ttk.Label(
            panel,
            text="Checking active audio system…",
            style="CardMuted.TLabel",
            wraplength=330,
        )
        self.audio_api_status.pack(anchor="w", pady=(4, 8))

        ttk.Label(
            panel,
            text="Input volume",
            style="CardMuted.TLabel",
        ).pack(anchor="w")
        volume = ttk.Frame(panel, style="Card.TFrame")
        volume.pack(fill="x", pady=(3, 8))
        self.volume_var = tk.DoubleVar(value=self.config.input_volume_percent)
        self.volume_slider = ttk.Scale(
            volume,
            from_=0,
            to=200,
            variable=self.volume_var,
            command=self._volume_changed,
        )
        self.volume_slider.pack(side="left", fill="x", expand=True)
        self.volume_label = ttk.Label(
            volume,
            text=f"{self.config.input_volume_percent}%",
            width=6,
            anchor="e",
            style="Card.TLabel",
        )
        self.volume_label.pack(side="left", padx=(8, 0))
        ttk.Button(
            volume,
            text="Reset",
            command=self._reset_volume,
        ).pack(side="left", padx=(8, 0))

        ttk.Label(
            panel,
            text="Processing",
            style="CardMuted.TLabel",
        ).pack(anchor="w")
        self.processing_var = tk.StringVar(value=self.config.processing_preset)
        self.processing_combo = ttk.Combobox(
            panel,
            textvariable=self.processing_var,
            values=list(PROCESSING_PRESETS),
            state="readonly",
        )
        self.processing_combo.pack(fill="x", pady=(3, 3))
        self.processing_combo.bind(
            "<<ComboboxSelected>>",
            self._processing_selected,
        )
        self.processing_detail = ttk.Label(
            panel,
            text=PROCESSING_PRESETS[self.config.processing_preset].description,
            style="CardMuted.TLabel",
            wraplength=330,
        )
        self.processing_detail.pack(anchor="w")

        if include_meters:
            meter_area = ttk.Frame(panel, style="Card.TFrame")
            meter_area.pack(fill="x", pady=(14, 5))
            ttk.Label(
                meter_area,
                text="L",
                style="CardMuted.TLabel",
                width=2,
            ).grid(row=0, column=0, padx=(0, 8))
            self.left_meter = LevelMeter(meter_area)
            self.left_meter.grid(row=0, column=1, sticky="ew")
            ttk.Label(
                meter_area,
                text="R",
                style="CardMuted.TLabel",
                width=2,
            ).grid(row=1, column=0, padx=(0, 8), pady=(6, 0))
            self.right_meter = LevelMeter(meter_area)
            self.right_meter.grid(row=1, column=1, sticky="ew", pady=(6, 0))
            meter_area.columnconfigure(1, weight=1)

        self.sound_hint = ttk.Label(
            panel,
            text="Aim for healthy green movement without red peaks.",
            style="CardMuted.TLabel",
            wraplength=340,
        )
        self.sound_hint.pack(anchor="w", pady=(8, 0))
        preview = ttk.Frame(panel, style="Card.TFrame")
        preview.pack(fill="x", pady=(10, 0))
        for column in range(3):
            preview.columnconfigure(column, weight=1, uniform="preview")
        self.sound_button = ttk.Button(
            preview,
            text="Test my sound",
            style="Compact.TButton",
            command=self.test_sound,
        )
        self.sound_button.grid(row=0, column=0, sticky="ew")
        self.play_original_button = ttk.Button(
            preview,
            text="Original",
            style="Compact.TButton",
            command=lambda: self._play_test_file(self.last_test_path),
            state="disabled",
        )
        self.play_original_button.grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )
        self.play_processed_button = ttk.Button(
            preview,
            text="Processed",
            style="Compact.TButton",
            command=lambda: self._play_test_file(self.processed_test_path),
            state="disabled",
        )
        self.play_processed_button.grid(
            row=0, column=2, sticky="ew", padx=(6, 0)
        )
        return panel

    def _build_alt_signal_panel(self, parent: tk.Misc) -> ttk.Frame:
        panel = self._card(parent)
        ttk.Label(
            panel,
            text="Signal",
            style="CardTitle.TLabel",
        ).pack(anchor="w")
        scale = ttk.Frame(panel, style="Card.TFrame")
        scale.pack(fill="x", pady=(22, 7), padx=(30, 0))
        for index, label in enumerate(("-60", "-48", "-36", "-24", "-12", "-6", "0")):
            scale.columnconfigure(index, weight=1)
            ttk.Label(
                scale,
                text=label,
                style="CardMuted.TLabel",
            ).grid(row=0, column=index, sticky="e")

        left = ttk.Frame(panel, style="Card.TFrame")
        left.pack(fill="x", pady=(8, 16))
        ttk.Label(
            left,
            text="L",
            style="CardTitle.TLabel",
            width=2,
        ).pack(side="left")
        self.left_meter = LevelMeter(left, height=34)
        self.left_meter.pack(side="left", fill="x", expand=True, padx=(10, 0))
        right = ttk.Frame(panel, style="Card.TFrame")
        right.pack(fill="x", pady=(8, 0))
        ttk.Label(
            right,
            text="R",
            style="CardTitle.TLabel",
            width=2,
        ).pack(side="left")
        self.right_meter = LevelMeter(right, height=34)
        self.right_meter.pack(side="left", fill="x", expand=True, padx=(10, 0))
        ttk.Label(
            panel,
            text=(
                "Green is healthy. Yellow is close to the limit. "
                "Red means the input should be lowered."
            ),
            style="CardMuted.TLabel",
            wraplength=520,
        ).pack(anchor="w", pady=(22, 0))
        return panel

    def _build_alt_on_air_panel(self, parent: tk.Misc) -> ttk.Frame:
        panel = self._card(parent)
        ttk.Label(
            panel,
            text="On air",
            style="CardTitle.TLabel",
        ).pack(anchor="w")
        self.quality_var = tk.StringVar(value=self.config.quality)
        self.quality_combo = ttk.Combobox(
            panel,
            textvariable=self.quality_var,
            values=list(QUALITY_PRESETS),
            state="readonly",
        )
        self.quality_combo.pack(fill="x", pady=(12, 3))
        self.quality_combo.bind("<<ComboboxSelected>>", self._quality_selected)
        self.quality_detail = ttk.Label(
            panel,
            text=self._quality_description(self.config.quality),
            style="CardMuted.TLabel",
        )
        self.quality_detail.pack(anchor="w")
        sample_rate_label = next(
            (
                label
                for label, rate in SAMPLE_RATES.items()
                if rate == self.config.output_sample_rate
            ),
            "44.1 kHz",
        )
        self.sample_rate_var = tk.StringVar(value=sample_rate_label)
        self.sample_rate_combo = ttk.Combobox(
            panel,
            textvariable=self.sample_rate_var,
            values=list(SAMPLE_RATES),
            state="readonly",
        )
        self.sample_rate_combo.pack(fill="x", pady=(7, 3))
        self.sample_rate_combo.bind(
            "<<ComboboxSelected>>",
            self._sample_rate_selected,
        )

        ttk.Separator(panel).pack(fill="x", pady=12)
        self.station_name = ttk.Label(
            panel,
            text="No station added",
            style="Card.TLabel",
            font=("Segoe UI Semibold", 11),
        )
        self.station_name.pack(anchor="w")
        self.station_detail = ttk.Label(
            panel,
            text="Add a station to continue.",
            style="CardMuted.TLabel",
            wraplength=360,
        )
        self.station_detail.pack(anchor="w", pady=(2, 0))
        self.server_status_frame = ttk.Frame(panel, style="Card.TFrame")
        self.server_status_frame.pack(fill="x", pady=(6, 0))
        self.server_status_labels = {}
        self.listener_status_labels = {}
        self.test_server_button = ttk.Button(
            panel,
            text="Test connection",
            command=lambda: self.test_server(self.config.selected_server()),
        )
        self.test_server_button.pack(anchor="e", pady=(5, 0))

        ttk.Separator(panel).pack(fill="x", pady=12)
        ttk.Label(
            panel,
            text="Now Playing",
            style="CardTitle.TLabel",
        ).pack(anchor="w")
        self.song_var = tk.StringVar()
        self.artist_var = tk.StringVar()
        self.title_var = tk.StringVar()
        ttk.Label(
            panel,
            text="Artist",
            style="CardMuted.TLabel",
        ).pack(anchor="w", pady=(7, 2))
        self.artist_entry = ttk.Entry(panel, textvariable=self.artist_var)
        self.artist_entry.pack(fill="x")
        ttk.Label(
            panel,
            text="Title",
            style="CardMuted.TLabel",
        ).pack(anchor="w", pady=(6, 2))
        self.title_entry = ttk.Entry(panel, textvariable=self.title_var)
        self.title_entry.pack(fill="x")
        self.metadata_button = ttk.Button(
            panel,
            text="SEND NOW PLAYING",
            command=self.send_metadata,
        )
        self.metadata_button.pack(anchor="e", pady=(8, 0))
        return panel

    def _build_alt_broadcast_dock(self, root: ttk.Frame) -> None:
        dock = self._card(root)
        dock.pack(fill="x", pady=(10, 0))
        summary = ttk.Frame(dock, style="Card.TFrame")
        summary.pack(side="left", fill="x", expand=True)
        ttk.Label(
            summary,
            text="Ready for the selected station",
            style="Card.TLabel",
            font=("Segoe UI Semibold", 11),
        ).pack(anchor="w")
        self.detail_label = ttk.Label(
            summary,
            text="Ready to broadcast",
            style="CardMuted.TLabel",
        )
        self.detail_label.pack(anchor="w", pady=(2, 0))
        self.broadcast_button = ttk.Button(
            dock,
            text="▶  START BROADCAST",
            style="Broadcast.TButton",
            command=self.toggle_broadcast,
        )
        self.broadcast_button.pack(
            side="right",
            fill="x",
            expand=True,
            padx=(30, 0),
        )

    def _build_dashboard_console(self, root: ttk.Frame) -> None:
        self._build_alt_startup_banner(root)
        self._build_alt_station_strip(root)
        body = ttk.Frame(root)
        self.dashboard_body = body
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=3, uniform="console")
        body.columnconfigure(1, weight=2, uniform="console")
        body.rowconfigure(0, weight=1)
        source = self._build_alt_source_panel(body, include_meters=True)
        source.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        on_air = self._build_alt_on_air_panel(body)
        on_air.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self._build_alt_broadcast_dock(root)

    def _build_dashboard_studio(self, root: ttk.Frame) -> None:
        self._build_alt_startup_banner(root)
        self._build_alt_station_strip(root)
        body = ttk.Frame(root)
        self.dashboard_body = body
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=3, uniform="studio")
        body.columnconfigure(1, weight=5, uniform="studio")
        body.columnconfigure(2, weight=3, uniform="studio")
        body.rowconfigure(0, weight=1)
        source = self._build_alt_source_panel(body, include_meters=False)
        source.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        signal = self._build_alt_signal_panel(body)
        signal.grid(row=0, column=1, sticky="nsew", padx=6)
        on_air = self._build_alt_on_air_panel(body)
        on_air.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        self._build_alt_broadcast_dock(root)

    def _build_recordings_page(self, root: ttk.Frame) -> None:
        ttk.Label(root, text="Recordings", style="PageTitle.TLabel").pack(anchor="w")
        ttk.Label(
            root,
            text="Capture a 320 kbps MP3 locally, with or without broadcasting.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(2, 18))
        recording = self._card(root)
        recording.pack(fill="x")
        recording_top = ttk.Frame(recording, style="Card.TFrame")
        recording_top.pack(fill="x")
        ttk.Label(
            recording_top,
            text="Local recording",
            style="CardTitle.TLabel",
        ).pack(side="left")
        ttk.Label(
            recording_top,
            text=f"MP3 · {RECORDING_BITRATE} kbps",
            style="CardMuted.TLabel",
        ).pack(side="right")
        folder_row = ttk.Frame(recording, style="Card.TFrame")
        folder_row.pack(fill="x", pady=(14, 10))
        self.recording_folder_var = tk.StringVar(value=str(self._recording_folder()))
        self.recording_folder_entry = ttk.Entry(
            folder_row,
            textvariable=self.recording_folder_var,
            state="readonly",
        )
        self.recording_folder_entry.pack(side="left", fill="x", expand=True)
        self.recording_folder_button = ttk.Button(
            folder_row,
            text="Choose folder",
            command=self.choose_recording_folder,
        )
        self.recording_folder_button.pack(side="right", padx=(10, 0))
        recording_actions = ttk.Frame(recording, style="Card.TFrame")
        recording_actions.pack(fill="x")
        self.record_broadcasts_var = tk.BooleanVar(value=self.config.record_broadcasts)
        self.record_broadcasts_check = ttk.Checkbutton(
            recording_actions,
            text="Record every broadcast",
            variable=self.record_broadcasts_var,
            command=self._record_broadcasts_changed,
            style="Card.TCheckbutton",
        )
        self.record_broadcasts_check.pack(side="left")
        self.recording_button = ttk.Button(
            recording_actions,
            text="Record without broadcasting",
            command=self.toggle_recording,
        )
        self.recording_button.pack(side="right")

    def _build_settings_page(self, root: ttk.Frame) -> None:
        ttk.Label(root, text="Settings", style="PageTitle.TLabel").pack(anchor="w")
        ttk.Label(
            root,
            text="Appearance, automation, metadata integration, and support tools.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(2, 18))

        appearance = self._card(root)
        appearance.pack(fill="x", pady=(0, 12))
        appearance_top = ttk.Frame(appearance, style="Card.TFrame")
        appearance_top.pack(fill="x")
        ttk.Label(
            appearance_top,
            text="Interface skin",
            style="CardTitle.TLabel",
        ).pack(side="left")
        self.skin_var = tk.StringVar(value=self.config.ui_skin)
        self.skin_combo = ttk.Combobox(
            appearance_top,
            textvariable=self.skin_var,
            values=list(SKINS),
            state="readonly",
            width=24,
        )
        self.skin_combo.pack(side="right")
        self.skin_combo.bind("<<ComboboxSelected>>", self._skin_selected)
        self.skin_description = ttk.Label(
            appearance,
            text=str(SKINS[self.config.ui_skin]["description"]),
            style="CardMuted.TLabel",
            wraplength=780,
        )
        self.skin_description.pack(anchor="w", pady=(10, 0))

        theme_row = ttk.Frame(appearance, style="Card.TFrame")
        theme_row.pack(fill="x", pady=(12, 0))
        ttk.Label(
            theme_row,
            text="Classic appearance variation",
            style="CardMuted.TLabel",
        ).pack(side="left")
        self.theme_var = tk.StringVar(value=self.config.ui_theme)
        self.theme_combo = ttk.Combobox(
            theme_row,
            textvariable=self.theme_var,
            values=CLASSIC_THEMES,
            state="readonly",
            width=24,
        )
        self.theme_combo.pack(side="right")
        self.theme_combo.bind("<<ComboboxSelected>>", self._theme_selected)
        self.theme_description = ttk.Label(
            appearance,
            text=(
                str(THEMES[self.config.ui_theme]["description"])
                if self.config.ui_skin == "Classic SimpleCast"
                else (
                    "Classic variations are available when the "
                    "Classic SimpleCast skin is selected."
                )
            ),
            style="CardMuted.TLabel",
            wraplength=780,
        )
        self.theme_description.pack(anchor="w", pady=(6, 0))
        if self.config.ui_skin != "Classic SimpleCast":
            self.theme_combo.configure(state="disabled")

        metadata = self._card(root)
        metadata.pack(fill="x", pady=(0, 12))
        ttk.Label(
            metadata,
            text="Automatic metadata from a text file",
            style="CardTitle.TLabel",
        ).pack(anchor="w")
        metadata_auto_row = ttk.Frame(metadata, style="Card.TFrame")
        metadata_auto_row.pack(fill="x", pady=(12, 0))
        self.metadata_auto_var = tk.BooleanVar(value=self.config.metadata_auto)
        self.metadata_auto_check = ttk.Checkbutton(
            metadata_auto_row,
            text="Enable text-file updates",
            variable=self.metadata_auto_var,
            command=self._metadata_auto_changed,
            style="Card.TCheckbutton",
        )
        self.metadata_auto_check.pack(side="left")
        self.metadata_format_var = tk.StringVar(value=self.config.metadata_format)
        self.metadata_format_combo = ttk.Combobox(
            metadata_auto_row,
            textvariable=self.metadata_format_var,
            values=METADATA_FORMATS,
            state="readonly",
            width=31,
        )
        self.metadata_format_combo.pack(side="right")
        self.metadata_format_combo.bind(
            "<<ComboboxSelected>>",
            self._metadata_format_changed,
        )
        metadata_file_row = ttk.Frame(metadata, style="Card.TFrame")
        metadata_file_row.pack(fill="x", pady=(8, 0))
        self.metadata_file_var = tk.StringVar(
            value=self.config.metadata_file or "No metadata file selected"
        )
        self.metadata_file_entry = ttk.Entry(
            metadata_file_row,
            textvariable=self.metadata_file_var,
            state="readonly",
        )
        self.metadata_file_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(
            metadata_file_row,
            text="Choose text file",
            command=self.choose_metadata_file,
        ).pack(side="right", padx=(10, 0))
        self.metadata_status_label = ttk.Label(
            metadata,
            text="Automatic metadata is off",
            style="CardMuted.TLabel",
            wraplength=780,
        )
        self.metadata_status_label.pack(anchor="w", pady=(7, 0))

        automation = self._card(root)
        automation.pack(fill="x", pady=(0, 12))
        ttk.Label(
            automation,
            text="Startup automation",
            style="CardTitle.TLabel",
        ).pack(anchor="w")
        automation_options = ttk.Frame(automation, style="Card.TFrame")
        automation_options.pack(fill="x", pady=(12, 0))
        self.start_with_windows_var = tk.BooleanVar(
            value=self.config.start_with_windows
        )
        ttk.Checkbutton(
            automation_options,
            text="Start SimpleCast with Windows",
            variable=self.start_with_windows_var,
            command=self._start_with_windows_changed,
            style="Card.TCheckbutton",
        ).grid(row=0, column=0, sticky="w")
        self.start_minimized_var = tk.BooleanVar(value=self.config.start_minimized)
        ttk.Checkbutton(
            automation_options,
            text="Start minimized to the tray",
            variable=self.start_minimized_var,
            command=self._startup_setting_changed,
            style="Card.TCheckbutton",
        ).grid(row=1, column=0, sticky="w", pady=(7, 0))
        self.auto_broadcast_var = tk.BooleanVar(value=self.config.auto_broadcast)
        ttk.Checkbutton(
            automation_options,
            text="Automatically start broadcasting",
            variable=self.auto_broadcast_var,
            command=self._startup_setting_changed,
            style="Card.TCheckbutton",
        ).grid(row=2, column=0, sticky="w", pady=(7, 0))
        ttk.Label(
            automation_options,
            text="Countdown",
            style="CardMuted.TLabel",
        ).grid(row=0, column=1, sticky="e", padx=(28, 8))
        delay_label = next(
            (
                label
                for label, seconds in STARTUP_DELAYS.items()
                if seconds == self.config.startup_delay_seconds
            ),
            "10 seconds",
        )
        self.startup_delay_var = tk.StringVar(value=delay_label)
        self.startup_delay_combo = ttk.Combobox(
            automation_options,
            textvariable=self.startup_delay_var,
            values=list(STARTUP_DELAYS),
            state="readonly",
            width=13,
        )
        self.startup_delay_combo.grid(row=0, column=2, sticky="e")
        self.startup_delay_combo.bind(
            "<<ComboboxSelected>>",
            self._startup_setting_changed,
        )
        automation_options.columnconfigure(0, weight=1)

        updates = self._card(root)
        updates.pack(fill="x", pady=(0, 12))
        update_top = ttk.Frame(updates, style="Card.TFrame")
        update_top.pack(fill="x")
        ttk.Label(
            update_top,
            text="Software updates",
            style="CardTitle.TLabel",
        ).pack(side="left")
        self.update_button = ttk.Button(
            update_top,
            text="Check for updates",
            command=self.check_for_updates,
        )
        self.update_button.pack(side="right")
        self.update_status_label = ttk.Label(
            updates,
            text=(
                f"Installed version: {__version__}. "
                "Updates are checked only when you click the button."
            ),
            style="CardMuted.TLabel",
            wraplength=780,
        )
        self.update_status_label.pack(anchor="w", pady=(10, 0))

        support = self._card(root)
        support.pack(fill="x")
        ttk.Label(support, text="Support", style="CardTitle.TLabel").pack(anchor="w")
        support_actions = ttk.Frame(support, style="Card.TFrame")
        support_actions.pack(fill="x", pady=(12, 0))
        ttk.Button(
            support_actions,
            text="Export support report",
            command=self.export_report,
        ).pack(side="left")
        ttk.Button(
            support_actions,
            text="Run readiness check",
            command=self.run_readiness_check,
        ).pack(side="left", padx=(8, 0))
        ttk.Label(
            support_actions,
            text="Icecast + SHOUTcast MP3",
            style="CardMuted.TLabel",
        ).pack(side="right")

    def _show_page(self, page_name: str) -> None:
        page = self.pages.get(page_name)
        if page is None:
            return
        for current in self.pages.values():
            current.pack_forget()
        page.pack(fill="both", expand=True)
        top_navigation = self.active_skin in {
            "Studio Workspace",
            "Studio Dark",
        }
        for name, button in self.nav_buttons.items():
            button.configure(
                style=(
                    "TopNavActive.TButton"
                    if top_navigation and name == page_name
                    else "TopNav.TButton"
                    if top_navigation
                    else "NavActive.TButton"
                    if name == page_name
                    else "Nav.TButton"
                )
            )
        self.content_canvas.yview_moveto(0)
        self.after(
            0,
            lambda: self.content_canvas.configure(
                scrollregion=self.content_canvas.bbox("all")
            ),
        )

    def save_config(self) -> None:
        try:
            self.store.save(self.config)
        except OSError as error:
            messagebox.showerror("Could not save settings", str(error), parent=self)

    def check_for_updates(self) -> None:
        if self._update_download_active:
            return
        self.update_button.configure(state="disabled", text="Checking…")
        self.update_status_label.configure(
            text="Checking published SimpleCast releases on GitHub…",
            foreground=COLORS["muted"],
        )

        def worker() -> None:
            try:
                release = check_for_update(
                    __version__,
                    include_prereleases="-" in __version__,
                )
                error = ""
            except Exception as problem:
                logging.warning("Update check failed: %s", problem)
                release = None
                error = str(problem) or "The update check failed"
            try:
                self.after(
                    0,
                    lambda: self._apply_update_check(release, error),
                )
            except RuntimeError:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _apply_update_check(
        self,
        release: UpdateRelease | None,
        error: str,
    ) -> None:
        if self._closing:
            return
        self.update_button.configure(
            state="normal",
            text="Check for updates",
        )
        if error:
            self.update_status_label.configure(
                text=f"Could not check for updates: {error}",
                foreground=COLORS["error"],
            )
            return
        if release is None:
            self._available_update = None
            self.update_status_label.configure(
                text=f"SimpleCast {__version__} is up to date.",
                foreground=COLORS["accent"],
            )
            return
        self._available_update = release
        self.update_status_label.configure(
            text=(
                f"SimpleCast {release.version} is available"
                + (" as a beta release." if release.prerelease else ".")
            ),
            foreground=COLORS["accent"],
        )
        notes = " ".join(release.notes.strip().split())
        if len(notes) > 900:
            notes = f"{notes[:897]}…"
        detail = (
            f"Installed: {__version__}\n"
            f"Available: {release.version}\n\n"
        )
        if notes:
            detail += f"{notes}\n\n"
        detail += (
            "Download and verify the Windows installer now?\n\n"
            "SimpleCast will ask again before launching it."
        )
        if messagebox.askyesno(
            "SimpleCast update available",
            detail,
            parent=self,
        ):
            self._download_update(release)

    def _download_update(self, release: UpdateRelease) -> None:
        if self.stream.active or self.recording.active:
            self.update_status_label.configure(
                text=(
                    f"Version {release.version} is available. Stop broadcasting "
                    "or recording before installing it."
                ),
                foreground=COLORS["warning"],
            )
            messagebox.showinfo(
                "Stop audio first",
                (
                    "Stop the broadcast or recording, then click "
                    "Check for updates again."
                ),
                parent=self,
            )
            return
        self._update_download_active = True
        self.update_button.configure(state="disabled", text="Downloading…")
        self.update_status_label.configure(
            text=f"Downloading SimpleCast {release.version}…",
            foreground=COLORS["muted"],
        )

        def worker() -> None:
            last_percent = -1

            def progress(received: int, total: int) -> None:
                nonlocal last_percent
                percent = min(100, int(received * 100 / max(1, total)))
                if percent == last_percent:
                    return
                last_percent = percent
                try:
                    self.after(
                        0,
                        lambda: self._apply_update_progress(
                            release.version,
                            percent,
                        ),
                    )
                except RuntimeError:
                    pass

            try:
                path = download_installer(
                    release,
                    progress_callback=progress,
                )
                error = ""
            except Exception as problem:
                logging.warning("Update download failed: %s", problem)
                path = None
                error = str(problem) or "The update download failed"
            try:
                self.after(
                    0,
                    lambda: self._apply_update_download(
                        release,
                        path,
                        error,
                    ),
                )
            except RuntimeError:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _apply_update_progress(self, version: str, percent: int) -> None:
        if not self._closing and self._update_download_active:
            self.update_status_label.configure(
                text=f"Downloading SimpleCast {version}… {percent}%"
            )

    def _apply_update_download(
        self,
        release: UpdateRelease,
        path: Path | None,
        error: str,
    ) -> None:
        if self._closing:
            return
        self._update_download_active = False
        self.update_button.configure(
            state="normal",
            text="Check for updates",
        )
        if error or path is None:
            self.update_status_label.configure(
                text=f"Could not prepare the update: {error}",
                foreground=COLORS["error"],
            )
            return
        self.update_status_label.configure(
            text=(
                f"SimpleCast {release.version} was downloaded and passed "
                "SHA-256 verification."
            ),
            foreground=COLORS["accent"],
        )
        if messagebox.askyesno(
            "Update ready to install",
            (
                f"SimpleCast {release.version} is verified and ready.\n\n"
                "Launch the installer and close SimpleCast now?"
            ),
            parent=self,
        ):
            self._launch_update_installer(path)

    def _launch_update_installer(self, path: Path) -> None:
        if self.stream.active or self.recording.active:
            messagebox.showinfo(
                "Stop audio first",
                "Stop broadcasting or recording before installing the update.",
                parent=self,
            )
            return
        try:
            subprocess.Popen([str(path)], close_fds=True)
        except OSError as error:
            self.update_status_label.configure(
                text=f"Could not launch the installer: {error}",
                foreground=COLORS["error"],
            )
            return
        logging.info("Verified update installer launched: %s", path.name)
        self.close()

    def refresh_devices(self) -> None:
        try:
            self.devices = list_input_devices()
        except Exception as error:
            logging.exception("Could not enumerate audio devices")
            self.devices = []
            self.sound_hint.configure(text=f"Audio devices unavailable: {error}")
        labels = [device.label for device in self.devices]
        self.device_combo.configure(values=labels)
        selected: AudioDevice | None = None
        has_saved_name = bool(self.config.selected_device_name)
        if has_saved_name:
            selected = next(
                (
                    item
                    for item in self.devices
                    if item.name == self.config.selected_device_name
                ),
                None,
            )
        if (
            selected is None
            and not has_saved_name
            and self.config.selected_device is not None
        ):
            selected = next(
                (
                    item
                    for item in self.devices
                    if item.index == self.config.selected_device
                ),
                None,
            )
        if selected is None and self.devices and not has_saved_name:
            selected = self.devices[0]
        self.current_device = selected
        if selected:
            self.device_var.set(selected.label)
            self.config.selected_device = selected.index
            self.config.selected_device_name = selected.name
            self.save_config()
            # WASAPI may invoke its first callback during InputStream.start().
            # Delay initial capture until Tk's event loop is active so that
            # callback can safely schedule meter updates on the UI thread.
            self.after(100, self._start_meter)
        else:
            if has_saved_name:
                self.device_var.set(
                    f"{self.config.selected_device_name} — unavailable"
                )
                self.audio_api_status.configure(
                    text="Connect the saved audio device, then refresh"
                )
            else:
                self.device_var.set("No recording devices found")
                self.audio_api_status.configure(text="No audio input is available")

    def _device_selected(self, _event: object = None) -> None:
        label = self.device_var.get()
        selected = next((item for item in self.devices if item.label == label), None)
        if selected:
            self.current_device = selected
            self.config.selected_device = selected.index
            self.config.selected_device_name = selected.name
            self.save_config()
            self._start_meter()

    def _audio_system_selected(self, _event: object = None) -> None:
        self.config.audio_system = self.audio_system_var.get()
        self.audio_api_status.configure(text="Opening selected audio system…")
        self.save_config()
        self._start_meter()

    @staticmethod
    def _resolve_device(device: AudioDevice) -> AudioDevice:
        matches = [
            item
            for item in list_input_devices()
            if item.name == device.name
        ]
        if not matches:
            raise RuntimeError(
                f"Audio device “{device.name}” is disconnected. "
                "SimpleCast will keep trying."
            )
        return matches[0]

    def _quality_selected(self, _event: object = None) -> None:
        self.config.quality = self.quality_var.get()
        self.quality_detail.configure(
            text=self._quality_description(self.config.quality)
        )
        self.save_config()

    def _sample_rate_selected(self, _event: object = None) -> None:
        self.config.output_sample_rate = SAMPLE_RATES.get(
            self.sample_rate_var.get(),
            44100,
        )
        self.save_config()

    def _processing_selected(self, _event: object = None) -> None:
        self.config.processing_preset = self.processing_var.get()
        preset = PROCESSING_PRESETS[self.config.processing_preset]
        self.processing_detail.configure(text=preset.description)
        self._test_ready = False
        self.play_original_button.configure(state="disabled")
        self.play_processed_button.configure(state="disabled")
        self.save_config()

    def _skin_selected(self, _event: object = None) -> None:
        skin_name = self.skin_var.get()
        if skin_name not in SKINS:
            return
        self.config.ui_skin = skin_name
        self.skin_description.configure(
            text=str(SKINS[skin_name]["description"])
        )
        if skin_name == "Classic SimpleCast":
            self.theme_combo.configure(state="readonly")
            self.theme_description.configure(
                text=str(THEMES[self.config.ui_theme]["description"])
            )
        else:
            self.theme_combo.configure(state="disabled")
            self.theme_description.configure(
                text=(
                    "Classic variations are available when the "
                    "Classic SimpleCast skin is selected."
                )
            )
        self.save_config()
        if skin_name == self.active_skin:
            return
        if messagebox.askyesno(
            "Restart to apply skin?",
            (
                f"“{skin_name}” is saved as your interface skin.\n\n"
                "Restart SimpleCast now to apply the complete layout?"
            ),
            parent=self,
        ):
            self.restart_application()
        else:
            self.skin_description.configure(
                text=(
                    f"{SKINS[skin_name]['description']} "
                    "The new skin will be applied after SimpleCast restarts."
                )
            )

    def _theme_selected(self, _event: object = None) -> None:
        theme_name = self.theme_var.get()
        if theme_name not in THEMES:
            return
        self.config.ui_theme = theme_name
        self.theme_description.configure(
            text=str(THEMES[theme_name]["description"])
        )
        self.save_config()
        if (
            self.active_skin != "Classic SimpleCast"
            or self.config.ui_skin != "Classic SimpleCast"
        ):
            return
        COLORS.clear()
        COLORS.update(THEMES[theme_name]["colors"])
        self.configure(background=COLORS["bg"])
        self._configure_styles()
        self.content_canvas.configure(background=COLORS["bg"])
        self.left_meter.configure(background=COLORS["surface"])
        self.right_meter.configure(background=COLORS["surface"])
        self.left_meter.redraw()
        self.right_meter.redraw()
        state_colors = {
            BroadcastState.OFFLINE: COLORS["offline"],
            BroadcastState.CONNECTING: COLORS["warning"],
            BroadcastState.ON_AIR: COLORS["accent"],
            BroadcastState.RECONNECTING: COLORS["warning"],
            BroadcastState.ERROR: COLORS["error"],
        }
        self.status_label.configure(foreground=state_colors[self.state])
        sidebar_colors = dict(state_colors)
        if self.active_skin not in {"Studio Workspace", "Studio Dark"}:
            sidebar_colors[BroadcastState.OFFLINE] = COLORS["sidebar_muted"]
            sidebar_colors[BroadcastState.ON_AIR] = COLORS["sidebar_accent"]
        self.sidebar_connection_label.configure(
            foreground=sidebar_colors[self.state]
        )
        self.refresh_station()

    def restart_application(self) -> None:
        if self.stream.active or self.recording.active:
            messagebox.showinfo(
                "Stop audio first",
                (
                    "Stop broadcasting or recording before restarting "
                    "SimpleCast to change skins."
                ),
                parent=self,
            )
            return
        self._restart_requested = True
        self.close()

    @staticmethod
    def _restart_command() -> tuple[list[str], Path]:
        if getattr(sys, "frozen", False):
            executable = Path(sys.executable).resolve()
            return [str(executable)], executable.parent
        project_root = Path(__file__).resolve().parent.parent
        return [sys.executable, str(project_root / "main.py")], project_root

    def _launch_restart(self) -> None:
        command, working_directory = self._restart_command()
        try:
            subprocess.Popen(command, cwd=working_directory)
            logging.info("Restarted SimpleCast with skin %s", self.config.ui_skin)
        except OSError:
            logging.exception("Could not restart SimpleCast")

    def _start_with_windows_changed(self) -> None:
        enabled = self.start_with_windows_var.get()
        try:
            set_start_with_windows(enabled)
        except OSError as error:
            logging.exception("Could not update Windows startup registration")
            self.start_with_windows_var.set(self.config.start_with_windows)
            messagebox.showerror(
                "Could not change Windows startup",
                str(error),
                parent=self,
            )
            return
        self.config.start_with_windows = enabled
        self.save_config()

    def _startup_setting_changed(self, _event: object = None) -> None:
        self.config.start_minimized = self.start_minimized_var.get()
        self.config.auto_broadcast = self.auto_broadcast_var.get()
        self.config.startup_delay_seconds = STARTUP_DELAYS.get(
            self.startup_delay_var.get(),
            10,
        )
        self.save_config()

    def _apply_launch_automation(self) -> None:
        if self._closing:
            return
        if self.config.start_with_windows:
            try:
                # Refresh the registered path if a portable build was moved or
                # an installed version replaced an older executable.
                set_start_with_windows(True)
            except OSError:
                logging.exception("Could not refresh Windows startup registration")
        if self._launched_by_windows and self.config.start_minimized:
            self.withdraw()
            try:
                self.tray.notify(
                    "SimpleCast started with Windows",
                    "SimpleCast is running in the tray.",
                )
            except Exception:
                pass
        if self.config.auto_broadcast:
            self._begin_automatic_start()

    def _begin_automatic_start(self) -> None:
        if self.stream.active or self.recording.active or self._closing:
            return
        self._auto_start_active = True
        self._auto_start_remaining = self.config.startup_delay_seconds
        self.startup_banner.pack(
            fill="x",
            pady=(0, 12),
            before=self.dashboard_body,
        )
        self._automatic_start_tick()
        if self._launched_by_windows and self.config.start_minimized:
            try:
                self.tray.notify(
                    "Automatic broadcast scheduled",
                    (
                        "Broadcasting will start in "
                        f"{self._auto_start_remaining} seconds. "
                        "Open SimpleCast to cancel."
                    ),
                )
            except Exception:
                pass

    def _automatic_start_tick(self) -> None:
        self._auto_start_job = None
        if not self._auto_start_active or self._closing:
            return
        if self._auto_start_remaining > 0:
            self.startup_status_label.configure(
                text=(
                    "Automatic broadcast starts in "
                    f"{self._auto_start_remaining} seconds…"
                ),
                foreground=COLORS["warning"],
            )
            self._auto_start_remaining -= 1
            self._auto_start_job = self.after(
                1000,
                self._automatic_start_tick,
            )
            return
        self._attempt_automatic_broadcast()

    def _attempt_automatic_broadcast(self) -> None:
        if not self._auto_start_active or self._closing:
            return
        desired_name = self.config.selected_device_name
        if (
            self.current_device is None
            or (desired_name and self.current_device.name != desired_name)
        ):
            self.startup_status_label.configure(
                text=(
                    f"Waiting for audio device: {desired_name}"
                    if desired_name
                    else "Waiting for an audio input device…"
                ),
                foreground=COLORS["warning"],
            )
            self.refresh_devices()
            self._auto_start_job = self.after(
                2000,
                self._attempt_automatic_broadcast,
            )
            return
        servers = self.config.enabled_servers()
        if not servers:
            self._automatic_start_problem(
                "Automatic start stopped: no stations are included."
            )
            return
        missing_passwords = [
            server.name
            for server in servers
            if not self.store.get_password(server.id)
        ]
        if missing_passwords:
            self._automatic_start_problem(
                "Automatic start stopped: missing password for "
                + ", ".join(missing_passwords)
                + "."
            )
            return
        self._auto_start_active = False
        self._auto_start_job = None
        self.startup_banner.pack_forget()
        try:
            self.tray.notify(
                "Starting broadcast",
                f"Connecting to {len(servers)} included station(s).",
            )
        except Exception:
            pass
        self.toggle_broadcast()

    def _automatic_start_problem(self, detail: str) -> None:
        self._auto_start_active = False
        self._auto_start_job = None
        self.startup_status_label.configure(
            text=detail,
            foreground=COLORS["error"],
        )
        self.detail_label.configure(text=detail)
        try:
            self.tray.notify("Automatic broadcast needs attention", detail)
        except Exception:
            pass

    def cancel_automatic_start(self) -> None:
        self._auto_start_active = False
        if self._auto_start_job is not None:
            try:
                self.after_cancel(self._auto_start_job)
            except (ValueError, tk.TclError):
                pass
            self._auto_start_job = None
        self.startup_banner.pack_forget()
        self.detail_label.configure(text="Automatic broadcast cancelled")

    def choose_metadata_file(self) -> None:
        current = Path(self.config.metadata_file) if self.config.metadata_file else None
        selected = filedialog.askopenfilename(
            title="Choose now-playing text file",
            initialdir=str(current.parent) if current else str(Path.home()),
            filetypes=[
                ("Text files", "*.txt"),
                ("All files", "*.*"),
            ],
            parent=self,
        )
        if not selected:
            return
        self.config.metadata_file = selected
        self.metadata_file_var.set(selected)
        self.save_config()
        self._sync_metadata_watcher()

    def _metadata_auto_changed(self) -> None:
        self.config.metadata_auto = self.metadata_auto_var.get()
        self.save_config()
        self._sync_metadata_watcher()

    def _metadata_format_changed(self, _event: object = None) -> None:
        self.config.metadata_format = self.metadata_format_var.get()
        self.save_config()
        self._sync_metadata_watcher()

    def _sync_metadata_watcher(self) -> None:
        self.metadata_watcher.stop()
        if not self.config.metadata_auto:
            self.metadata_status_label.configure(
                text="Automatic metadata is off",
                foreground=COLORS["muted"],
            )
            return
        if not self.config.metadata_file:
            self.metadata_status_label.configure(
                text="Choose a text file to enable automatic metadata",
                foreground=COLORS["warning"],
            )
            return
        self.metadata_status_label.configure(
            text="Watching for title changes…",
            foreground=COLORS["muted"],
        )
        self.metadata_watcher.start(
            Path(self.config.metadata_file),
            self.config.metadata_format,
        )

    def _on_metadata_file_title(self, title: str) -> None:
        try:
            self.after(0, lambda: self._apply_metadata_file_title(title))
        except RuntimeError:
            pass

    def _apply_metadata_file_title(self, title: str) -> None:
        self.auto_metadata_title = title
        self.song_var.set(title)
        if self.stream.active:
            self._publish_metadata(title, automatic=True)
        else:
            self.metadata_status_label.configure(
                text=f"Title ready for the next broadcast: {title}",
                foreground=COLORS["accent"],
            )

    def _on_metadata_watcher_status(self, detail: str) -> None:
        try:
            self.after(
                0,
                lambda: self._apply_metadata_watcher_status(detail),
            )
        except RuntimeError:
            pass

    def _apply_metadata_watcher_status(self, detail: str) -> None:
        if not self.config.metadata_auto:
            return
        self.metadata_status_label.configure(
            text=detail,
            foreground=COLORS["warning"],
        )

    def _publish_metadata(self, song: str, automatic: bool) -> None:
        enabled = self.config.enabled_servers()
        if self.stream.active:
            online_ids = set(self.stream.online_server_ids)
            servers = [server for server in enabled if server.id in online_ids]
        elif automatic:
            servers = []
        else:
            servers = enabled
        if not servers:
            if automatic:
                self.metadata_status_label.configure(
                    text=f"Title ready; waiting for an online server: {song}",
                    foreground=COLORS["warning"],
                )
            return
        destinations = [
            (server, self.store.get_password(server.id))
            for server in servers
        ]
        self.metadata_delivery_results = {
            server.id: None for server in servers
        }
        self.metadata_generation = self.metadata_delivery.publish(
            destinations,
            song,
        )
        self.metadata_status_label.configure(
            text=f"Sending title to {len(servers)} server(s)…",
            foreground=COLORS["muted"],
        )
        self.detail_label.configure(
            text=f"Sending now playing: {song}"
        )

    def _on_metadata_delivery_result(
        self,
        generation: int,
        server_id: str,
        ok: bool,
        detail: str,
    ) -> None:
        try:
            self.after(
                0,
                lambda: self._apply_metadata_delivery_result(
                    generation,
                    server_id,
                    ok,
                    detail,
                ),
            )
        except RuntimeError:
            pass

    def _apply_metadata_delivery_result(
        self,
        generation: int,
        server_id: str,
        ok: bool,
        detail: str,
    ) -> None:
        if generation != self.metadata_generation:
            return
        self.metadata_delivery_results[server_id] = ok
        total = len(self.metadata_delivery_results)
        sent = sum(result is True for result in self.metadata_delivery_results.values())
        retrying = sum(
            result is False for result in self.metadata_delivery_results.values()
        )
        if sent == total:
            title = self.song_var.get().strip()
            self.metadata_status_label.configure(
                text=f"Sent to all {total} server(s): {title}",
                foreground=COLORS["accent"],
            )
            self.detail_label.configure(
                text=f"Now playing updated: {title}"
            )
        else:
            status = f"Sent to {sent} of {total} server(s)"
            if retrying:
                status += f" · {retrying} retrying"
            self.metadata_status_label.configure(
                text=f"{status} · {detail}",
                foreground=COLORS["warning"],
            )

    def _recording_folder(self) -> Path:
        return (
            Path(self.config.recording_folder)
            if self.config.recording_folder
            else default_recording_folder()
        )

    def choose_recording_folder(self) -> None:
        selected = filedialog.askdirectory(
            title="Choose recording folder",
            initialdir=str(self._recording_folder()),
            parent=self,
        )
        if not selected:
            return
        self.config.recording_folder = selected
        self.recording_folder_var.set(selected)
        self.save_config()

    def _record_broadcasts_changed(self) -> None:
        self.config.record_broadcasts = self.record_broadcasts_var.get()
        self.save_config()

    def toggle_recording(self) -> None:
        if self.recording.active:
            self.recording_button.configure(state="disabled", text="STOPPING…")
            threading.Thread(
                target=self.recording.stop,
                kwargs={"wait_timeout": 4.5},
                daemon=True,
            ).start()
            return
        if self.stream.active:
            messagebox.showinfo(
                "Broadcast in progress",
                "Stop the broadcast before starting a recording-only session.",
                parent=self,
            )
            return
        if not self.current_device:
            messagebox.showinfo(
                "Choose your sound",
                "Select a recording device first.",
                parent=self,
            )
            return
        device = self.current_device
        output_sample_rate = SAMPLE_RATES.get(self.sample_rate_var.get(), 44100)
        audio_system = self.audio_system_var.get()
        self.recording_button.configure(state="disabled", text="PREPARING…")
        self.broadcast_button.configure(state="disabled")
        self.device_combo.configure(state="disabled")
        self.sound_button.configure(state="disabled")
        self.play_original_button.configure(state="disabled")
        self.play_processed_button.configure(state="disabled")

        def prepare() -> None:
            try:
                destination = next_recording_path(self._recording_folder())
                self.audio.stop_meter()
                time.sleep(0.15)
                self.recording.start(
                    device,
                    destination,
                    output_sample_rate,
                    audio_system,
                    self.processing_var.get(),
                )
            except Exception as error:
                logging.exception("Could not prepare local recording")
                self._on_recording_state(
                    RecordingState.ERROR,
                    f"Recording could not start: {error}",
                    None,
                )

        threading.Thread(target=prepare, daemon=True).start()

    def _on_recording_state(
        self,
        state: RecordingState,
        detail: str,
        path: Path | None,
    ) -> None:
        try:
            self.after(
                0,
                lambda: self._apply_recording_state(state, detail, path),
            )
        except RuntimeError:
            pass

    def _on_broadcast_recording(
        self,
        active: bool,
        detail: str,
        path: Path | None,
    ) -> None:
        state = RecordingState.RECORDING if active else RecordingState.OFFLINE
        if not active and detail.startswith(("Recording failed", "Recording could not")):
            state = RecordingState.ERROR
        self._on_recording_state(state, detail, path)

    def _apply_recording_state(
        self,
        state: RecordingState,
        detail: str,
        _path: Path | None,
    ) -> None:
        if state == RecordingState.RECORDING:
            self.sleep_preventer.set_broadcasting(True)
        elif not self.stream.active:
            self.sleep_preventer.set_broadcasting(False)
        self.recording_status_label.configure(
            text=detail,
            foreground=(
                COLORS["error"]
                if state == RecordingState.ERROR
                else COLORS["accent"]
                if state == RecordingState.RECORDING
                else COLORS["muted"]
            ),
        )
        if self.stream.active:
            self.recording_button.configure(
                state="disabled",
                text="Record without broadcasting",
            )
            return
        if state == RecordingState.RECORDING:
            self.recording_button.configure(
                state="normal",
                text="STOP RECORDING",
            )
            self.broadcast_button.configure(state="disabled")
            self.device_combo.configure(state="disabled")
            self.audio_system_combo.configure(state="disabled")
            self.sample_rate_combo.configure(state="disabled")
            self.processing_combo.configure(state="disabled")
            self.sound_button.configure(state="disabled")
            self.play_original_button.configure(state="disabled")
            self.play_processed_button.configure(state="disabled")
        else:
            self.recording_button.configure(
                state="normal",
                text="Record without broadcasting",
            )
            self.broadcast_button.configure(state="normal")
            self.device_combo.configure(state="readonly")
            self.audio_system_combo.configure(state="readonly")
            self.sample_rate_combo.configure(state="readonly")
            self.processing_combo.configure(state="readonly")
            self.sound_button.configure(state="normal")
            if self._test_ready:
                self.play_original_button.configure(state="normal")
                self.play_processed_button.configure(state="normal")
            self._start_meter()

    def _scroll_content(self, event: tk.Event) -> str | None:
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if widget == self.content_canvas:
                direction = -1 if event.delta > 0 else 1
                self.content_canvas.yview_scroll(
                    direction,
                    "units",
                )
                return "break"
            widget = getattr(widget, "master", None)
        return None

    @staticmethod
    def _ignore_closed_combobox_wheel(_event: tk.Event) -> str:
        return "break"

    @staticmethod
    def _quality_description(quality: str) -> str:
        preset = QUALITY_PRESETS.get(
            quality,
            QUALITY_PRESETS["SL Standard"],
        )
        channel_text = " · mono" if preset.channels == 1 else ""
        return f"MP3 · {preset.bitrate} kbps{channel_text}"

    def _volume_changed(self, value: str) -> None:
        percent = int(round(float(value)))
        self.config.input_volume_percent = percent
        self.gain.set_percent(percent)
        self.volume_label.configure(text=f"{percent}%")
        if self._volume_save_job is not None:
            self.after_cancel(self._volume_save_job)
        self._volume_save_job = self.after(300, self._save_volume)

    def _save_volume(self) -> None:
        self._volume_save_job = None
        self.save_config()

    def _reset_volume(self) -> None:
        self.volume_var.set(100)
        self._volume_changed("100")

    def _start_meter(self) -> None:
        if not self.current_device or self.stream.active:
            return
        device = self.current_device

        def worker() -> None:
            try:
                self.audio.start_meter(
                    device,
                    self._capture_meter_level,
                    self.config.audio_system,
                )
                active_api = self.audio.active_api
                self.after(
                    0,
                    lambda: (
                        self.sound_hint.configure(
                            text="Speak or play audio. Aim for green movement without red peaks.",
                            foreground=COLORS["muted"],
                        ),
                        self.audio_api_status.configure(
                            text=f"Active: {active_api}"
                        ),
                    ),
                )
            except Exception as error:
                logging.exception("Could not start the meter")
                error_message = str(error)
                self.after(
                    0,
                    lambda: (
                        self.sound_hint.configure(
                            text=f"Could not open this input: {error_message}"
                        ),
                        self.audio_api_status.configure(
                            text=f"Unavailable: {self.config.audio_system}"
                        ),
                    ),
                )

        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def _linear_meter(rms: float) -> float:
        if rms <= 0:
            return 0
        db = 20 * math.log10(rms)
        return max(0.0, min(1.0, (db + 60) / 60))

    def _on_level(
        self,
        left: float,
        right: float,
        peak: float | None = None,
    ) -> None:
        if peak is not None and peak >= 0.995:
            now = time.monotonic()
            if now - self._last_clip_warning >= 2:
                self._last_clip_warning = now
                try:
                    self.after(
                        0,
                        lambda: self.sound_hint.configure(
                            text=(
                                "Clipping detected before processing. "
                                "Lower the input volume until red peaks stop."
                            ),
                            foreground=COLORS["error"],
                        ),
                    )
                except RuntimeError:
                    pass
        try:
            self.after(
                0,
                lambda: (
                    self.left_meter.set_level(self._linear_meter(left)),
                    self.right_meter.set_level(self._linear_meter(right)),
                ),
            )
        except RuntimeError:
            pass

    def _capture_meter_level(
        self,
        left: float,
        right: float,
        peak: float = 0.0,
    ) -> None:
        # PortAudio callbacks must return immediately and must never call Tk.
        self._meter_levels = (left, right)
        self._meter_peak = peak

    def _poll_meter_levels(self) -> None:
        if not self.stream.active:
            left, right = self._meter_levels
            self.left_meter.set_level(self._linear_meter(left))
            self.right_meter.set_level(self._linear_meter(right))
            if self._meter_peak >= 0.995:
                now = time.monotonic()
                if now - self._last_clip_warning >= 2:
                    self._last_clip_warning = now
                    self.sound_hint.configure(
                        text=(
                            "Clipping detected before processing. "
                            "Lower the input volume until red peaks stop."
                        ),
                        foreground=COLORS["error"],
                    )
        if not self._closing:
            self.after(50, self._poll_meter_levels)

    def test_sound(self) -> None:
        if not self.current_device:
            messagebox.showinfo(
                "Choose an input",
                "Connect or choose a recording device first.",
                parent=self,
            )
            return
        self.sound_button.configure(state="disabled", text="Recording 5…")
        self.play_original_button.configure(state="disabled")
        self.play_processed_button.configure(state="disabled")
        self.sound_hint.configure(
            text="Make the kind of sound you plan to broadcast.",
            foreground=COLORS["muted"],
        )

        def progress(remaining: int) -> None:
            self.after(
                0,
                lambda: self.sound_button.configure(text=f"Recording {remaining}…"),
            )

        def worker() -> None:
            try:
                rms, peak = self.audio.record_test(
                    self.current_device,
                    self.last_test_path,
                    progress=progress,
                    audio_system=self.config.audio_system,
                )
                process_test_file(
                    self.last_test_path,
                    self.processed_test_path,
                    self.processing_var.get(),
                )
                self._test_ready = True
                db = 20 * math.log10(max(rms, 1e-9))
                if peak >= 0.98:
                    verdict = "Your audio clipped. Lower the input level and try again."
                elif db < -45:
                    verdict = "Very little sound was detected. Check the selected input."
                elif db < -28:
                    verdict = "The sound is a little quiet, but it was recorded."
                else:
                    verdict = (
                        "Sound captured successfully. "
                        "Playing the processed version now."
                    )
                self.after(
                    0,
                    lambda: self.sound_hint.configure(
                        text=verdict,
                        foreground=(
                            COLORS["error"]
                            if peak >= 0.98
                            else COLORS["muted"]
                        ),
                    ),
                )
                self.after(
                    0,
                    lambda: (
                        self.sound_button.configure(
                            state="normal",
                            text="Recording captured…",
                        ),
                        self.play_original_button.configure(state="normal"),
                        self.play_processed_button.configure(state="normal"),
                    ),
                )
                AudioEngine.play_file(self.processed_test_path)
            except Exception as error:
                logging.exception("Sound test failed")
                self.after(
                    0,
                    lambda: messagebox.showerror(
                        "Sound test failed",
                        str(error),
                        parent=self,
                    ),
                )
            finally:
                self.after(
                    0,
                    lambda: (
                        self.sound_button.configure(
                            state="normal",
                            text="Test my sound",
                        ),
                        self._start_meter(),
                    ),
                )

        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def _play_test_file(path: Path) -> None:
        threading.Thread(
            target=AudioEngine.play_file,
            args=(path,),
            daemon=True,
        ).start()

    def manage_servers(self) -> None:
        ServerManager(self)

    def _server_choice_labels(self) -> dict[str, str]:
        labels: dict[str, str] = {}
        occurrences: dict[str, int] = {}
        for server in self.config.servers:
            count = occurrences.get(server.name, 0) + 1
            label = server.name if count == 1 else f"{server.name} ({count})"
            while label in labels:
                count += 1
                label = f"{server.name} ({count})"
            occurrences[server.name] = count
            labels[label] = server.id
        return labels

    def _refresh_server_choices(self) -> None:
        self._server_choice_ids = self._server_choice_labels()
        labels = list(self._server_choice_ids)
        self.server_choice_combo.configure(values=labels)
        selected_label = next(
            (
                label
                for label, server_id in self._server_choice_ids.items()
                if server_id == self.config.selected_server_id
            ),
            "",
        )
        self.server_choice_var.set(
            selected_label
            if selected_label
            else "No servers added"
        )
        has_servers = bool(labels)
        control_state = (
            "disabled"
            if self.stream.active
            else "readonly"
            if has_servers
            else "disabled"
        )
        self.server_choice_combo.configure(state=control_state)
        button_state = "normal" if has_servers and not self.stream.active else "disabled"
        self.edit_server_button.configure(state=button_state)
        self.delete_server_button.configure(state=button_state)
        self.add_server_button.configure(
            state="disabled" if self.stream.active else "normal"
        )

    def _server_choice_selected(self, _event: object = None) -> None:
        if self.stream.active:
            return
        server_id = self._server_choice_ids.get(self.server_choice_var.get())
        if server_id and self.config.select_only_server(server_id):
            self.save_config()
            self.refresh_station()

    def _save_server(self, profile: ServerProfile, password: str) -> None:
        existing = next(
            (item for item in self.config.servers if item.id == profile.id),
            None,
        )
        if existing:
            self.config.servers[self.config.servers.index(existing)] = profile
        else:
            self.config.servers.append(profile)
            self.config.select_only_server(profile.id)
        self.config.selected_server_id = profile.id
        self.store.set_password(profile.id, password)
        self.save_config()
        self.refresh_station()

    def add_server(self) -> None:
        if not self.stream.active:
            ServerDialog(self, None, "", self._save_server)

    def edit_selected_server(self) -> None:
        if self.stream.active:
            return
        profile = self.config.selected_server()
        if profile is None:
            messagebox.showinfo(
                "Choose a server",
                "Select a server to edit.",
                parent=self,
            )
            return
        ServerDialog(
            self,
            profile,
            self.store.get_password(profile.id),
            self._save_server,
        )

    def delete_selected_server(self) -> None:
        if self.stream.active:
            return
        profile = self.config.selected_server()
        if profile is None:
            return
        if not messagebox.askyesno(
            "Delete server?",
            (
                f"Are you sure you want to delete “{profile.name}”?\n\n"
                "Its saved connection details and password will be removed."
            ),
            parent=self,
        ):
            return
        was_enabled = profile.id in self.config.enabled_server_ids
        self.config.servers.remove(profile)
        self.config.enabled_server_ids = [
            server_id
            for server_id in self.config.enabled_server_ids
            if server_id != profile.id
        ]
        self.config.favorite_server_ids = [
            server_id
            for server_id in self.config.favorite_server_ids
            if server_id != profile.id
        ]
        self.store.delete_password(profile.id)
        if self.config.servers:
            self.config.selected_server_id = self.config.servers[0].id
            if was_enabled and not self.config.enabled_server_ids:
                self.config.enabled_server_ids = [
                    self.config.selected_server_id
                ]
        else:
            self.config.selected_server_id = ""
        self.save_config()
        self.refresh_station()

    @staticmethod
    def _quick_station_label(server: ServerProfile) -> str:
        return f"★  {server.name}"

    def _refresh_quick_stations(self) -> None:
        for child in self.favorite_grid.winfo_children():
            child.destroy()
        self.favorite_buttons = []
        favorites = self.config.favorite_servers()[:6]
        enabled_ids = self.config.enabled_server_ids
        selected_id = enabled_ids[0] if len(enabled_ids) == 1 else ""
        columns = getattr(self, "favorite_columns", 3)
        for index in range(6):
            row, column = divmod(index, columns)
            if index < len(favorites):
                server = favorites[index]
                selected = server.id == selected_id
                button = ttk.Button(
                    self.favorite_grid,
                    text=(
                        f"{self._quick_station_label(server)}     ✓"
                        if selected
                        else self._quick_station_label(server)
                    ),
                    style=(
                        "FavoriteSelected.TButton"
                        if selected
                        else "Favorite.TButton"
                    ),
                    command=lambda server_id=server.id: (
                        self._select_favorite_station(server_id)
                    ),
                    state="disabled" if self.stream.active else "normal",
                )
            else:
                button = ttk.Button(
                    self.favorite_grid,
                    text="☆  Add favorite",
                    style="Favorite.TButton",
                    command=self.manage_servers,
                    state="disabled" if self.stream.active else "normal",
                )
            button.grid(
                row=row,
                column=column,
                sticky="ew",
                padx=(
                    0 if column == 0 else 4,
                    0 if column == columns - 1 else 4,
                ),
                pady=(0 if row == 0 else 5, 5 if row == 0 else 0),
            )
            self.favorite_buttons.append(button)

    def _select_favorite_station(self, server_id: str) -> None:
        if self.stream.active:
            return
        # Quick switching intentionally chooses one destination. Multi-station
        # broadcasting remains available through Manage stations.
        if not self.config.select_only_server(server_id):
            return
        self.save_config()
        self.refresh_station()

    def refresh_station(self) -> None:
        self._refresh_server_choices()
        self._refresh_quick_stations()
        for child in self.server_status_frame.winfo_children():
            child.destroy()
        self.server_status_labels = {}
        self.listener_status_labels = {}
        enabled = self.config.enabled_servers()
        selected = self.config.selected_server()
        if enabled:
            self.station_name.configure(
                text=(
                    enabled[0].name
                    if len(enabled) == 1
                    else f"{len(enabled)} stations included"
                )
            )
            self.station_detail.configure(
                text=" · ".join(server.name for server in enabled)
            )
            for server in enabled:
                row = ttk.Frame(
                    self.server_status_frame,
                    style="Card.TFrame",
                )
                row.pack(fill="x", pady=2)
                status_row = ttk.Frame(row, style="Card.TFrame")
                status_row.pack(fill="x")
                name_label = ttk.Label(
                    status_row,
                    text=f"●  {server.name}",
                    foreground=COLORS["offline"],
                    style="Card.TLabel",
                )
                name_label.pack(side="left")
                status_label = ttk.Label(
                    status_row,
                    text="Ready",
                    style="CardMuted.TLabel",
                )
                status_label.pack(side="right")
                listener_label = ttk.Label(
                    row,
                    text=self._listener_status_text(server),
                    style="CardMuted.TLabel",
                )
                listener_label.pack(anchor="w", padx=(14, 0))
                self.server_status_labels[server.id] = (
                    name_label,
                    status_label,
                )
                self.listener_status_labels[server.id] = listener_label
            self.test_server_button.configure(
                state="normal" if selected else "disabled"
            )
        elif self.config.servers:
            self.station_name.configure(text="No stations included")
            self.station_detail.configure(
                text="Open Manage stations and include at least one destination."
            )
            self.test_server_button.configure(
                state="normal" if selected else "disabled"
            )
        else:
            self.station_name.configure(text="No station added")
            self.station_detail.configure(
                text="Add your Icecast or SHOUTcast connection details to continue."
            )
            self.test_server_button.configure(state="disabled")

    def test_server(
        self,
        server: ServerProfile | None,
        parent: tk.Misc | None = None,
    ) -> None:
        parent = parent or self
        if not server:
            return
        if self.stream.active:
            messagebox.showinfo(
                "Already broadcasting",
                "Stop the broadcast before testing this connection.",
                parent=parent,
            )
            return
        if not messagebox.askokcancel(
            "Test connection?",
            "The test briefly opens and closes this stream path. Do not continue if "
            "another encoder is currently using it.",
            parent=parent,
        ):
            return
        dialog = tk.Toplevel(parent)
        dialog.title("Testing connection")
        dialog.geometry("590x330")
        dialog.configure(background=COLORS["bg"])
        dialog.transient(parent)
        content = ttk.Frame(dialog, padding=24)
        content.pack(fill="both", expand=True)
        _fit_window(dialog, 590, 330, 500, 300)
        ttk.Label(content, text=f"Testing {server.name}", style="Title.TLabel").pack(
            anchor="w"
        )
        status = ttk.Label(
            content,
            text="Checking the server address…",
            style="Muted.TLabel",
        )
        status.pack(anchor="w", pady=(6, 16))
        results_frame = ttk.Frame(content)
        results_frame.pack(fill="both", expand=True)

        def worker() -> None:
            results = run_server_diagnostic(
                server,
                self.store.get_password(server.id),
            )
            self.after(0, lambda: show_results(results))

        def show_results(results: list[DiagnosticStep]) -> None:
            for child in results_frame.winfo_children():
                child.destroy()
            for result in results:
                row = ttk.Frame(results_frame)
                row.pack(fill="x", pady=5)
                ttk.Label(
                    row,
                    text="✓" if result.ok else "×",
                    foreground=COLORS["accent"] if result.ok else COLORS["error"],
                ).pack(side="left")
                ttk.Label(row, text=result.name, width=20).pack(side="left", padx=8)
                ttk.Label(
                    row,
                    text=result.detail,
                    style="Muted.TLabel",
                    wraplength=340,
                ).pack(side="left", fill="x", expand=True)
            ok = bool(results) and all(item.ok for item in results)
            status.configure(
                text=(
                    "Everything looks good. This station is ready."
                    if ok
                    else "The connection needs attention. Review the failed step."
                )
            )
            ttk.Button(content, text="Close", command=dialog.destroy).pack(
                anchor="e", pady=(12, 0)
            )
            _fit_window(dialog, 590, 330, 500, 300)

        threading.Thread(target=worker, daemon=True).start()

    def toggle_broadcast(self) -> None:
        if self._auto_start_active:
            self.cancel_automatic_start()
        if self.stream.active:
            if messagebox.askyesno(
                "Stop broadcasting?",
                "Listeners will immediately lose the live audio.",
                parent=self,
            ):
                self.broadcast_button.configure(state="disabled", text="STOPPING…")
                self.stream.stop()
            return
        if self.recording.active:
            messagebox.showinfo(
                "Recording in progress",
                "Stop the recording-only session before starting a broadcast.",
                parent=self,
            )
            return
        servers = self.config.enabled_servers()
        if not self.current_device:
            messagebox.showinfo(
                "Choose your sound",
                "Select a recording device before broadcasting.",
                parent=self,
            )
            return
        if not servers:
            messagebox.showinfo(
                "Include a station",
                "Include at least one Icecast or SHOUTcast station before broadcasting.",
                parent=self,
            )
            self.manage_servers()
            return
        passwords = {
            server.id: self.store.get_password(server.id)
            for server in servers
        }
        missing_passwords = [
            server.name for server in servers if not passwords[server.id]
        ]
        if missing_passwords:
            messagebox.showinfo(
                "Passwords missing",
                "Enter a source password for: "
                + ", ".join(missing_passwords),
                parent=self,
            )
            return
        destinations = [
            StreamDestination(server, passwords[server.id])
            for server in servers
        ]
        device = self.current_device
        quality = self.quality_var.get()
        output_sample_rate = SAMPLE_RATES.get(self.sample_rate_var.get(), 44100)
        audio_system = self.audio_system_var.get()
        record_broadcast = self.record_broadcasts_var.get()
        self.broadcast_button.configure(state="disabled", text="PREPARING AUDIO…")
        self.device_combo.configure(state="disabled")
        self.sound_button.configure(state="disabled")
        self.play_original_button.configure(state="disabled")
        self.play_processed_button.configure(state="disabled")
        self.recording_button.configure(state="disabled")
        self.detail_label.configure(text=f"Opening {device.name}…")

        def prepare() -> None:
            try:
                # PortAudio calls may block inside third-party USB drivers, so
                # they must never run on Tk's UI thread.
                self.audio.stop_meter()
                time.sleep(0.15)
                recording_path: Path | None = None
                if record_broadcast:
                    try:
                        recording_path = next_recording_path(
                            self._recording_folder()
                        )
                    except OSError as error:
                        logging.exception("Could not create the recording file")
                        self._on_broadcast_recording(
                            False,
                            f"Recording could not start: {error}",
                            None,
                        )
                self.stream.start(
                    device,
                    destinations,
                    quality,
                    output_sample_rate,
                    audio_system,
                    recording_path,
                    self.processing_var.get(),
                )
            except Exception as error:
                logging.exception("Could not prepare audio for broadcast")
                error_message = str(error)
                self.after(
                    0,
                    lambda: (
                        messagebox.showerror(
                            "Could not start the audio input",
                            f"{error_message}\n\nTry unplugging and reconnecting the audio "
                            "device, then select it again.",
                            parent=self,
                        ),
                        self._apply_stream_state(
                            BroadcastState.OFFLINE,
                            "The audio input could not be opened.",
                        ),
                    ),
                )

        threading.Thread(target=prepare, daemon=True).start()

    def _on_server_stream_state(
        self,
        server_id: str,
        state: BroadcastState,
        detail: str,
    ) -> None:
        try:
            self.after(
                0,
                lambda: self._apply_server_stream_state(
                    server_id,
                    state,
                    detail,
                ),
            )
        except RuntimeError:
            pass

    def _listener_status_text(self, server: ServerProfile) -> str:
        count = self.listener_counts.get(server.id)
        if count is not None:
            current = str(count)
        elif server.id in self.listener_errors:
            current = "unavailable"
        else:
            current = "—"
        return (
            f"Live listeners: {current}  ·  "
            f"Personal best: {server.personal_listener_peak}"
        )

    def _refresh_listener_status(self, server_id: str) -> None:
        label = self.listener_status_labels.get(server_id)
        server = next(
            (
                item
                for item in self.config.servers
                if item.id == server_id
            ),
            None,
        )
        if label is not None and server is not None:
            label.configure(
                text=self._listener_status_text(server),
                foreground=(
                    COLORS["accent"]
                    if server_id in self.listener_counts
                    else COLORS["muted"]
                ),
            )

    def _start_listener_poll(self, server: ServerProfile) -> None:
        if server.id in self._listener_polling or self._closing:
            return
        self._listener_polling.add(server.id)

        def fetch() -> None:
            try:
                count = fetch_listener_count(server)
                error = ""
            except Exception as problem:
                count = None
                error = str(problem) or "Listener statistics are unavailable"
            try:
                self.after(
                    0,
                    lambda: self._apply_listener_result(
                        server.id,
                        count,
                        error,
                    ),
                )
            except RuntimeError:
                self._listener_polling.discard(server.id)

        threading.Thread(target=fetch, daemon=True).start()

    def _poll_listener_stats(self) -> None:
        if self._closing:
            return
        online_ids = set(self.stream.online_server_ids)
        known_ids = set(self.listener_counts) | set(self.listener_errors)
        for server_id in known_ids - online_ids:
            self.listener_counts.pop(server_id, None)
            self.listener_errors.pop(server_id, None)
            self._refresh_listener_status(server_id)
        for server in self.config.servers:
            if server.id in online_ids:
                self._start_listener_poll(server)
        self.after(10_000, self._poll_listener_stats)

    def _apply_listener_result(
        self,
        server_id: str,
        count: int | None,
        error: str,
    ) -> None:
        self._listener_polling.discard(server_id)
        server = next(
            (
                item
                for item in self.config.servers
                if item.id == server_id
            ),
            None,
        )
        if server is None:
            return
        if server_id not in set(self.stream.online_server_ids):
            self.listener_counts.pop(server_id, None)
            self.listener_errors.pop(server_id, None)
            self._refresh_listener_status(server_id)
            return
        if count is None:
            self.listener_counts.pop(server_id, None)
            self.listener_errors[server_id] = error
            logging.debug(
                "Listener statistics unavailable for %s: %s",
                server.name,
                error,
            )
        else:
            self.listener_counts[server_id] = count
            self.listener_errors.pop(server_id, None)
            if server.observe_listener_count(count):
                self.save_config()
        self._refresh_listener_status(server_id)

    def _apply_server_stream_state(
        self,
        server_id: str,
        state: BroadcastState,
        detail: str,
    ) -> None:
        labels = self.server_status_labels.get(server_id)
        if labels is None:
            return
        name_label, status_label = labels
        colors = {
            BroadcastState.ON_AIR: COLORS["accent"],
            BroadcastState.CONNECTING: COLORS["warning"],
            BroadcastState.RECONNECTING: COLORS["warning"],
            BroadcastState.ERROR: COLORS["error"],
            BroadcastState.OFFLINE: COLORS["offline"],
        }
        name_label.configure(foreground=colors[state])
        status_label.configure(
            text=detail if len(detail) <= 72 else f"{detail[:69]}…",
            foreground=colors[state],
        )
        if state == BroadcastState.ON_AIR:
            server = next(
                (
                    item
                    for item in self.config.servers
                    if item.id == server_id
                ),
                None,
            )
            if server is not None:
                self.after(250, lambda: self._start_listener_poll(server))
        else:
            self.listener_counts.pop(server_id, None)
            self.listener_errors.pop(server_id, None)
            self._refresh_listener_status(server_id)
        if (
            state == BroadcastState.ON_AIR
            and self.config.metadata_auto
            and self.auto_metadata_title
        ):
            self._publish_metadata(
                self.auto_metadata_title,
                automatic=True,
            )

    def _on_stream_state(self, state: BroadcastState, detail: str) -> None:
        try:
            self.after(0, lambda: self._apply_stream_state(state, detail))
        except RuntimeError:
            pass

    def _apply_stream_state(self, state: BroadcastState, detail: str) -> None:
        previous_state = self.state
        self.state = state
        colors = {
            BroadcastState.ON_AIR: COLORS["error"],
            BroadcastState.CONNECTING: COLORS["warning"],
            BroadcastState.RECONNECTING: COLORS["warning"],
            BroadcastState.ERROR: COLORS["error"],
            BroadcastState.OFFLINE: COLORS["offline"],
        }
        self.status_label.configure(
            text=f"● {state.value.upper()}",
            foreground=colors[state],
        )
        sidebar_colors = dict(colors)
        if self.active_skin not in {"Studio Workspace", "Studio Dark"}:
            sidebar_colors[BroadcastState.OFFLINE] = COLORS["sidebar_muted"]
            sidebar_colors[BroadcastState.ON_AIR] = COLORS["sidebar_accent"]
        self.sidebar_connection_label.configure(
            text=(
                "●  Connection ready"
                if state == BroadcastState.OFFLINE
                else f"●  {state.value.title()}"
            ),
            foreground=sidebar_colors[state],
        )
        self.detail_label.configure(text=detail)
        self.sleep_preventer.set_broadcasting(state != BroadcastState.OFFLINE)
        try:
            self.tray.update(state.value)
            if state == BroadcastState.ON_AIR and previous_state != BroadcastState.ON_AIR:
                self.tray.notify("SimpleCast is on air", detail)
            elif (
                state == BroadcastState.RECONNECTING
                and previous_state == BroadcastState.ON_AIR
            ):
                self.tray.notify("Broadcast interrupted", detail)
        except Exception:
            logging.exception("Could not update the tray status")
        if state == BroadcastState.OFFLINE:
            self.listener_counts.clear()
            self.listener_errors.clear()
            self.metadata_generation = self.metadata_delivery.cancel()
            if self.config.metadata_auto and self.auto_metadata_title:
                self.metadata_status_label.configure(
                    text=(
                        "Title ready for the next broadcast: "
                        f"{self.auto_metadata_title}"
                    ),
                    foreground=COLORS["accent"],
                )
            for name_label, server_status in self.server_status_labels.values():
                name_label.configure(foreground=COLORS["offline"])
                server_status.configure(
                    text="Ready",
                    foreground=COLORS["muted"],
                )
            for server_id in self.listener_status_labels:
                self._refresh_listener_status(server_id)
            self.broadcast_button.configure(
                state="normal",
                text="▶  START BROADCAST",
                style="Broadcast.TButton",
            )
            self.sound_button.configure(state="normal")
            if self._test_ready:
                self.play_original_button.configure(state="normal")
                self.play_processed_button.configure(state="normal")
            self.device_combo.configure(state="readonly")
            self.audio_system_combo.configure(state="readonly")
            self.quality_combo.configure(state="readonly")
            self.sample_rate_combo.configure(state="readonly")
            self.processing_combo.configure(state="readonly")
            self.recording_button.configure(
                state="normal",
                text="Record without broadcasting",
            )
            self.recording_folder_button.configure(state="normal")
            self.record_broadcasts_check.configure(state="normal")
            self._refresh_server_choices()
            self._refresh_quick_stations()
            self._start_meter()
        else:
            self.broadcast_button.configure(
                state="normal",
                text="■  STOP BROADCAST",
                style="Stop.TButton",
            )
            self.sound_button.configure(state="disabled")
            self.play_original_button.configure(state="disabled")
            self.play_processed_button.configure(state="disabled")
            self.device_combo.configure(state="disabled")
            self.audio_system_combo.configure(state="disabled")
            self.quality_combo.configure(state="disabled")
            self.sample_rate_combo.configure(state="disabled")
            self.processing_combo.configure(state="disabled")
            self.recording_button.configure(state="disabled")
            self.recording_folder_button.configure(state="disabled")
            self.record_broadcasts_check.configure(state="disabled")
            self._refresh_server_choices()
            self._refresh_quick_stations()

    def _update_timer(self) -> None:
        if self.stream.started_at:
            elapsed = int(time.monotonic() - self.stream.started_at)
            hours, remainder = divmod(elapsed, 3600)
            minutes, seconds = divmod(remainder, 60)
            self.timer_label.configure(text=f"{hours:02}:{minutes:02}:{seconds:02}")
        else:
            self.timer_label.configure(text="")
        recording_started = (
            self.stream.recording_started_at or self.recording.started_at
        )
        recording_path = self.stream.recording_path or self.recording.path
        if recording_started and recording_path:
            elapsed = int(time.monotonic() - recording_started)
            hours, remainder = divmod(elapsed, 3600)
            minutes, seconds = divmod(remainder, 60)
            try:
                size_mb = recording_path.stat().st_size / (1024 * 1024)
            except OSError:
                size_mb = 0.0
            self.recording_status_label.configure(
                text=(
                    f"Recording · {hours:02}:{minutes:02}:{seconds:02} · "
                    f"{size_mb:.1f} MB · {recording_path.name}"
                ),
                foreground=COLORS["accent"],
            )
        self.after(500, self._update_timer)

    def send_metadata(self) -> None:
        song = format_manual_now_playing(
            self.artist_var.get(),
            self.title_var.get(),
        )
        if not song:
            messagebox.showinfo(
                "Now playing",
                "Enter an artist or title first.",
                parent=self,
            )
            return
        self.song_var.set(song)
        enabled = self.config.enabled_servers()
        online = (
            set(self.stream.online_server_ids)
            if self.stream.active
            else {server.id for server in enabled}
        )
        if not any(server.id in online for server in enabled):
            messagebox.showinfo(
                "Now playing",
                "No included server is currently available.",
                parent=self,
            )
            return
        self._publish_metadata(song, automatic=False)

    def export_report(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Export support report",
            defaultextension=".txt",
            filetypes=[("Text report", "*.txt")],
            initialfile="SimpleCast-support-report.txt",
        )
        if not path:
            return
        servers = self.config.enabled_servers()
        report = [
            f"SimpleCast {__version__}",
            f"Windows: {platform.platform()}",
            f"Python: {platform.python_version()}",
            f"State: {self.state.value}",
            f"Audio device: {self.current_device.name if self.current_device else 'None'}",
            f"Audio system: {self.config.audio_system}",
            f"Quality: {self.config.quality}",
            f"Sample rate: {self.config.output_sample_rate} Hz",
            f"Processing: {self.config.processing_preset}",
            f"Input volume: {self.config.input_volume_percent}%",
            f"Record broadcasts: {self.config.record_broadcasts}",
            f"Recording folder: {self._recording_folder()}",
            f"Start with Windows: {self.config.start_with_windows}",
            f"Start minimized: {self.config.start_minimized}",
            f"Automatic broadcast: {self.config.auto_broadcast}",
            f"Startup delay: {self.config.startup_delay_seconds}s",
            f"Log file: {self.log_path}",
            "",
            "Included servers (passwords are never included):",
            (
                "\n".join(sanitized_server_json(server) for server in servers)
                if servers
                else "None"
            ),
            "",
            "Recent log:",
        ]
        try:
            log_lines = self.log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            report.extend(
                sanitize_support_text(line)
                for line in log_lines[-200:]
            )
        except OSError as error:
            report.append(f"Could not read log: {error}")
        Path(path).write_text("\n".join(report), encoding="utf-8")
        messagebox.showinfo(
            "Support report exported",
            "The report was saved without passwords.",
            parent=self,
        )

    def run_readiness_check(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Beta readiness check")
        dialog.configure(background=COLORS["bg"])
        dialog.transient(self)
        content = ttk.Frame(dialog, padding=24)
        content.pack(fill="both", expand=True)
        ttk.Label(
            content,
            text="BETA READINESS",
            style="CardTitle.TLabel",
        ).pack(anchor="w")
        summary = ttk.Label(
            content,
            text="Checking this computer and configuration…",
            style="CardMuted.TLabel",
        )
        summary.pack(anchor="w", pady=(8, 14))
        results_frame = ttk.Frame(content)
        results_frame.pack(fill="both", expand=True)
        close_button = ttk.Button(
            content,
            text="Close",
            command=dialog.destroy,
            state="disabled",
        )
        close_button.pack(anchor="e", pady=(14, 0))
        _fit_window(dialog, 700, 520, 600, 420)

        def show_results(checks: list[ReadinessCheck]) -> None:
            for child in results_frame.winfo_children():
                child.destroy()
            status_colors = {
                "Pass": COLORS["accent"],
                "Warning": COLORS["warning"],
                "Fail": COLORS["error"],
            }
            for row, check in enumerate(checks):
                ttk.Label(
                    results_frame,
                    text=f"{check.status.upper()}  {check.name}",
                    foreground=status_colors[check.status],
                ).grid(row=row, column=0, sticky="nw", pady=4)
                ttk.Label(
                    results_frame,
                    text=check.detail,
                    style="CardMuted.TLabel",
                    wraplength=420,
                ).grid(
                    row=row,
                    column=1,
                    sticky="nw",
                    padx=(16, 0),
                    pady=4,
                )
            results_frame.columnconfigure(1, weight=1)
            failures = sum(check.status == "Fail" for check in checks)
            warnings = sum(check.status == "Warning" for check in checks)
            summary.configure(
                text=(
                    f"{failures} failure(s), {warnings} warning(s). "
                    "Warnings do not prevent local testing."
                ),
                foreground=(
                    COLORS["error"]
                    if failures
                    else COLORS["warning"]
                    if warnings
                    else COLORS["accent"]
                ),
            )
            close_button.configure(state="normal")

        def worker() -> None:
            try:
                passwords = {
                    server.id: self.store.get_password(server.id)
                    for server in self.config.enabled_servers()
                }
                checks = run_readiness_checks(
                    self.config,
                    list(self.devices),
                    passwords,
                    self.store.root,
                    self._recording_folder(),
                )
                self.after(0, lambda: show_results(checks))
            except Exception as error:
                logging.exception("Readiness check failed")
                self.after(
                    0,
                    lambda: (
                        summary.configure(
                            text=f"Readiness check failed: {error}",
                            foreground=COLORS["error"],
                        ),
                        close_button.configure(state="normal"),
                    ),
                )

        threading.Thread(target=worker, daemon=True).start()

    def _on_unmap(self, _event: object) -> None:
        if self.wm_state() == "iconic":
            self.after(100, self._minimize_to_tray)

    def _minimize_to_tray(self) -> None:
        if self.wm_state() == "iconic":
            self.withdraw()
            try:
                self.tray.notify(
                    "SimpleCast is still running",
                    "Use the tray icon to reopen or control the broadcast.",
                )
            except Exception:
                pass

    def show_window(self) -> None:
        self.deiconify()
        self.wm_state("normal")
        self.lift()
        self.focus_force()

    def _tray_toggle_broadcast(self) -> None:
        self.show_window()
        self.toggle_broadcast()

    def close(self) -> None:
        if self._closing:
            return
        if self.stream.active:
            title = "Close while broadcasting?"
            message = "Closing SimpleCast will stop the broadcast"
            if self.stream.recording_started_at:
                message += " and safely finish the recording"
            if not messagebox.askyesno(title, f"{message}.", parent=self):
                return
        elif self.recording.active and not messagebox.askyesno(
            "Close while recording?",
            "Closing SimpleCast will stop and safely finish the recording.",
            parent=self,
        ):
            return
        self._closing = True
        self.cancel_automatic_start()
        logging.info("Shutdown requested")
        # Disappear immediately. No driver or tray operation is allowed to hold
        # Tk's interface thread while Windows is closing the application.
        self.withdraw()
        self.sleep_preventer.set_broadcasting(False)
        actions = {
            "broadcast engine": self.stream.close,
            "recording engine": self.recording.close,
            "metadata watcher": self.metadata_watcher.stop,
            "metadata delivery": self.metadata_delivery.stop,
            "audio device": self.audio.stop_meter,
            "tray icon": self.tray.stop,
        }
        self._shutdown_steps = {
            name: threading.Event()
            for name in actions
        }
        for name, action in actions.items():
            threading.Thread(
                target=self._run_shutdown_step,
                args=(name, action),
                daemon=True,
            ).start()

        self.after(50, self._poll_shutdown)
        self.after(self.SHUTDOWN_GRACE_MS, self._finish_shutdown_after_timeout)
        threading.Thread(target=self._shutdown_watchdog, daemon=True).start()

    def _run_shutdown_step(self, name: str, action: callable) -> None:
        logging.info("Stopping %s", name)
        try:
            action()
        except Exception:
            logging.exception("Could not stop %s cleanly", name)
        finally:
            logging.info("Stopped %s", name)
            self._shutdown_steps[name].set()

    def _poll_shutdown(self) -> None:
        if not self._closing or not self.winfo_exists():
            return
        if self._shutdown_steps and all(
            event.is_set() for event in self._shutdown_steps.values()
        ):
            logging.info("Shutdown completed cleanly")
            self._shutdown_clean.set()
            if self._restart_requested:
                self._launch_restart()
            self.destroy()
            return
        self.after(50, self._poll_shutdown)

    def _finish_shutdown_after_timeout(self) -> None:
        if self._shutdown_clean.is_set() or not self.winfo_exists():
            return
        pending = [
            name
            for name, event in self._shutdown_steps.items()
            if not event.is_set()
        ]
        logging.warning(
            "Shutdown cleanup timed out; closing the window with these steps pending: %s",
            ", ".join(pending) or "unknown",
        )
        if self._restart_requested:
            logging.error(
                "SimpleCast was not restarted because shutdown did not finish cleanly"
            )
        self.destroy()

    def _shutdown_watchdog(self) -> None:
        if self._shutdown_clean.wait(self.FORCE_EXIT_SECONDS):
            return
        logging.critical(
            "A Windows driver or background component did not exit; "
            "forcing process termination"
        )
        logging.shutdown()
        os._exit(0)


def run() -> None:
    if os.name != "nt":
        raise SystemExit("SimpleCast currently supports Windows only.")
    _enable_windows_dpi_awareness()
    SimpleCastApp().mainloop()

"""
Theme management for Mycelium NiceGUI application.

Provides 8 color themes and light/dark mode, aligned with Spore/Hyphae device UIs.
"""

from nicegui import ui, app

# Color themes matching Spore/Hyphae exactly
COLOR_THEMES = {
    "purple": {"primary": "#a500a5", "hover": "#66006c"},
    "red": {"primary": "#d32f2f", "hover": "#b71c1c"},
    "orange": {"primary": "#f57c00", "hover": "#e65100"},
    "yellow": {"primary": "#fbc02d", "hover": "#f9a825"},
    "green": {"primary": "#388e3c", "hover": "#2e7d32"},
    "blue": {"primary": "#1976d2", "hover": "#0d47a1"},
    "indigo": {"primary": "#303f9f", "hover": "#1a237e"},
    "violet": {"primary": "#7b1fa2", "hover": "#4a148c"},
}

# Background colors aligned to Spore/Hyphae devices
LIGHT_COLORS = {
    "background": "#c2c2c2",
    "surface": "#a8a8a8",
    "input_bg": "#b5b5b5",
    "header_bg": "#b8b8b8",
    "text": "#333333",
    "text_secondary": "#555555",
    "text_muted": "#777777",
    "error": "#d32f2f",
}

DARK_COLORS = {
    "background": "#333333",
    "surface": "#4d4d4d",
    "input_bg": "#5a5a5a",
    "header_bg": "#3d3d3d",
    "text": "#ffffff",
    "text_secondary": "#cccccc",
    "text_muted": "#b3b3b3",
    "error": "#ff5252",
}

# Status indicator colors
STATUS_COLORS = {
    "online": "#2ecc71",
    "offline": "#e74c3c",
    "warning": "#f39c12",
}


def get_theme() -> dict:
    """Get current theme from user storage, with defaults."""
    storage = app.storage.user
    return {
        "color": storage.get("theme_color", "purple"),
        "mode": storage.get("theme_mode", "dark"),
    }


def set_theme_color(color: str):
    """Set the active color theme."""
    if color in COLOR_THEMES:
        app.storage.user["theme_color"] = color


def set_theme_mode(mode: str):
    """Set light or dark mode."""
    if mode in ("light", "dark"):
        app.storage.user["theme_mode"] = mode


def toggle_theme_mode():
    """Toggle between light and dark mode."""
    current = app.storage.user.get("theme_mode", "dark")
    app.storage.user["theme_mode"] = "light" if current == "dark" else "dark"


def get_colors() -> dict:
    """Get the full color palette for the current theme."""
    theme = get_theme()
    color_theme = COLOR_THEMES.get(theme["color"], COLOR_THEMES["purple"])
    mode_colors = DARK_COLORS if theme["mode"] == "dark" else LIGHT_COLORS

    return {
        "primary": color_theme["primary"],
        "primary_hover": color_theme["hover"],
        **mode_colors,
    }


def apply_theme():
    """Apply the current theme to the page. Call this at the top of each page."""
    theme = get_theme()
    colors = get_colors()
    is_dark = theme["mode"] == "dark"

    # Set Quasar dark mode
    ui.dark_mode(is_dark)

    # Apply Quasar primary color
    ui.colors(primary=colors["primary"])

    # Inject custom CSS for backgrounds aligned to Spore/Hyphae
    ui.add_css(f"""
        body {{
            background-color: {colors["background"]} !important;
            color: {colors["text"]} !important;
        }}
        .q-card {{
            background-color: {colors["surface"]} !important;
            color: {colors["text"]} !important;
        }}
        .q-drawer {{
            background-color: {colors["surface"]} !important;
            color: {colors["text"]} !important;
        }}
        .q-header {{
            background-color: {colors["header_bg"]} !important;
        }}
        .q-input .q-field__control {{
            background-color: {colors["input_bg"]} !important;
            color: {colors["text"]} !important;
        }}
        .q-table {{
            background-color: {colors["surface"]} !important;
            color: {colors["text"]} !important;
        }}
        .q-table th {{
            color: {colors["text"]} !important;
        }}
        .q-table td {{
            color: {colors["text"]} !important;
        }}
        .text-caption, .text-subtitle2, .text-subtitle1,
        .text-body1, .text-body2, .text-overline {{
            color: {colors["text"]} !important;
        }}
        .text-secondary {{
            color: {colors["text_secondary"]} !important;
        }}
        .text-muted {{
            color: {colors["text_muted"]} !important;
        }}
        .q-btn__content {{
            color: inherit;
        }}
        .q-item__label {{
            color: {colors["text"]} !important;
        }}
        .mycelium-color-circle {{
            width: 28px;
            height: 28px;
            border-radius: 50%;
            cursor: pointer;
            transition: transform 0.15s ease, box-shadow 0.15s ease;
            display: inline-block;
        }}
        .mycelium-color-circle:hover {{
            transform: scale(1.15);
        }}
        .mycelium-color-circle.active {{
            border: 3px solid white !important;
            box-shadow: 0 2px 6px rgba(0,0,0,0.4);
        }}
    """)

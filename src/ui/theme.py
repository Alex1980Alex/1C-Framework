"""Custom Gradio theme for PDF Vector & Graph Framework.

Branded theme with full dark mode support.
"""

from __future__ import annotations

from gradio.themes.base import Base
from gradio.themes.utils import colors, fonts, sizes


class PDFFrameworkTheme(Base):
    """Custom theme with professional dark/light mode support."""

    def __init__(
        self,
        *,
        primary_hue: colors.Color | str = colors.blue,
        secondary_hue: colors.Color | str = colors.slate,
        neutral_hue: colors.Color | str = colors.gray,
        spacing_size: sizes.Size | str = sizes.spacing_md,
        radius_size: sizes.Size | str = sizes.radius_md,
        text_size: sizes.Size | str = sizes.text_md,
    ):
        _font: list[fonts.Font | str] = [
            fonts.GoogleFont("Inter"),
            "ui-sans-serif",
            "system-ui",
            "sans-serif",
        ]
        _font_mono: list[fonts.Font | str] = [
            fonts.GoogleFont("JetBrains Mono"),
            "ui-monospace",
            "Consolas",
            "monospace",
        ]
        super().__init__(
            primary_hue=primary_hue,
            secondary_hue=secondary_hue,
            neutral_hue=neutral_hue,
            spacing_size=spacing_size,
            radius_size=radius_size,
            text_size=text_size,
            font=_font,
            font_mono=_font_mono,
        )

        # ── Light mode overrides ──
        super().set(
            # Body
            body_background_fill="#f8fafc",
            body_background_fill_dark="#0f172a",
            body_text_color="#1e293b",
            body_text_color_dark="#e2e8f0",
            body_text_color_subdued="#64748b",
            body_text_color_subdued_dark="#94a3b8",
            # Blocks
            block_background_fill="#ffffff",
            block_background_fill_dark="#1e293b",
            block_border_color="#e2e8f0",
            block_border_color_dark="#334155",
            block_label_text_color="#475569",
            block_label_text_color_dark="#94a3b8",
            block_title_text_color="#1e293b",
            block_title_text_color_dark="#f1f5f9",
            block_shadow="0 1px 3px 0 rgb(0 0 0 / 0.05)",
            block_shadow_dark="0 1px 3px 0 rgb(0 0 0 / 0.3)",
            # Inputs
            input_background_fill="#ffffff",
            input_background_fill_dark="#1e293b",
            input_border_color="#cbd5e1",
            input_border_color_dark="#475569",
            input_border_color_focus="#3b82f6",
            input_border_color_focus_dark="#60a5fa",
            # Buttons — primary
            button_primary_background_fill="#2563eb",
            button_primary_background_fill_dark="#3b82f6",
            button_primary_background_fill_hover="#1d4ed8",
            button_primary_background_fill_hover_dark="#2563eb",
            button_primary_text_color="#ffffff",
            button_primary_text_color_dark="#ffffff",
            # Buttons — secondary
            button_secondary_background_fill="#f1f5f9",
            button_secondary_background_fill_dark="#334155",
            button_secondary_background_fill_hover="#e2e8f0",
            button_secondary_background_fill_hover_dark="#475569",
            button_secondary_text_color="#475569",
            button_secondary_text_color_dark="#e2e8f0",
            # Buttons — cancel/stop
            button_cancel_background_fill="#fef2f2",
            button_cancel_background_fill_dark="#450a0a",
            button_cancel_background_fill_hover="#fee2e2",
            button_cancel_background_fill_hover_dark="#7f1d1d",
            button_cancel_text_color="#dc2626",
            button_cancel_text_color_dark="#fca5a5",
            # Tables
            table_even_background_fill="#f8fafc",
            table_even_background_fill_dark="#1e293b",
            table_odd_background_fill="#ffffff",
            table_odd_background_fill_dark="#0f172a",
            table_border_color="#e2e8f0",
            table_border_color_dark="#334155",
            # Tabs
            border_color_accent="#2563eb",
            border_color_accent_dark="#3b82f6",
            # Shadows
            shadow_spread="2px",
        )


# ── Custom CSS additions ──
CUSTOM_CSS = """
/* Header bar */
.header-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 20px;
    margin: -8px -8px 16px -8px;
    border-radius: 8px;
    background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%);
    color: white;
}
.dark .header-bar {
    background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%);
}
.header-bar h1 {
    margin: 0;
    font-size: 1.4em;
    font-weight: 700;
    color: white !important;
}
.header-bar .version-badge {
    font-size: 0.75em;
    background: rgba(255,255,255,0.2);
    padding: 3px 10px;
    border-radius: 12px;
    font-weight: 500;
}

/* Dark mode toggle button */
#dark-toggle {
    cursor: pointer;
    background: transparent;
    border: 1px solid rgba(255,255,255,0.3);
    color: white;
    padding: 6px 14px;
    border-radius: 6px;
    font-size: 0.85em;
    transition: all 0.2s;
}
#dark-toggle:hover {
    background: rgba(255,255,255,0.15);
}

/* Score bar in search results */
.score-bar {
    display: inline-block;
    height: 6px;
    border-radius: 3px;
    background: linear-gradient(90deg, #3b82f6, #2563eb);
    transition: width 0.3s;
}
.dark .score-bar {
    background: linear-gradient(90deg, #60a5fa, #3b82f6);
}

/* Source cards */
.source-card {
    border: 1px solid var(--block-border-color);
    border-radius: 8px;
    padding: 12px 16px;
    margin: 6px 0;
    background: var(--block-background-fill);
    transition: box-shadow 0.2s;
}
.source-card:hover {
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
.dark .source-card:hover {
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
}
.source-card .score {
    font-weight: 600;
    color: #2563eb;
    font-size: 0.9em;
}
.dark .source-card .score {
    color: #60a5fa;
}
.source-card .breadcrumb {
    color: #64748b;
    font-size: 0.8em;
    margin-top: 4px;
}
.dark .source-card .breadcrumb {
    color: #94a3b8;
}
.source-card .content {
    margin-top: 6px;
    line-height: 1.5;
    font-size: 0.92em;
}
.source-card .meta-pills {
    margin-top: 8px;
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
}
.source-card .pill {
    font-size: 0.75em;
    padding: 2px 8px;
    border-radius: 10px;
    background: #e2e8f0;
    color: #475569;
}
.dark .source-card .pill {
    background: #334155;
    color: #cbd5e1;
}

/* Empty state */
.empty-state {
    text-align: center;
    padding: 40px 20px;
    color: #94a3b8;
}
.empty-state .icon {
    font-size: 2.5em;
    margin-bottom: 12px;
    opacity: 0.5;
}
.empty-state p {
    margin: 4px 0;
    font-size: 0.95em;
}

/* Confirmation overlay */
.confirm-overlay {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
}
.confirm-dialog {
    background: white;
    border-radius: 12px;
    padding: 24px;
    max-width: 420px;
    width: 90%;
    box-shadow: 0 20px 60px rgba(0,0,0,0.2);
}
.dark .confirm-dialog {
    background: #1e293b;
    color: #e2e8f0;
}
.confirm-dialog h3 {
    margin: 0 0 12px 0;
    font-size: 1.1em;
}
.confirm-dialog p {
    margin: 0 0 20px 0;
    color: #64748b;
    font-size: 0.9em;
}
.dark .confirm-dialog p {
    color: #94a3b8;
}
.confirm-dialog .actions {
    display: flex;
    gap: 10px;
    justify-content: flex-end;
}
.confirm-dialog button {
    padding: 8px 20px;
    border-radius: 6px;
    border: none;
    cursor: pointer;
    font-size: 0.9em;
    font-weight: 500;
}
.confirm-dialog .btn-cancel {
    background: #f1f5f9;
    color: #475569;
}
.dark .confirm-dialog .btn-cancel {
    background: #334155;
    color: #e2e8f0;
}
.confirm-dialog .btn-danger {
    background: #dc2626;
    color: white;
}
.confirm-dialog .btn-danger:hover {
    background: #b91c1c;
}

/* Health status indicators */
.status-dot {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    margin-right: 6px;
}
.status-dot.ok { background: #22c55e; }
.status-dot.error { background: #ef4444; }
.status-dot.warning { background: #f59e0b; }

/* Progress bar dark mode fix */
.dark .progress-track {
    background: #334155 !important;
}

/* Footer */
.footer-bar {
    text-align: center;
    padding: 8px;
    font-size: 0.8em;
    color: #94a3b8;
    border-top: 1px solid var(--block-border-color);
    margin-top: 16px;
}

/* Chatbot adaptive height */
.chatbot-container .chatbot {
    min-height: 300px;
    max-height: calc(100vh - 350px);
}
"""

# ── JavaScript for dark mode toggle + confirmations ──
CUSTOM_JS = """
() => {
    // --- Dark mode toggle ---
    const saved = localStorage.getItem('pdf_framework_theme');
    if (saved === 'dark') {
        document.body.classList.add('dark');
    } else if (saved === 'light') {
        document.body.classList.remove('dark');
    }
    // else follow system preference (Gradio default)

    window.toggleDarkMode = function() {
        const isDark = document.body.classList.toggle('dark');
        localStorage.setItem('pdf_framework_theme', isDark ? 'dark' : 'light');
        const btn = document.getElementById('dark-toggle');
        if (btn) btn.textContent = isDark ? 'Light Mode' : 'Dark Mode';
    };

    // Update button text on load
    setTimeout(() => {
        const btn = document.getElementById('dark-toggle');
        if (btn) {
            btn.textContent = document.body.classList.contains('dark') ? 'Light Mode' : 'Dark Mode';
        }
    }, 100);

    // --- Confirmation dialog system ---
    window.showConfirmDialog = function(title, message, onConfirm) {
        // Remove existing
        const existing = document.querySelector('.confirm-overlay');
        if (existing) existing.remove();

        const overlay = document.createElement('div');
        overlay.className = 'confirm-overlay';
        overlay.innerHTML = `
            <div class="confirm-dialog">
                <h3>${title}</h3>
                <p>${message}</p>
                <div class="actions">
                    <button class="btn-cancel" onclick="this.closest('.confirm-overlay').remove()">Отмена</button>
                    <button class="btn-danger" id="confirm-yes-btn">Подтвердить</button>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);

        // Close on overlay click
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) overlay.remove();
        });

        // Close on Escape
        const escHandler = (e) => {
            if (e.key === 'Escape') {
                overlay.remove();
                document.removeEventListener('keydown', escHandler);
            }
        };
        document.addEventListener('keydown', escHandler);

        document.getElementById('confirm-yes-btn').addEventListener('click', () => {
            overlay.remove();
            if (onConfirm) onConfirm();
        });
    };
}
"""

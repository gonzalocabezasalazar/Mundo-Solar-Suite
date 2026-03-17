"""
components/__init__.py
Exporta todos los componentes reutilizables de la capa UI.
"""
from components.theme import (
    get_theme,
    get_colors,
    toggle_theme,
    theme_toggle_button,
    apply_theme,
)
from components.cards import (
    planta_card,
    kpi_row,
    health_gauge,
    role_badge,
    breadcrumb,
)
from components.filters import (
    period_selector,
    campaign_selector,
    date_range_filter,
    context_bar,
)

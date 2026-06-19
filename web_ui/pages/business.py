"""
Business page for Mycelium NiceGUI application.

Provides access to business operations and management features including
KPI overview, management navigation, quick actions, and business intelligence.
"""

from nicegui import ui, app
from web_ui.layout import page_layout, back_to_dashboard
from web_ui.theme import get_colors


@ui.page("/business")
def business_page():
    """Business operations dashboard with KPIs, management links, and quick actions."""
    user = app.storage.user
    if not user.get("user_id"):
        ui.navigate.to("/login")
        return

    page_layout("Business")
    back_to_dashboard()
    colors = get_colors()

    with ui.column().classes("w-full max-w-6xl mx-auto p-4 gap-4"):
        # Section 1: Business Overview Dashboard
        with ui.card().classes("w-full p-4"):
            ui.label("Business Overview Dashboard").classes("text-h5 q-mb-md")

            # Row 1: Inventory / operational KPIs
            with ui.row().classes("w-full gap-4 flex-wrap q-mb-md"):
                _kpi_card("science", "LC On Hand", "0", "Liquid Cultures", colors)
                _kpi_card("grass", "Spawn On Hand", "0", "Spawn Ready", colors)
                _kpi_card(
                    "inventory_2", "Substrate On Hand", "0", "Substrate Ready", colors
                )
                _kpi_card("schedule", "Staff Hours", "0", "This Month", colors)

            # Row 2: Financial KPIs
            with ui.row().classes("w-full gap-4 flex-wrap"):
                _kpi_card("attach_money", "Total Revenue", "$0", "All Time", colors)
                _kpi_card("trending_down", "Total Expenses", "$0", "All Time", colors)
                _kpi_card(
                    "trending_up", "Net Profit", "$0", "Revenue - Expenses", colors
                )
                _kpi_card("pie_chart", "Profit Margin", "0%", "Net Margin %", colors)

        # Section 2: Business Management
        ui.label("Business Management").classes("text-h5 q-mt-md q-mb-sm")

        with ui.row().classes("w-full gap-4 flex-wrap"):
            _mgmt_card(
                "home_work",
                "Farms & Grow Rooms",
                "Farm location management, grow room configuration, "
                "capacity planning, and facility analytics",
                "Manage Farms",
                colors,
                href="/farms",
            )
            _mgmt_card(
                "groups",
                "Employees",
                "Employee roster management, pay rates, roles, "
                "performance tracking, and employment history",
                "Manage Employees",
                colors,
            )
            _mgmt_card(
                "inventory",
                "Inventory",
                "Product categories, purchase orders, cost tracking, "
                "loss monitoring, and supplier management",
                "Manage Inventory",
                colors,
            )

        with ui.row().classes("w-full gap-4 flex-wrap"):
            _mgmt_card(
                "eco",
                "Production",
                "Spawn batches, bulk substrates, harvest tracking, "
                "labor management, and utilities monitoring",
                "Manage Production",
                colors,
            )
            _mgmt_card(
                "point_of_sale",
                "Sales",
                "Customer relationships, sales orders, harvest traceability, "
                "pricing, and performance analytics",
                "Manage Sales",
                colors,
            )
            _mgmt_card(
                "assessment",
                "Financials",
                "Revenue analysis, expense tracking, P&L reports, "
                "profit margins, and business intelligence",
                "View Financials",
                colors,
            )

        # Section 3: Quick Actions Panel
        with ui.card().classes("w-full p-4"):
            ui.label("Quick Actions").classes("text-h5 q-mb-md")
            with ui.row().classes("w-full gap-3 flex-wrap"):
                _quick_button("add_circle", "Add New Sale", colors)
                _quick_button("content_cut", "Record Harvest", colors)
                _quick_button("schedule", "Log Labour Hours", colors)
                _quick_button("add_box", "Add Inventory", colors)
                _quick_button("receipt_long", "Pay Utility Bill", colors)
                _quick_button("summarize", "Generate Report", colors)

        # Section 4: Business Intelligence
        with ui.row().classes("w-full gap-4 flex-wrap"):
            with ui.card().classes("p-4 flex-1 min-w-72"):
                ui.label("Recent Activity").classes("text-h5 q-mb-md")
                ui.label(
                    "Recent sales, harvests, and alerts will appear here..."
                ).classes("text-muted text-center")

            with ui.card().classes("p-4 flex-1 min-w-72"):
                ui.label("Performance Metrics").classes("text-h5 q-mb-md")
                with ui.row().classes("w-full gap-4 q-mb-md"):
                    with ui.column().classes("flex-1 items-center gap-0"):
                        ui.label("Production Efficiency").classes(
                            "text-subtitle2 text-weight-bold"
                        )
                        ui.label("Yield per batch tracking").classes(
                            "text-caption text-muted"
                        )
                    with ui.column().classes("flex-1 items-center gap-0"):
                        ui.label("Labour Productivity").classes(
                            "text-subtitle2 text-weight-bold"
                        )
                        ui.label("Revenue per hour worked").classes(
                            "text-caption text-muted"
                        )
                with ui.row().classes("w-full gap-4 q-mb-md"):
                    with ui.column().classes("flex-1 items-center gap-0"):
                        ui.label("Inventory Turnover").classes(
                            "text-subtitle2 text-weight-bold"
                        )
                        ui.label("Days of stock on hand").classes(
                            "text-caption text-muted"
                        )
                    with ui.column().classes("flex-1 items-center gap-0"):
                        ui.label("Customer Analysis").classes(
                            "text-subtitle2 text-weight-bold"
                        )
                        ui.label("Top customers by revenue").classes(
                            "text-caption text-muted"
                        )

                ui.separator().classes("q-my-sm")
                ui.label("System Alerts").classes(
                    "text-subtitle1 text-weight-bold text-center q-mb-sm"
                )
                ui.label(
                    "Low inventory warnings and overdue bills will appear here..."
                ).classes("text-muted text-center text-caption")


def _kpi_card(icon: str, title: str, value: str, subtitle: str, colors: dict):
    """Render a single KPI metric card."""
    with ui.card().classes("p-4 flex-1 min-w-48 items-center"):
        ui.icon(icon, size="sm").style(f"color: {colors['primary']}")
        ui.label(title).classes("text-subtitle2 q-mt-xs")
        ui.label(value).classes("text-h4").style(f"color: {colors['primary']}")
        ui.label(subtitle).classes("text-caption text-muted")


def _mgmt_card(
    icon: str,
    title: str,
    description: str,
    button_label: str,
    colors: dict,
    href: str = None,
):
    """Render a management navigation card. If href is set, navigates instead of showing placeholder."""
    with ui.card().classes("p-4 flex-1 min-w-64"):
        with ui.column().classes("items-center gap-2 w-full"):
            ui.icon(icon, size="md").style(f"color: {colors['primary']}")
            ui.label(title).classes("text-h6")
            ui.label(description).classes("text-caption text-muted text-center")
            if href:
                ui.button(
                    button_label, on_click=lambda h=href: ui.navigate.to(h)
                ).classes("w-full q-mt-sm")
            else:
                ui.button(
                    button_label, on_click=lambda: ui.notify("Coming soon", type="info")
                ).classes("w-full q-mt-sm")


def _quick_button(icon: str, label: str, colors: dict):
    """Render a quick-action button."""
    ui.button(label, icon=icon, on_click=lambda: ui.notify("Coming soon", type="info"))

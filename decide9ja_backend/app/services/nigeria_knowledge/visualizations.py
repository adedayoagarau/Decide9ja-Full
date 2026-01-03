"""
WhatsApp Visualization Generator

Creates visual representations of data that can be sent via WhatsApp:
1. Text-based charts (ASCII art for simple data)
2. Image charts (using matplotlib/PIL)
3. Info cards with formatted text
4. Trend indicators and comparisons

WhatsApp supports images up to 16MB, so we generate optimized PNGs.
"""

import io
import base64
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class WhatsAppVisualizer:
    """Generates visualizations optimized for WhatsApp"""

    def __init__(self):
        self.chart_width = 800
        self.chart_height = 600
        self._matplotlib_available = self._check_matplotlib()
        self._pillow_available = self._check_pillow()

    def _check_matplotlib(self) -> bool:
        try:
            import matplotlib
            matplotlib.use('Agg')  # Non-interactive backend
            return True
        except ImportError:
            logger.warning("matplotlib not available. Install with: pip install matplotlib")
            return False

    def _check_pillow(self) -> bool:
        try:
            from PIL import Image
            return True
        except ImportError:
            logger.warning("Pillow not available. Install with: pip install Pillow")
            return False

    # ===========================================
    # TEXT-BASED VISUALIZATIONS (Always work)
    # ===========================================

    def text_bar_chart(self, data: List[Dict], title: str = "",
                       label_key: str = "label", value_key: str = "value",
                       max_width: int = 20) -> str:
        """
        Generate a text-based bar chart.

        Args:
            data: List of dicts with label and value keys
            title: Chart title
            label_key: Key for labels in data dicts
            value_key: Key for values in data dicts
            max_width: Maximum bar width in characters

        Returns:
            Formatted text chart
        """
        if not data:
            return "No data available"

        # Get max value for scaling
        values = [d.get(value_key, 0) for d in data]
        max_val = max(values) if values else 1

        # Get max label length
        labels = [str(d.get(label_key, ""))[:15] for d in data]
        max_label = max(len(l) for l in labels) if labels else 10

        lines = []
        if title:
            lines.append(f"📊 *{title}*")
            lines.append("")

        for i, item in enumerate(data[:10]):  # Limit to 10 items
            label = str(item.get(label_key, ""))[:15].ljust(max_label)
            value = item.get(value_key, 0)

            # Calculate bar length
            bar_len = int((value / max_val) * max_width) if max_val > 0 else 0
            bar = "█" * bar_len + "░" * (max_width - bar_len)

            # Format value
            if isinstance(value, float):
                val_str = f"{value:.1f}"
            else:
                val_str = str(value)

            lines.append(f"{label} {bar} {val_str}")

        return "\n".join(lines)

    def text_trend_indicator(self, current: float, previous: float,
                            label: str = "Value", unit: str = "") -> str:
        """
        Generate a trend indicator with arrow and percentage change.

        Args:
            current: Current value
            previous: Previous value
            label: Value label
            unit: Unit suffix (%, NGN, etc.)

        Returns:
            Formatted trend indicator
        """
        if previous == 0:
            change_pct = 0
        else:
            change_pct = ((current - previous) / abs(previous)) * 100

        if change_pct > 0:
            arrow = "📈"
            direction = "up"
        elif change_pct < 0:
            arrow = "📉"
            direction = "down"
        else:
            arrow = "➡️"
            direction = "stable"

        return f"""*{label}*

Current: {current:,.2f}{unit}
Previous: {previous:,.2f}{unit}

{arrow} {abs(change_pct):.1f}% {direction}"""

    def text_comparison_card(self, items: List[Dict], title: str = "Comparison") -> str:
        """
        Generate a comparison card for multiple items.

        Args:
            items: List of dicts with 'name' and 'values' (dict of metrics)
            title: Card title

        Returns:
            Formatted comparison card
        """
        if not items:
            return "No data to compare"

        lines = [f"📋 *{title}*", ""]

        for item in items[:5]:
            name = item.get("name", "Unknown")
            lines.append(f"▪️ *{name}*")

            values = item.get("values", {})
            for key, val in list(values.items())[:5]:
                if isinstance(val, float):
                    val_str = f"{val:,.2f}"
                else:
                    val_str = str(val)
                lines.append(f"  • {key}: {val_str}")
            lines.append("")

        return "\n".join(lines)

    def text_info_card(self, entity: Dict, card_type: str = "default") -> str:
        """
        Generate an info card for an entity.

        Args:
            entity: Entity data dict
            card_type: Type of card (politician, state, economic, event)

        Returns:
            Formatted info card
        """
        name = entity.get("name", "Unknown")
        entity_type = entity.get("type", "").replace("_", " ").title()

        if card_type == "politician" or "politician" in entity.get("type", ""):
            return self._politician_card(entity)
        elif card_type == "state" or entity.get("type") == "state":
            return self._state_card(entity)
        elif card_type == "economic":
            return self._economic_card(entity)
        else:
            return self._default_card(entity)

    def _politician_card(self, entity: Dict) -> str:
        """Generate politician info card"""
        name = entity.get("name", "Unknown")
        position = entity.get("position", "")
        party = entity.get("party", entity.get("partyLabel", ""))
        state = entity.get("state", entity.get("stateLabel", ""))

        card = f"""👤 *{name}*

🏛️ Position: {position or 'N/A'}
🎫 Party: {party or 'N/A'}
📍 State: {state or 'Federal'}"""

        if entity.get("start_date"):
            card += f"\n📅 Since: {entity['start_date']}"

        return card

    def _state_card(self, entity: Dict) -> str:
        """Generate state info card"""
        name = entity.get("name", "Unknown")
        capital = entity.get("capital", "")
        zone = entity.get("geopolitical_zone", "")
        created = entity.get("year_created", "")

        return f"""🏙️ *{name}*

🏛️ Capital: {capital or 'N/A'}
🗺️ Zone: {zone or 'N/A'}
📅 Created: {created or 'N/A'}"""

    def _economic_card(self, entity: Dict) -> str:
        """Generate economic data card"""
        indicator = entity.get("indicator", entity.get("name", "Unknown"))
        value = entity.get("value", "N/A")
        year = entity.get("year", "")
        unit = entity.get("unit", "")

        if isinstance(value, float):
            if unit == "percent":
                val_str = f"{value:.2f}%"
            else:
                val_str = f"{value:,.2f}"
        else:
            val_str = str(value)

        return f"""📊 *{indicator}*

💰 Value: {val_str}
📅 Year: {year or 'N/A'}
📈 Source: {entity.get('source', 'Knowledge Base')}"""

    def _default_card(self, entity: Dict) -> str:
        """Generate default info card"""
        name = entity.get("name", "Unknown")
        entity_type = entity.get("type", "").replace("_", " ").title()
        description = entity.get("description", entity.get("content", ""))

        if isinstance(description, list):
            description = " ".join(str(d) for d in description)
        description = str(description)[:200] if description else ""

        card = f"""ℹ️ *{name}*
📁 Type: {entity_type}"""

        if description:
            card += f"\n\n{description}..."

        return card

    def text_timeline(self, events: List[Dict], title: str = "Timeline") -> str:
        """
        Generate a text-based timeline.

        Args:
            events: List of events with 'year', 'name', 'description'
            title: Timeline title

        Returns:
            Formatted timeline
        """
        if not events:
            return "No events found"

        # Sort by year
        sorted_events = sorted(events, key=lambda x: x.get("year", 0))

        lines = [f"📅 *{title}*", ""]

        for event in sorted_events[:10]:
            year = event.get("year", "")
            name = event.get("name", "Unknown")
            desc = event.get("description", "")[:50]

            lines.append(f"*{year}* ─── {name}")
            if desc:
                lines.append(f"        {desc}")
            lines.append("        │")

        # Remove last connector
        if lines and lines[-1] == "        │":
            lines[-1] = "        ▼"

        return "\n".join(lines)

    def text_leaderboard(self, items: List[Dict], title: str = "Top Rankings",
                        label_key: str = "name", value_key: str = "value") -> str:
        """
        Generate a leaderboard with medals.

        Args:
            items: List of items to rank
            title: Leaderboard title
            label_key: Key for item names
            value_key: Key for item values

        Returns:
            Formatted leaderboard
        """
        if not items:
            return "No data available"

        # Sort by value descending
        sorted_items = sorted(items, key=lambda x: x.get(value_key, 0), reverse=True)

        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

        lines = [f"🏆 *{title}*", ""]

        for i, item in enumerate(sorted_items[:10]):
            medal = medals[i] if i < len(medals) else f"{i+1}."
            name = item.get(label_key, "Unknown")
            value = item.get(value_key, 0)

            if isinstance(value, float):
                val_str = f"{value:,.2f}"
            else:
                val_str = str(value)

            lines.append(f"{medal} {name}: {val_str}")

        return "\n".join(lines)

    # ===========================================
    # IMAGE-BASED VISUALIZATIONS (requires matplotlib)
    # ===========================================

    def generate_line_chart(self, data: List[Dict], title: str = "",
                           x_key: str = "year", y_key: str = "value",
                           label: str = "") -> Optional[bytes]:
        """
        Generate a line chart as PNG bytes.

        Args:
            data: List of data points
            title: Chart title
            x_key: Key for x-axis values
            y_key: Key for y-axis values
            label: Line label

        Returns:
            PNG image bytes or None if matplotlib unavailable
        """
        if not self._matplotlib_available:
            return None

        import matplotlib.pyplot as plt

        # Sort data
        sorted_data = sorted(data, key=lambda x: x.get(x_key, 0))

        x_vals = [d.get(x_key) for d in sorted_data]
        y_vals = [d.get(y_key) for d in sorted_data]

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(x_vals, y_vals, marker='o', linewidth=2, markersize=6, label=label)

        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel(x_key.title())
        ax.set_ylabel(y_key.title())
        ax.grid(True, alpha=0.3)

        if label:
            ax.legend()

        # Save to bytes
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight',
                   facecolor='white', edgecolor='none')
        plt.close(fig)
        buf.seek(0)

        return buf.getvalue()

    def generate_bar_chart(self, data: List[Dict], title: str = "",
                          label_key: str = "label", value_key: str = "value",
                          horizontal: bool = True) -> Optional[bytes]:
        """
        Generate a bar chart as PNG bytes.

        Args:
            data: List of data points
            title: Chart title
            label_key: Key for labels
            value_key: Key for values
            horizontal: Whether to make horizontal bars

        Returns:
            PNG image bytes or None if matplotlib unavailable
        """
        if not self._matplotlib_available:
            return None

        import matplotlib.pyplot as plt

        labels = [str(d.get(label_key, ""))[:20] for d in data[:15]]
        values = [d.get(value_key, 0) for d in data[:15]]

        fig, ax = plt.subplots(figsize=(10, 6))

        if horizontal:
            ax.barh(labels, values, color='#2E86AB')
            ax.set_xlabel(value_key.title())
        else:
            ax.bar(labels, values, color='#2E86AB')
            ax.set_ylabel(value_key.title())
            plt.xticks(rotation=45, ha='right')

        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='x' if horizontal else 'y')

        # Save to bytes
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight',
                   facecolor='white', edgecolor='none')
        plt.close(fig)
        buf.seek(0)

        return buf.getvalue()

    def generate_pie_chart(self, data: List[Dict], title: str = "",
                          label_key: str = "label", value_key: str = "value") -> Optional[bytes]:
        """
        Generate a pie chart as PNG bytes.

        Args:
            data: List of data points
            title: Chart title
            label_key: Key for labels
            value_key: Key for values

        Returns:
            PNG image bytes or None if matplotlib unavailable
        """
        if not self._matplotlib_available:
            return None

        import matplotlib.pyplot as plt

        labels = [str(d.get(label_key, ""))[:15] for d in data[:8]]
        values = [d.get(value_key, 0) for d in data[:8]]

        fig, ax = plt.subplots(figsize=(10, 8))

        colors = plt.cm.Set3(range(len(labels)))
        ax.pie(values, labels=labels, autopct='%1.1f%%', colors=colors,
               startangle=90, explode=[0.02] * len(labels))

        ax.set_title(title, fontsize=14, fontweight='bold')

        # Save to bytes
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight',
                   facecolor='white', edgecolor='none')
        plt.close(fig)
        buf.seek(0)

        return buf.getvalue()

    # ===========================================
    # UTILITY METHODS
    # ===========================================

    def image_to_base64(self, image_bytes: bytes) -> str:
        """Convert image bytes to base64 string"""
        return base64.b64encode(image_bytes).decode('utf-8')

    def save_chart(self, image_bytes: bytes, filename: str):
        """Save chart to file"""
        output_dir = Path(__file__).parent.parent.parent.parent / "nigeria_knowledge_data" / "charts"
        output_dir.mkdir(parents=True, exist_ok=True)

        filepath = output_dir / filename
        with open(filepath, 'wb') as f:
            f.write(image_bytes)

        return str(filepath)


# Convenience functions
def create_text_chart(data: List[Dict], chart_type: str = "bar", **kwargs) -> str:
    """Create a text-based chart"""
    viz = WhatsAppVisualizer()

    if chart_type == "bar":
        return viz.text_bar_chart(data, **kwargs)
    elif chart_type == "trend":
        return viz.text_trend_indicator(**kwargs)
    elif chart_type == "comparison":
        return viz.text_comparison_card(data, **kwargs)
    elif chart_type == "timeline":
        return viz.text_timeline(data, **kwargs)
    elif chart_type == "leaderboard":
        return viz.text_leaderboard(data, **kwargs)
    else:
        return viz.text_bar_chart(data, **kwargs)


def create_info_card(entity: Dict, card_type: str = "default") -> str:
    """Create an info card for an entity"""
    viz = WhatsAppVisualizer()
    return viz.text_info_card(entity, card_type)

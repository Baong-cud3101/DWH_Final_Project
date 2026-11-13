"""Kiểu biểu đồ thống nhất cho báo cáo (nền sáng, phù hợp in ấn)."""

import matplotlib
import matplotlib.pyplot as plt

from common import FIG_DIR

PALETTE = ["#1f4e79", "#e67e22", "#28b463", "#c0392b", "#8e44ad", "#16a085", "#7f8c8d"]


def apply_style() -> None:
    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": "#444444",
        "axes.grid": True,
        "grid.color": "#dddddd",
        "grid.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.prop_cycle": matplotlib.cycler(color=PALETTE),
        "legend.frameon": False,
    })


def save(fig, name: str) -> None:
    path = FIG_DIR / f"{name}.png"
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"  [hinh] {path.name}")


def fmt_usd(x, _=None) -> str:
    if abs(x) >= 1e6:
        return f"{x / 1e6:.1f}M"
    if abs(x) >= 1e3:
        return f"{x / 1e3:.0f}K"
    return f"{x:.0f}"

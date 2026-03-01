"""
solo_builder_live_multi_snapshot.py
Generates multi-page PDF timeline snapshots of the Solo Builder DAG and memory state.

Requires: matplotlib
"""

import os
from datetime import datetime
from typing import Dict, Any

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.backends.backend_pdf import PdfPages
    import numpy as np
    _MATPLOTLIB_OK = True
except ImportError:
    _MATPLOTLIB_OK = False


# ── Color Palettes ────────────────────────────────────────────────────────────
_STATUS_HEX = {
    "Pending":  "#FFC107",
    "Running":  "#2196F3",
    "Verified": "#4CAF50",
    "Failed":   "#F44336",
}
_SHADOW_HEX = {
    "Pending": "#9C27B0",
    "Done":    "#4CAF50",
}
_BG_DARK   = "#0d0d1a"
_BG_PANEL  = "#1a1a2e"
_GRID_LINE = "#2a2a44"
_TEXT_MAIN = "#e0e0f0"
_TEXT_DIM  = "#888899"
_BRANCH_COLORS = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7",
                  "#DDA0DD", "#F0A500", "#00CEC9", "#E17055", "#74B9FF"]


def _status_hex(status: str) -> str:
    return _STATUS_HEX.get(status, "#9E9E9E")


def _shadow_hex(shadow: str) -> str:
    return _SHADOW_HEX.get(shadow, "#9E9E9E")


# ── Public API ────────────────────────────────────────────────────────────────
def generate_live_multi_pdf(dag: Dict, memory_store: Dict, filename: str) -> None:
    """
    Generate a multi-page PDF snapshot of the DAG and memory state.

    Args:
        dag:          dict of tasks → branches → subtasks
        memory_store: dict of branch → list of memory snapshot dicts
        filename:     output PDF path (directories created automatically)
    """
    if not _MATPLOTLIB_OK:
        raise ImportError(
            "matplotlib is required for PDF generation. "
            "Install it with: pip install matplotlib"
        )

    out_dir = os.path.dirname(filename)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with PdfPages(filename) as pdf:
        _page_dag_overview(pdf, dag)
        _page_branch_progress(pdf, dag)
        _page_memory_timeline(pdf, memory_store)
        _page_status_distribution(pdf, dag)

        d = pdf.infodict()
        d["Title"]        = "Solo Builder Timeline Snapshot"
        d["Author"]       = "Solo Builder AI Agent CLI"
        d["Subject"]      = "DAG + Memory State"
        d["CreationDate"] = datetime.now()


# ── Page 1: DAG Hierarchy Overview ───────────────────────────────────────────
def _page_dag_overview(pdf: PdfPages, dag: Dict) -> None:
    fig = plt.figure(figsize=(16, 10))
    fig.patch.set_facecolor(_BG_PANEL)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(_BG_PANEL)
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 10)
    ax.axis("off")

    ax.text(8, 9.75, "Solo Builder — DAG Hierarchy Overview",
            ha="center", va="top", fontsize=15, fontweight="bold",
            color=_TEXT_MAIN, fontfamily="monospace")
    ax.text(8, 9.45, f"Generated: {datetime.now().strftime('%Y-%m-%d  %H:%M:%S')}",
            ha="center", va="top", fontsize=8, color=_TEXT_DIM, fontfamily="monospace")

    # Draw horizontal separator
    ax.axhline(9.3, color=_GRID_LINE, linewidth=1.0)

    y_cursor = 8.9
    task_x   = 0.5
    col_branch   = 3.5
    col_subtask  = 7.5

    for task_name, task_data in dag.items():
        if y_cursor < 0.4:
            break

        t_status = task_data.get("status", "Pending")
        t_color  = _status_hex(t_status)

        # Task box
        _fancy_box(ax, task_x, y_cursor, 2.6, 0.38, t_color, label=f"{task_name}",
                   sub=f"[{t_status}]", fontsize=9)

        branch_y = y_cursor
        for branch_name, branch_data in task_data.get("branches", {}).items():
            if branch_y < 0.4:
                break

            b_status = branch_data.get("status", "Pending")
            b_color  = _status_hex(b_status)

            # Connector: task → branch
            ax.annotate("", xy=(col_branch, branch_y), xytext=(task_x + 2.6, y_cursor),
                        arrowprops=dict(arrowstyle="-|>", color=_GRID_LINE, lw=0.8))

            # Branch box
            _fancy_box(ax, col_branch, branch_y, 3.2, 0.35, b_color,
                       label=branch_name, sub=f"[{b_status}]", fontsize=8)

            subtask_start_x = col_subtask
            subtask_y       = branch_y
            for i, (st_name, st_data) in enumerate(branch_data.get("subtasks", {}).items()):
                sx = subtask_start_x + (i % 5) * 1.5
                sy = subtask_y       - (i // 5) * 0.55

                if sy < 0.2:
                    break

                st_status = st_data.get("status", "Pending")
                st_shadow = st_data.get("shadow", "Pending")
                fc        = _status_hex(st_status)
                ec        = _shadow_hex(st_shadow)

                circle = plt.Circle((sx + 0.35, sy), 0.22, facecolor=fc,
                                    edgecolor=ec, linewidth=2.0, zorder=3)
                ax.add_patch(circle)
                ax.text(sx + 0.35, sy, st_name, ha="center", va="center",
                        fontsize=6.5, fontweight="bold", color="#000000",
                        fontfamily="monospace", zorder=4)

                ax.plot([col_branch + 3.2, sx + 0.13], [branch_y, sy],
                        color=_GRID_LINE, linewidth=0.5, linestyle=":", zorder=1)

            branch_y -= max(0.7, ((len(branch_data.get("subtasks", {})) - 1) // 5 + 1) * 0.6)

        y_cursor = min(branch_y, y_cursor) - 0.5

    # Legend
    _draw_legend(ax, x=0.3, y=0.5, items=[
        ("Pending",  _STATUS_HEX["Pending"]),
        ("Running",  _STATUS_HEX["Running"]),
        ("Verified", _STATUS_HEX["Verified"]),
    ], title="Status", shape="circle")
    _draw_legend(ax, x=5.0, y=0.5, items=[
        ("Shadow Pending", _SHADOW_HEX["Pending"]),
        ("Shadow Done",    _SHADOW_HEX["Done"]),
    ], title="Shadow (ring)", shape="ring")

    pdf.savefig(fig, facecolor=fig.get_facecolor())
    plt.close(fig)


# ── Page 2: Branch Progress Bars ─────────────────────────────────────────────
def _page_branch_progress(pdf: PdfPages, dag: Dict) -> None:
    rows = []
    for task_name, task_data in dag.items():
        for branch_name, branch_data in task_data.get("branches", {}).items():
            sts      = branch_data.get("subtasks", {})
            total    = len(sts)
            verified = sum(1 for s in sts.values() if s.get("status") == "Verified")
            running  = sum(1 for s in sts.values() if s.get("status") == "Running")
            shadow   = sum(1 for s in sts.values() if s.get("shadow") == "Done")
            rows.append((f"{task_name} / {branch_name}", verified, running, total, shadow))

    fig, ax = plt.subplots(figsize=(14, max(5, len(rows) * 1.2 + 2)))
    fig.patch.set_facecolor(_BG_PANEL)
    ax.set_facecolor(_BG_DARK)

    ax.set_title("Branch Progress Overview", color=_TEXT_MAIN, fontsize=13,
                 fontweight="bold", fontfamily="monospace", pad=14)

    spacing   = 1.4
    bar_h     = 0.55
    shadow_h  = 0.22
    max_total = max((r[3] for r in rows), default=1)
    y_pos     = np.arange(len(rows)) * spacing

    for i, (label, verified, running, total, shadow) in enumerate(rows):
        y    = y_pos[i]
        safe = max(total, 1)
        color = _BRANCH_COLORS[i % len(_BRANCH_COLORS)]

        # Background
        ax.barh(y, safe, height=bar_h, color=_GRID_LINE, align="center", zorder=1)
        # Verified
        ax.barh(y, verified, height=bar_h, color=_STATUS_HEX["Verified"],
                align="center", zorder=2)
        # Running (stacked on verified)
        ax.barh(y, running, left=verified, height=bar_h, color=_STATUS_HEX["Running"],
                align="center", zorder=2, alpha=0.85)
        # Shadow bar (smaller, below)
        ax.barh(y - bar_h * 0.7, shadow, height=shadow_h,
                color=_SHADOW_HEX["Done"], align="center", zorder=3, alpha=0.75)

        ax.text(-0.3, y, label, ha="right", va="center",
                color=color, fontsize=8.5, fontfamily="monospace")
        pct = f"{verified/safe*100:.0f}%"
        ax.text(safe + 0.1, y, f"{verified}/{total}  {pct}", ha="left", va="center",
                color=_TEXT_DIM, fontsize=7.5, fontfamily="monospace")

    ax.set_xlim(-0.5, max_total + 2)
    ax.set_ylim(-spacing * 0.8, len(rows) * spacing)
    ax.set_xlabel("Subtask count", color=_TEXT_DIM, fontfamily="monospace", fontsize=9)
    ax.tick_params(colors=_TEXT_DIM, labelsize=7)
    for spine in ax.spines.values():
        spine.set_color(_GRID_LINE)
    ax.set_yticks([])

    handles = [
        mpatches.Patch(color=_STATUS_HEX["Verified"], label="Verified"),
        mpatches.Patch(color=_STATUS_HEX["Running"],  label="Running"),
        mpatches.Patch(color=_GRID_LINE,              label="Pending"),
        mpatches.Patch(color=_SHADOW_HEX["Done"],     label="Shadow Done"),
    ]
    ax.legend(handles=handles, loc="lower right", facecolor=_BG_PANEL,
              edgecolor=_GRID_LINE, labelcolor=_TEXT_MAIN, fontsize=8)

    fig.tight_layout()
    pdf.savefig(fig, facecolor=fig.get_facecolor())
    plt.close(fig)


# ── Page 3: Memory Timeline ───────────────────────────────────────────────────
def _page_memory_timeline(pdf: PdfPages, memory_store: Dict) -> None:
    fig, ax = plt.subplots(figsize=(14, 8))
    fig.patch.set_facecolor(_BG_PANEL)
    ax.set_facecolor(_BG_DARK)
    ax.set_title("Memory Timeline per Branch", color=_TEXT_MAIN, fontsize=13,
                 fontweight="bold", fontfamily="monospace", pad=14)

    branches = [b for b, snaps in memory_store.items() if snaps]
    if not branches:
        ax.text(0.5, 0.5, "No memory snapshots recorded yet.",
                transform=ax.transAxes, ha="center", va="center",
                fontsize=12, color=_TEXT_DIM, fontfamily="monospace")
        pdf.savefig(fig, facecolor=fig.get_facecolor())
        plt.close(fig)
        return

    for i, branch in enumerate(branches):
        snaps      = memory_store[branch]
        timestamps = [s.get("timestamp", 0) for s in snaps]
        color      = _BRANCH_COLORS[i % len(_BRANCH_COLORS)]

        ax.scatter(timestamps, [i] * len(timestamps), color=color, s=55,
                   zorder=3, alpha=0.9, edgecolors="white", linewidths=0.5)

        if len(timestamps) > 1:
            ax.plot(timestamps, [i] * len(timestamps), color=color,
                    alpha=0.35, linewidth=1.5, zorder=2)

        for j, (t, snap) in enumerate(zip(timestamps[:6], snaps[:6])):
            label = snap.get("snapshot", "")[:12]
            ax.text(t, i + 0.18, label, ha="center", va="bottom",
                    fontsize=5.5, color=color, fontfamily="monospace",
                    rotation=45, zorder=4)

    ax.set_yticks(range(len(branches)))
    ax.set_yticklabels(branches, color=_TEXT_MAIN, fontsize=9,
                       fontfamily="monospace")
    ax.set_xlabel("Step", color=_TEXT_DIM, fontfamily="monospace", fontsize=9)
    ax.tick_params(colors=_TEXT_DIM, labelsize=7)
    ax.set_ylim(-0.6, len(branches) - 0.4)
    ax.grid(axis="x", color=_GRID_LINE, linewidth=0.5, linestyle="--", alpha=0.5)
    for spine in ax.spines.values():
        spine.set_color(_GRID_LINE)

    fig.tight_layout()
    pdf.savefig(fig, facecolor=fig.get_facecolor())
    plt.close(fig)


# ── Page 4: Status Distribution (Pie Charts) ──────────────────────────────────
def _page_status_distribution(pdf: PdfPages, dag: Dict) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 7))
    fig.patch.set_facecolor(_BG_PANEL)
    fig.suptitle("Solo Builder — Status Analytics", color=_TEXT_MAIN,
                 fontsize=14, fontweight="bold", fontfamily="monospace", y=0.97)

    subtask_counts = {"Pending": 0, "Running": 0, "Verified": 0}
    shadow_counts  = {"Shadow Pending": 0, "Shadow Done": 0}

    for task_data in dag.values():
        for branch_data in task_data.get("branches", {}).values():
            for st_data in branch_data.get("subtasks", {}).values():
                status = st_data.get("status", "Pending")
                if status in subtask_counts:
                    subtask_counts[status] += 1
                shadow = st_data.get("shadow", "Pending")
                key = "Shadow Done" if shadow == "Done" else "Shadow Pending"
                shadow_counts[key] += 1

    _pie(ax1, subtask_counts,
         colors=[_STATUS_HEX["Pending"], _STATUS_HEX["Running"], _STATUS_HEX["Verified"]],
         title="Subtask Status Distribution")
    _pie(ax2, shadow_counts,
         colors=[_SHADOW_HEX["Pending"], _SHADOW_HEX["Done"]],
         title="Shadow Agent Distribution")

    for ax in (ax1, ax2):
        ax.set_facecolor(_BG_DARK)

    fig.tight_layout(rect=[0, 0, 1, 0.94])
    pdf.savefig(fig, facecolor=fig.get_facecolor())
    plt.close(fig)


# ── Internal Helpers ──────────────────────────────────────────────────────────
def _pie(ax: Any, counts: Dict[str, int], colors: list, title: str) -> None:
    labels = list(counts.keys())
    sizes  = list(counts.values())
    if not any(s > 0 for s in sizes):
        ax.text(0.5, 0.5, "No data", transform=ax.transAxes,
                ha="center", va="center", color=_TEXT_DIM, fontsize=11)
        ax.set_title(title, color=_TEXT_MAIN, fontfamily="monospace", fontsize=11)
        return
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=colors,
        autopct="%1.1f%%", startangle=90,
        textprops={"color": _TEXT_MAIN, "fontfamily": "monospace", "fontsize": 9},
        wedgeprops={"edgecolor": _BG_DARK, "linewidth": 2.5},
    )
    for at in autotexts:
        at.set_fontsize(8)
    ax.set_title(title, color=_TEXT_MAIN, fontfamily="monospace",
                 fontsize=11, pad=12)


def _fancy_box(ax: Any, x: float, y: float, w: float, h: float,
               color: str, label: str, sub: str = "", fontsize: int = 9) -> None:
    rect = mpatches.FancyBboxPatch(
        (x, y - h / 2), w, h,
        boxstyle="round,pad=0.04",
        facecolor=color, edgecolor="white",
        alpha=0.85, linewidth=1.2, zorder=2,
    )
    ax.add_patch(rect)
    ax.text(x + w / 2, y + 0.05, label, ha="center", va="center",
            fontsize=fontsize, fontweight="bold",
            color="#000000", fontfamily="monospace", zorder=3)
    if sub:
        ax.text(x + w / 2, y - 0.12, sub, ha="center", va="center",
                fontsize=fontsize - 2, color="#222222",
                fontfamily="monospace", zorder=3)


def _draw_legend(ax: Any, x: float, y: float,
                 items: list, title: str, shape: str = "circle") -> None:
    ax.text(x, y + 0.25, title, color=_TEXT_DIM, fontsize=7,
            fontfamily="monospace", va="bottom")
    for i, (label, color) in enumerate(items):
        cx = x + i * 1.9
        if shape == "circle":
            c = plt.Circle((cx, y), 0.13, color=color, zorder=4)
            ax.add_patch(c)
        else:
            c = plt.Circle((cx, y), 0.13, facecolor="none",
                           edgecolor=color, linewidth=2.5, zorder=4)
            ax.add_patch(c)
        ax.text(cx + 0.18, y, label, va="center", fontsize=6.5,
                color=_TEXT_MAIN, fontfamily="monospace")

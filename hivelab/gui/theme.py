"""HiveLab 统一设计令牌（Qt 样式表）。

设计依据：
- emil-design-eng：刻意细节的累积；hover/press 微反馈；用细边框子厘代替重阴影。
- minimalist-skill：暖高级单色、大留白、1px 结构边、克制 accent、编辑风排版。

Qt QSS 限制说明：
- 无 transform scale，用 hover→pressed 的色阶变化模拟"按下去"的反馈。
- 无 box-shadow，卡片用 1px 边框 + 同色系浅底建立层次。
"""

from __future__ import annotations

# ---------- 设计令牌（暖高级中性色 + 靛蓝 accent） ----------
_CANVAS = "#F6F4EF"  # 应用背景（暖骨白）
_SURFACE = "#FFFFFF"  # 卡片/输入面
_SURFACE_ALT = "#FBFAF7"  # 次级面
_BORDER = "#E6E2DA"  # 结构性微边框（品牌感暖灰）
_BORDER_STRONG = "#D8D3C8"
_TEXT = "#1F1B16"  # 主文案（暖深炭，非纯黑）
_TEXT_MUTED = "#6F6A5F"  # 次级文案
_TEXT_FAINT = "#9B968B"
_ACCENT = "#5751E1"  # 靛蓝（收敛、线性风）
_ACCENT_HOVER = "#4640C8"
_ACCENT_PRESSED = "#3731A6"
_ACCENT_TINT = "#EEEDFD"

# 状态色（语义，低饱和，参考 minimalist 淡马卡龙）
_ST_DONE_BG = "#E9F2EA"
_ST_DONE_FG = "#33613A"
_ST_RUN_BG = "#E5EEFB"
_ST_RUN_FG = "#2F5B9E"
_ST_FAIL_BG = "#FBEAE9"
_ST_FAIL_FG = "#9C3D38"
_ST_WARN_BG = "#FBF1DC"
_ST_WARN_FG = "#8A6508"
_ST_NEUTRAL_BG = "#ECE9E4"
_ST_NEUTRAL_FG = "#5C574E"


def _status_qss(cls: str, bg: str, fg: str) -> str:
    return (
        f"QWidget#{cls} {{ background:{bg}; color:{fg}; border:1px solid {_BORDER}; "
        f"border-radius:999px; padding:2px 10px; font-size:12px; }}"
    )


def build_stylesheet() -> str:
    """返回全局样式表。"""
    return f"""
/* ============ 窗口与根 ============ */
QMainWindow, #root {{ background:{_CANVAS}; }}
QWidget {{ color:{_TEXT}; font-family:"Segoe UI","Microsoft YaHei UI","Microsoft YaHei","PingFang SC"; }}

/* ============ 左侧导航 ============ */
#navList {{
    background:{_CANVAS};
    border:none;
    border-right:1px solid {_BORDER};
    padding:16px 10px;
    outline:none;
    font-size:14px;
}}
#navList::item {{
    color:{_TEXT_MUTED};
    border-radius:9px;
    margin:2px 4px;
    padding:11px 12px;
}}
#navList::item:hover {{ color:{_TEXT}; background:{_SURFACE_ALT}; }}
#navList::item:selected {{
    color:{_ACCENT};
    background:{_ACCENT_TINT};
    font-weight:600;
}}
#navList::item:selected:hover {{ background:{_ACCENT_TINT}; }}

/* 品牌区 */
#brand {{
    background:{_ACCENT};
    color:white;
    border-radius:7px;
}}
QLabel#brandName {{ font-size:16px; font-weight:700; color:{_TEXT}; }}

/* ============ 标题层级（编辑风） ============ */
QLabel#panelTitle {{
    font-size:19px;
    font-weight:700;
    color:{_TEXT};
    letter-spacing:0.1px;
}}
/* 编辑风衬线大标题 */
QLabel#serifTitle {{
    font-family:"Playfair Display","Songti SC","STSong","SimSun",serif;
    font-size:26px;
    font-weight:600;
    color:{_TEXT};
    letter-spacing:-0.4px;
}}
QLabel#moduleKicker {{
    font-size:12px;
    font-weight:600;
    color:{_ACCENT};
    letter-spacing:0.6px;
}}
QLabel#hint, QLabel#muted {{ color:{_TEXT_MUTED}; font-size:13px; }}
QLabel#sectionLabel {{ font-size:13px; font-weight:600; color:{_TEXT}; }}

/* ============ 卡片容器（1px 微边框取代重阴影） ============ */
QFrame#card {{
    background:{_SURFACE};
    border:1px solid {_BORDER};
    border-radius:12px;
}}
QFrame#cardAlt {{
    background:{_SURFACE_ALT};
    border:1px solid {_BORDER};
    border-radius:12px;
}}

/* ============ 输入类 ============ */
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {{
    background:{_SURFACE};
    border:1px solid {_BORDER_STRONG};
    border-radius:8px;
    padding:7px 10px;
    font-size:14px;
    selection-background-color:{_ACCENT};
    selection-color:white;
}}
QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover, QComboBox:hover, QSpinBox:hover {{
    border-color:{_ACCENT};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border:1px solid {_ACCENT};
}}
QComboBox::drop-down {{ border:none; width:24px; }}
QComboBox::down-arrow {{
    image:none;
    border-left:5px solid transparent;
    border-right:5px solid transparent;
    border-top:6px solid {_TEXT_MUTED};
    margin-right:8px;
}}
QComboBox QAbstractItemView {{
    background:{_SURFACE};
    border:1px solid {_BORDER};
    border-radius:8px;
    padding:4px;
    selection-background-color:{_ACCENT_TINT};
    selection-color:{_TEXT};
    outline:none;
}}

/* ============ 按钮（hover/pressed 色阶模拟按压反馈） ============ */
QPushButton {{
    background:{_ACCENT};
    color:white;
    border:none;
    border-radius:9px;
    padding:9px 18px;
    font-size:14px;
    font-weight:600;
}}
QPushButton:hover {{ background:{_ACCENT_HOVER}; }}
QPushButton:pressed {{ background:{_ACCENT_PRESSED}; padding-top:11px; padding-bottom:7px; }}
QPushButton:disabled {{ background:{_BORDER_STRONG}; color:{_TEXT_FAINT}; }}

QPushButton#secondary {{
    background:{_SURFACE};
    color:{_TEXT};
    border:1px solid {_BORDER_STRONG};
    font-weight:500;
}}
QPushButton#secondary:hover {{ background:{_SURFACE_ALT}; border-color:{_ACCENT}; color:{_ACCENT}; }}
QPushButton#secondary:pressed {{ background:{_BORDER}; }}

/* ============ 表格（无网格、行悬停、语义状态） ============ */
QTableWidget, QTableView {{
    background:{_SURFACE};
    border:1px solid {_BORDER};
    border-radius:12px;
    gridline-color:transparent;
    font-size:13px;
    padding:4px;
}}
QTableWidget::item, QTableView::item {{
    padding:9px 8px;
    border-bottom:1px solid {_BORDER};
    border-left:none; border-right:none;
}}
QTableWidget::item:selected {{ background:{_ACCENT_TINT}; color:{_TEXT}; }}
QTableWidget::item:hover {{ background:{_SURFACE_ALT}; }}
QHeaderView::section {{
    background:{_SURFACE};
    color:{_TEXT_MUTED};
    border:none;
    border-bottom:1px solid {_BORDER_STRONG};
    padding:9px 8px;
    font-size:12px;
    font-weight:600;
}}
QTableCornerButton::section {{ background:{_SURFACE}; border:none; }}

QTabWidget::pane {{
    border:1px solid {_BORDER};
    border-radius:12px;
    background:{_SURFACE};
    top:-1px;
}}
QTabBar::tab {{
    background:transparent;
    color:{_TEXT_MUTED};
    padding:8px 16px;
    border:none;
    font-size:13px;
    border-bottom:2px solid transparent;
}}
QTabBar::tab:selected {{ color:{_ACCENT}; font-weight:600; border-bottom:2px solid {_ACCENT}; }}
QTabBar::tab:hover {{ color:{_TEXT}; }}

/* ============ 消息区 ============ */
QTextBrowser {{
    background:{_SURFACE};
    border:1px solid {_BORDER};
    border-radius:12px;
    padding:12px;
}}
QTextBrowser#reportBrowser {{
    background:transparent;
    border:none;
    padding:6px;
}}

/* ============ 复选框 ============ */
QCheckBox {{ font-size:14px; spacing:8px; }}
QCheckBox::indicator {{
    width:18px; height:18px;
    border:1px solid {_BORDER_STRONG};
    border-radius:5px;
    background:{_SURFACE};
}}
QCheckBox::indicator:checked {{
    background:{_ACCENT};
    border-color:{_ACCENT};
}}
QCheckBox::indicator:hover {{ border-color:{_ACCENT}; }}

QScrollBar:vertical {{ background:transparent; width:10px; margin:0; }}
QScrollBar::handle:vertical {{ background:{_BORDER_STRONG}; border-radius:5px; min-height:30px; }}
QScrollBar::handle:vertical:hover {{ background:{_TEXT_FAINT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
QScrollBar:horizontal {{ background:transparent; height:10px; margin:0; }}
QScrollBar::handle:horizontal {{ background:{_BORDER_STRONG}; border-radius:5px; min-width:30px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0; }}

QMessageBox {{ background:{_SURFACE}; }}
QToolTip {{ background:{_TEXT}; color:white; border:none; border-radius:6px; padding:6px 10px; font-size:12px; }}
"""
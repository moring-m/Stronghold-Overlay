"""stronghold-protocol-web 스타일 (어두운 청록 패널, 민트 강조, 각진 모서리)."""

PAGE = "#081519"
PANEL = "#0d2023"
RAISED = "#10272a"
RULE = "#2b5754"
ACCENT = "#79dcb7"
INK = "#eafaf3"
MUTED = "#91b6ad"
SIGNAL = "#f0d18a"     # 핵심 맹약
DANGER = "#b34332"
FONT = '"Bahnschrift", "Source Han Sans SC", "Noto Sans CJK SC", "Malgun Gothic", "Microsoft YaHei UI", sans-serif'

QSS = f"""
* {{ font-family: {FONT}; font-size: 13px; color: {INK}; }}
QWidget#Panel {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0b1d21, stop:1 {PAGE});
                 border: 1px solid {RULE}; }}
QLabel#Title {{ font-size: 20px; font-weight: 700; }}
QLabel#Section {{ font-size: 16px; font-weight: 700; }}
QLabel#Muted, QLabel#Hint {{ color: {MUTED}; }}
QLabel#Count {{ color: {ACCENT}; font-size: 18px; font-weight: 700; }}
QFrame#Rule {{ background: {RULE}; max-height: 1px; }}
QLineEdit, QComboBox, QPlainTextEdit, QSpinBox {{
    background: {PANEL}; border: 1px solid {RULE}; border-radius: 2px; padding: 6px 8px;
    selection-background-color: {ACCENT}; selection-color: {PAGE}; }}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QSpinBox:focus {{ border-color: {ACCENT}; }}
QComboBox QAbstractItemView {{ background: {PANEL}; border: 1px solid {RULE};
    selection-background-color: {RAISED}; selection-color: {ACCENT}; }}
QComboBox {{ padding-right: 26px; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{ image: url({{ARROW}}); width: 10px; height: 10px; }}
QPushButton {{ background: {PANEL}; border: 1px solid {RULE}; border-radius: 2px; padding: 6px 14px; }}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:checked, QPushButton#Primary {{ background: {ACCENT}; color: {PAGE}; border-color: {ACCENT}; font-weight: 700; }}
QPushButton#Seg {{ padding: 6px 0; min-width: 34px; }}
QPushButton#Tab {{ border: none; border-bottom: 2px solid transparent; background: transparent;
    padding: 8px 18px; color: {MUTED}; font-size: 14px; font-weight: 600; }}
QPushButton#Tab:hover {{ color: {INK}; }}
QPushButton#Tab:checked {{ color: {ACCENT}; border-bottom-color: {ACCENT}; background: {RAISED}; }}
QPushButton#Nav {{ text-align: left; padding: 10px 14px; border: none; border-left: 3px solid transparent;
    background: transparent; color: {MUTED}; font-size: 14px; }}
QPushButton#Nav:checked {{ border-left-color: {ACCENT}; background: {RAISED}; color: {INK}; font-weight: 700; }}
QPushButton#Close {{ border: none; background: transparent; font-size: 18px; padding: 2px 8px; color: {MUTED}; }}
QPushButton#Close:hover {{ color: {INK}; }}
QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {RULE}; background: {PANEL}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{ background: {RULE}; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QWidget#FilterBar {{ background: {PANEL}; border: 1px solid {RULE}; }}
QToolTip {{ background: {PANEL}; color: {INK}; border: 1px solid {RULE}; }}
QMenu {{ background: {PANEL}; border: 1px solid {RULE}; padding: 4px; }}
QMenu::item {{ padding: 6px 22px; }}
QMenu::item:selected {{ background: {RAISED}; color: {ACCENT}; }}
QMenu::separator {{ height: 1px; background: {RULE}; margin: 4px 0; }}
"""


def stylesheet() -> str:
    """드롭다운 화살표 이미지를 임시 파일로 만들어 QSS에 넣는다."""
    import tempfile
    from pathlib import Path
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
           f'<path d="M1 3 L5 7 L9 3" fill="none" stroke="{ACCENT}" stroke-width="1.6"/></svg>')
    path = Path(tempfile.gettempdir()) / "stronghold_overlay_arrow.svg"
    path.write_text(svg, "utf-8")
    return QSS.replace("{ARROW}", path.as_posix())

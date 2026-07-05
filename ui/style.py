# -*- coding: utf-8 -*-
"""
Bảng màu / stylesheet dùng chung cho toàn bộ phần mềm,
mô phỏng giao diện HMI công nghiệp (nền xanh dương - vàng nhạt)
theo đúng tinh thần các ảnh chụp màn hình WeinView gốc.
"""

COLOR_HEADER_BLUE = "#1857a4"
COLOR_HEADER_BLUE_DARK = "#123f7c"
COLOR_BG_CREAM = "#f5f0dc"
COLOR_BG_WHITE = "#ffffff"
COLOR_NAV_BLUE = "#1857a4"
COLOR_NAV_BLUE_ACTIVE = "#0e3f8a"
COLOR_ON_GREEN = "#2fae4e"
COLOR_OFF_GRAY = "#8a8a8a"
COLOR_ALARM_RED = "#d13c3c"
COLOR_TEXT_DARK = "#1c2b4a"

APP_STYLESHEET = f"""
QWidget {{
    font-family: "Segoe UI", "Arial", sans-serif;
    color: {COLOR_TEXT_DARK};
}}

QMainWindow, #centralArea {{
    background-color: {COLOR_BG_CREAM};
}}

#headerBar {{
    background-color: {COLOR_HEADER_BLUE};
}}

#headerTitle {{
    color: white;
    font-size: 20px;
    font-weight: 700;
    padding-left: 12px;
}}

#headerClock {{
    color: white;
    font-size: 14px;
    padding-right: 14px;
}}

#navBar {{
    background-color: {COLOR_NAV_BLUE};
}}

QPushButton#navButton {{
    background-color: {COLOR_NAV_BLUE};
    color: white;
    border: none;
    border-right: 1px solid #2a6bc2;
    font-size: 13px;
    font-weight: 600;
    padding: 10px 4px;
}}

QPushButton#navButton:hover {{
    background-color: #2569b8;
}}

QPushButton#navButton:checked {{
    background-color: {COLOR_NAV_BLUE_ACTIVE};
    border-bottom: 3px solid #ffd54a;
}}

QGroupBox {{
    background-color: {COLOR_BG_WHITE};
    border: 1px solid #c9c2a0;
    border-radius: 6px;
    margin-top: 14px;
    font-weight: 700;
    font-size: 13px;
    color: {COLOR_HEADER_BLUE_DARK};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}}

QLabel[role="value"] {{
    background-color: #fbf8ec;
    border: 1px solid #b9b28e;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 16px;
    font-weight: 700;
}}

QLabel[role="unit"] {{
    color: #6b6b6b;
    font-size: 12px;
}}

QPushButton[role="toggleOn"] {{
    background-color: {COLOR_ON_GREEN};
    color: white;
    font-weight: 700;
    border-radius: 6px;
    border: 1px solid #218a3c;
}}

QPushButton[role="toggleOff"] {{
    background-color: #d9d9d9;
    color: #444;
    font-weight: 700;
    border-radius: 6px;
    border: 1px solid #aaaaaa;
}}

QTableWidget {{
    background-color: white;
    gridline-color: #d8d2b8;
    border: 1px solid #c9c2a0;
}}

QHeaderView::section {{
    background-color: {COLOR_HEADER_BLUE};
    color: white;
    padding: 4px;
    border: none;
    font-weight: 600;
}}
"""

"""
RF Event Analyzer - Modern Style Definitions
"""

# Основная цветовая палитра
COLORS = {
    "primary": "#1a73e8",
    "primary_dark": "#1557b0",
    "primary_light": "#4285f4",
    "secondary": "#5f6368",
    "success": "#1e8e3e",
    "warning": "#f9ab00",
    "danger": "#d93025",
    "info": "#1a73e8",
    
    "bg_dark": "#1e1e2e",
    "bg_medium": "#2d2d3d",
    "bg_light": "#363647",
    "bg_card": "#3d3d4f",
    
    "text_primary": "#e4e4e7",
    "text_secondary": "#a1a1aa",
    "text_muted": "#71717a",
    
    "border": "#4d4d5f",
    "border_light": "#5d5d6f",
    
    "accent_blue": "#60a5fa",
    "accent_green": "#34d399",
    "accent_yellow": "#fbbf24",
    "accent_red": "#f87171",
    "accent_purple": "#a78bfa",
    "accent_cyan": "#22d3ee",
}

# Современный тёмный стиль для PySide6
DARK_STYLE = """
/* ========== GLOBAL ========== */
QWidget {
    background-color: #1e1e2e;
    color: #e4e4e7;
    font-family: "Segoe UI", "SF Pro Display", -apple-system, sans-serif;
    font-size: 13px;
}

QMainWindow {
    background-color: #1e1e2e;
}

/* ========== MENU BAR ========== */
QMenuBar {
    background-color: #2d2d3d;
    border-bottom: 1px solid #3d3d4f;
    padding: 4px 0;
}

QMenuBar::item {
    padding: 6px 12px;
    border-radius: 4px;
    margin: 2px 2px;
}

QMenuBar::item:selected {
    background-color: #3d3d4f;
}

QMenu {
    background-color: #2d2d3d;
    border: 1px solid #3d3d4f;
    border-radius: 8px;
    padding: 8px 4px;
}

QMenu::item {
    padding: 8px 32px 8px 16px;
    border-radius: 4px;
    margin: 2px 4px;
}

QMenu::item:selected {
    background-color: #1a73e8;
}

QMenu::separator {
    height: 1px;
    background-color: #3d3d4f;
    margin: 8px 12px;
}

/* ========== TAB WIDGET ========== */
QTabWidget::pane {
    border: 1px solid #3d3d4f;
    border-radius: 8px;
    background-color: #2d2d3d;
    top: -1px;
}

QTabBar::tab {
    background-color: #1e1e2e;
    color: #a1a1aa;
    padding: 12px 24px;
    margin-right: 2px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    border: 1px solid transparent;
    border-bottom: none;
    font-weight: 500;
}

QTabBar::tab:selected {
    background-color: #2d2d3d;
    color: #60a5fa;
    border: 1px solid #3d3d4f;
    border-bottom: 1px solid #2d2d3d;
}

QTabBar::tab:hover:!selected {
    background-color: #363647;
    color: #e4e4e7;
}

/* ========== GROUP BOX ========== */
QGroupBox {
    background-color: #2d2d3d;
    border: 1px solid #3d3d4f;
    border-radius: 12px;
    margin-top: 16px;
    padding: 20px 16px 16px 16px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 16px;
    top: 4px;
    background-color: #2d2d3d;
    padding: 4px 12px;
    border-radius: 4px;
    color: #60a5fa;
}

/* ========== BUTTONS ========== */
QPushButton {
    background-color: #3d3d4f;
    color: #e4e4e7;
    border: 1px solid #4d4d5f;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 500;
    min-width: 80px;
}

QPushButton:hover {
    background-color: #4d4d5f;
    border-color: #5d5d6f;
}

QPushButton:pressed {
    background-color: #363647;
}

QPushButton:disabled {
    background-color: #2d2d3d;
    color: #71717a;
    border-color: #3d3d4f;
}

/* Primary Button */
QPushButton[primary="true"], QPushButton#startBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
        stop:0 #1a73e8, stop:1 #4285f4);
    border: none;
    color: white;
}

QPushButton[primary="true"]:hover, QPushButton#startBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
        stop:0 #1557b0, stop:1 #1a73e8);
}

/* Danger Button */
QPushButton[danger="true"], QPushButton#stopBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
        stop:0 #d93025, stop:1 #ea4335);
    border: none;
    color: white;
}

QPushButton[danger="true"]:hover, QPushButton#stopBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
        stop:0 #b52a1f, stop:1 #d93025);
}

/* Success Button */
QPushButton[success="true"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
        stop:0 #1e8e3e, stop:1 #34a853);
    border: none;
    color: white;
}

/* ========== INPUT FIELDS ========== */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #1e1e2e;
    border: 2px solid #3d3d4f;
    border-radius: 8px;
    padding: 10px 12px;
    color: #e4e4e7;
    selection-background-color: #1a73e8;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #1a73e8;
    background-color: #252535;
}

QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {
    border-color: #4d4d5f;
}

QLineEdit::placeholder {
    color: #71717a;
}

/* ========== COMBO BOX ========== */
QComboBox {
    padding-right: 32px;
}

QComboBox::drop-down {
    border: none;
    width: 32px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #a1a1aa;
    margin-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #2d2d3d;
    border: 1px solid #3d3d4f;
    border-radius: 8px;
    selection-background-color: #1a73e8;
    padding: 4px;
}

QComboBox QAbstractItemView::item {
    padding: 8px 12px;
    border-radius: 4px;
    margin: 2px;
}

/* ========== SPIN BOX ========== */
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    background-color: #3d3d4f;
    border: none;
    border-radius: 4px;
    width: 20px;
    margin: 2px;
}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #4d4d5f;
}

QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid #a1a1aa;
}

QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #a1a1aa;
}

/* ========== TABLE ========== */
QTableWidget {
    background-color: #1e1e2e;
    alternate-background-color: #252535;
    border: 1px solid #3d3d4f;
    border-radius: 8px;
    gridline-color: #2d2d3d;
    selection-background-color: rgba(26, 115, 232, 0.3);
    selection-color: #e4e4e7;
}

QTableWidget::item {
    padding: 8px 12px;
    border-bottom: 1px solid #2d2d3d;
}

QTableWidget::item:selected {
    background-color: rgba(26, 115, 232, 0.3);
}

QTableWidget::item:hover {
    background-color: rgba(96, 165, 250, 0.1);
}

QHeaderView::section {
    background-color: #2d2d3d;
    color: #a1a1aa;
    padding: 12px 16px;
    border: none;
    border-bottom: 2px solid #3d3d4f;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 0.5px;
}

QHeaderView::section:first {
    border-top-left-radius: 8px;
}

QHeaderView::section:last {
    border-top-right-radius: 8px;
}

QTableCornerButton::section {
    background-color: #2d2d3d;
    border: none;
}

/* ========== SCROLL BARS ========== */
QScrollBar:vertical {
    background-color: #1e1e2e;
    width: 12px;
    border-radius: 6px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #4d4d5f;
    border-radius: 6px;
    min-height: 30px;
    margin: 2px;
}

QScrollBar::handle:vertical:hover {
    background-color: #5d5d6f;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
    height: 0;
}

QScrollBar:horizontal {
    background-color: #1e1e2e;
    height: 12px;
    border-radius: 6px;
}

QScrollBar::handle:horizontal {
    background-color: #4d4d5f;
    border-radius: 6px;
    min-width: 30px;
    margin: 2px;
}

/* ========== TEXT EDIT ========== */
QTextEdit {
    background-color: #1e1e2e;
    border: 1px solid #3d3d4f;
    border-radius: 8px;
    padding: 12px;
    color: #e4e4e7;
    selection-background-color: #1a73e8;
}

/* ========== CHECKBOX ========== */
QCheckBox {
    spacing: 10px;
    color: #e4e4e7;
}

QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border: 2px solid #4d4d5f;
    border-radius: 6px;
    background-color: #1e1e2e;
}

QCheckBox::indicator:checked {
    background-color: #1a73e8;
    border-color: #1a73e8;
    image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAxMiAxMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cGF0aCBkPSJNMTAgM0w0LjUgOC41TDIgNiIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz48L3N2Zz4=);
}

QCheckBox::indicator:hover {
    border-color: #60a5fa;
}

/* ========== PROGRESS BAR ========== */
QProgressBar {
    background-color: #1e1e2e;
    border: none;
    border-radius: 8px;
    height: 8px;
    text-align: center;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
        stop:0 #1a73e8, stop:1 #60a5fa);
    border-radius: 8px;
}

/* ========== STATUS BAR ========== */
QStatusBar {
    background-color: #2d2d3d;
    border-top: 1px solid #3d3d4f;
    padding: 4px 12px;
    color: #a1a1aa;
}

QStatusBar::item {
    border: none;
}

/* ========== DIALOG ========== */
QDialog {
    background-color: #1e1e2e;
}

QDialogButtonBox QPushButton {
    min-width: 100px;
}

/* ========== LABEL ========== */
QLabel {
    color: #e4e4e7;
}

QLabel[heading="true"] {
    font-size: 18px;
    font-weight: 600;
    color: #60a5fa;
}

QLabel[subheading="true"] {
    font-size: 14px;
    color: #a1a1aa;
}

/* ========== TOOL TIP ========== */
QToolTip {
    background-color: #2d2d3d;
    color: #e4e4e7;
    border: 1px solid #3d3d4f;
    border-radius: 6px;
    padding: 8px 12px;
}

/* ========== SPLITTER ========== */
QSplitter::handle {
    background-color: #3d3d4f;
}

QSplitter::handle:horizontal {
    width: 2px;
}

QSplitter::handle:vertical {
    height: 2px;
}

/* ========== MESSAGE BOX ========== */
QMessageBox {
    background-color: #1e1e2e;
}

QMessageBox QLabel {
    color: #e4e4e7;
}
"""

# Светлая тема
LIGHT_STYLE = """
/* ========== GLOBAL ========== */
QWidget {
    background-color: #f8fafc;
    color: #1e293b;
    font-family: "Segoe UI", "SF Pro Display", -apple-system, sans-serif;
    font-size: 13px;
}

QMainWindow {
    background-color: #f8fafc;
}

/* ========== MENU BAR ========== */
QMenuBar {
    background-color: #ffffff;
    border-bottom: 1px solid #e2e8f0;
    padding: 4px 0;
}

QMenuBar::item {
    padding: 6px 12px;
    border-radius: 4px;
    margin: 2px 2px;
}

QMenuBar::item:selected {
    background-color: #f1f5f9;
}

QMenu {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 8px 4px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

QMenu::item {
    padding: 8px 32px 8px 16px;
    border-radius: 4px;
    margin: 2px 4px;
}

QMenu::item:selected {
    background-color: #1a73e8;
    color: white;
}

/* ========== TAB WIDGET ========== */
QTabWidget::pane {
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    background-color: #ffffff;
    top: -1px;
}

QTabBar::tab {
    background-color: #f8fafc;
    color: #64748b;
    padding: 12px 24px;
    margin-right: 2px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    border: 1px solid transparent;
    border-bottom: none;
    font-weight: 500;
}

QTabBar::tab:selected {
    background-color: #ffffff;
    color: #1a73e8;
    border: 1px solid #e2e8f0;
    border-bottom: 1px solid #ffffff;
}

QTabBar::tab:hover:!selected {
    background-color: #f1f5f9;
    color: #1e293b;
}

/* ========== GROUP BOX ========== */
QGroupBox {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    margin-top: 16px;
    padding: 20px 16px 16px 16px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 16px;
    top: 4px;
    background-color: #ffffff;
    padding: 4px 12px;
    border-radius: 4px;
    color: #1a73e8;
}

/* ========== BUTTONS ========== */
QPushButton {
    background-color: #ffffff;
    color: #1e293b;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 500;
    min-width: 80px;
}

QPushButton:hover {
    background-color: #f1f5f9;
    border-color: #cbd5e1;
}

QPushButton:pressed {
    background-color: #e2e8f0;
}

QPushButton:disabled {
    background-color: #f8fafc;
    color: #94a3b8;
    border-color: #e2e8f0;
}

QPushButton[primary="true"], QPushButton#startBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
        stop:0 #1a73e8, stop:1 #4285f4);
    border: none;
    color: white;
}

QPushButton[danger="true"], QPushButton#stopBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
        stop:0 #d93025, stop:1 #ea4335);
    border: none;
    color: white;
}

/* ========== INPUT FIELDS ========== */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #ffffff;
    border: 2px solid #e2e8f0;
    border-radius: 8px;
    padding: 10px 12px;
    color: #1e293b;
    selection-background-color: #1a73e8;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #1a73e8;
}

/* ========== TABLE ========== */
QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    gridline-color: #f1f5f9;
    selection-background-color: rgba(26, 115, 232, 0.15);
    selection-color: #1e293b;
}

QTableWidget::item {
    padding: 8px 12px;
    border-bottom: 1px solid #f1f5f9;
}

QHeaderView::section {
    background-color: #f8fafc;
    color: #64748b;
    padding: 12px 16px;
    border: none;
    border-bottom: 2px solid #e2e8f0;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 11px;
}

/* ========== SCROLL BARS ========== */
QScrollBar:vertical {
    background-color: #f8fafc;
    width: 12px;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background-color: #cbd5e1;
    border-radius: 6px;
    min-height: 30px;
    margin: 2px;
}

QScrollBar::handle:vertical:hover {
    background-color: #94a3b8;
}

/* ========== STATUS BAR ========== */
QStatusBar {
    background-color: #ffffff;
    border-top: 1px solid #e2e8f0;
    color: #64748b;
}

/* ========== TEXT EDIT ========== */
QTextEdit {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 12px;
}

/* ========== CHECKBOX ========== */
QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border: 2px solid #cbd5e1;
    border-radius: 6px;
    background-color: #ffffff;
}

QCheckBox::indicator:checked {
    background-color: #1a73e8;
    border-color: #1a73e8;
}
"""


def get_style(dark_mode: bool = True) -> str:
    """Получить стиль в зависимости от темы"""
    return DARK_STYLE if dark_mode else LIGHT_STYLE

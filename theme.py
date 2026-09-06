"""
theme.py
---------
One global QSS stylesheet, applied once in main.py to the whole
QApplication. This gives every screen a consistent, professional dark
look - rounded buttons/cards, readable fonts, consistent spacing - without
needing to hand-style every individual widget in every file. Screens that
need a specific accent colour (success green, warning orange, error red,
info blue) still set that inline, matching the same palette used here.
"""

DARK_THEME_QSS = """
QWidget {
    background-color: #1e1e22;
    color: #e8e8ea;
    font-family: "Segoe UI", sans-serif;
    font-size: 10.5pt;
}

QMainWindow, QDialog {
    background-color: #1e1e22;
}

QFrame {
    background-color: #26262b;
    border-radius: 8px;
}

QLabel {
    background: transparent;
}

QPushButton {
    background-color: #33333a;
    color: #e8e8ea;
    border: 1px solid #46464e;
    border-radius: 6px;
    padding: 8px 14px;
}
QPushButton:hover {
    background-color: #3d3d46;
    border: 1px solid #3a7bd5;
}
QPushButton:pressed {
    background-color: #2a2a30;
}
QPushButton:disabled {
    color: #6b6b70;
    background-color: #2a2a2e;
}

QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {
    background-color: #2a2a30;
    color: #e8e8ea;
    border: 1px solid #46464e;
    border-radius: 6px;
    padding: 5px 8px;
    selection-background-color: #3a7bd5;
}
QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #3a7bd5;
}
QComboBox::drop-down {
    border: none;
}
QComboBox QAbstractItemView {
    background-color: #2a2a30;
    color: #e8e8ea;
    selection-background-color: #3a7bd5;
}

QTableWidget, QListWidget {
    background-color: #222226;
    alternate-background-color: #26262b;
    color: #e8e8ea;
    border: 1px solid #33333a;
    border-radius: 6px;
    gridline-color: #33333a;
}
QHeaderView::section {
    background-color: #2a2a30;
    color: #b8b8bc;
    padding: 6px;
    border: none;
    border-bottom: 1px solid #46464e;
}
QTableWidget::item:selected, QListWidget::item:selected {
    background-color: #3a7bd5;
    color: white;
}

QScrollBar:vertical {
    background: #1e1e22;
    width: 12px;
}
QScrollBar::handle:vertical {
    background: #46464e;
    border-radius: 5px;
    min-height: 24px;
}

QProgressBar {
    border: none;
}

QToolTip {
    background-color: #2a2a30;
    color: #e8e8ea;
    border: 1px solid #46464e;
}
"""

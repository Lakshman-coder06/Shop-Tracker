"""
main.py
--------
Entry point for Shop Work & Collection Tracker.

Run this file to start the application:
    python main.py
"""

import sys
from PySide6.QtWidgets import QApplication

import database
from ui.login_window import LoginWindow
from ui.dashboard_window import DashboardWindow


class App:
    def __init__(self):
        database.init_db()
        self.qt_app = QApplication(sys.argv)
        self.qt_app.setStyle("Fusion")  # looks consistent on both old and new Windows
        self.login_window = None
        self.dashboard = None
        self.show_login()

    def show_login(self):
        if self.dashboard is not None:
            self.dashboard.close()
        self.login_window = LoginWindow(on_login_success=self.show_dashboard)
        self.login_window.show()

    def show_dashboard(self, user):
        self.login_window.close()
        self.dashboard = DashboardWindow(user, on_logout=self.show_login)
        self.dashboard.show()

    def run(self):
        sys.exit(self.qt_app.exec())


if __name__ == "__main__":
    app = App()
    app.run()

"""
main.py
--------
Entry point for Shop Work & Collection Tracker.

Run this file to start the application:
    python main.py
"""

import sys
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget, QVBoxLayout, QLabel

import database
from theme import DARK_THEME_QSS
from ui.login_window import LoginWindow
from ui.dashboard_window import DashboardWindow
from ui.change_pin_window import ChangePinWindow


class App:
    def __init__(self):
        database.init_db()
        self.qt_app = QApplication(sys.argv)
        self.qt_app.setStyle("Fusion")  # a consistent base style across Windows versions
        self.qt_app.setStyleSheet(DARK_THEME_QSS)  # the professional dark theme, applied globally
        self.qt_app.aboutToQuit.connect(self._on_quit)
        self.login_window = None
        self.dashboard = None
        self.forced_pin_window = None
        self._pending_user = None
        self.show_login()

    def show_login(self):
        if self.dashboard is not None:
            self.dashboard.close()  # triggers its closeEvent -> ends session + stops monitor
            self.dashboard = None
        self.login_window = LoginWindow(on_login_success=self.show_dashboard)
        self.login_window.show()

    def show_dashboard(self, user):
        if user["must_change_pin"]:
            # A temporary/reset PIN was used - require a change before
            # anything else is reachable.
            self._pending_user = user
            self.login_window.close()
            self.forced_pin_window = ChangePinWindow(
                user, on_changed=self._after_forced_pin_change, forced=True,
            )
            self.forced_pin_window.show()
            return
        self._enter_dashboard(user)

    def _after_forced_pin_change(self):
        self.forced_pin_window.close()
        self.forced_pin_window = None
        self._enter_dashboard(self._pending_user)
        self._pending_user = None

    def _enter_dashboard(self, user):
        if self.login_window is not None:
            self.login_window.close()
        session_id = database.start_worker_session(user["id"])
        self.dashboard = DashboardWindow(user, session_id, on_logout=self.show_login)
        self.dashboard.show()

    def _on_quit(self):
        """Safety net: if the app closes in a way that skips the dashboard's
        own closeEvent (forced close, Alt+F4, etc.), still end the session
        and stop the activity monitor cleanly instead of leaving it open."""
        if self.dashboard is not None:
            self.dashboard._cleanup()

    def run(self):
        sys.exit(self.qt_app.exec())


if __name__ == "__main__":
    app = App()
    app.run()

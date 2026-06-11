"""Atlas Robot Touchscreen App — main window."""
import threading

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QGridLayout, QSizePolicy,
    QStackedWidget,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSlot, QMetaObject
from PyQt5.QtGui import QFont

from .api_client import RobotApiClient

# ── Palette ────────────────────────────────────────────────────────────────────
_BG      = '#1a1a2e'
_BG2     = '#16213e'
_ACCENT  = '#4e9af1'
_GREEN   = '#2ea84a'
_RED     = '#c04444'
_ORANGE  = '#e07c20'
_TEXT    = '#e0e0f0'
_SUBTEXT = '#8888aa'

_STYLE = f"""
QMainWindow, QWidget {{ background: {_BG}; color: {_TEXT}; font-size: 15px; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: {_BG2}; width: 10px; border-radius: 5px; }}
QScrollBar::handle:vertical {{ background: #444; border-radius: 5px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QPushButton {{
    background: #252540; color: {_TEXT}; border: 1px solid #3a3a5e;
    border-radius: 8px; padding: 12px 16px; font-size: 15px;
}}
QPushButton:hover   {{ background: {_ACCENT}; border-color: {_ACCENT}; color: #fff; }}
QPushButton:pressed {{ background: #2a5aaf; }}
"""


def _lbl(text, color=_SUBTEXT, size=12):
    l = QLabel(text)
    l.setStyleSheet(f'color:{color};font-size:{size}px;background:transparent;')
    l.setWordWrap(True)
    return l


def _divider():
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet(f'background:{_BG2};border:none;margin:4px 0;')
    f.setFixedHeight(1)
    return f


class _WaypointBtn(QPushButton):
    """Large touchscreen waypoint button."""
    def __init__(self, pos: dict, parent=None):
        name = pos.get('name', '?')
        ptype = pos.get('type', pos.get('func', 'waypoint')).lower()
        super().__init__(f'  {name}', parent)
        self._pos = pos
        self.setMinimumHeight(64)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        _type_colors = {
            'charge': _ORANGE, 'dock': '#6090d0', 'home': '#e06060',
            'pickup': _GREEN,  'dropoff': '#c07050',
        }
        color = _type_colors.get(ptype, _ACCENT)
        self.setStyleSheet(f"""
            QPushButton {{
                background: #1e2040; color: {_TEXT};
                border: 2px solid {color}; border-radius: 10px;
                padding: 12px 18px; font-size: 16px; font-weight: bold;
                text-align: left;
            }}
            QPushButton:hover   {{ background: {color}33; border-color: {color}; }}
            QPushButton:pressed {{ background: {color}66; }}
        """)
        # Type badge
        self.setToolTip(f'{ptype}  ({pos.get("x", 0):.2f}, {pos.get("y", 0):.2f})')


class RobotAppWindow(QMainWindow):
    def __init__(self, host: str = 'localhost:8080'):
        super().__init__()
        self.api = RobotApiClient(host)
        self._waypoints: list = []
        self._last_route_status: str = 'idle'

        self.setWindowTitle('Atlas Robot')
        self.resize(800, 480)
        self.setStyleSheet(_STYLE)

        self._build_ui()

        # Poll timers
        self._wp_timer = QTimer()
        self._wp_timer.timeout.connect(self._refresh_waypoints)
        self._wp_timer.start(5000)

        self._status_timer = QTimer()
        self._status_timer.timeout.connect(self._refresh_route_status)
        self._status_timer.start(800)

        # Initial load
        QTimer.singleShot(300, self._refresh_waypoints)

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        root_lay = QHBoxLayout(root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)
        self.setCentralWidget(root)

        # ── Left panel: waypoints ──────────────────────────────────────────
        left = QWidget()
        left.setFixedWidth(520)
        left.setStyleSheet(f'background:{_BG};border-right:2px solid #252540;')
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(12, 12, 12, 12)
        left_lay.setSpacing(6)

        hdr = QHBoxLayout()
        title = QLabel('Waypoints')
        title.setStyleSheet(
            f'color:{_TEXT};font-size:20px;font-weight:bold;background:transparent;')
        self._nav_cancel_btn = QPushButton('Cancel Nav')
        self._nav_cancel_btn.setFixedWidth(120)
        self._nav_cancel_btn.setStyleSheet(
            f'QPushButton{{background:{_RED};color:#fff;border:none;border-radius:6px;padding:8px;}}'
            f'QPushButton:hover{{background:#e05555;}}')
        self._nav_cancel_btn.clicked.connect(self._cancel_nav)
        hdr.addWidget(title, 1)
        hdr.addWidget(self._nav_cancel_btn)
        left_lay.addLayout(hdr)

        self._nav_state_lbl = _lbl('Nav: idle', _ACCENT, 13)
        left_lay.addWidget(self._nav_state_lbl)
        left_lay.addWidget(_divider())

        # Scrollable waypoint buttons
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self._wp_container = QWidget()
        self._wp_container.setStyleSheet('background:transparent;')
        self._wp_lay = QVBoxLayout(self._wp_container)
        self._wp_lay.setContentsMargins(0, 0, 0, 0)
        self._wp_lay.setSpacing(6)
        self._wp_lay.addStretch()
        scroll.setWidget(self._wp_container)
        left_lay.addWidget(scroll, 1)

        self._wp_status = _lbl('Loading…', _SUBTEXT, 12)
        left_lay.addWidget(self._wp_status)

        # ── Right panel: route status ──────────────────────────────────────
        right = QWidget()
        right.setStyleSheet(f'background:{_BG2};')
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(16, 16, 16, 16)
        right_lay.setSpacing(10)

        route_title = QLabel('Route Status')
        route_title.setStyleSheet(
            f'color:{_TEXT};font-size:18px;font-weight:bold;background:transparent;')
        right_lay.addWidget(route_title)
        right_lay.addWidget(_divider())

        self._route_status_lbl = QLabel('Idle')
        self._route_status_lbl.setStyleSheet(
            f'color:{_SUBTEXT};font-size:16px;font-weight:bold;background:transparent;')
        self._route_status_lbl.setWordWrap(True)
        self._route_status_lbl.setAlignment(Qt.AlignTop)
        right_lay.addWidget(self._route_status_lbl)

        self._route_progress_lbl = _lbl('', _SUBTEXT, 13)
        right_lay.addWidget(self._route_progress_lbl)

        self._route_wp_lbl = _lbl('', _TEXT, 15)
        right_lay.addWidget(self._route_wp_lbl)

        right_lay.addStretch()

        # Big CONFIRM button
        self._confirm_btn = QPushButton('CONFIRM\nTiếp tục →')
        self._confirm_btn.setMinimumHeight(100)
        self._confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_GREEN}; color: #fff;
                border: none; border-radius: 12px;
                font-size: 22px; font-weight: bold; padding: 16px;
            }}
            QPushButton:hover   {{ background: #3ac060; }}
            QPushButton:pressed {{ background: #1a8030; }}
        """)
        self._confirm_btn.setVisible(False)
        self._confirm_btn.clicked.connect(self._confirm_wp)
        right_lay.addWidget(self._confirm_btn)

        root_lay.addWidget(left)
        root_lay.addWidget(right, 1)

    # ── Waypoint list ──────────────────────────────────────────────────────────

    def _refresh_waypoints(self):
        def _fetch():
            wps = self.api.get_waypoints()
            self._waypoints = wps
            QMetaObject.invokeMethod(self, '_rebuild_wp_list', Qt.QueuedConnection)
        threading.Thread(target=_fetch, daemon=True).start()

    @pyqtSlot()
    def _rebuild_wp_list(self):
        # Clear existing buttons (keep stretch at end)
        while self._wp_lay.count() > 1:
            item = self._wp_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for pos in self._waypoints:
            btn = _WaypointBtn(pos)
            btn.clicked.connect(lambda _, p=pos: self._nav_to_wp(p))
            self._wp_lay.insertWidget(self._wp_lay.count() - 1, btn)

        n = len(self._waypoints)
        self._wp_status.setText(f'{n} waypoint{"s" if n != 1 else ""}')

    def _nav_to_wp(self, pos: dict):
        name = pos.get('name', '?')
        self._nav_state_lbl.setText(f'Navigating → {name}…')
        self._nav_state_lbl.setStyleSheet(
            f'color:{_ACCENT};font-size:13px;background:transparent;')
        self.api.post_async(
            '/atlas/nav/goal',
            {'x': pos['x'], 'y': pos['y'], 'yaw': pos.get('yaw', 0.0)})

    def _cancel_nav(self):
        self.api.post_async('/atlas/nav/cancel')
        self._nav_state_lbl.setText('Nav: cancelled')
        self._nav_state_lbl.setStyleSheet(
            f'color:{_RED};font-size:13px;background:transparent;')

    # ── Route status polling ───────────────────────────────────────────────────

    def _refresh_route_status(self):
        def _fetch():
            r = self.api.get_route_status()
            self._route_poll_result = r
            QMetaObject.invokeMethod(self, '_apply_route_status', Qt.QueuedConnection)
        threading.Thread(target=_fetch, daemon=True).start()

    @pyqtSlot()
    def _apply_route_status(self):
        r = getattr(self, '_route_poll_result', None)
        if not r:
            return

        status = r.get('status', 'idle')
        idx    = r.get('current_idx', -1)
        total  = r.get('total', 0)
        name   = r.get('current_name', '')
        rtype  = r.get('type', 'auto')

        _STATUS_COLOR = {
            'idle':            _SUBTEXT,
            'navigating':      _ACCENT,
            'waiting':         _ORANGE,
            'waiting_confirm': _GREEN,
            'charging':        _ORANGE,
            'done':            _GREEN,
            'stopped':         _RED,
            'failed':          _RED,
        }
        _STATUS_TEXT = {
            'idle':            'Idle',
            'navigating':      f'Navigating\n→ {name}',
            'waiting':         f'Đang dừng tại\n{name}',
            'waiting_confirm': f'Chờ xác nhận\ntại {name}',
            'charging':        'Route done\n→ Về sạc…',
            'done':            'Route hoàn thành ✓',
            'stopped':         'Đã dừng',
            'failed':          f'Lỗi: {r.get("error", "?")}',
        }

        color = _STATUS_COLOR.get(status, _SUBTEXT)
        text  = _STATUS_TEXT.get(status, status)
        self._route_status_lbl.setText(text)
        self._route_status_lbl.setStyleSheet(
            f'color:{color};font-size:16px;font-weight:bold;background:transparent;')

        if total > 0 and idx >= 0:
            pct = int((idx + 1) / total * 100)
            self._route_progress_lbl.setText(f'Bước {idx + 1} / {total}  ({pct}%)')
            self._route_wp_lbl.setText(name)
        else:
            self._route_progress_lbl.setText('')
            self._route_wp_lbl.setText('')

        # Show confirm button only when waiting for confirm
        waiting_confirm = (status == 'waiting_confirm')
        self._confirm_btn.setVisible(waiting_confirm)

        # Update nav state label from route state
        if status == 'navigating':
            self._nav_state_lbl.setText(f'Nav: → {name}')
            self._nav_state_lbl.setStyleSheet(
                f'color:{_ACCENT};font-size:13px;background:transparent;')
        elif status in ('done', 'idle', 'stopped'):
            self._nav_state_lbl.setText('Nav: idle')
            self._nav_state_lbl.setStyleSheet(
                f'color:{_SUBTEXT};font-size:13px;background:transparent;')

    def _confirm_wp(self):
        self._confirm_btn.setEnabled(False)
        self.api.post_async('/atlas/route/confirm',
                            callback=lambda r: self._confirm_btn.setEnabled(True))

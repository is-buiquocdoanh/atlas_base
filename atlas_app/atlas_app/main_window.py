import math
import threading

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QStatusBar, QSplitter, QFrame, QPushButton,
    QSizePolicy, QAction, QStackedWidget, QMessageBox,
)
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QFont

from .map_widget import MapWidget
from .api_client import AtlasApiClient
from .panels import (
    NaviModePanel, BuildModePanel, PositionPanel, NaviRoutePanel,
    VirtualWallPanel, SpecialAreaPanel, MapPanel, RobotStatusPanel,
    LogPanel, SettingsPanel,
)

_STYLE = """
QMainWindow, QWidget { background: #1e1e2e; color: #d0d0e0; font-size: 13px; }
QScrollArea { border: none; }
QScrollBar:vertical { background: #252535; width: 8px; border-radius: 4px; }
QScrollBar::handle:vertical { background: #444; border-radius: 4px; min-height: 20px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QGroupBox {
    border: 1px solid #3a3a52; border-radius: 5px; margin-top: 10px;
    padding-top: 8px; color: #d0d0e0;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; color: #7090d0; }
QPushButton {
    background: #2a2a3e; color: #d0d0e0; border: 1px solid #4a4a64;
    border-radius: 4px; padding: 5px 12px; min-height: 24px;
}
QPushButton:hover  { background: #4e9af1; color: #fff; border-color: #4e9af1; }
QPushButton:checked { background: #4e9af1; color: #fff; }
QPushButton:pressed { background: #3a7ad1; }
QDoubleSpinBox, QLineEdit, QTextEdit, QComboBox {
    background: #2a2a3e; color: #d0d0e0;
    border: 1px solid #4a4a64; border-radius: 3px; padding: 3px 5px;
}
QListWidget { background: #252535; border: 1px solid #3a3a52; border-radius: 3px; }
QListWidget::item { padding: 4px 8px; }
QListWidget::item:selected { background: #4e9af1; color: #fff; }
QListWidget::item:hover { background: #303048; }
QCheckBox { color: #d0d0e0; }
QCheckBox::indicator { width: 14px; height: 14px; border: 1px solid #4a4a64;
    border-radius: 3px; background: #2a2a3e; }
QCheckBox::indicator:checked { background: #4e9af1; }
QLabel { color: #d0d0e0; }
QStatusBar { background: #16161f; color: #888; font-size: 11px; }
QSplitter::handle { background: #2a2a42; }
QSplitter::handle:horizontal { width: 4px; }
QSplitter::handle:hover { background: #4e9af1; }
"""

_SIDEBAR_ITEMS = [
    # (key, icon, label)
    ('navi',     '△', 'Navi mode'),
    ('build',    '⬡', 'Build mode'),
    None,
    ('position', '◉', 'Position'),
    ('route',    '⤴', 'Navi route'),
    ('wall',     '╌', 'Virtual wall'),
    ('area',     '⬡', 'Special area'),
    ('map',      '▣', 'Map'),
    ('status',   '○', 'Robot status'),
    ('log',      '≡', 'Logs'),
    ('settings', '⚙', 'Settings'),
]

# sidebar list index → panel stack index
_IDX_TO_PANEL = {
    0: 0, 1: 1, 3: 2, 4: 3, 5: 4,
    6: 5, 7: 6, 8: 7, 9: 8, 10: 9,
}


class _SidebarBtn(QPushButton):
    def __init__(self, icon: str, label: str):
        super().__init__(f'  {icon}  {label}')
        self.setCheckable(True)
        self.setFlat(True)
        self.setFixedHeight(36)
        self.setStyleSheet("""
            QPushButton {
                background: transparent; color: #b0b0c8;
                border: none; border-radius: 5px;
                text-align: left; padding-left: 10px; font-size: 13px;
            }
            QPushButton:hover   { background: #2a2a42; color: #d0d0f0; }
            QPushButton:checked { background: #3a4a6e; color: #6eb4ff; font-weight: bold; }
        """)


class _SectionLabel(QLabel):
    def __init__(self, text):
        super().__init__(text)
        self.setFixedHeight(24)
        self.setStyleSheet(
            'color:#606080;font-size:10px;font-weight:bold;'
            'padding-left:14px;letter-spacing:1px;')


class _Divider(QFrame):
    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.HLine)
        self.setFixedHeight(1)
        self.setStyleSheet('background:#2a2a42;border:none;margin:4px 8px;')


class AtlasAppWindow(QMainWindow):
    def __init__(self, node):
        super().__init__()
        self.node = node
        self.setWindowTitle('Atlas A2 — Control App')
        self.resize(1380, 840)
        self.setStyleSheet(_STYLE)

        robot_host = node.config.settings.get('robot_host', 'localhost:8080')
        self.api = AtlasApiClient(host=robot_host)

        self._build_toolbar()
        self._build_central()
        self._build_statusbar()

        # load config overlays onto map
        self.map_widget.set_virtual_walls(node.config.walls)
        self.map_widget.set_special_areas(node.config.areas)

        # 10 Hz poll
        self._timer = QTimer()
        self._timer.timeout.connect(self._poll_ros)
        self._timer.start(100)

        # Launch status poll from robot API (2s interval to avoid HTTP spam)
        self._api_status: dict = {}
        self._status_timer = QTimer()
        self._status_timer.timeout.connect(self._poll_launch_status_async)
        self._status_timer.start(2000)

        # load data from robot API once after startup
        QTimer.singleShot(2000, self._load_from_api)

        self._select_sidebar(0)

    # ------------------------------------------------------------------ #
    # toolbar                                                              #
    # ------------------------------------------------------------------ #

    def _build_toolbar(self):
        from PyQt5.QtWidgets import QToolBar
        tb = QToolBar()
        tb.setMovable(False)
        self.addToolBar(tb)
        tb.setStyleSheet("""
            QToolBar { background:#14141f; border-bottom:2px solid #333355;
                       padding:2px 6px; spacing:4px; }
            QToolButton {
                background:#222234; color:#ccc; border:1px solid #444466;
                border-radius:4px; padding:4px 10px; font-size:12px; min-width:68px;
            }
            QToolButton:hover   { background:#3a6abf; color:#fff; border-color:#4e9af1; }
            QToolButton:checked { background:#4e9af1; color:#fff; border-color:#6eb8ff; }
            QToolButton:pressed { background:#2a5a9f; }
        """)

        def _grp_lbl(text):
            lbl = QLabel(text)
            lbl.setStyleSheet(
                'color:#44446a;font-size:9px;font-weight:bold;'
                'letter-spacing:1px;padding:0 3px;')
            return lbl

        self._mode_lbl = QLabel('Navigation Mode')
        self._mode_lbl.setStyleSheet(
            'color:#7090d0;font-weight:bold;font-size:13px;padding:0 8px;')
        tb.addWidget(self._mode_lbl)
        tb.addSeparator()

        # ── Group: CONTROL ────────────────────────────────────────────────
        tb.addWidget(_grp_lbl('CONTROL'))
        self._act_cancel  = QAction('Cancel Nav', self)
        self._act_stop    = QAction('STOP', self)
        self._act_stopall = QAction('Stop All Nodes', self)
        self._act_cancel.triggered.connect(self._cancel_nav)
        self._act_stop.triggered.connect(self._emergency_stop)
        self._act_stopall.triggered.connect(self._stop_all)
        tb.addAction(self._act_cancel)
        tb.addAction(self._act_stop)
        tb.addAction(self._act_stopall)
        tb.addSeparator()

        # ── Group: CHARGING ───────────────────────────────────────────────
        tb.addWidget(_grp_lbl('CHARGING'))
        self._act_navi_charge = QAction('Navi Charge', self)
        self._act_docking     = QAction('Docking',     self)
        self._act_charge      = QAction('Charge',      self)
        self._act_stop_dock   = QAction('Stop Dock',   self)
        tb.addAction(self._act_navi_charge)
        tb.addAction(self._act_docking)
        tb.addAction(self._act_charge)
        tb.addAction(self._act_stop_dock)
        self._act_navi_charge.triggered.connect(self._navi_charge)
        self._act_docking.triggered.connect(self._start_docking)
        self._act_charge.triggered.connect(self._full_charge)
        self._act_stop_dock.triggered.connect(self._stop_dock)
        tb.addSeparator()

        # ── Group: MAP TOOLS ──────────────────────────────────────────────
        tb.addWidget(_grp_lbl('MAP'))
        self._act_drag    = QAction('Drag',     self, checkable=True, checked=True)
        self._act_goal    = QAction('Nav Goal', self, checkable=True)
        self._act_pose    = QAction('Set Pose', self, checkable=True)
        self._act_measure = QAction('Measure',  self, checkable=True)
        self._act_fit     = QAction('Fit Map',  self)
        for a in (self._act_drag, self._act_goal, self._act_pose,
                  self._act_measure, self._act_fit):
            tb.addAction(a)
        self._act_drag.triggered.connect(lambda: self.request_map_mode('drag'))
        self._act_goal.triggered.connect(lambda: self.request_map_mode('nav_goal'))
        self._act_pose.triggered.connect(lambda: self.request_map_mode('set_pose'))
        self._act_measure.triggered.connect(
            lambda checked: self.request_map_mode('measure' if checked else 'drag'))
        # fit_map connected after map_widget is created

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)

        # ── Status indicators ──────────────────────────────────────────────
        self._laser_dot = QLabel('● Laser')
        self._imu_dot   = QLabel('● IMU')
        self._estop_dot = QLabel('● E-stop')
        for l in (self._laser_dot, self._imu_dot, self._estop_dot):
            l.setStyleSheet('color:#444;font-size:12px;padding:0 4px;')
            tb.addWidget(l)
        tb.addSeparator()

        self._speed_lbl = QLabel('Vx 0.00  Wz 0.00')
        self._speed_lbl.setStyleSheet('color:#888;font-size:12px;padding:0 4px;')
        tb.addWidget(self._speed_lbl)

        self._pose_lbl2 = QLabel('X 0.00  Y 0.00  0°')
        self._pose_lbl2.setStyleSheet('color:#888;font-size:12px;padding:0 8px;')
        tb.addWidget(self._pose_lbl2)

    # ------------------------------------------------------------------ #
    # central layout                                                       #
    # ------------------------------------------------------------------ #

    def _build_central(self):
        root = QHBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── sidebar ──
        sidebar = QWidget()
        sidebar.setFixedWidth(188)
        sidebar.setStyleSheet('background:#171724;')
        sb_lay = QVBoxLayout(sidebar)
        sb_lay.setContentsMargins(4, 8, 4, 8)
        sb_lay.setSpacing(0)
        sb_lay.addWidget(_SectionLabel('CHANGE MODE'))

        self._sb_btns: list = []  # [(sidebar_idx, btn)]

        for i, item in enumerate(_SIDEBAR_ITEMS):
            if item is None:
                sb_lay.addWidget(_Divider())
                continue
            key, icon, label = item
            btn = _SidebarBtn(icon, label)
            btn.clicked.connect(lambda _, idx=i: self._select_sidebar(idx))
            sb_lay.addWidget(btn)
            self._sb_btns.append((i, btn))

        sb_lay.addStretch()

        # ── map canvas (created FIRST so panels can reference it) ──
        self.map_widget = MapWidget()
        self.map_widget.goal_selected.connect(self._on_goal_selected)
        self.map_widget.pose_selected.connect(self._on_pose_selected)
        self.map_widget.wall_drawn.connect(self._on_wall_drawn)
        self.map_widget.area_drawn.connect(self._on_area_drawn)
        self._act_fit.triggered.connect(self.map_widget.fit_map)

        # ── panel stack (QStackedWidget) ──
        self._panel_stack = QStackedWidget()
        self._panel_stack.setMinimumWidth(200)

        self._panel_navi     = NaviModePanel(self)
        self._panel_build    = BuildModePanel(self)
        self._panel_pos      = PositionPanel(self)
        self._panel_route    = NaviRoutePanel(self)
        self._panel_wall     = VirtualWallPanel(self)
        self._panel_area     = SpecialAreaPanel(self)
        self._panel_map      = MapPanel(self)
        self._panel_status   = RobotStatusPanel(self)
        self._panel_log      = LogPanel(self)
        self._panel_settings = SettingsPanel(self)

        self._all_panels = [
            self._panel_navi, self._panel_build, self._panel_pos,
            self._panel_route, self._panel_wall, self._panel_area,
            self._panel_map, self._panel_status, self._panel_log,
            self._panel_settings,
        ]
        for p in self._all_panels:
            self._panel_stack.addWidget(p)

        self._current_panel = self._panel_navi

        # ── splitter: panel | map ──
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._panel_stack)
        splitter.addWidget(self.map_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 1080])
        splitter.setChildrenCollapsible(True)

        root.addWidget(sidebar)
        root.addWidget(splitter, 1)

        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)

    def _build_statusbar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)
        self._sb_bat  = QLabel('Battery: —')
        self._sb_api  = QLabel('API: —')
        self._sb_nav  = QLabel('Nav: idle')
        self._sb_pose = QLabel('Pose: —')
        for w in (self._sb_bat, self._sb_api, self._sb_nav, self._sb_pose):
            sb.addPermanentWidget(w)

    # ------------------------------------------------------------------ #
    # sidebar selection                                                    #
    # ------------------------------------------------------------------ #

    def _select_sidebar(self, sidebar_idx: int):
        # Clear route overlay when leaving NaviRoutePanel
        if isinstance(self._current_panel, NaviRoutePanel):
            self.map_widget.set_route_waypoints([])

        for idx, btn in self._sb_btns:
            btn.setChecked(idx == sidebar_idx)

        panel_idx = _IDX_TO_PANEL.get(sidebar_idx, 0)
        panel = self._all_panels[panel_idx]
        self._current_panel = panel
        self._panel_stack.setCurrentWidget(panel)

        # Sync available positions and restore route overlay on enter
        if isinstance(panel, NaviRoutePanel):
            panel._reload_avail()
            panel._update_route_on_map()

        item = _SIDEBAR_ITEMS[sidebar_idx] if sidebar_idx < len(_SIDEBAR_ITEMS) else None
        key = item[0] if item else None

        if key == 'navi':
            self._mode_lbl.setText('Navigation Mode')
        elif key == 'build':
            self._mode_lbl.setText('Build Mode')

    # ------------------------------------------------------------------ #
    # map mode management                                                  #
    # ------------------------------------------------------------------ #

    def request_map_mode(self, mode: str):
        self.map_widget.set_mode(mode)
        for act, m in ((self._act_drag,    'drag'),
                       (self._act_goal,    'nav_goal'),
                       (self._act_pose,    'set_pose'),
                       (self._act_measure, 'measure')):
            act.setChecked(m == mode)

    # ------------------------------------------------------------------ #
    # map signals                                                          #
    # ------------------------------------------------------------------ #

    def _on_goal_selected(self, x: float, y: float, yaw: float):
        self.map_widget.set_goal_marker(x, y)
        if isinstance(self._current_panel, NaviModePanel):
            self._current_panel.set_goal_from_map(x, y, yaw)
        else:
            self._send_goal_api(x, y, yaw)
        self.request_map_mode('drag')

    def _on_pose_selected(self, x: float, y: float, yaw: float):
        # If toolbar Set Pose is active, publish immediately and stay in set_pose mode
        if self._act_pose.isChecked():
            self._relocate_api(x, y, yaw)
            return  # keep set_pose mode active for continuous use

        if isinstance(self._current_panel, NaviModePanel):
            self._current_panel.set_pose_from_map(x, y, yaw)
            self.request_map_mode('drag')
        elif isinstance(self._current_panel, PositionPanel):
            self._current_panel.on_pose_selected(x, y, yaw)
        else:
            self._relocate_api(x, y, yaw)
            self.request_map_mode('drag')

    def _on_wall_drawn(self, points: list):
        self.node.config.walls.append(points)
        self.node.config.save_walls()
        self.map_widget.set_virtual_walls(self.node.config.walls)
        self.api.post_async('/atlas/virtual_wall',
                            {'walls': self.node.config.walls})
        if isinstance(self._current_panel, VirtualWallPanel):
            self._current_panel.on_wall_drawn()
        self.request_map_mode('drag')

    def _on_area_drawn(self, points: list):
        if isinstance(self._current_panel, SpecialAreaPanel):
            self._current_panel.on_area_drawn(points)
        self.request_map_mode('drag')

    # ------------------------------------------------------------------ #
    # commands (prefer API, fallback to direct ROS)                       #
    # ------------------------------------------------------------------ #

    def _send_goal_api(self, x: float, y: float, yaw: float):
        def _cb(r):
            if not r:
                self.node.send_nav_goal(x, y, yaw)
        self.api.post_async('/atlas/nav/goal',
                            {'x': x, 'y': y, 'yaw': yaw}, _cb)

    def _relocate_api(self, x: float, y: float, yaw: float):
        def _cb(r):
            if not r:
                self.node.publish_initial_pose(x, y, yaw)
        self.api.post_async('/atlas/nav/relocate',
                            {'x': x, 'y': y, 'yaw': yaw}, _cb)

    def _cancel_nav(self):
        self.node.cancel_nav()
        self.api.post_async('/atlas/nav/cancel')
        self.api.post_async('/atlas/nav/dock_stop')
        self.map_widget.clear_goal_marker()

    def _emergency_stop(self):
        self.node.emergency_stop()
        self.api.post_async('/atlas/nav/cancel')
        self.api.post_async('/atlas/nav/dock_stop')
        self.map_widget.clear_goal_marker()

    def _navi_charge(self):
        from .node import _log
        def _cb(r):
            if r and r.get('status') == 'success':
                _log('Navigating to charging station approach...')
            else:
                msg = r.get('message', 'no response') if r else 'no response'
                _log(f'Navi charge error: {msg}')
        self.api.post_async('/atlas/nav/charge_approach', {}, _cb)

    def _start_docking(self):
        from .node import _log
        def _cb(r):
            if r and r.get('status') == 'success':
                _log(f'Docking started [{r.get("method", "?")}]')
            else:
                msg = r.get('message', 'no response') if r else 'no response'
                _log(f'Docking error: {msg}')
        self.api.post_async('/atlas/nav/dock', {}, _cb)

    def _full_charge(self):
        from .node import _log
        def _cb(r):
            if r and r.get('status') == 'success':
                _log(f'Charge sequence started [approach → {r.get("dock_method", "?")}]')
            else:
                msg = r.get('message', 'no response') if r else 'no response'
                _log(f'Charge error: {msg}')
        self.api.post_async('/atlas/nav/charge', {}, _cb)

    def _stop_dock(self):
        self.api.post_async('/atlas/nav/dock_stop')
        self.api.post_async('/atlas/nav/cancel')
        self.map_widget.clear_goal_marker()

    def _stop_all(self):
        from .node import _log
        _log('Stop All requested')
        self.node.stop_all_local()
        self.map_widget.clear_goal_marker()
        self.api.post_async('/atlas/mode', {'mode': 0})

    # ------------------------------------------------------------------ #
    # load initial data from robot API                                     #
    # ------------------------------------------------------------------ #

    def _load_from_api(self):
        from .node import _log
        import threading

        def _fetch():
            # waypoints
            wps = self.api.get_waypoints()
            if wps:
                self.node.config.positions = wps
                self.node.config.save_positions()
                from PyQt5.QtCore import QMetaObject, Qt
                QMetaObject.invokeMethod(
                    self, '_apply_waypoints_from_api', Qt.QueuedConnection)

            # virtual walls
            walls = self.api.get_walls()
            if walls:
                self.node.config.walls = walls
                self.node.config.save_walls()
                QMetaObject.invokeMethod(
                    self, '_apply_walls_from_api', Qt.QueuedConnection)

            # special areas
            areas = self.api.get_areas()
            if areas:
                self.node.config.areas = areas
                self.node.config.save_areas()
                QMetaObject.invokeMethod(
                    self, '_apply_areas_from_api', Qt.QueuedConnection)

            _log('API sync complete')

        threading.Thread(target=_fetch, daemon=True).start()

    from PyQt5.QtCore import pyqtSlot

    @pyqtSlot()
    def _apply_waypoints_from_api(self):
        self.map_widget.set_waypoints(self.node.config.positions)
        if isinstance(self._current_panel, PositionPanel):
            self._current_panel._reload()
        if isinstance(self._current_panel, NaviRoutePanel):
            self._current_panel._reload_avail()

    @pyqtSlot()
    def _apply_walls_from_api(self):
        self.map_widget.set_virtual_walls(self.node.config.walls)
        if isinstance(self._current_panel, VirtualWallPanel):
            self._current_panel._reload()

    @pyqtSlot()
    def _apply_areas_from_api(self):
        self.map_widget.set_special_areas(self.node.config.areas)
        if isinstance(self._current_panel, SpecialAreaPanel):
            self._current_panel._reload()

    # ------------------------------------------------------------------ #
    # Close event — stop all nodes before exiting                         #
    # ------------------------------------------------------------------ #

    def closeEvent(self, event):
        self._timer.stop()
        self._status_timer.stop()
        self.node.stop_all_local()
        self.api.post_async('/atlas/mode', {'mode': 0})
        event.accept()

    # ------------------------------------------------------------------ #
    # Launch status poll (2 Hz via API, non-blocking)                    #
    # ------------------------------------------------------------------ #

    def _poll_launch_status_async(self):
        def _cb(r):
            if r:
                self._api_status = r
                self.node.set_api_launch_status(r)
        threading.Thread(
            target=lambda: _cb(self.api.get('/atlas/launch/status', timeout=2)),
            daemon=True).start()

    # ------------------------------------------------------------------ #
    # ROS poll (10 Hz, Qt main thread)                                    #
    # ------------------------------------------------------------------ #

    def _poll_ros(self):
        self.node.update_robot_pose_from_tf()

        self.map_widget.update_map(self.node.get_map())
        self.map_widget.update_scan(self.node.get_scan_points())
        pose = self.node.get_robot_pose()
        self.map_widget.update_robot_pose(pose)
        self.map_widget.update_plan(self.node.get_plan_poses())

        bat   = self.node.get_battery_pct()
        nav   = self.node.get_nav_state()
        estop = self.node.get_emergency_stop()
        vx, wz = self.node.get_speed()
        laser = self.node.get_laser_ok()
        imu   = self.node.get_imu_ok()
        x, y, yaw = pose

        # toolbar dots
        def _dot(ok, label):
            c = '#60c060' if ok else '#444'
            return f'<span style="color:{c}">●</span> {label}'
        self._laser_dot.setText('● Laser')
        self._laser_dot.setStyleSheet(
            f'color:{"#60c060" if laser else "#444"};font-size:12px;padding:0 4px;')
        self._imu_dot.setText('● IMU')
        self._imu_dot.setStyleSheet(
            f'color:{"#60c060" if imu else "#444"};font-size:12px;padding:0 4px;')
        self._estop_dot.setText('● E-stop')
        self._estop_dot.setStyleSheet(
            f'color:{"#e05555" if estop else "#444"};font-size:12px;padding:0 4px;')

        self._speed_lbl.setText(f'Vx {vx:.2f}  Wz {wz:.2f}')
        self._pose_lbl2.setText(f'X {x:.2f}  Y {y:.2f}  {math.degrees(yaw):.0f}°')

        # status bar
        self._sb_bat.setText(f'Battery: {bat:.0f}%' if bat >= 0 else 'Battery: —')
        self._sb_nav.setText(f'Nav: {nav}')
        self._sb_pose.setText(f'X:{x:.2f} Y:{y:.2f} θ:{math.degrees(yaw):.0f}°')

        # launch status overlay on map (merged local + API — node.get_launch_status() does the merge)
        self.map_widget.update_launch_status(self.node.get_launch_status())

        # active panel refresh
        if hasattr(self._current_panel, 'refresh'):
            self._current_panel.refresh(self.node)

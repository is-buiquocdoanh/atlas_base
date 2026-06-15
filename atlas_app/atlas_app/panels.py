"""All sidebar panel classes for atlas_app."""
import os
import math
import threading

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFormLayout, QGroupBox,
    QDoubleSpinBox, QLineEdit, QTextEdit, QComboBox,
    QCheckBox, QScrollArea, QDialog, QDialogButtonBox,
    QFileDialog, QFrame, QAbstractItemView, QSizePolicy,
    QButtonGroup, QRadioButton, QSpinBox,
)
from PyQt5.QtCore import Qt, QSize, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QPixmap, QFont

from .node import app_log, _log


# ── SVG icon helper ───────────────────────────────────────────────────── #

_SVG = {
    'pin':    '<svg viewBox="0 0 24 24" fill="none" stroke="C" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/><circle cx="12" cy="9" r="2.5" fill="C" stroke="none"/></svg>',
    'check':  '<svg viewBox="0 0 24 24" fill="none" stroke="C" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20,6 9,17 4,12"/></svg>',
    'xmark':  '<svg viewBox="0 0 24 24" fill="none" stroke="C" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
    'plus':   '<svg viewBox="0 0 24 24" fill="none" stroke="C" stroke-width="2.5" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>',
    'play':   '<svg viewBox="0 0 24 24" fill="C"><polygon points="5,3 19,12 5,21"/></svg>',
    'trash':  '<svg viewBox="0 0 24 24" fill="none" stroke="C" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3,6 5,6 21,6"/><path d="M19,6v14a2,2 0,0,1-2,2H7a2,2,0,0,1-2-2V6m3,0V4a2,2,0,0,1,2-2h4a2,2,0,0,1,2,2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>',
    'navigate':'<svg viewBox="0 0 24 24" fill="C"><polygon points="3,11 22,2 13,21 11,13"/></svg>',
    'cursor': '<svg viewBox="0 0 24 24" fill="none" stroke="C" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 3l14 9-7 1-4 7z"/></svg>',
}


def _svg_icon(key: str, size: int = 16, color: str = '#ffffff'):
    from PyQt5.QtGui import QPixmap, QPainter as _QP, QIcon
    svg = _SVG[key].replace('C', color)
    try:
        from PyQt5.QtSvg import QSvgRenderer
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        r = QSvgRenderer(svg.encode())
        painter = _QP(pix)
        r.render(painter)
        painter.end()
        return QIcon(pix)
    except Exception:
        return None


def _icon_btn(text: str, icon_key: str, icon_color: str = '#ffffff',
              icon_size: int = 14, style: str = '') -> 'QPushButton':
    btn = QPushButton(text)
    ic  = _svg_icon(icon_key, icon_size, icon_color)
    if ic:
        btn.setIcon(ic)
        btn.setText(f'  {text}')
    if style:
        btn.setStyleSheet(style)
    return btn


# ── small helpers ─────────────────────────────────────────────────────── #

def _grp(title):
    g = QGroupBox(title)
    g.setLayout(QVBoxLayout())
    g.layout().setContentsMargins(8, 12, 8, 8)
    g.layout().setSpacing(4)
    return g


def _lbl(text, color='#aaa'):
    l = QLabel(text)
    l.setStyleSheet(f'color:{color};font-size:11px;')
    l.setWordWrap(True)
    return l


def _btn(text, color=''):
    b = QPushButton(text)
    if color:
        b.setStyleSheet(
            f'background:{color};color:#fff;font-weight:bold;'
            'border:none;border-radius:4px;padding:5px 10px;')
    return b


def _scroll_wrap(inner: QWidget) -> QScrollArea:
    s = QScrollArea()
    s.setWidgetResizable(True)
    s.setFrameShape(QFrame.NoFrame)
    s.setWidget(inner)
    return s


# ── dialog helpers ────────────────────────────────────────────────────── #

class _PositionDialog(QDialog):
    FUNC_TYPES = ['Waypoint', 'Home', 'Dock', 'Charge', 'Pickup', 'Dropoff', 'Custom']

    def __init__(self, x=0.0, y=0.0, yaw=0.0, name='', func='Waypoint', parent=None):
        super().__init__(parent)
        self.setWindowTitle('Save Position')
        self.setMinimumWidth(260)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self._name = QLineEdit(name)
        self._func = QComboBox()
        self._func.addItems(self.FUNC_TYPES)
        self._func.setCurrentIndex(self.FUNC_TYPES.index(func) if func in self.FUNC_TYPES else 0)
        self._x   = QDoubleSpinBox(); self._x.setRange(-999, 999);   self._x.setDecimals(3);  self._x.setValue(x)
        self._y   = QDoubleSpinBox(); self._y.setRange(-999, 999);   self._y.setDecimals(3);  self._y.setValue(y)
        self._yaw = QDoubleSpinBox(); self._yaw.setRange(-180, 180); self._yaw.setDecimals(1); self._yaw.setValue(math.degrees(yaw))
        form.addRow('Name:', self._name)
        form.addRow('Function:', self._func)
        form.addRow('X (m):', self._x)
        form.addRow('Y (m):', self._y)
        form.addRow('Yaw (°):', self._yaw)
        lay.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def result_data(self):
        return {
            'name': self._name.text().strip() or 'Position',
            'func': self._func.currentText(),
            'type': self._func.currentText().lower(),
            'x': self._x.value(), 'y': self._y.value(),
            'yaw': math.radians(self._yaw.value()),
        }


class _AreaDialog(QDialog):
    TYPES  = ['forbidden', 'slow', 'fast', 'custom']
    LABELS = ['Forbidden zone', 'Slow zone', 'Fast zone', 'Custom zone']

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Define Special Area')
        self.setMinimumWidth(240)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self._name  = QLineEdit('Area')
        self._type  = QComboBox(); self._type.addItems(self.LABELS)
        self._speed = QDoubleSpinBox()
        self._speed.setRange(0.0, 2.0); self._speed.setSingleStep(0.05)
        self._speed.setValue(0.2); self._speed.setSuffix(' m/s')
        form.addRow('Name:', self._name)
        form.addRow('Type:', self._type)
        form.addRow('Speed limit:', self._speed)
        lay.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def result_data(self):
        return {
            'name':  self._name.text().strip() or 'Area',
            'type':  self.TYPES[self._type.currentIndex()],
            'speed': self._speed.value(),
        }


# ══════════════════════════════════════════════════════════════════════════ #
# 1. Navi Mode Panel                                                         #
# ══════════════════════════════════════════════════════════════════════════ #

class NaviModePanel(QWidget):
    def __init__(self, win):
        super().__init__()
        self._win = win
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(8, 8, 8, 8); lay.setSpacing(8)

        # active map
        self._map_lbl = _lbl('—')
        ml = _grp('Active Map')
        ml.layout().addWidget(self._map_lbl)
        hm = QHBoxLayout()
        self._restart_btn = QPushButton('↺ Restart Nav')
        self._stop_nav_btn = QPushButton('⬛ Stop Nav')
        self._stop_nav_btn.setStyleSheet(
            'QPushButton{background:#c04444;color:#fff;font-weight:bold;'
            'border:none;border-radius:4px;padding:5px 10px;}'
            'QPushButton:hover{background:#e05555;border:1px solid #ff7777;}'
            'QPushButton:pressed{background:#a03030;}')
        hm.addWidget(self._restart_btn); hm.addWidget(self._stop_nav_btn)
        ml.layout().addLayout(hm)
        lay.addWidget(ml)
        self._restart_btn.clicked.connect(self._restart_nav)
        self._stop_nav_btn.clicked.connect(self._cancel)

        # robot status
        sg = _grp('Robot Status')
        fl = QFormLayout(); fl.setSpacing(4)
        self._state_lbl = QLabel('IDLE'); self._pos_lbl = QLabel('—')
        self._head_lbl  = QLabel('—');   self._speed_lbl = QLabel('—')
        self._bat_lbl   = QLabel('—');   self._estop_lbl = QLabel('OFF')
        for k, v in [('State', self._state_lbl), ('Position', self._pos_lbl),
                     ('Heading', self._head_lbl), ('Speed', self._speed_lbl),
                     ('Battery', self._bat_lbl), ('E-Stop', self._estop_lbl)]:
            kl = QLabel(k); kl.setStyleSheet('color:#888;')
            v.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            fl.addRow(kl, v)
        sg.layout().addLayout(fl)
        lay.addWidget(sg)

        # send goal
        gg = _grp('Send Goal')
        gg.layout().addWidget(_lbl('Click map and drag to set direction.'))
        gfl = QFormLayout(); gfl.setSpacing(4)
        self._gx  = QDoubleSpinBox(); self._gx.setRange(-999, 999);   self._gx.setDecimals(3)
        self._gy  = QDoubleSpinBox(); self._gy.setRange(-999, 999);   self._gy.setDecimals(3)
        self._gth = QDoubleSpinBox(); self._gth.setRange(-180, 180);  self._gth.setDecimals(1); self._gth.setSuffix('°')
        gfl.addRow('X (m):', self._gx); gfl.addRow('Y (m):', self._gy); gfl.addRow('θ:', self._gth)
        gg.layout().addLayout(gfl)
        hg = QHBoxLayout()
        self._nav_btn    = _btn('▷ Navigate', '#4e9af1')
        self._cancel_btn = QPushButton('✕ Cancel')
        hg.addWidget(self._nav_btn); hg.addWidget(self._cancel_btn)
        gg.layout().addLayout(hg)
        self._click_map_btn = QPushButton('⊕ Click Map')
        self._click_map_btn.setCheckable(True)
        self._click_map_btn.toggled.connect(
            lambda on: win.request_map_mode('nav_goal' if on else 'drag'))
        gg.layout().addWidget(self._click_map_btn)
        lay.addWidget(gg)
        self._nav_btn.clicked.connect(self._send_goal)
        self._cancel_btn.clicked.connect(self._cancel)

        # relocate
        rg = _grp('Relocate (2D Pose Estimate)')
        rg.layout().addWidget(_lbl('Click map and drag to set initial pose.'))
        rfl = QFormLayout(); rfl.setSpacing(4)
        self._rx  = QDoubleSpinBox(); self._rx.setRange(-999, 999);   self._rx.setDecimals(3)
        self._ry  = QDoubleSpinBox(); self._ry.setRange(-999, 999);   self._ry.setDecimals(3)
        self._rth = QDoubleSpinBox(); self._rth.setRange(-180, 180);  self._rth.setDecimals(1); self._rth.setSuffix('°')
        rfl.addRow('X (m):', self._rx); rfl.addRow('Y (m):', self._ry); rfl.addRow('θ:', self._rth)
        rg.layout().addLayout(rfl)
        hr = QHBoxLayout()
        self._pose_btn       = _btn('✓ Set Pose', '#555')
        self._click_pose_btn = QPushButton('⊕ Click Map')
        self._click_pose_btn.setCheckable(True)
        self._click_pose_btn.toggled.connect(
            lambda on: win.request_map_mode('set_pose' if on else 'drag'))
        hr.addWidget(self._pose_btn); hr.addWidget(self._click_pose_btn)
        rg.layout().addLayout(hr)
        lay.addWidget(rg)
        self._pose_btn.clicked.connect(self._set_pose)

        lay.addStretch()
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(_scroll_wrap(inner))

    def set_goal_from_map(self, x, y, yaw):
        self._gx.setValue(x); self._gy.setValue(y)
        self._gth.setValue(math.degrees(yaw))
        self._click_map_btn.setChecked(False)

    def set_pose_from_map(self, x, y, yaw):
        self._rx.setValue(x); self._ry.setValue(y)
        self._rth.setValue(math.degrees(yaw))
        self._click_pose_btn.setChecked(False)

    def _send_goal(self):
        x, y, yaw = self._gx.value(), self._gy.value(), math.radians(self._gth.value())
        self._win.map_widget.set_goal_marker(x, y)
        api = self._win.api

        def _cb(r):
            if not r:
                self._win.node.send_nav_goal(x, y, yaw)
        api.post_async('/atlas/nav/goal', {'x': x, 'y': y, 'yaw': yaw}, _cb)

    def _cancel(self):
        def _cb(r):
            if not r:
                self._win.node.cancel_nav()
        self._win.api.post_async('/atlas/nav/cancel', callback=_cb)

    def _set_pose(self):
        x, y, yaw = self._rx.value(), self._ry.value(), math.radians(self._rth.value())

        def _cb(r):
            if not r:
                self._win.node.publish_initial_pose(x, y, yaw)
        self._win.api.post_async('/atlas/nav/relocate', {'x': x, 'y': y, 'yaw': yaw}, _cb)

    def _restart_nav(self):
        self._win.api.post_async('/atlas/mode', {'mode': 2})

    def refresh(self, node):
        pose = node.get_robot_pose()
        nav  = node.get_nav_state()
        bat  = node.get_battery_pct()
        vx, wz = node.get_speed()
        estop   = node.get_emergency_stop()
        x, y, yaw = pose
        self._pos_lbl.setText(f'({x:.2f}, {y:.2f})')
        self._head_lbl.setText(f'{math.degrees(yaw):.1f}°')
        self._speed_lbl.setText(f'{vx:.2f} m/s')
        self._bat_lbl.setText(f'{bat:.0f}%' if bat >= 0 else '—')
        self._state_lbl.setText(nav.upper())
        if estop:
            self._estop_lbl.setText('ON')
            self._estop_lbl.setStyleSheet('color:#e05555;font-weight:bold;')
        else:
            self._estop_lbl.setText('OFF')
            self._estop_lbl.setStyleSheet('color:#60c060;')


# ══════════════════════════════════════════════════════════════════════════ #
# 2. Build Mode Panel                                                        #
# ══════════════════════════════════════════════════════════════════════════ #

class BuildModePanel(QWidget):
    def __init__(self, win):
        super().__init__()
        self._win = win
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8); lay.setSpacing(8)

        # mode control
        mg = _grp('Mapping Mode')
        self._status_lbl = _lbl('Mode: unknown', '#aaa')
        mg.layout().addWidget(self._status_lbl)

        b1 = _btn('▶ Start Mapping',     '#3a8a3a')
        b2 = _btn('▶ Start Nav',         '#3a5a8a')
        b3 = _btn('⊕ Extend Map',        '#3a6a6a')
        b4 = _btn('■ Stop All',          '#8a3a3a')
        for b in (b1, b2, b3, b4):
            mg.layout().addWidget(b)
        lay.addWidget(mg)

        b1.clicked.connect(lambda: self._set_mode(1))
        b2.clicked.connect(lambda: self._set_mode(2))
        b3.clicked.connect(self._extend_map)
        b4.clicked.connect(lambda: self._set_mode(0))

        # save map
        sg = _grp('Save Map')
        sfl = QFormLayout(); sfl.setSpacing(4)
        self._map_name = QLineEdit('map1')
        sfl.addRow('Name:', self._map_name)
        sg.layout().addLayout(sfl)
        save_btn = _btn('💾 Save Map', '#4e6ea0')
        save_btn.clicked.connect(self._save_map)
        sg.layout().addWidget(save_btn)
        self._save_status = _lbl('')
        sg.layout().addWidget(self._save_status)
        lay.addWidget(sg)

        lay.addStretch()

    def _set_mode(self, mode: int):
        labels = {0: 'Stopping…', 1: 'Starting Mapping…', 2: 'Starting Nav…', 3: 'Extending Map…'}
        self._status_lbl.setText(labels.get(mode, '…'))
        self._status_lbl.setStyleSheet('color:#aaa;font-size:11px;')

        def _cb(r):
            try:
                import time as _t
                ok = bool(r and r.get('status') == 'success')
                _log(f'Mode {mode}: API {"OK" if ok else f"unavailable (r={r!r}), using local"}')
                if ok:
                    # Mark pending so refresh() holds off showing Idle for a few seconds
                    self._mode_pending_until = _t.time() + 6.0
                    self._mode_pending_val   = mode
                else:
                    self._mode_pending_until = 0
                    node = self._win.node
                    if mode == 0:
                        node.stop_all_local()
                    elif mode == 1:
                        node.stop_all_local()
                        node.start_slam()
                    elif mode == 2:
                        node.stop_all_local()
                        node.start_nav()
                    elif mode == 3:
                        node.stop_all_local()
                        node.start_slam()
            except Exception as e:
                _log(f'[ERROR] _set_mode({mode}): {e}')

        self._win.api.post_async('/atlas/mode', {'mode': mode}, _cb)

    def _extend_map(self):
        # mode 3 = incremental mapping using current map's posegraph
        self._win.api.post_async('/atlas/mode', {'mode': 3},
                                  lambda r: _log(f'Extend map: {"OK" if r else "FAILED"}'))

    def _save_map(self):
        alias = self._map_name.text().strip() or 'map1'
        self._save_status.setText('Saving…')
        self._save_status.setStyleSheet('color:#aaa;font-size:11px;')

        def _cb(r):
            if r and r.get('status') == 'success':
                self._save_status.setText(f'✓ Saved: {r.get("name", alias)}')
                self._save_status.setStyleSheet('color:#60c060;font-size:11px;')
                _log(f'Map saved: {r.get("name", alias)}')
            else:
                self._save_status.setText('✗ Save failed (fallback to map_saver_cli)')
                self._save_status.setStyleSheet('color:#e05555;font-size:11px;')
                from .node import _MAPS_DIR
                maps_dir = self._win.node.config.settings.get('maps_dir', _MAPS_DIR)
                path = os.path.join(maps_dir, alias)
                self._win.node.save_map(path)

        self._win.api.post_async('/atlas/map/save', {'alias': alias}, _cb)

    def refresh(self, node):
        import time as _t
        status = node.get_launch_status()   # merged local + API
        slam   = status['slam']
        nav    = status['nav']
        mapsrv = status['map_server']
        if slam:
            self._status_lbl.setText('Mode: Mapping ●')
            self._status_lbl.setStyleSheet('color:#60c060;font-size:11px;font-weight:bold;')
            self._mode_pending_until = 0
        elif nav:
            self._status_lbl.setText('Mode: Navigation ●')
            self._status_lbl.setStyleSheet('color:#4e9af1;font-size:11px;font-weight:bold;')
            self._mode_pending_until = 0
        elif mapsrv:
            self._status_lbl.setText('Mode: Map Server ●')
            self._status_lbl.setStyleSheet('color:#aaa;font-size:11px;')
            self._mode_pending_until = 0
        else:
            # If API just accepted a mode change, hold off showing Idle
            # until the API launch/status poll can confirm (up to 6s)
            pending_until = getattr(self, '_mode_pending_until', 0)
            if pending_until and _t.time() < pending_until:
                pmode = getattr(self, '_mode_pending_val', 1)
                labels = {1: 'Starting Mapping…', 2: 'Starting Nav…', 3: 'Extending Map…'}
                self._status_lbl.setText(labels.get(pmode, 'Starting…'))
                self._status_lbl.setStyleSheet('color:#aaa;font-size:11px;')
            else:
                self._status_lbl.setText('Mode: Idle')
                self._status_lbl.setStyleSheet('color:#666;font-size:11px;')


# ══════════════════════════════════════════════════════════════════════════ #
# 3. Position Panel                                                          #
# ══════════════════════════════════════════════════════════════════════════ #

_FUNC_COLORS = {
    'home':     '#e06060', 'dock':     '#6090d0', 'charge':   '#d0b040',
    'pickup':   '#50c080', 'dropoff':  '#c07050', 'delivery': '#9060d0',
    'waypoint': '#6090ff', 'custom':   '#888888',
}
_FUNC_ABBREV = {
    'home': 'HM', 'dock': 'DK', 'charge': 'CH',
    'pickup': 'PU', 'dropoff': 'DO', 'delivery': 'DL',
    'waypoint': 'WP', 'custom': 'CU',
}


class _WaypointItemWidget(QWidget):
    navigate_requested = pyqtSignal()
    delete_requested   = pyqtSignal()
    edit_requested     = pyqtSignal()

    _BTN_SIZE = 32
    _ICO_SIZE = 18

    def __init__(self, idx, pos, parent=None):
        super().__init__(parent)
        self.setFixedHeight(54)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            'QWidget#wpitem{'
            '  background:#252535;border-radius:5px;border:1px solid #333;}'
            'QWidget#wpitem:hover{'
            '  background:#2d2d45;border:1px solid #4a4a6a;}')
        self.setObjectName('wpitem')

        h = QHBoxLayout(self)
        h.setContentsMargins(10, 5, 8, 5)
        h.setSpacing(8)

        ftype  = pos.get('func', pos.get('type', 'waypoint')).lower()
        color  = _FUNC_COLORS.get(ftype, '#6090ff')
        abbrev = _FUNC_ABBREV.get(ftype, 'WP')

        # ── left: number + type badge ────────────────────────────────────
        left = QVBoxLayout()
        left.setSpacing(2)
        left.setContentsMargins(0, 0, 0, 0)
        num_lbl = QLabel(str(idx + 1))
        num_lbl.setAlignment(Qt.AlignCenter)
        num_lbl.setFixedWidth(28)
        num_lbl.setStyleSheet(
            'color:#ccddee;font-size:13px;font-weight:bold;'
            'background:transparent;border:none;')
        badge = QLabel(abbrev)
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedWidth(28)
        badge.setStyleSheet(
            f'color:#111;background:{color};border-radius:3px;'
            f'font-size:8px;font-weight:bold;padding:1px 0;border:none;')
        left.addWidget(num_lbl)
        left.addWidget(badge)
        h.addLayout(left)

        # ── center: name + coords ────────────────────────────────────────
        info = QVBoxLayout()
        info.setSpacing(2)
        info.setContentsMargins(0, 0, 0, 0)
        name_lbl = QLabel(pos.get('name', f'Point {idx + 1}'))
        name_lbl.setStyleSheet(
            'color:#ddeeff;font-size:12px;font-weight:bold;'
            'background:transparent;border:none;')
        yaw_deg   = math.degrees(pos.get('yaw', 0.0))
        coord_lbl = QLabel(
            f"({pos.get('x', 0):.2f}, {pos.get('y', 0):.2f})  {yaw_deg:.1f}°")
        coord_lbl.setStyleSheet(
            'color:#6677aa;font-size:10px;background:transparent;border:none;')
        info.addWidget(name_lbl)
        info.addWidget(coord_lbl)
        h.addLayout(info, 1)

        # ── right: action buttons ────────────────────────────────────────
        nav_btn = QPushButton()
        nav_btn.setFixedSize(self._BTN_SIZE, self._BTN_SIZE)
        nav_btn.setIconSize(QSize(self._ICO_SIZE, self._ICO_SIZE))
        nav_btn.setStyleSheet(
            'QPushButton{background:#1a4a1a;border:1px solid #3a6a3a;border-radius:5px;}'
            'QPushButton:hover{background:#2a6a2a;}'
            'QPushButton:pressed{background:#0a3a0a;}')
        nav_ic = _svg_icon('navigate', self._ICO_SIZE, '#6ddd6d')
        if nav_ic:
            nav_btn.setIcon(nav_ic)

        del_btn = QPushButton()
        del_btn.setFixedSize(self._BTN_SIZE, self._BTN_SIZE)
        del_btn.setIconSize(QSize(self._ICO_SIZE, self._ICO_SIZE))
        del_btn.setStyleSheet(
            'QPushButton{background:#3a1a1a;border:1px solid #6a3a3a;border-radius:5px;}'
            'QPushButton:hover{background:#5a2a2a;}'
            'QPushButton:pressed{background:#2a0a0a;}')
        del_ic = _svg_icon('trash', self._ICO_SIZE, '#dd6666')
        if del_ic:
            del_btn.setIcon(del_ic)

        h.addWidget(nav_btn)
        h.addWidget(del_btn)

        nav_btn.clicked.connect(self.navigate_requested)
        del_btn.clicked.connect(self.delete_requested)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Only fire edit if the click is NOT on a child button
            child = self.childAt(event.pos())
            if not isinstance(child, QPushButton):
                self.edit_requested.emit()
        super().mousePressEvent(event)


class PositionPanel(QWidget):
    FUNC_TYPES = ['Waypoint', 'Home', 'Dock', 'Charge', 'Pickup', 'Dropoff', 'Delivery', 'Custom']

    def __init__(self, win):
        super().__init__()
        self._win         = win
        self._editing_idx = -1   # -1 = new,  >= 0 = editing existing index

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        # ── header ────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel('Positions / Waypoints')
        title.setStyleSheet('font-weight:bold;font-size:13px;color:#ddd;')
        self._add_btn = QPushButton('Add')
        self._add_btn.setFixedWidth(70)
        add_ic = _svg_icon('plus', 13, '#88ccff')
        if add_ic:
            self._add_btn.setIcon(add_ic)
        self._add_btn.setStyleSheet(
            'QPushButton{background:#1a3a5a;color:#8cf;border:1px solid #2a5a8a;'
            'border-radius:4px;padding:4px 8px;}'
            'QPushButton:hover{background:#2a4a6a;}')
        self._add_btn.clicked.connect(self._on_add_clicked)
        hdr.addWidget(title, 1)
        hdr.addWidget(self._add_btn)
        lay.addLayout(hdr)

        # ── inline form ───────────────────────────────────────────────────
        self._form_frame = QFrame()
        self._form_frame.setStyleSheet(
            'QFrame{background:#22223a;border:1px solid #3a3a5a;border-radius:6px;}'
            'QLabel{color:#bbc;font-size:11px;background:transparent;border:none;}'
            'QLineEdit,QDoubleSpinBox,QComboBox{'
            'background:#1a1a2a;color:#eef;border:1px solid #444;'
            'border-radius:3px;padding:2px 5px;}')
        fl = QVBoxLayout(self._form_frame)
        fl.setContentsMargins(10, 8, 10, 10)
        fl.setSpacing(5)

        self._form_title = QLabel('New Waypoint')
        self._form_title.setStyleSheet(
            'font-weight:bold;color:#9af;font-size:12px;background:transparent;border:none;')
        fl.addWidget(self._form_title)

        nr = QHBoxLayout(); nr.setSpacing(6)
        nr.addWidget(QLabel('Name'))
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText('e.g. office_desk')
        nr.addWidget(self._name_edit, 1)
        fl.addLayout(nr)

        tr = QHBoxLayout(); tr.setSpacing(6)
        tr.addWidget(QLabel('Type'))
        self._type_combo = QComboBox()
        self._type_combo.addItems(self.FUNC_TYPES)
        tr.addWidget(self._type_combo, 1)
        fl.addLayout(tr)

        xyr = QHBoxLayout(); xyr.setSpacing(6)
        xyr.addWidget(QLabel('X (m)'))
        self._x_spin = QDoubleSpinBox()
        self._x_spin.setRange(-9999, 9999); self._x_spin.setDecimals(3)
        xyr.addWidget(self._x_spin)
        xyr.addWidget(QLabel('Y (m)'))
        self._y_spin = QDoubleSpinBox()
        self._y_spin.setRange(-9999, 9999); self._y_spin.setDecimals(3)
        xyr.addWidget(self._y_spin)
        fl.addLayout(xyr)

        yawr = QHBoxLayout(); yawr.setSpacing(6)
        yawr.addWidget(QLabel('Yaw (°)'))
        self._yaw_spin = QDoubleSpinBox()
        self._yaw_spin.setRange(-180, 180); self._yaw_spin.setDecimals(1)
        yawr.addWidget(self._yaw_spin, 1)
        fl.addLayout(yawr)

        hint = QLabel('Click bản đồ để chọn vị trí, kéo để chọn hướng')
        hint.setStyleSheet('color:#6af;font-size:10px;background:transparent;border:none;')
        hint.setWordWrap(True)
        fl.addWidget(hint)

        abr = QHBoxLayout(); abr.setSpacing(4)
        self._pick_btn = QPushButton('Pick on map')
        pin_ic = _svg_icon('pin', 14, '#99ccff')
        if pin_ic:
            self._pick_btn.setIcon(pin_ic)
        self._pick_btn.setCheckable(True)
        self._pick_btn.setStyleSheet(
            'QPushButton{background:#2a3a5a;color:#9cf;border:1px solid #3a5a8a;'
            'border-radius:4px;padding:4px;font-size:11px;}'
            'QPushButton:checked{background:#1a5a8a;color:#fff;}')
        self._pick_btn.toggled.connect(self._on_pick_toggled)
        save_btn = QPushButton('Save')
        save_ic = _svg_icon('check', 13, '#99dd99')
        if save_ic:
            save_btn.setIcon(save_ic)
        save_btn.setStyleSheet(
            'QPushButton{background:#1a4a1a;color:#9d9;border:1px solid #3a6a3a;'
            'border-radius:4px;padding:4px 10px;font-weight:bold;}'
            'QPushButton:hover{background:#2a6a2a;}')
        cancel_btn = QPushButton('Cancel')
        cancel_ic = _svg_icon('xmark', 13, '#aaaaaa')
        if cancel_ic:
            cancel_btn.setIcon(cancel_ic)
        cancel_btn.setStyleSheet(
            'QPushButton{background:#333;color:#999;border:1px solid #555;'
            'border-radius:4px;padding:4px 8px;}'
            'QPushButton:hover{background:#444;}')
        abr.addWidget(self._pick_btn, 1)
        abr.addWidget(save_btn)
        abr.addWidget(cancel_btn)
        fl.addLayout(abr)

        save_btn.clicked.connect(self._save_form)
        cancel_btn.clicked.connect(self._cancel_form)

        self._form_frame.setVisible(False)
        lay.addWidget(self._form_frame)

        # ── waypoint list ─────────────────────────────────────────────────
        self._list_container = QWidget()
        self._list_container.setStyleSheet('background:transparent;')
        self._list_lay = QVBoxLayout(self._list_container)
        self._list_lay.setContentsMargins(0, 0, 0, 0)
        self._list_lay.setSpacing(4)
        self._list_lay.addStretch()

        lay.addWidget(_scroll_wrap(self._list_container), 1)

        self._reload()

    # ── form helpers ──────────────────────────────────────────────────────

    def _on_add_clicked(self):
        if self._form_frame.isVisible() and self._editing_idx == -1:
            self._close_form()
        else:
            self._open_form_for_new()

    def _open_form_for_new(self):
        self._editing_idx = -1
        self._form_title.setText('New Waypoint')
        x, y, yaw = self._win.node.get_robot_pose()
        self._name_edit.setText('')
        self._type_combo.setCurrentIndex(0)
        self._x_spin.setValue(x)
        self._y_spin.setValue(y)
        self._yaw_spin.setValue(math.degrees(yaw))
        self._pick_btn.setChecked(False)
        self._form_frame.setVisible(True)

    def _open_form_for_edit(self, idx):
        positions = self._win.node.config.positions
        if idx < 0 or idx >= len(positions):
            return
        self._editing_idx = idx
        pos = positions[idx]
        self._form_title.setText('Edit Waypoint')
        self._name_edit.setText(pos.get('name', ''))
        func = pos.get('func', pos.get('type', 'Waypoint'))
        fl   = [f.lower() for f in self.FUNC_TYPES]
        self._type_combo.setCurrentIndex(
            fl.index(func.lower()) if func.lower() in fl else 0)
        self._x_spin.setValue(pos.get('x', 0.0))
        self._y_spin.setValue(pos.get('y', 0.0))
        self._yaw_spin.setValue(math.degrees(pos.get('yaw', 0.0)))
        self._pick_btn.setChecked(False)
        self._form_frame.setVisible(True)

    def _close_form(self):
        self._form_frame.setVisible(False)
        self._editing_idx = -1
        self._pick_btn.setChecked(False)
        self._win.request_map_mode('drag')

    def _on_pick_toggled(self, checked):
        if checked:
            if not self._form_frame.isVisible():
                self._open_form_for_new()
            self._win.request_map_mode('set_pose')
        else:
            self._win.request_map_mode('drag')

    def on_pose_selected(self, x, y, yaw):
        if not self._form_frame.isVisible():
            self._open_form_for_new()
        self._x_spin.setValue(x)
        self._y_spin.setValue(y)
        self._yaw_spin.setValue(math.degrees(yaw))

    def _save_form(self):
        name = self._name_edit.text().strip() or 'Position'
        func = self._type_combo.currentText()
        pos  = {
            'name': name,
            'func': func,
            'type': func.lower(),
            'x':   self._x_spin.value(),
            'y':   self._y_spin.value(),
            'yaw': math.radians(self._yaw_spin.value()),
        }
        self._save_position(pos)
        self._close_form()

    def _cancel_form(self):
        self._close_form()

    # ── data helpers ──────────────────────────────────────────────────────

    def _save_position(self, pos):
        wp = {'name': pos['name'], 'type': pos.get('type', 'custom'),
              'x': pos['x'], 'y': pos['y'], 'yaw': pos['yaw']}

        def _cb(r):
            if not r:
                _log('Waypoint sync failed, saving locally only')
            existing = [p for p in self._win.node.config.positions
                        if p.get('name') != pos['name']]
            existing.append(pos)
            self._win.node.config.positions = existing
            self._win.node.config.save_positions()
            self._reload_ui()

        self._win.api.post_async('/atlas/waypoints', wp, _cb)

    def _reload(self):
        def _fetch():
            wps = self._win.api.get_waypoints()
            if wps:
                self._win.node.config.positions = wps
                self._win.node.config.save_positions()
            self._reload_ui()
        threading.Thread(target=_fetch, daemon=True).start()

    def _reload_ui(self):
        from PyQt5.QtCore import QMetaObject, Qt as Qt2
        QMetaObject.invokeMethod(self, '_do_reload_ui', Qt2.QueuedConnection)

    @pyqtSlot()
    def _do_reload_ui(self):
        while self._list_lay.count() > 1:
            item = self._list_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i, pos in enumerate(self._win.node.config.positions):
            w = _WaypointItemWidget(i, pos)
            w.navigate_requested.connect(
                lambda _=False, idx=i: self._go_to_idx(idx))
            w.delete_requested.connect(
                lambda _=False, idx=i: self._delete_idx(idx))
            w.edit_requested.connect(
                lambda _=False, idx=i: self._open_form_for_edit(idx))
            self._list_lay.insertWidget(self._list_lay.count() - 1, w)

        self._win.map_widget.set_waypoints(self._win.node.config.positions)

    def _go_to_idx(self, row):
        positions = self._win.node.config.positions
        if row < 0 or row >= len(positions):
            return
        pos = positions[row]
        def _cb(r):
            if not r:
                self._win.node.send_nav_goal(pos['x'], pos['y'], pos.get('yaw', 0.0))
        self._win.api.post_async(
            '/atlas/nav/goal',
            {'x': pos['x'], 'y': pos['y'], 'yaw': pos.get('yaw', 0)}, _cb)
        self._win.map_widget.set_goal_marker(pos['x'], pos['y'])

    def _delete_idx(self, row):
        positions = self._win.node.config.positions
        if row < 0 or row >= len(positions):
            return
        name = positions[row].get('name', '')
        self._win.api.delete_async(f'/atlas/waypoints/{name}')
        positions.pop(row)
        self._win.node.config.save_positions()
        self._reload_ui()

    def refresh(self, _node):
        pass


# ══════════════════════════════════════════════════════════════════════════ #
# 4. Navi Route Panel                                                        #
# ══════════════════════════════════════════════════════════════════════════ #

class NaviRoutePanel(QWidget):
    def __init__(self, win):
        super().__init__()
        self._win = win
        self._polling = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8); lay.setSpacing(6)

        # ── Available positions ───────────────────────────────────────────
        lay.addWidget(_lbl('Available positions:'))
        self._avail = QListWidget()
        self._avail.setMaximumHeight(100)
        lay.addWidget(self._avail)

        ha = QHBoxLayout()
        self._add_btn = QPushButton('Add ▼')
        self._rem_btn = QPushButton('Remove')
        ha.addWidget(self._add_btn); ha.addWidget(self._rem_btn)
        lay.addLayout(ha)

        lay.addWidget(_lbl('Route sequence:'))
        self._route = QListWidget()
        self._route.setDragDropMode(QAbstractItemView.InternalMove)
        self._route.setMaximumHeight(120)
        lay.addWidget(self._route)

        hm = QHBoxLayout()
        self._up_btn   = QPushButton('↑')
        self._down_btn = QPushButton('↓')
        hm.addWidget(self._up_btn); hm.addWidget(self._down_btn)
        lay.addLayout(hm)

        # ── Route type ────────────────────────────────────────────────────
        tg = _grp('Route type')
        self._rb_auto    = QRadioButton('Auto timer — dừng tự động mỗi điểm')
        self._rb_confirm = QRadioButton('Manual confirm — chờ xác nhận mỗi điểm')
        self._rb_auto.setChecked(True)
        tg.layout().addWidget(self._rb_auto)
        tg.layout().addWidget(self._rb_confirm)

        dur_row = QHBoxLayout()
        dur_row.addWidget(QLabel('Dừng tại mỗi điểm:'))
        self._stop_dur = QDoubleSpinBox()
        self._stop_dur.setRange(1.0, 300.0); self._stop_dur.setSingleStep(1.0)
        self._stop_dur.setValue(10.0); self._stop_dur.setSuffix(' s')
        dur_row.addWidget(self._stop_dur)
        tg.layout().addLayout(dur_row)

        self._rb_auto.toggled.connect(lambda on: self._stop_dur.setEnabled(on))
        self._auto_charge_cb = QCheckBox('Tự động về sạc sau khi xong route')
        self._auto_charge_cb.setChecked(True)
        tg.layout().addWidget(self._auto_charge_cb)
        lay.addWidget(tg)

        # ── Controls ──────────────────────────────────────────────────────
        hx = QHBoxLayout()
        self._start_btn = _btn('▶ Start Route', '#3a8a3a')
        self._stop_btn  = _btn('■ Stop',        '#8a3a3a')
        hx.addWidget(self._start_btn); hx.addWidget(self._stop_btn)
        lay.addLayout(hx)

        # ── Status display ────────────────────────────────────────────────
        self._status_lbl = _lbl('Status: idle')
        self._progress_lbl = _lbl('')
        lay.addWidget(self._status_lbl)
        lay.addWidget(self._progress_lbl)

        # Confirm button (visible only in waiting_confirm state)
        self._confirm_btn = QPushButton('✓  Xác nhận — tiếp tục')
        self._confirm_btn.setStyleSheet(
            'QPushButton{background:#1a6a1a;color:#fff;font-weight:bold;font-size:14px;'
            'border:none;border-radius:6px;padding:10px;}'
            'QPushButton:hover{background:#2a8a2a;}'
            'QPushButton:pressed{background:#0a4a0a;}')
        self._confirm_btn.setVisible(False)
        self._confirm_btn.clicked.connect(self._confirm_wp)
        lay.addWidget(self._confirm_btn)

        # ── Poll timer ────────────────────────────────────────────────────
        self._poll_timer = QTimer()
        self._poll_timer.setInterval(800)
        self._poll_timer.timeout.connect(self._poll_status)

        # ── Connections ───────────────────────────────────────────────────
        self._avail.itemDoubleClicked.connect(lambda _: self._add_to_route())
        self._add_btn.clicked.connect(self._add_to_route)
        self._rem_btn.clicked.connect(self._remove_from_route)
        self._up_btn.clicked.connect(self._move_up)
        self._down_btn.clicked.connect(self._move_down)
        self._start_btn.clicked.connect(self._start_route)
        self._stop_btn.clicked.connect(self._stop_route)
        self._route.model().rowsMoved.connect(lambda *_: self._update_route_on_map())

        self._reload_avail()

    # ── list helpers ──────────────────────────────────────────────────────

    def _reload_avail(self):
        cur = self._avail.currentRow()
        self._avail.clear()
        for p in self._win.node.config.positions:
            self._avail.addItem(p.get('name', '?'))
        if cur >= 0:
            self._avail.setCurrentRow(min(cur, self._avail.count() - 1))

    def _update_route_on_map(self):
        wps = []
        for i in range(self._route.count()):
            idx = self._route.item(i).data(Qt.UserRole)
            positions = self._win.node.config.positions
            if idx is not None and idx < len(positions):
                wps.append(positions[idx])
        self._win.map_widget.set_route_waypoints(wps)

    def _add_to_route(self):
        row = self._avail.currentRow()
        if row < 0:
            return
        pos = self._win.node.config.positions[row]
        item = QListWidgetItem(pos.get('name', '?'))
        item.setData(Qt.UserRole, row)
        self._route.addItem(item)
        self._update_route_on_map()

    def _remove_from_route(self):
        row = self._route.currentRow()
        if row >= 0:
            self._route.takeItem(row)
            self._update_route_on_map()

    def _move_up(self):
        row = self._route.currentRow()
        if row > 0:
            item = self._route.takeItem(row)
            self._route.insertItem(row - 1, item)
            self._route.setCurrentRow(row - 1)
            self._update_route_on_map()

    def _move_down(self):
        row = self._route.currentRow()
        if row < self._route.count() - 1:
            item = self._route.takeItem(row)
            self._route.insertItem(row + 1, item)
            self._route.setCurrentRow(row + 1)
            self._update_route_on_map()

    # ── route execution ───────────────────────────────────────────────────

    def _collect_waypoints(self) -> list:
        wps = []
        for i in range(self._route.count()):
            idx = self._route.item(i).data(Qt.UserRole)
            if idx is not None and idx < len(self._win.node.config.positions):
                p = self._win.node.config.positions[idx]
                wps.append({'x': p['x'], 'y': p['y'],
                             'yaw': p.get('yaw', 0.0),
                             'name': p.get('name', f'WP{i+1}')})
        return wps

    def _start_route(self):
        wps = self._collect_waypoints()
        if not wps:
            return

        route_type  = 'confirm' if self._rb_confirm.isChecked() else 'auto'
        stop_dur    = self._stop_dur.value()
        auto_charge = self._auto_charge_cb.isChecked()

        self._status_lbl.setText('Status: starting…')
        self._confirm_btn.setVisible(False)

        def _cb(r):
            if r and r.get('status') == 'success':
                self._poll_timer.start()
            else:
                self._status_lbl.setText('Status: failed to start')
        self._win.api.post_async(
            '/atlas/route/execute',
            {'waypoints': wps, 'type': route_type,
             'stop_duration': stop_dur, 'auto_charge': auto_charge},
            _cb)

    def _stop_route(self):
        self._poll_timer.stop()
        self._confirm_btn.setVisible(False)
        self._win.api.post_async('/atlas/route/stop')
        self._status_lbl.setText('Status: stopped')
        self._progress_lbl.setText('')

    def _confirm_wp(self):
        self._confirm_btn.setVisible(False)
        self._win.api.post_async('/atlas/route/confirm')

    # ── status polling ────────────────────────────────────────────────────

    @pyqtSlot()
    def _poll_status(self):
        def _cb(r):
            from PyQt5.QtCore import QMetaObject, Qt as Qt2
            self._poll_result = r
            QMetaObject.invokeMethod(self, '_apply_status', Qt2.QueuedConnection)
        self._win.api.get_async('/atlas/route/status', _cb)

    @pyqtSlot()
    def _apply_status(self):
        r = getattr(self, '_poll_result', None)
        if not r:
            return
        status = r.get('status', 'idle')
        idx    = r.get('current_idx', -1)
        total  = r.get('total', 0)
        name   = r.get('current_name', '')

        _STATUS_TEXT = {
            'idle':            'Status: idle',
            'navigating':      f'Navigating → {name}  ({idx + 1}/{total})',
            'waiting':         f'Waiting at {name}  ({idx + 1}/{total})',
            'waiting_confirm': f'Chờ xác nhận tại {name}  ({idx + 1}/{total})',
            'charging':        'Route done — về sạc…',
            'done':            'Route done ✓',
            'stopped':         'Status: stopped',
            'failed':          f'Failed: {r.get("error", "?")}',
        }
        self._status_lbl.setText(_STATUS_TEXT.get(status, f'Status: {status}'))

        progress_pct = int((idx + 1) / total * 100) if total > 0 and idx >= 0 else 0
        self._progress_lbl.setText(
            f'{idx + 1}/{total}  ({progress_pct}%)' if total > 0 else '')

        show_confirm = (status == 'waiting_confirm')
        self._confirm_btn.setVisible(show_confirm)

        if status in ('done', 'stopped', 'failed', 'idle'):
            self._poll_timer.stop()
            self._confirm_btn.setVisible(False)

    def refresh(self, node):
        pass


# ══════════════════════════════════════════════════════════════════════════ #
# 5. Virtual Wall Panel                                                      #
# ══════════════════════════════════════════════════════════════════════════ #

class VirtualWallPanel(QWidget):
    def __init__(self, win):
        super().__init__()
        self._win = win
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8); lay.setSpacing(6)

        lay.addWidget(_lbl(
            'Click map to add points.\nRight-click or double-click to finish wall.\nEsc to cancel.'))

        self._draw_btn = QPushButton('✏ Draw Wall')
        self._draw_btn.setCheckable(True)
        self._draw_btn.toggled.connect(
            lambda on: win.request_map_mode('wall' if on else 'drag'))
        win.map_widget.drawing_cancelled.connect(
            lambda: self._draw_btn.setChecked(False))
        lay.addWidget(self._draw_btn)

        lay.addWidget(QLabel('Walls:'))
        self._list = QListWidget()
        lay.addWidget(self._list, 1)

        h = QHBoxLayout()
        self._del_btn   = QPushButton('Delete')
        self._clear_btn = QPushButton('Clear all')
        h.addWidget(self._del_btn); h.addWidget(self._clear_btn)
        lay.addLayout(h)

        self._sync_lbl = _lbl('')
        lay.addWidget(self._sync_lbl)

        self._del_btn.clicked.connect(self._delete)
        self._clear_btn.clicked.connect(self._clear)

        self._reload()

    def on_wall_drawn(self):
        self._draw_btn.setChecked(False)
        self._sync_to_api()
        self._reload()

    def _sync_to_api(self):
        walls = self._win.node.config.walls

        def _cb(r):
            ok = r and r.get('status') == 'success'
            self._sync_lbl.setText('✓ Synced to robot' if ok else '⚠ Local only')
            self._sync_lbl.setStyleSheet(
                f'color:{"#60c060" if ok else "#e0a030"};font-size:11px;')
        self._win.api.post_async('/atlas/virtual_wall', {'walls': walls}, _cb)

    def _reload(self):
        self._list.clear()
        for i, wall in enumerate(self._win.node.config.walls):
            self._list.addItem(f'Wall {i+1}  ({len(wall)} pts)')

    def _delete(self):
        row = self._list.currentRow()
        if row >= 0:
            self._win.node.config.walls.pop(row)
            self._win.node.config.save_walls()
            self._win.map_widget.set_virtual_walls(self._win.node.config.walls)
            self._sync_to_api()
            self._reload()

    def _clear(self):
        self._win.node.config.walls.clear()
        self._win.node.config.save_walls()
        self._win.map_widget.clear_virtual_walls()
        self._win.api.post_async('/atlas/virtual_wall',
                                  {'walls': []},
                                  lambda r: None)
        self._reload()

    def refresh(self, _node):
        pass


# ══════════════════════════════════════════════════════════════════════════ #
# 6. Special Area Panel                                                      #
# ══════════════════════════════════════════════════════════════════════════ #

class SpecialAreaPanel(QWidget):
    def __init__(self, win):
        super().__init__()
        self._win = win
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8); lay.setSpacing(6)

        lay.addWidget(_lbl(
            'Click to add polygon vertices.\nRight-click or double-click to finish.'))
        lay.addWidget(_lbl('■ Red=Forbidden  ■ Yellow=Slow  ■ Green=Fast', '#888'))

        self._draw_btn = QPushButton('✏ Draw Area')
        self._draw_btn.setCheckable(True)
        self._draw_btn.toggled.connect(
            lambda on: win.request_map_mode('polygon' if on else 'drag'))
        win.map_widget.drawing_cancelled.connect(
            lambda: self._draw_btn.setChecked(False))
        lay.addWidget(self._draw_btn)

        lay.addWidget(QLabel('Areas:'))
        self._list = QListWidget()
        lay.addWidget(self._list, 1)

        h = QHBoxLayout()
        self._del_btn   = QPushButton('Delete')
        self._clear_btn = QPushButton('Clear all')
        h.addWidget(self._del_btn); h.addWidget(self._clear_btn)
        lay.addLayout(h)

        self._sync_lbl = _lbl('')
        lay.addWidget(self._sync_lbl)

        self._del_btn.clicked.connect(self._delete)
        self._clear_btn.clicked.connect(self._clear)

        self._reload()

    def on_area_drawn(self, polygon):
        self._draw_btn.setChecked(False)
        dlg = _AreaDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            import uuid
            data = dlg.result_data()
            data['polygon'] = polygon
            data['id'] = uuid.uuid4().hex[:8]
            self._win.node.config.areas.append(data)
            self._win.node.config.save_areas()
            self._win.map_widget.set_special_areas(self._win.node.config.areas)
            self._sync_to_api()
            self._reload()

    def _sync_to_api(self):
        areas = self._win.node.config.areas

        def _cb(r):
            ok = r and r.get('status') == 'success'
            self._sync_lbl.setText('✓ Synced to robot' if ok else '⚠ Local only')
            self._sync_lbl.setStyleSheet(
                f'color:{"#60c060" if ok else "#e0a030"};font-size:11px;')
        self._win.api.post_async('/atlas/special_area', {'areas': areas}, _cb)

    def _reload(self):
        self._list.clear()
        for a in self._win.node.config.areas:
            self._list.addItem(
                f"{a.get('name','?')}  [{a.get('type','?')}]  {len(a.get('polygon',[]))} pts")

    def _delete(self):
        row = self._list.currentRow()
        if row < 0:
            return
        area = self._win.node.config.areas[row]
        area_id = area.get('id', '')
        if area_id:
            self._win.api.post_async(f'/atlas/special_area/{area_id}', None, lambda r: None)
        self._win.node.config.areas.pop(row)
        self._win.node.config.save_areas()
        self._win.map_widget.set_special_areas(self._win.node.config.areas)
        self._reload()

    def _clear(self):
        self._win.node.config.areas.clear()
        self._win.node.config.save_areas()
        self._win.map_widget.set_special_areas([])
        self._win.api.post_async('/atlas/special_area', {'areas': []}, lambda r: None)
        self._reload()

    def refresh(self, _node):
        pass


# ══════════════════════════════════════════════════════════════════════════ #
# 7. Map Panel                                                               #
# ══════════════════════════════════════════════════════════════════════════ #

class _MapCard(QWidget):
    """Card widget hiển thị thông tin 1 map trong danh sách."""
    def __init__(self, entry: dict):
        super().__init__()
        self.setAutoFillBackground(False)
        self.setStyleSheet('background: transparent;')
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(10)

        # Thumbnail
        self._thumb_lbl = QLabel('…')
        self._thumb_lbl.setFixedSize(88, 66)
        self._thumb_lbl.setAlignment(Qt.AlignCenter)
        self._thumb_lbl.setStyleSheet(
            'background:#1a1a2e; border:1px solid #333; color:#666; font-size:18px;')
        lay.addWidget(self._thumb_lbl)

        # Info
        info = QVBoxLayout()
        info.setSpacing(2)
        info.setContentsMargins(0, 0, 0, 0)

        alias = entry.get('alias') or entry.get('name', '?')
        name_lbl = QLabel(alias)
        font = QFont(); font.setBold(True); font.setPointSize(11)
        name_lbl.setFont(font)
        info.addWidget(name_lbl)

        # Ngày tạo
        created = entry.get('created_at', '')
        if created:
            try:
                from datetime import datetime, timezone
                dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                dt_local = dt.astimezone()
                date_str = dt_local.strftime('%Y-%m-%d  %H:%M')
            except Exception:
                date_str = created[:16]
            info.addWidget(_lbl(f'  {date_str}'))

        # Kích thước
        w   = entry.get('width',  0)
        h   = entry.get('height', 0)
        res = entry.get('resolution', 0.0)
        kb  = entry.get('size_kb', 0)
        parts = []
        if w and h:
            parts.append(f'{w} x {h} px')
        if res:
            parts.append(f'{res:.3f} m/px')
        if kb:
            parts.append(f'{kb/1024:.1f} MB' if kb >= 1024 else f'{kb} KB')
        if parts:
            info.addWidget(_lbl('  ' + '   |   '.join(parts)))

        info.addStretch()
        lay.addLayout(info, 1)

    def set_thumbnail(self, pix: QPixmap):
        self._thumb_lbl.setPixmap(
            pix.scaled(88, 66, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self._thumb_lbl.setText('')


class MapPanel(QWidget):
    _thumb_ready = pyqtSignal(int, bytes)   # row, png_data — thread-safe delivery

    def __init__(self, win):
        super().__init__()
        self._win = win
        self._map_entries: list = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8); lay.setSpacing(6)

        hd = QHBoxLayout()
        hd.addWidget(QLabel('Maps on robot:'))
        hd.addStretch()
        ref_btn = QPushButton('↺ Refresh')
        ref_btn.clicked.connect(self._refresh)
        hd.addWidget(ref_btn)
        lay.addLayout(hd)

        self._list = QListWidget()
        self._list.setSpacing(2)
        self._list.setUniformItemSizes(False)
        lay.addWidget(self._list, 1)

        h = QHBoxLayout()
        self._apply_btn  = _btn('▶ Apply Map', '#4e6ea0')
        self._delete_btn = QPushButton('Delete')
        h.addWidget(self._apply_btn); h.addWidget(self._delete_btn)
        lay.addLayout(h)

        self._status = _lbl('')
        lay.addWidget(self._status)

        self._apply_btn.clicked.connect(self._apply_map)
        self._delete_btn.clicked.connect(self._delete_map)
        self._thumb_ready.connect(self._apply_thumb)

        self._refresh()

    def _refresh(self):
        self._status.setText('Loading…')
        self._list.clear()
        self._map_entries.clear()

        def _fetch():
            entries = self._win.api.list_maps()
            from PyQt5.QtCore import QMetaObject, Qt as Qt2
            self._map_entries = entries
            QMetaObject.invokeMethod(self, '_populate_list', Qt2.QueuedConnection)

        threading.Thread(target=_fetch, daemon=True).start()

    @pyqtSlot()
    def _populate_list(self):
        self._list.clear()
        n = len(self._map_entries)
        self._status.setText(f'{n} map{"s" if n != 1 else ""}')
        for i, entry in enumerate(self._map_entries):
            card = _MapCard(entry)
            item = QListWidgetItem()
            item.setData(Qt.UserRole, entry)
            item.setSizeHint(card.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, card)
            threading.Thread(
                target=self._load_thumb, args=(i, entry.get('name', '')),
                daemon=True).start()

    def _load_thumb(self, row: int, name: str):
        data = self._win.api.get_thumbnail(name)
        if data:
            self._thumb_ready.emit(row, data)   # signal → main thread

    @pyqtSlot(int, bytes)
    def _apply_thumb(self, row: int, data: bytes):
        if row >= self._list.count():
            return
        item = self._list.item(row)
        if item is None:
            return
        card = self._list.itemWidget(item)
        if not isinstance(card, _MapCard):
            return
        pix = QPixmap()
        pix.loadFromData(data)
        if not pix.isNull():
            card.set_thumbnail(pix)

    def _apply_map(self):
        item = self._list.currentItem()
        if not item:
            return
        entry = item.data(Qt.UserRole)
        name  = entry.get('name', '')
        self._status.setText(f'Applying {name}…')

        def _cb(r):
            ok = r and r.get('status') == 'success'
            self._status.setText(f'Applied: {name}' if ok else 'Apply failed')
            self._status.setStyleSheet(
                f'color:{"#60c060" if ok else "#e05555"};font-size:11px;')
        self._win.api.post_async('/atlas/map/apply', {'name': name}, _cb)

    def _delete_map(self):
        item = self._list.currentItem()
        if not item:
            return
        entry = item.data(Qt.UserRole)
        name  = entry.get('name', '')

        def _cb(r):
            if r and r.get('status') == 'success':
                self._refresh()
        self._win.api.delete_async(f'/atlas/map/{name}', _cb)

    def refresh(self, _node):
        pass


# ══════════════════════════════════════════════════════════════════════════ #
# 8. Robot Status Panel                                                      #
# ══════════════════════════════════════════════════════════════════════════ #

class RobotStatusPanel(QWidget):
    def __init__(self, win):
        super().__init__()
        self._win = win
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8); lay.setSpacing(8)

        sg = _grp('Connections')
        sfl = QFormLayout(); sfl.setSpacing(4)
        self._laser_lbl = QLabel('—'); self._imu_lbl = QLabel('—')
        self._nav_lbl   = QLabel('—'); self._api_lbl = QLabel('—')
        for k, v in [('Laser', self._laser_lbl), ('IMU', self._imu_lbl),
                     ('Nav2', self._nav_lbl), ('Atlas API', self._api_lbl)]:
            kl = QLabel(k); kl.setStyleSheet('color:#888;')
            v.setAlignment(Qt.AlignRight)
            sfl.addRow(kl, v)
        sg.layout().addLayout(sfl)
        lay.addWidget(sg)

        rg = _grp('Robot')
        rfl = QFormLayout(); rfl.setSpacing(4)
        self._pose_lbl  = QLabel('—'); self._yaw_lbl = QLabel('—')
        self._vx_lbl    = QLabel('—'); self._wz_lbl  = QLabel('—')
        self._bat_lbl   = QLabel('—'); self._estop_lbl = QLabel('—')
        for k, v in [('Position', self._pose_lbl), ('Heading', self._yaw_lbl),
                     ('Vx (m/s)', self._vx_lbl),   ('Wz (r/s)', self._wz_lbl),
                     ('Battery',  self._bat_lbl),   ('E-Stop',   self._estop_lbl)]:
            kl = QLabel(k); kl.setStyleSheet('color:#888;')
            v.setAlignment(Qt.AlignRight)
            rfl.addRow(kl, v)
        rg.layout().addLayout(rfl)
        lay.addWidget(rg)

        self._check_api_btn = QPushButton('Check API connection')
        self._check_api_btn.clicked.connect(self._check_api)
        lay.addWidget(self._check_api_btn)

        lay.addStretch()
        self._api_ok = False

    def _dot(self, ok):
        return ('● OK', 'color:#60c060;') if ok else ('● —', 'color:#555;')

    def _check_api(self):
        def _cb(r):
            self._api_ok = r is not None
            from PyQt5.QtCore import QMetaObject, Qt as Qt2
            QMetaObject.invokeMethod(self, '_update_api_lbl', Qt2.QueuedConnection)
        self._win.api.get_async('/atlas/status', _cb)

    @pyqtSlot()
    def _update_api_lbl(self):
        txt, style = self._dot(self._api_ok)
        self._api_lbl.setText(txt)
        self._api_lbl.setStyleSheet(style)

    def refresh(self, node):
        x, y, yaw = node.get_robot_pose()
        vx, wz    = node.get_speed()
        bat, estop = node.get_battery_pct(), node.get_emergency_stop()

        self._pose_lbl.setText(f'({x:.3f}, {y:.3f})')
        self._yaw_lbl.setText(f'{math.degrees(yaw):.1f}°')
        self._vx_lbl.setText(f'{vx:.3f}')
        self._wz_lbl.setText(f'{wz:.3f}')
        self._bat_lbl.setText(f'{bat:.0f}%' if bat >= 0 else '—')

        if estop:
            self._estop_lbl.setText('● ON')
            self._estop_lbl.setStyleSheet('color:#e05555;font-weight:bold;')
        else:
            self._estop_lbl.setText('● OFF')
            self._estop_lbl.setStyleSheet('color:#60c060;')

        for lbl, ok in [(self._laser_lbl, node.get_laser_ok()),
                        (self._imu_lbl,   node.get_imu_ok())]:
            txt, style = self._dot(ok)
            lbl.setText(txt); lbl.setStyleSheet(style)

        self._nav_lbl.setText(node.get_nav_state())


# ══════════════════════════════════════════════════════════════════════════ #
# 9. Log Panel                                                               #
# ══════════════════════════════════════════════════════════════════════════ #

class LogPanel(QWidget):
    def __init__(self, _win):
        super().__init__()
        self._last_len = 0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8); lay.setSpacing(4)

        h = QHBoxLayout()
        h.addWidget(QLabel('Logs'))
        h.addStretch()
        clear_btn = QPushButton('Clear')
        clear_btn.clicked.connect(self._clear)
        h.addWidget(clear_btn)
        lay.addLayout(h)

        self._txt = QTextEdit()
        self._txt.setReadOnly(True)
        self._txt.setFont(QFont('Monospace', 9))
        self._txt.setStyleSheet('background:#111;color:#9f9;border:none;')
        lay.addWidget(self._txt, 1)

    def _clear(self):
        app_log.clear()
        self._last_len = 0
        self._txt.clear()

    def refresh(self, _node):
        cur = len(app_log)
        if cur > self._last_len:
            new_lines = list(app_log)[self._last_len:]
            self._txt.append('\n'.join(new_lines))
            self._last_len = cur


# ══════════════════════════════════════════════════════════════════════════ #
# 10. Settings Panel                                                         #
# ══════════════════════════════════════════════════════════════════════════ #

class SettingsPanel(QWidget):
    def __init__(self, win):
        super().__init__()
        self._win = win
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(8, 8, 8, 8); lay.setSpacing(8)

        s = win.node.config.settings

        # connection
        cg = _grp('Robot connection')
        cfl = QFormLayout(); cfl.setSpacing(6)
        self._host = QLineEdit(s.get('robot_host', 'localhost:8080'))
        self._host.returnPressed.connect(self._save)
        cfl.addRow('Robot host (IP:port):', self._host)
        cg.layout().addLayout(cfl)
        test_btn = QPushButton('Test connection')
        test_btn.clicked.connect(self._test_conn)
        self._conn_lbl = _lbl('')
        cg.layout().addWidget(test_btn)
        cg.layout().addWidget(self._conn_lbl)
        lay.addWidget(cg)

        # motion
        rg = _grp('Robot motion')
        rfl = QFormLayout(); rfl.setSpacing(6)
        self._max_v   = QDoubleSpinBox(); self._max_v.setRange(0.05, 3.0);    self._max_v.setSingleStep(0.05);  self._max_v.setValue(s.get('max_linear', 0.5));     self._max_v.setSuffix(' m/s')
        self._max_w   = QDoubleSpinBox(); self._max_w.setRange(0.1, 6.28);    self._max_w.setSingleStep(0.05);  self._max_w.setValue(s.get('max_angular', 1.0));    self._max_w.setSuffix(' r/s')
        self._bat_pct = QDoubleSpinBox(); self._bat_pct.setRange(5, 100);     self._bat_pct.setSingleStep(1);   self._bat_pct.setValue(s.get('battery_charge_pct', 20)); self._bat_pct.setSuffix(' %')
        for _sb in (self._max_v, self._max_w, self._bat_pct):
            _sb.editingFinished.connect(self._save)
        rfl.addRow('Max linear speed:', self._max_v)
        rfl.addRow('Max angular speed:', self._max_w)
        rfl.addRow('Charge threshold:', self._bat_pct)
        rg.layout().addLayout(rfl)
        test_charge_btn = _btn('🧪 Test: trigger auto-charge now', '#6a4080')
        test_charge_btn.setToolTip(
            'Kích hoạt lệnh về sạc ngay (bỏ qua kiểm tra % pin) — dùng để test')
        test_charge_btn.clicked.connect(self._test_auto_charge)
        rg.layout().addWidget(test_charge_btn)
        lay.addWidget(rg)

        # nav2
        ng = _grp('Navigation tolerances')
        nfl = QFormLayout(); nfl.setSpacing(6)
        self._infl   = QDoubleSpinBox(); self._infl.setRange(0.05, 1.0);   self._infl.setSingleStep(0.05); self._infl.setValue(s.get('inflation_radius', 0.3));  self._infl.setSuffix(' m')
        self._xy_tol = QDoubleSpinBox(); self._xy_tol.setRange(0.05, 1.0); self._xy_tol.setSingleStep(0.05); self._xy_tol.setValue(s.get('xy_tolerance', 0.25)); self._xy_tol.setSuffix(' m')
        self._y_tol  = QDoubleSpinBox(); self._y_tol.setRange(0.05, 3.14); self._y_tol.setSingleStep(0.05); self._y_tol.setValue(s.get('yaw_tolerance', 0.2));   self._y_tol.setSuffix(' rad')
        for _sb in (self._infl, self._xy_tol, self._y_tol):
            _sb.editingFinished.connect(self._save)
        nfl.addRow('Inflation radius:', self._infl)
        nfl.addRow('XY tolerance:', self._xy_tol)
        nfl.addRow('Yaw tolerance:', self._y_tol)
        ng.layout().addLayout(nfl)
        apply_nav_btn = QPushButton('Apply to Nav2 (ros2 param set)')
        apply_nav_btn.clicked.connect(self._apply_nav2)
        ng.layout().addWidget(apply_nav_btn)
        self._nav2_lbl = _lbl('')
        ng.layout().addWidget(self._nav2_lbl)
        lay.addWidget(ng)

        # docking
        dcg = _grp('Charging / Docking')
        dcfl = QFormLayout(); dcfl.setSpacing(6)
        self._charging_pile = QLineEdit(s.get('charging_pile', 'charging_pile'))
        self._charging_pile.returnPressed.connect(self._save)
        self._dock_method = QComboBox()
        self._dock_method.addItems(['line_follow', 'nav2_waypoint', 'aruco'])
        cur = s.get('dock_method', 'line_follow')
        idx = self._dock_method.findText(cur)
        if idx >= 0:
            self._dock_method.setCurrentIndex(idx)
        dcfl.addRow('Approach waypoint:', self._charging_pile)
        dcfl.addRow('Dock method:', self._dock_method)
        dcg.layout().addLayout(dcfl)
        dcg.layout().addWidget(_lbl(
            'line_follow: magnetic line (line_follow.py)\n'
            'nav2_waypoint: navigate to <name>_dock waypoint\n'
            'aruco: ArUco marker docking (future)', '#888'))
        lay.addWidget(dcg)

        # storage — read-only, auto-resolved at startup, không lưu vào settings
        dg = _grp('Storage')
        dfl = QFormLayout(); dfl.setSpacing(6)
        from .node import _MAPS_DIR as _resolved_maps_dir
        self._maps_dir = QLineEdit(_resolved_maps_dir)
        self._maps_dir.setReadOnly(True)
        self._maps_dir.setStyleSheet('color: #888; background: #1a1a2e;')
        self._maps_dir.setToolTip('Đường dẫn tự động theo workspace, không cần chỉnh tay')
        dfl.addRow('Maps dir:', self._maps_dir)
        dg.layout().addLayout(dfl)
        lay.addWidget(dg)

        save_btn = QPushButton('Save Settings')
        save_btn.setStyleSheet(
            'QPushButton{'
            '  background:#4e6ea0;color:#fff;font-weight:bold;'
            '  border:none;border-radius:4px;padding:6px 14px;'
            '}'
            'QPushButton:hover{background:#6080bb;}'
            'QPushButton:pressed{background:#3a5280;}')
        save_btn.clicked.connect(self._save)
        self._save_lbl = _lbl('')
        lay.addWidget(save_btn)
        lay.addWidget(self._save_lbl)
        lay.addStretch()

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(_scroll_wrap(inner))

    def _test_conn(self):
        host = self._host.text().strip()
        self._win.api.host = host
        self._conn_lbl.setText('Testing…')

        def _cb(r):
            from PyQt5.QtCore import QMetaObject, Qt as Qt2
            self._conn_result = r
            QMetaObject.invokeMethod(self, '_show_conn_result', Qt2.QueuedConnection)

        self._win.api.get_async('/atlas/status', _cb)

    @pyqtSlot()
    def _show_conn_result(self):
        r = getattr(self, '_conn_result', None)
        if r:
            name = r.get('hostname', '') or 'robot'
            self._conn_lbl.setText(f'✓ Connected to {name}')
            self._conn_lbl.setStyleSheet('color:#60c060;font-size:11px;')
        else:
            self._conn_lbl.setText('✗ Connection failed')
            self._conn_lbl.setStyleSheet('color:#e05555;font-size:11px;')

    def _save(self):
        s = self._win.node.config.settings
        s['robot_host']         = self._host.text().strip()
        s['max_linear']         = self._max_v.value()
        s['max_angular']        = self._max_w.value()
        s['battery_charge_pct'] = self._bat_pct.value()
        s['inflation_radius']   = self._infl.value()
        s['xy_tolerance']       = self._xy_tol.value()
        s['yaw_tolerance']      = self._y_tol.value()
        s['charging_pile']      = self._charging_pile.text().strip() or 'charging_pile'
        s['dock_method']        = self._dock_method.currentText()
        self._win.node.config.save_settings()
        self._win.api.host = s['robot_host']
        # push velocity to nav2 via API so it takes effect immediately
        self._win.api.post_async(
            '/atlas/chassis/max_speed',
            {'speed': self._max_v.value(), 'angular': self._max_w.value()},
            lambda r: None,
        )
        # push dock settings to robot API
        self._win.api.post_async(
            '/atlas/settings',
            {'dock_method': s['dock_method'], 'charging_pile': s['charging_pile']},
            lambda r: None,
        )
        _log('Settings saved')
        self._save_lbl.setText('Settings saved')
        self._save_lbl.setStyleSheet('color:#60c060;font-size:11px;')
        QTimer.singleShot(3000, lambda: self._save_lbl.setText(''))

    def _apply_nav2(self):
        import subprocess, threading
        infl   = self._infl.value()
        xy_tol = self._xy_tol.value()
        y_tol  = self._y_tol.value()
        max_v  = self._max_v.value()
        max_w  = self._max_w.value()
        self._nav2_lbl.setText('Applying…')
        self._nav2_lbl.setStyleSheet('color:#aaa;font-size:11px;')
        cmds = [
            # DWB velocity limits
            ['ros2', 'param', 'set', '/controller_server',
             'FollowPath.max_vel_x', str(max_v)],
            ['ros2', 'param', 'set', '/controller_server',
             'FollowPath.max_speed_xy', str(max_v)],
            ['ros2', 'param', 'set', '/controller_server',
             'FollowPath.max_vel_theta', str(max_w)],
            ['ros2', 'param', 'set', '/velocity_smoother',
             'max_velocity', f'[{max_v}, 0.0, {max_w}]'],
            ['ros2', 'param', 'set', '/velocity_smoother',
             'min_velocity', f'[-{max_v}, 0.0, -{max_w}]'],
            # costmap & tolerance
            ['ros2', 'param', 'set', '/local_costmap/local_costmap',
             'inflation_layer.inflation_radius', str(infl)],
            ['ros2', 'param', 'set', '/global_costmap/global_costmap',
             'inflation_layer.inflation_radius', str(infl)],
            ['ros2', 'param', 'set', '/controller_server',
             'general_goal_checker.xy_goal_tolerance', str(xy_tol)],
            ['ros2', 'param', 'set', '/controller_server',
             'general_goal_checker.yaw_goal_tolerance', str(y_tol)],
        ]

        def _run():
            errors = []
            for cmd in cmds:
                try:
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                    if r.returncode != 0:
                        errors.append((cmd[4], r.stderr.strip() or 'failed'))
                except Exception as e:
                    errors.append((cmd[4], str(e)))
            from PyQt5.QtCore import QMetaObject, Qt as Qt2
            self._nav2_result = errors
            self._nav2_vals   = (max_v, max_w, infl, xy_tol, y_tol)
            QMetaObject.invokeMethod(self, '_show_nav2_result', Qt2.QueuedConnection)

        threading.Thread(target=_run, daemon=True).start()

    @pyqtSlot()
    def _show_nav2_result(self):
        errors = getattr(self, '_nav2_result', [])
        max_v, max_w, infl, xy_tol, y_tol = getattr(self, '_nav2_vals', (0, 0, 0, 0, 0))
        if errors:
            param, msg = errors[0]
            self._nav2_lbl.setText(f'Error ({param}): {msg[:50]}')
            self._nav2_lbl.setStyleSheet('color:#e05555;font-size:11px;')
        else:
            self._nav2_lbl.setText(
                f'Applied — {max_v:.2f} m/s  |  {max_w:.2f} r/s  |  infl {infl:.2f} m  |  tol {xy_tol:.2f}/{y_tol:.2f}')
            self._nav2_lbl.setStyleSheet('color:#60c060;font-size:11px;')
        _log(f'Nav2 params: max_v={max_v:.2f} max_w={max_w:.2f} inflation={infl:.2f} xy_tol={xy_tol:.2f}')

    def _test_auto_charge(self):
        from .node import _log
        _log('Test: manually triggering auto-charge sequence')
        self._win._auto_dock_triggered = True
        self._win._full_charge()

    def refresh(self, _node):
        pass


# ══════════════════════════════════════════════════════════════════════════ #
# VideoStreamPanel                                                           #
# ══════════════════════════════════════════════════════════════════════════ #

import urllib.request
import urllib.error
import re as _re
from PyQt5.QtCore import QThread, pyqtSignal as _Signal, QPoint
from PyQt5.QtWidgets import QProxyStyle, QStyle
from PyQt5.QtGui import QPainter as _QPainter, QPolygon as _QPolygon, QColor as _QColor

_DEFAULT_TOPICS = ['/inference_result', '/image_raw', '/yolo_image_raw']
_VIDEO_PORT = 6060

_CL_RE = _re.compile(rb'Content-Length:\s*(\d+)', _re.IGNORECASE)


class _ArrowStyle(QProxyStyle):
    """Draws a visible light-grey down-arrow for QComboBox on dark themes."""
    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PE_IndicatorArrowDown:
            painter.save()
            painter.setRenderHint(_QPainter.Antialiasing)
            r  = option.rect
            cx = r.center().x()
            cy = r.center().y()
            poly = _QPolygon([QPoint(cx - 4, cy - 2),
                              QPoint(cx + 4, cy - 2),
                              QPoint(cx,     cy + 3)])
            painter.setPen(Qt.NoPen)
            painter.setBrush(_QColor('#aaaaaa'))
            painter.drawPolygon(poly)
            painter.restore()
        else:
            super().drawPrimitive(element, option, painter, widget)


class _MjpegWorker(QThread):
    """QThread that reads a multipart/x-mixed-replace MJPEG stream."""
    frame_ready = _Signal(bytes)
    error       = _Signal(str)

    def __init__(self):
        super().__init__()
        self._url    = ''
        self._active = False

    def start_stream(self, url: str):
        if self.isRunning():
            self._active = False
            self.quit()
            self.wait(2000)
        self._url    = url
        self._active = True
        self.start()          # QThread.start() → calls run() in worker thread

    def stop_stream(self):
        self._active = False
        self.quit()
        self.wait(2000)

    def run(self):
        try:
            req = urllib.request.urlopen(self._url, timeout=8)
            buf = b''
            while self._active:
                chunk = req.read(4096)
                if not chunk:
                    break
                buf += chunk
                # Parse multipart frames using Content-Length header
                while self._active:
                    hdr_end = buf.find(b'\r\n\r\n')
                    if hdr_end == -1:
                        break
                    headers = buf[:hdr_end]
                    m = _CL_RE.search(headers)
                    if not m:
                        # No Content-Length — skip to next boundary
                        nxt = buf.find(b'--', hdr_end)
                        buf = buf[nxt:] if nxt != -1 else buf[hdr_end + 4:]
                        break
                    cl         = int(m.group(1))
                    data_start = hdr_end + 4
                    if len(buf) < data_start + cl:
                        break   # need more data
                    frame = buf[data_start:data_start + cl]
                    buf   = buf[data_start + cl:]
                    if self._active:
                        self.frame_ready.emit(frame)
        except Exception as e:
            if self._active:
                self.error.emit(str(e))


class VideoStreamPanel(QWidget):
    """MJPEG stream viewer at bottom of panel column; draggable to resize."""

    # Signal emitted from background thread → safely updates combo in main thread
    _topics_fetched = pyqtSignal(list)

    def __init__(self, video_host: str, parent=None):
        super().__init__(parent)
        self._video_host = video_host
        self._worker     = _MjpegWorker()
        self._worker.frame_ready.connect(self._on_frame)
        self._worker.error.connect(self._on_error)
        self._topics_fetched.connect(self._populate_combo)

        self._build_ui()
        QTimer.singleShot(800, self._fetch_topics)
        QTimer.singleShot(1200, lambda: self._change_topic(_DEFAULT_TOPICS[0]))

    # ── build ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.setMinimumHeight(40)
        self.setStyleSheet('background:#0f0f1a;')
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 3, 4, 3)
        lay.setSpacing(3)

        # Header: topic combo + refresh button
        hdr = QHBoxLayout()
        hdr.setSpacing(4)

        self._combo = QComboBox()
        self._combo.setEditable(True)
        self._combo.setInsertPolicy(QComboBox.NoInsert)
        for t in _DEFAULT_TOPICS:
            self._combo.addItem(t)
        self._combo.setCurrentText(_DEFAULT_TOPICS[0])
        # Hide native drop-down button — we provide our own ▼ button
        self._combo.setStyleSheet(
            'QComboBox{background:#1a1a2e;color:#ccc;border:1px solid #444;'
            'border-right:none;border-radius:3px 0 0 3px;padding:2px 6px;font-size:11px;}'
            'QComboBox::drop-down{width:0;border:none;}'
            'QComboBox QAbstractItemView{background:#1a1a2e;color:#ccc;'
            'selection-background-color:#2a2a4e;border:1px solid #555;}')
        self._combo.activated[str].connect(self._change_topic)
        hdr.addWidget(self._combo, 1)

        _btn_ss = ('QPushButton{background:#252540;color:#aaa;border:1px solid #444;'
                   'padding:0;font-size:11px;}'
                   'QPushButton:hover{background:#333366;color:#fff;}')

        arrow_btn = QPushButton('▼')
        arrow_btn.setFixedSize(18, 22)
        arrow_btn.setStyleSheet(_btn_ss + 'QPushButton{border-radius:0 3px 3px 0;}')
        arrow_btn.clicked.connect(self._combo.showPopup)
        hdr.addWidget(arrow_btn)

        refresh_btn = QPushButton('⟳')
        refresh_btn.setFixedSize(22, 22)
        refresh_btn.setToolTip('Refresh topic list from web_video_server')
        refresh_btn.setStyleSheet(_btn_ss + 'QPushButton{border-radius:3px;margin-left:3px;}')
        refresh_btn.clicked.connect(self._fetch_topics)
        hdr.addWidget(refresh_btn)

        lay.addLayout(hdr)

        # Video frame label
        self._frame_lbl = QLabel('No stream')
        self._frame_lbl.setAlignment(Qt.AlignCenter)
        self._frame_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._frame_lbl.setStyleSheet('color:#555;font-size:12px;background:#0a0a14;')
        self._frame_lbl.setMinimumHeight(20)
        lay.addWidget(self._frame_lbl, 1)

    # ── topic management ───────────────────────────────────────────────────

    def _base_url(self):
        ip = self._video_host.split(':')[0]
        return f'http://{ip}:{_VIDEO_PORT}'

    def _fetch_topics(self):
        def _run():
            try:
                html = urllib.request.urlopen(
                    self._base_url() + '/', timeout=3).read().decode('utf-8', errors='ignore')
                topics = sorted(set(_re.findall(r'topic=(/[^"&\s]+)', html)))
                if topics:
                    self._topics_fetched.emit(topics)   # safely crosses to main thread
            except Exception:
                pass
        threading.Thread(target=_run, daemon=True).start()

    def _populate_combo(self, topics: list):
        current = self._combo.currentText()
        self._combo.blockSignals(True)
        self._combo.clear()
        for t in topics:
            self._combo.addItem(t)
        idx = self._combo.findText(current)
        self._combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._combo.blockSignals(False)

    def _change_topic(self, topic: str):
        if not topic:
            return
        url = self._base_url() + f'/stream?topic={topic}&type=mjpeg'
        self._frame_lbl.setText('Connecting…')
        self._frame_lbl.setStyleSheet('color:#888;font-size:12px;background:#0a0a14;')
        self._worker.start_stream(url)

    # ── frame display ──────────────────────────────────────────────────────

    def _on_frame(self, data: bytes):
        pix = QPixmap()
        pix.loadFromData(data, 'JPEG')
        if pix.isNull():
            return
        lbl = self._frame_lbl
        scaled = pix.scaled(lbl.width(), lbl.height(),
                            Qt.KeepAspectRatio, Qt.SmoothTransformation)
        lbl.setPixmap(scaled)

    def _on_error(self, msg: str):
        self._frame_lbl.setText(f'Stream error\n{msg[:60]}')
        self._frame_lbl.setStyleSheet('color:#e05555;font-size:11px;background:#0a0a14;')

    def set_video_host(self, host: str):
        """Update host (called when settings change)."""
        self._video_host = host
        topic = self._combo.currentText()
        if topic:
            self._change_topic(topic)

    def closeEvent(self, event):
        self._worker.stop_stream()
        super().closeEvent(event)

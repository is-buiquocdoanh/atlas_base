import math
import numpy as np

from PyQt5.QtWidgets import QWidget, QLabel
from PyQt5.QtCore import Qt, QPoint, QPointF, pyqtSignal
from PyQt5.QtGui import (
    QPainter, QColor, QImage, QPen, QBrush, QPolygonF, QFont,
)

_AREA_FILL = {
    'forbidden': QColor(220, 50,  50,  80),
    'slow':      QColor(255, 200,  0,  80),
    'fast':      QColor(50,  200, 50,  80),
    'custom':    QColor(100, 100, 255, 80),
}
_AREA_BORDER = {
    'forbidden': QColor(220, 50,  50),
    'slow':      QColor(200, 160,  0),
    'fast':      QColor(50,  180, 50),
    'custom':    QColor(100, 100, 220),
}
_LEGEND = [
    (QColor(30,  160, 80),       'Robot'),
    (QColor(0,   200, 255),      'LiDAR'),
    (QColor(255, 165, 0),        'Global path'),
    (QColor(80,  140, 255),      'Waypoint'),
    (QColor(220,  60, 60),       'Virtual wall'),
    (QColor(220,  50, 50,  120), 'Forbidden'),
    (QColor(255, 200,  0,  120), 'Slow zone'),
    (QColor(50,  200, 50,  120), 'Fast zone'),
    (QColor(255, 200,  0),       'Goal'),
]


class MapWidget(QWidget):
    goal_selected      = pyqtSignal(float, float, float)
    pose_selected      = pyqtSignal(float, float, float)
    wall_drawn         = pyqtSignal(list)
    area_drawn         = pyqtSignal(list)
    drawing_cancelled  = pyqtSignal()

    MODE_DRAG     = 'drag'
    MODE_NAV_GOAL = 'nav_goal'
    MODE_SET_POSE = 'set_pose'
    MODE_WALL     = 'wall'
    MODE_POLYGON  = 'polygon'
    MODE_MEASURE  = 'measure'

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 400)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self._zoom   = 50.0
        self._pan_x  = 0.0
        self._pan_y  = 0.0
        self._drag_anchor: QPoint = None

        self._map_img    = None
        self._map_origin = (0.0, 0.0)
        self._map_res    = 0.05
        self._map_w      = 0
        self._map_h      = 0

        self._scan_points:    list  = []
        self._robot_pose:     tuple = (0.0, 0.0, 0.0)
        self._plan_poses:     list  = []
        self._waypoints:      list  = []   # [(x, y, label, yaw), ...]
        self._route_waypoints:list  = []   # [(x, y, yaw), ...] ordered route
        self._virtual_walls:  list  = []   # [[(x,y), ...], ...]
        self._special_areas:  list  = []   # [{'type','name','polygon'}, ...]
        self._goal_marker:    tuple = None # (x, y)

        self._mode              = self.MODE_DRAG
        self._mouse_down_world  = None
        self._mouse_pos_world   = (0.0, 0.0)
        self._drawing_poly:list = []

        # SET_POSE interactive placement state
        self._pose_preview    = None   # {'x', 'y', 'yaw'} once placed
        self._pose_anchor     = None   # (wx, wy) click point for initial drag
        self._pose_drag_mode  = None   # 'initial_yaw' | 'move' | 'yaw'

        # MEASURE state
        self._measure_start: tuple = None   # (wx, wy) first click
        self._measure_end:   tuple = None   # (wx, wy) second click or live mouse
        self._measure_fixed: bool  = False  # True after second click (frozen)

        # launch process status (updated from main window)
        self._launch_status: dict = {'slam': False, 'map_server': False, 'nav': False}

        self._coord_lbl = QLabel('', self)
        self._coord_lbl.setStyleSheet(
            'background:rgba(0,0,0,160);color:#adf;padding:2px 6px;border-radius:3px;font-size:11px;')
        self._coord_lbl.move(8, 8)

    # ------------------------------------------------------------------ #
    # public API                                                           #
    # ------------------------------------------------------------------ #

    def set_mode(self, mode: str):
        self._mode = mode
        self._drawing_poly    = []
        self._pose_preview    = None
        self._pose_anchor     = None
        self._pose_drag_mode  = None
        self._mouse_down_world = None
        self._measure_start   = None
        self._measure_end     = None
        self._measure_fixed   = False
        cursors = {
            self.MODE_DRAG:     Qt.OpenHandCursor,
            self.MODE_NAV_GOAL: Qt.CrossCursor,
            self.MODE_SET_POSE: Qt.CrossCursor,
            self.MODE_WALL:     Qt.CrossCursor,
            self.MODE_POLYGON:  Qt.CrossCursor,
            self.MODE_MEASURE:  Qt.CrossCursor,
        }
        self.setCursor(cursors.get(mode, Qt.ArrowCursor))
        self.update()

    def set_goal_marker(self, x: float, y: float):
        self._goal_marker = (x, y)
        self.update()

    def clear_goal_marker(self):
        self._goal_marker = None
        self.update()

    def update_map(self, grid):
        if grid is None:
            return
        info = grid.info
        w, h = info.width, info.height
        data = np.array(grid.data, dtype=np.int8).reshape((h, w))
        img = np.full((h, w, 4), 100, dtype=np.uint8)
        img[data == 0]   = [245, 245, 245, 255]
        img[data == 100] = [25,  25,  25,  255]
        img[(data > 0) & (data < 100)] = [180, 180, 180, 255]
        img[data == -1]  = [100, 100, 100, 200]
        img = np.flipud(img)
        self._map_img    = QImage(img.tobytes(), w, h, w * 4,
                                  QImage.Format_RGBA8888).copy()
        self._map_origin = (info.origin.position.x, info.origin.position.y)
        self._map_res    = info.resolution
        self._map_w, self._map_h = w, h
        self.update()

    def update_scan(self, pts):
        self._scan_points = pts
        self.update()

    def update_robot_pose(self, pose):
        self._robot_pose = pose
        self.update()

    def update_plan(self, poses):
        self._plan_poses = poses
        self.update()

    def set_waypoints(self, wps):
        self._waypoints = [(p['x'], p['y'], p.get('name', ''), p.get('yaw', 0.0)) for p in wps]
        self.update()

    def set_route_waypoints(self, wps):
        self._route_waypoints = [(p['x'], p['y'], p.get('yaw', 0.0)) for p in wps]
        self.update()

    def set_virtual_walls(self, walls):
        self._virtual_walls = walls
        self.update()

    def add_virtual_wall(self, pts):
        self._virtual_walls.append(pts)
        self.update()

    def clear_virtual_walls(self):
        self._virtual_walls = []
        self.update()

    def set_special_areas(self, areas):
        self._special_areas = areas
        self.update()

    def update_launch_status(self, status: dict):
        if status != self._launch_status:
            self._launch_status = dict(status)
            self.update()

    def fit_map(self):
        if not self._map_w:
            return
        map_w_m = self._map_w * self._map_res
        map_h_m = self._map_h * self._map_res
        self._zoom = min(self.width() / map_w_m, self.height() / map_h_m) * 0.9
        cx = self._map_origin[0] + map_w_m / 2
        cy = self._map_origin[1] + map_h_m / 2
        self._pan_x = self.width()  / 2 - cx * self._zoom
        self._pan_y = self.height() / 2 + cy * self._zoom
        self.update()

    # ------------------------------------------------------------------ #
    # coordinates                                                          #
    # ------------------------------------------------------------------ #

    def _w2c(self, wx, wy) -> QPointF:
        return QPointF(wx * self._zoom + self._pan_x,
                       -wy * self._zoom + self._pan_y)

    def _c2w(self, cx, cy) -> tuple:
        return ((cx - self._pan_x) / self._zoom,
                -(cy - self._pan_y) / self._zoom)

    # ------------------------------------------------------------------ #
    # paint                                                                #
    # ------------------------------------------------------------------ #

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(42, 42, 42))
        self._draw_map(p)
        self._draw_special_areas(p)
        self._draw_virtual_walls(p)
        self._draw_plan(p)
        self._draw_scan(p)
        self._draw_route(p)
        self._draw_waypoints(p)
        self._draw_robot(p)
        self._draw_goal_marker(p)
        self._draw_pose_preview(p)
        self._draw_poly_in_progress(p)
        self._draw_measure(p)
        self._draw_legend(p)
        self._draw_launch_status(p)

    def _draw_map(self, p):
        if self._map_img is None:
            return
        ox, oy = self._map_origin
        pw = int(self._map_w * self._map_res * self._zoom)
        ph = int(self._map_h * self._map_res * self._zoom)
        tl = self._w2c(ox, oy + self._map_h * self._map_res)
        p.drawImage(
            tl.toPoint(),
            self._map_img.scaled(pw, ph, Qt.IgnoreAspectRatio,
                                 Qt.SmoothTransformation))

    def _draw_scan(self, p):
        if not self._scan_points:
            return
        rx, ry, ryaw = self._robot_pose
        p.setPen(QPen(QColor(0, 200, 255, 200), 2))
        for lx, ly in self._scan_points:
            mx = rx + lx * math.cos(ryaw) - ly * math.sin(ryaw)
            my = ry + lx * math.sin(ryaw) + ly * math.cos(ryaw)
            p.drawPoint(self._w2c(mx, my).toPoint())

    def _draw_robot(self, p):
        rx, ry, ryaw = self._robot_pose
        c = self._w2c(rx, ry)
        r = max(6.0, 0.2 * self._zoom)
        p.setBrush(QBrush(QColor(30, 160, 80)))
        p.setPen(QPen(QColor(255, 255, 255), 1.5))
        p.drawEllipse(c, r, r)
        tip = QPointF(c.x() + r * 1.8 * math.cos(-ryaw),
                      c.y() + r * 1.8 * math.sin(-ryaw))
        p.setPen(QPen(QColor(255, 255, 255), 2))
        p.drawLine(c.toPoint(), tip.toPoint())

    def _draw_goal_marker(self, p):
        if self._goal_marker is None:
            return
        c = self._w2c(*self._goal_marker)
        r = max(8.0, 0.15 * self._zoom)
        p.setBrush(QBrush(QColor(255, 200, 0, 160)))
        p.setPen(QPen(QColor(255, 200, 0), 2))
        p.drawEllipse(c, r, r)
        p.drawLine(QPointF(c.x() - r, c.y()), QPointF(c.x() + r, c.y()))
        p.drawLine(QPointF(c.x(), c.y() - r), QPointF(c.x(), c.y() + r))

    def _draw_plan(self, p):
        if len(self._plan_poses) < 2:
            return
        p.setPen(QPen(QColor(255, 165, 0, 220), 2))
        pts = [self._w2c(x, y) for x, y in self._plan_poses]
        for i in range(len(pts) - 1):
            p.drawLine(pts[i].toPoint(), pts[i + 1].toPoint())

    def _draw_waypoints(self, p):
        p.setFont(QFont('Sans', 9))
        for i, (wx, wy, label, yaw) in enumerate(self._waypoints):
            c   = self._w2c(wx, wy)
            arr = max(12.0, 0.18 * self._zoom)
            tip = QPointF(c.x() + arr * math.cos(-yaw),
                          c.y() + arr * math.sin(-yaw))
            p.setPen(QPen(QColor(160, 200, 255), 1.5))
            p.drawLine(c.toPoint(), tip.toPoint())
            self._draw_arrowhead(p, c, tip, QColor(160, 200, 255), 5)
            p.setBrush(QBrush(QColor(80, 140, 255)))
            p.setPen(QPen(QColor(255, 255, 255), 1))
            p.drawEllipse(c, 7, 7)
            p.setPen(QPen(QColor(200, 220, 255)))
            p.drawText(int(c.x()) + 10, int(c.y()) + 4, label or f'P{i+1}')

    def _draw_virtual_walls(self, p):
        p.setPen(QPen(QColor(220, 60, 60), 2, Qt.DashLine))
        for wall in self._virtual_walls:
            pts = [self._w2c(x, y).toPoint() for x, y in wall]
            for i in range(len(pts) - 1):
                p.drawLine(pts[i], pts[i + 1])

    def _draw_special_areas(self, p):
        p.setFont(QFont('Sans', 8))
        for area in self._special_areas:
            atype = area.get('type', 'custom')
            poly  = area.get('polygon', [])
            if len(poly) < 3:
                continue
            qpoly = QPolygonF([self._w2c(x, y) for x, y in poly])
            p.setBrush(QBrush(_AREA_FILL.get(atype, _AREA_FILL['custom'])))
            p.setPen(QPen(_AREA_BORDER.get(atype, _AREA_BORDER['custom']), 1.5))
            p.drawPolygon(qpoly)
            cx = sum(x for x, y in poly) / len(poly)
            cy = sum(y for x, y in poly) / len(poly)
            cc = self._w2c(cx, cy)
            p.setPen(QPen(_AREA_BORDER.get(atype, _AREA_BORDER['custom'])))
            p.drawText(cc.toPoint(), area.get('name', atype))

    def _draw_poly_in_progress(self, p):
        if self._mode not in (self.MODE_WALL, self.MODE_POLYGON):
            return
        is_wall  = self._mode == self.MODE_WALL
        color    = QColor(220,  80,  80) if is_wall else QColor(100, 160, 255)
        dot_col  = QColor(255, 120, 120) if is_wall else QColor(140, 190, 255)

        pts     = [self._w2c(x, y) for x, y in self._drawing_poly]
        mx, my  = self._mouse_pos_world
        mouse_c = self._w2c(mx, my)

        # solid lines between placed points
        if len(pts) >= 2:
            p.setPen(QPen(color, 2))
            for i in range(len(pts) - 1):
                p.drawLine(pts[i].toPoint(), pts[i + 1].toPoint())

        # dashed rubber-band from last placed point → mouse cursor
        if pts:
            dash = QPen(color, 2, Qt.DashLine)
            dash.setDashPattern([6, 4])
            p.setPen(dash)
            p.drawLine(pts[-1].toPoint(), mouse_c.toPoint())

        # for polygon: dotted close-preview from mouse back to first point
        if not is_wall and len(pts) >= 2:
            p.setPen(QPen(color, 1, Qt.DotLine))
            p.drawLine(mouse_c.toPoint(), pts[0].toPoint())

        # dots at each placed vertex
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(dot_col))
        for pt in pts:
            p.drawEllipse(pt, 4, 4)

        # small circle at cursor to show where next point would land
        p.setPen(QPen(color, 1.5))
        p.setBrush(QBrush(QColor(255, 255, 255, 100)))
        p.drawEllipse(mouse_c, 4, 4)

    def _draw_launch_status(self, p):
        items = [
            ('SLAM',       self._launch_status.get('slam',       False)),
            ('Nav',        self._launch_status.get('nav',        False)),
            ('Map Server', self._launch_status.get('map_server', False)),
        ]
        p.setFont(QFont('Sans', 9, QFont.Bold))
        row_h, pad, w = 20, 6, 106
        x0 = pad
        y0 = self.height() - len(items) * row_h - pad * 2
        p.fillRect(x0, y0, w, len(items) * row_h + pad,
                   QColor(0, 0, 0, 150))
        for i, (label, running) in enumerate(items):
            y = y0 + pad // 2 + i * row_h
            dot_color = QColor(60, 200, 80) if running else QColor(80, 80, 80)
            p.setBrush(QBrush(dot_color))
            p.setPen(Qt.NoPen)
            p.drawEllipse(x0 + 6, y + 5, 10, 10)
            p.setPen(QPen(QColor(210, 210, 210) if running else QColor(120, 120, 120)))
            p.drawText(x0 + 22, y + 14, label)

    def _draw_measure(self, p):
        if self._measure_start is None or self._measure_end is None:
            if self._measure_start is not None:
                # Show start dot only
                ca = self._w2c(*self._measure_start)
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(QColor(255, 220, 0)))
                p.drawEllipse(ca, 5, 5)
            return

        ax, ay = self._measure_start
        bx, by = self._measure_end
        ca = self._w2c(ax, ay)
        cb = self._w2c(bx, by)
        dist = math.hypot(bx - ax, by - ay)

        line_color = QColor(255, 220, 0) if self._measure_fixed else QColor(255, 220, 0, 200)
        pen = QPen(line_color, 2, Qt.SolidLine if self._measure_fixed else Qt.DashLine)
        if not self._measure_fixed:
            pen.setDashPattern([8, 4])
        p.setPen(pen)
        p.drawLine(ca.toPoint(), cb.toPoint())

        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(255, 220, 0)))
        p.drawEllipse(ca, 5, 5)
        p.drawEllipse(cb, 5, 5)

        mid = QPointF((ca.x() + cb.x()) / 2, (ca.y() + cb.y()) / 2)
        text = f'{dist:.2f} m'
        p.setFont(QFont('Sans', 10, QFont.Bold))
        tx, ty = mid.x() + 10, mid.y() - 4
        p.setPen(QPen(QColor(0, 0, 0, 200)))
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            p.drawText(QPointF(tx + dx, ty + dy), text)
        p.setPen(QPen(QColor(255, 240, 100)))
        p.drawText(QPointF(tx, ty), text)

    def _draw_pose_preview(self, p):
        # ── NAV_GOAL simple arrow ─────────────────────────────────────────
        if self._mode == self.MODE_NAV_GOAL and self._mouse_down_world:
            ax, ay = self._mouse_down_world
            mx, my = self._mouse_pos_world
            c0 = self._w2c(ax, ay)
            c1 = self._w2c(mx, my)
            col = QColor(255, 200, 0)
            p.setBrush(QBrush(col)); p.setPen(QPen(QColor(255,255,255), 1.5))
            p.drawEllipse(c0, 5, 5)
            p.setPen(QPen(col, 2, Qt.DashLine))
            p.drawLine(c0.toPoint(), c1.toPoint())
            self._draw_arrowhead(p, c0, c1, col, 9)
            return

        if self._mode != self.MODE_SET_POSE:
            return

        # ── Phase 1: initial click+drag (rubber-band yaw) ─────────────────
        if self._pose_drag_mode == 'initial_yaw' and self._pose_anchor:
            ax, ay = self._pose_anchor
            mx, my = self._mouse_pos_world
            c0 = self._w2c(ax, ay)
            c1 = self._w2c(mx, my)
            col = QColor(80, 220, 140)

            # anchor dot
            p.setBrush(QBrush(col))
            p.setPen(QPen(QColor(255, 255, 255), 1.5))
            p.drawEllipse(c0, 5, 5)

            # dashed rubber-band line
            dash = QPen(col, 2, Qt.DashLine)
            dash.setDashPattern([6, 4])
            p.setPen(dash)
            p.drawLine(c0.toPoint(), c1.toPoint())

            # arrowhead at drag end
            if math.hypot(mx - ax, my - ay) > 0.01:
                self._draw_arrowhead(p, c0, c1, col, 10)

        # ── Phase 2: marker placed, draggable ─────────────────────────────
        if self._pose_preview is not None:
            px, py = self._pose_preview['x'], self._pose_preview['y']
            pyaw   = self._pose_preview['yaw']
            c = self._w2c(px, py)
            r   = max(8.0, 0.16 * self._zoom)
            arr = max(22.0, 0.32 * self._zoom)
            col = QColor(80, 220, 140)

            # dashed outer ring (indicates draggable)
            ring = QPen(QColor(80, 220, 140, 160), 1.5, Qt.DashLine)
            p.setPen(ring); p.setBrush(Qt.NoBrush)
            p.drawEllipse(c, r + 5, r + 5)

            # filled body
            p.setBrush(QBrush(QColor(80, 220, 140, 210)))
            p.setPen(QPen(QColor(255, 255, 255), 1.5))
            p.drawEllipse(c, r, r)

            # direction shaft
            tip = QPointF(c.x() + arr * math.cos(-pyaw),
                          c.y() + arr * math.sin(-pyaw))
            p.setPen(QPen(col, 2.5))
            p.drawLine(c.toPoint(), tip.toPoint())
            self._draw_arrowhead(p, c, tip, col, 9)

            # yaw-handle circle (drag to rotate)
            p.setBrush(QBrush(QColor(255, 255, 255, 200)))
            p.setPen(QPen(col, 1.5))
            p.drawEllipse(tip, 5, 5)

    def _draw_route(self, p):
        if not self._route_waypoints:
            return
        col_line = QColor(255, 160, 30, 210)
        col_dot  = QColor(255, 140, 0,  230)
        pts = [self._w2c(x, y) for x, y, _ in self._route_waypoints]
        p.setFont(QFont('Sans', 8, QFont.Bold))

        # dashed connecting lines + mid-arrow
        dash = QPen(col_line, 2, Qt.DashLine)
        dash.setDashPattern([8, 4])
        for i in range(len(pts) - 1):
            p.setPen(dash)
            p.drawLine(pts[i].toPoint(), pts[i + 1].toPoint())
            # arrowhead at midpoint pointing toward next
            mid = QPointF((pts[i].x() + pts[i+1].x()) / 2,
                          (pts[i].y() + pts[i+1].y()) / 2)
            self._draw_arrowhead(p, pts[i], mid, col_line, 7)

        # numbered circles at each waypoint
        for i, (x, y, yaw) in enumerate(self._route_waypoints):
            c = self._w2c(x, y)
            r = max(9.0, 0.14 * self._zoom)
            p.setBrush(QBrush(col_dot))
            p.setPen(QPen(QColor(255, 255, 255), 1.5))
            p.drawEllipse(c, r, r)
            # yaw tick
            arr = r + max(7.0, 0.1 * self._zoom)
            tip = QPointF(c.x() + arr * math.cos(-yaw),
                          c.y() + arr * math.sin(-yaw))
            p.setPen(QPen(col_line, 1.5))
            p.drawLine(c.toPoint(), tip.toPoint())
            # sequence number
            p.setPen(QPen(QColor(255, 255, 255)))
            num = str(i + 1)
            p.drawText(int(c.x()) - (3 if len(num) == 1 else 5),
                       int(c.y()) + 4, num)

    def _draw_arrowhead(self, p, c_from: QPointF, c_tip: QPointF, color, size: int = 8):
        ang = math.atan2(c_tip.y() - c_from.y(), c_tip.x() - c_from.x())
        p.setPen(QPen(color, 2))
        p.drawLine(c_tip.toPoint(),
                   QPointF(c_tip.x() - size * math.cos(ang - 0.38),
                           c_tip.y() - size * math.sin(ang - 0.38)).toPoint())
        p.drawLine(c_tip.toPoint(),
                   QPointF(c_tip.x() - size * math.cos(ang + 0.38),
                           c_tip.y() - size * math.sin(ang + 0.38)).toPoint())

    def _draw_legend(self, p):
        p.setFont(QFont('Sans', 8))
        x0 = self.width() - 132
        y0 = 10
        p.fillRect(x0 - 6, y0 - 6, 132, len(_LEGEND) * 18 + 12,
                   QColor(0, 0, 0, 140))
        for i, (color, label) in enumerate(_LEGEND):
            y = y0 + i * 18
            p.setBrush(QBrush(color))
            p.setPen(Qt.NoPen)
            p.drawEllipse(x0, y + 1, 10, 10)
            p.setPen(QPen(QColor(210, 210, 210)))
            p.drawText(x0 + 14, y + 10, label)

    # ------------------------------------------------------------------ #
    # mouse                                                                #
    # ------------------------------------------------------------------ #

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            wx, wy = self._c2w(event.x(), event.y())
            if self._mode == self.MODE_DRAG:
                self._drag_anchor = event.pos()
                self.setCursor(Qt.ClosedHandCursor)
            elif self._mode == self.MODE_NAV_GOAL:
                self._mouse_down_world = (wx, wy)
            elif self._mode == self.MODE_SET_POSE:
                self._start_pose_interaction(event.x(), event.y(), wx, wy)
            elif self._mode in (self.MODE_WALL, self.MODE_POLYGON):
                self._drawing_poly.append((wx, wy))
                self.update()
            elif self._mode == self.MODE_MEASURE:
                if self._measure_start is None or self._measure_fixed:
                    self._measure_start = (wx, wy)
                    self._measure_end   = None
                    self._measure_fixed = False
                else:
                    self._measure_end   = (wx, wy)
                    self._measure_fixed = True
                self.update()
        elif event.button() == Qt.RightButton:
            if self._mode == self.MODE_MEASURE:
                self._measure_start = None
                self._measure_end   = None
                self._measure_fixed = False
                self.update()
            elif self._mode in (self.MODE_WALL, self.MODE_POLYGON):
                self._cancel_poly()

    def _start_pose_interaction(self, cx, cy, wx, wy):
        if self._pose_preview is not None:
            px, py = self._pose_preview['x'], self._pose_preview['y']
            pyaw   = self._pose_preview['yaw']
            pc     = self._w2c(px, py)
            r_hit  = max(14.0, 0.22 * self._zoom)
            if math.hypot(cx - pc.x(), cy - pc.y()) < r_hit:
                self._pose_drag_mode   = 'move'
                self._mouse_down_world = (wx, wy)
                self.setCursor(Qt.ClosedHandCursor)
                return
            arr  = max(22.0, 0.32 * self._zoom)
            tx   = pc.x() + arr * math.cos(-pyaw)
            ty   = pc.y() + arr * math.sin(-pyaw)
            if math.hypot(cx - tx, cy - ty) < 12:
                self._pose_drag_mode   = 'yaw'
                self._mouse_down_world = (wx, wy)
                self.setCursor(Qt.SizeAllCursor)
                return
        # Start fresh placement
        self._pose_preview   = None
        self._pose_anchor    = (wx, wy)
        self._pose_drag_mode = 'initial_yaw'
        self._mouse_down_world = (wx, wy)
        self.update()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._finish_poly()

    def _finish_poly(self):
        if self._mode == self.MODE_WALL and len(self._drawing_poly) >= 2:
            self.wall_drawn.emit(list(self._drawing_poly))
            self._drawing_poly = []
            self.update()
        elif self._mode == self.MODE_POLYGON and len(self._drawing_poly) >= 3:
            self.area_drawn.emit(list(self._drawing_poly))
            self._drawing_poly = []
            self.update()

    def _cancel_poly(self):
        self._drawing_poly = []
        self.drawing_cancelled.emit()
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._mode == self.MODE_DRAG:
                self._drag_anchor = None
                self.setCursor(Qt.OpenHandCursor)
            elif self._mode == self.MODE_NAV_GOAL:
                if self._mouse_down_world is not None:
                    wx0, wy0 = self._mouse_down_world
                    wx1, wy1 = self._c2w(event.x(), event.y())
                    yaw = math.atan2(wy1 - wy0, wx1 - wx0)
                    self.goal_selected.emit(wx0, wy0, yaw)
                    self._mouse_down_world = None
            elif self._mode == self.MODE_SET_POSE:
                self._finish_pose_interaction(event.x(), event.y())

    def _finish_pose_interaction(self, cx, cy):
        wx, wy = self._c2w(cx, cy)
        if self._pose_drag_mode == 'initial_yaw' and self._pose_anchor:
            ax, ay = self._pose_anchor
            yaw = math.atan2(wy - ay, wx - ax) if math.hypot(wx-ax, wy-ay) > 1e-4 else 0.0
            self._pose_preview = {'x': ax, 'y': ay, 'yaw': yaw}
            self.pose_selected.emit(ax, ay, yaw)
        self._pose_drag_mode   = None
        self._mouse_down_world = None
        self.setCursor(Qt.CrossCursor)
        self.update()

    def mouseMoveEvent(self, event):
        wx, wy = self._c2w(event.x(), event.y())
        self._coord_lbl.setText(f'x: {wx:.2f}  y: {wy:.2f}')
        self._coord_lbl.adjustSize()
        self._mouse_pos_world = (wx, wy)

        if self._mode == self.MODE_DRAG and self._drag_anchor is not None:
            d = event.pos() - self._drag_anchor
            self._pan_x += d.x()
            self._pan_y += d.y()
            self._drag_anchor = event.pos()
            self.update()
        elif self._mode == self.MODE_NAV_GOAL:
            self.update()
        elif self._mode == self.MODE_SET_POSE:
            if self._pose_drag_mode == 'move' and self._pose_preview:
                self._pose_preview['x'] = wx
                self._pose_preview['y'] = wy
                self.pose_selected.emit(wx, wy, self._pose_preview['yaw'])
            elif self._pose_drag_mode == 'yaw' and self._pose_preview:
                px, py = self._pose_preview['x'], self._pose_preview['y']
                yaw = math.atan2(wy - py, wx - px)
                self._pose_preview['yaw'] = yaw
                self.pose_selected.emit(px, py, yaw)
            elif self._pose_drag_mode is None and self._pose_preview:
                # Hover: update cursor based on proximity
                px, py  = self._pose_preview['x'], self._pose_preview['y']
                pyaw    = self._pose_preview['yaw']
                pc      = self._w2c(px, py)
                r_hit   = max(14.0, 0.22 * self._zoom)
                arr     = max(22.0, 0.32 * self._zoom)
                tx = pc.x() + arr * math.cos(-pyaw)
                ty = pc.y() + arr * math.sin(-pyaw)
                if math.hypot(event.x()-pc.x(), event.y()-pc.y()) < r_hit:
                    self.setCursor(Qt.OpenHandCursor)
                elif math.hypot(event.x()-tx, event.y()-ty) < 12:
                    self.setCursor(Qt.SizeAllCursor)
                else:
                    self.setCursor(Qt.CrossCursor)
            self.update()
        elif self._mode in (self.MODE_WALL, self.MODE_POLYGON):
            self.update()
        elif self._mode == self.MODE_MEASURE:
            if self._measure_start is not None and not self._measure_fixed:
                self._measure_end = (wx, wy)
            self.update()

    def wheelEvent(self, event):
        f = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        mx, my = self._c2w(event.x(), event.y())
        self._zoom  *= f
        self._pan_x  = event.x() - mx * self._zoom
        self._pan_y  = event.y() + my * self._zoom
        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            if self._mode in (self.MODE_WALL, self.MODE_POLYGON):
                self._cancel_poly()
            elif self._mode == self.MODE_MEASURE:
                self._measure_start = None
                self._measure_end   = None
                self._measure_fixed = False
                self.update()
            else:
                self.update()

import threading
import math
import time
import subprocess
import json
import os
from collections import deque
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy

from nav_msgs.msg import OccupancyGrid, Odometry, Path
from sensor_msgs.msg import LaserScan, BatteryState, Imu
from geometry_msgs.msg import Twist, PoseWithCovarianceStamped
from std_msgs.msg import Bool
from nav2_msgs.action import NavigateToPose

import tf2_ros


_CONFIG_DIR = os.path.expanduser('~/.config/atlas_app')


def _resolve_maps_dir() -> str:
    """Locate atlas_maps directory inside atlas_base."""
    try:
        from ament_index_python.packages import get_package_share_directory
        pkg_dir = get_package_share_directory('atlas_slam')
        ws_dir  = os.path.abspath(os.path.join(pkg_dir, '..', '..', '..', '..'))
        for candidate in ['src/atlas_base/atlas_maps', 'src/atlas_maps']:
            d = os.path.join(ws_dir, candidate)
            if os.path.isdir(d):
                return d
    except Exception:
        pass
    return os.path.expanduser('~/.atlas/maps')


_MAPS_DIR = _resolve_maps_dir()

_MAP_QOS = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
    depth=1,
)
_SENSOR_QOS = QoSProfile(
    reliability=ReliabilityPolicy.BEST_EFFORT,
    durability=DurabilityPolicy.VOLATILE,
    depth=5,
)

app_log: deque = deque(maxlen=1000)


def _log(msg: str):
    ts = time.strftime('%H:%M:%S')
    entry = f'[{ts}] {msg}'
    app_log.append(entry)


class AppConfig:
    def __init__(self):
        os.makedirs(_CONFIG_DIR, exist_ok=True)
        self.positions = self._load('positions.json', [])
        self.walls = self._load('walls.json', [])
        self.areas = self._load('areas.json', [])
        self.settings = self._load('settings.json', {
            'robot_host': 'localhost:8080',
            'max_linear': 0.5,
            'max_angular': 1.0,
            'battery_charge_pct': 20.0,
            'inflation_radius': 0.3,
            'xy_tolerance': 0.25,
            'yaw_tolerance': 0.2,
            'maps_dir': _MAPS_DIR,
        })

    def _load(self, name, default):
        path = os.path.join(_CONFIG_DIR, name)
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return default

    def _save(self, name, data):
        path = os.path.join(_CONFIG_DIR, name)
        try:
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            _log(f'Config save error: {e}')

    def save_positions(self): self._save('positions.json', self.positions)
    def save_walls(self):     self._save('walls.json', self.walls)
    def save_areas(self):     self._save('areas.json', self.areas)
    def save_settings(self):  self._save('settings.json', self.settings)


class AtlasNode(Node):
    def __init__(self):
        super().__init__('atlas_app')
        self._lock = threading.Lock()
        self.config = AppConfig()

        # state
        self._map: Optional[OccupancyGrid] = None
        self._scan_points: list = []
        self._robot_pose: tuple = (0.0, 0.0, 0.0)
        self._battery_pct: float = -1.0
        self._emergency_stop: bool = False
        self._plan_poses: list = []
        self._nav_state: str = 'idle'
        self._speed_lin: float = 0.0
        self._speed_ang: float = 0.0
        self._laser_ts: float = 0.0
        self._imu_ts: float = 0.0

        # costmap data
        self._local_costmap:  Optional[OccupancyGrid] = None
        self._global_costmap: Optional[OccupancyGrid] = None

        # route
        self._route_queue: list = []
        self._route_backup: list = []
        self._route_loop: bool = False
        self._route_active: bool = False

        # Launch subprocesses (slam / map_server / navigation)
        self._slam_proc       = None
        self._map_server_proc = None
        self._nav_proc        = None

        # subscriptions
        self.create_subscription(OccupancyGrid, '/map', self._on_map, _MAP_QOS)
        self.create_subscription(LaserScan, '/atlas/scan_filtered', self._on_scan, _SENSOR_QOS)
        self.create_subscription(Odometry, '/atlas/odom', self._on_odom, _SENSOR_QOS)
        self.create_subscription(BatteryState, '/atlas/battery', self._on_battery, _SENSOR_QOS)
        self.create_subscription(Bool, '/atlas/emergency_stop', self._on_estop, _SENSOR_QOS)
        self.create_subscription(Path, '/plan', self._on_plan, _SENSOR_QOS)
        self.create_subscription(Imu, '/atlas/imu', self._on_imu, _SENSOR_QOS)
        self.create_subscription(OccupancyGrid, '/local_costmap/costmap',
                                 self._on_local_costmap, _SENSOR_QOS)
        self.create_subscription(OccupancyGrid, '/global_costmap/costmap',
                                 self._on_global_costmap, _SENSOR_QOS)

        # publishers
        self._cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self._init_pose_pub = self.create_publisher(
            PoseWithCovarianceStamped, '/initialpose', 10)

        # TF2
        self._tf_buffer = tf2_ros.Buffer()
        self._tf_listener = tf2_ros.TransformListener(self._tf_buffer, self)

        # Nav2 action
        self._nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self._nav_goal_handle = None

    # ------------------------------------------------------------------ #
    # callbacks                                                            #
    # ------------------------------------------------------------------ #

    def _on_map(self, msg):
        with self._lock:
            self._map = msg

    def _on_scan(self, msg: LaserScan):
        self._laser_ts = time.time()
        pts = []
        angle = msg.angle_min
        for r in msg.ranges:
            if msg.range_min <= r <= msg.range_max:
                pts.append((r * math.cos(angle), r * math.sin(angle)))
            angle += msg.angle_increment
        # Transform scan from sensor frame → base_link so _draw_scan can apply
        # robot yaw correctly (avoids mismatch when laser is rotated in URDF).
        pts = self._scan_to_base(pts, msg.header.frame_id)
        with self._lock:
            self._scan_points = pts

    def _scan_to_base(self, pts: list, frame_id: str) -> list:
        """Rotate scan points from sensor frame into base_link frame (2D only)."""
        if frame_id == 'base_link':
            return pts
        try:
            t = self._tf_buffer.lookup_transform(
                'base_link', frame_id, rclpy.time.Time())
            tr = t.transform.translation
            q  = t.transform.rotation
            yaw = math.atan2(
                2.0 * (q.w * q.z + q.x * q.y),
                1.0 - 2.0 * (q.y * q.y + q.z * q.z))
            cos_y, sin_y = math.cos(yaw), math.sin(yaw)
            return [
                (tr.x + lx * cos_y - ly * sin_y,
                 tr.y + lx * sin_y + ly * cos_y)
                for lx, ly in pts
            ]
        except Exception:
            return pts

    def _on_odom(self, msg: Odometry):
        with self._lock:
            self._speed_lin = msg.twist.twist.linear.x
            self._speed_ang = msg.twist.twist.angular.z

    def _on_battery(self, msg: BatteryState):
        pct = msg.percentage
        with self._lock:
            self._battery_pct = pct * 100.0 if pct <= 1.0 else pct

    def _on_estop(self, msg: Bool):
        with self._lock:
            self._emergency_stop = msg.data

    def _on_plan(self, msg: Path):
        poses = [(p.pose.position.x, p.pose.position.y) for p in msg.poses]
        with self._lock:
            self._plan_poses = poses

    def _on_imu(self, msg: Imu):
        self._imu_ts = time.time()

    def _on_local_costmap(self, msg: OccupancyGrid):
        with self._lock:
            self._local_costmap = msg

    def _on_global_costmap(self, msg: OccupancyGrid):
        with self._lock:
            self._global_costmap = msg

    # ------------------------------------------------------------------ #
    # TF                                                                   #
    # ------------------------------------------------------------------ #

    def update_robot_pose_from_tf(self):
        try:
            t = self._tf_buffer.lookup_transform(
                'map', 'base_link', rclpy.time.Time())
            tr = t.transform.translation
            q = t.transform.rotation
            yaw = math.atan2(
                2.0 * (q.w * q.z + q.x * q.y),
                1.0 - 2.0 * (q.y * q.y + q.z * q.z))
            with self._lock:
                self._robot_pose = (tr.x, tr.y, yaw)
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # getters                                                              #
    # ------------------------------------------------------------------ #

    def get_map(self):
        with self._lock: return self._map

    def get_scan_points(self):
        with self._lock: return list(self._scan_points)

    def get_robot_pose(self):
        with self._lock: return self._robot_pose

    def get_battery_pct(self):
        with self._lock: return self._battery_pct

    def get_emergency_stop(self):
        with self._lock: return self._emergency_stop

    def get_plan_poses(self):
        with self._lock: return list(self._plan_poses)

    def get_nav_state(self):
        with self._lock: return self._nav_state

    def get_speed(self):
        with self._lock: return self._speed_lin, self._speed_ang

    def get_laser_ok(self):
        return (time.time() - self._laser_ts) < 2.0

    def get_imu_ok(self):
        return (time.time() - self._imu_ts) < 2.0

    def get_local_costmap(self):
        with self._lock: return self._local_costmap

    def get_global_costmap(self):
        with self._lock: return self._global_costmap

    # ------------------------------------------------------------------ #
    # publish commands                                                     #
    # ------------------------------------------------------------------ #

    def publish_cmd_vel(self, linear_x: float, angular_z: float):
        msg = Twist()
        msg.linear.x = linear_x
        msg.angular.z = angular_z
        self._cmd_vel_pub.publish(msg)

    def publish_initial_pose(self, x: float, y: float, yaw: float):
        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = 'map'
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.pose.pose.position.x = x
        msg.pose.pose.position.y = y
        msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        msg.pose.pose.orientation.w = math.cos(yaw / 2.0)
        msg.pose.covariance[0] = 0.25
        msg.pose.covariance[7] = 0.25
        msg.pose.covariance[35] = 0.068
        self._init_pose_pub.publish(msg)
        _log(f'Initial pose set: ({x:.3f}, {y:.3f}) yaw={math.degrees(yaw):.1f}°')

    def send_nav_goal(self, x: float, y: float, yaw: float):
        if not self._nav_client.wait_for_server(timeout_sec=1.0):
            _log('NavigateToPose server not available')
            with self._lock:
                self._nav_state = 'failed'
            return
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x = x
        goal.pose.pose.position.y = y
        goal.pose.pose.orientation.z = math.sin(yaw / 2.0)
        goal.pose.pose.orientation.w = math.cos(yaw / 2.0)
        with self._lock:
            if not self._route_active:
                self._nav_state = 'navigating'
        future = self._nav_client.send_goal_async(goal)
        future.add_done_callback(self._nav_goal_response)
        _log(f'Nav goal: ({x:.3f}, {y:.3f}) yaw={math.degrees(yaw):.1f}°')

    def cancel_nav(self):
        with self._lock:
            self._route_active = False
            self._route_queue = []
            self._nav_state = 'idle'
        if self._nav_goal_handle is not None:
            self._nav_goal_handle.cancel_goal_async()
        _log('Navigation cancelled')

    def emergency_stop(self):
        self.publish_cmd_vel(0.0, 0.0)
        self.cancel_nav()
        _log('EMERGENCY STOP')

    def _nav_goal_response(self, future):
        handle = future.result()
        if not handle.accepted:
            with self._lock:
                if not self._route_active:
                    self._nav_state = 'failed'
            _log('Goal rejected')
            return
        self._nav_goal_handle = handle
        handle.get_result_async().add_done_callback(self._nav_result)

    def _nav_result(self, future):
        status = future.result().status
        succeeded = (status == 4)
        with self._lock:
            route_active = self._route_active
        if route_active:
            self._advance_route()
        else:
            with self._lock:
                self._nav_state = 'succeeded' if succeeded else 'failed'
            _log(f'Navigation {"succeeded" if succeeded else "failed"} (status={status})')

    # ------------------------------------------------------------------ #
    # route                                                                #
    # ------------------------------------------------------------------ #

    def start_route(self, waypoints: list, loop: bool = False):
        if not waypoints:
            return
        with self._lock:
            self._route_queue = list(waypoints[1:])
            self._route_backup = list(waypoints)
            self._route_loop = loop
            self._route_active = True
            self._nav_state = 'route'
        first = waypoints[0]
        self.send_nav_goal(first['x'], first['y'], first.get('yaw', 0.0))
        _log(f'Route started: {len(waypoints)} points, loop={loop}')

    def stop_route(self):
        self.cancel_nav()
        _log('Route stopped')

    def _advance_route(self):
        next_wp = None
        with self._lock:
            if not self._route_active:
                return
            if self._route_queue:
                next_wp = self._route_queue.pop(0)
            elif self._route_loop:
                self._route_queue = list(self._route_backup)
                if self._route_queue:
                    next_wp = self._route_queue.pop(0)
            else:
                self._route_active = False
                self._nav_state = 'idle'
                _log('Route completed')
                return
        if next_wp:
            self.send_nav_goal(next_wp['x'], next_wp['y'], next_wp.get('yaw', 0.0))

    # ------------------------------------------------------------------ #
    # Process management helpers                                          #
    # ------------------------------------------------------------------ #

    def _spawn(self, attr: str, cmd: list, label: str):
        """Kill existing process for attr, then spawn a new one."""
        self._kill_proc(attr)
        proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            start_new_session=True,
        )
        setattr(self, attr, proc)
        _log(f'{label} launched (pid={proc.pid})')
        threading.Thread(target=self._monitor_proc,
                         args=(attr, proc, label), daemon=True).start()

    def _monitor_proc(self, attr: str, proc, label: str):
        """Watch a launched process: log early exit or first stderr lines."""
        import time as _time
        _time.sleep(3)
        if proc.poll() is not None:
            try:
                err = proc.stderr.read(2048).decode(errors='replace').strip()
            except Exception:
                err = ''
            _log(f'[ERROR] {label} exited early (rc={proc.returncode})'
                 + (f': {err[:200]}' if err else ''))
            if getattr(self, attr, None) is proc:
                setattr(self, attr, None)
        else:
            # drain stderr in background to prevent pipe blocking
            threading.Thread(target=proc.stderr.read, daemon=True).start()

    def _kill_proc(self, attr: str, label: str = ''):
        import signal as _sig
        proc = getattr(self, attr, None)
        if proc and proc.poll() is None:
            try:
                pgid = os.getpgid(proc.pid)
                os.killpg(pgid, _sig.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=6)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(proc.pid), _sig.SIGKILL)
                except ProcessLookupError:
                    pass
            if label:
                _log(f'{label} stopped')
        setattr(self, attr, None)

    def _proc_alive(self, attr: str) -> bool:
        p = getattr(self, attr, None)
        return p is not None and p.poll() is None

    # ------------------------------------------------------------------ #
    # SLAM                                                                 #
    # ------------------------------------------------------------------ #

    def start_slam(self):
        if self._proc_alive('_slam_proc'):
            _log('SLAM already running')
            return
        self._spawn('_slam_proc',
                    ['ros2', 'launch', 'atlas_slam', 'atlas_slam_toolbox_real.launch.py'],
                    'slam_toolbox')

    def stop_slam(self):
        self._kill_proc('_slam_proc', 'slam_toolbox')

    def is_slam_running(self) -> bool:
        return self._proc_alive('_slam_proc')

    # ------------------------------------------------------------------ #
    # Navigation stack                                                    #
    # ------------------------------------------------------------------ #

    def start_map_server(self, map_yaml: str = ''):
        cmd = ['ros2', 'launch', 'atlas_slam', 'atlas_map_server_real.launch.py']
        if map_yaml and os.path.exists(map_yaml):
            cmd += [f'map:={map_yaml}']
        self._spawn('_map_server_proc', cmd, 'map_server')

    def stop_map_server(self):
        self._kill_proc('_map_server_proc', 'map_server')

    def is_map_server_running(self) -> bool:
        return self._proc_alive('_map_server_proc')

    def start_nav(self, map_yaml: str = ''):
        """Stop slam, start map_server + navigation (same as mode=2 via API)."""
        self.stop_slam()
        self.start_map_server(map_yaml)
        self._spawn('_nav_proc',
                    ['ros2', 'launch', 'atlas_slam', 'atlas_navigation_real.launch.py'],
                    'navigation')

    def stop_nav(self):
        self._kill_proc('_nav_proc', 'navigation')
        self._kill_proc('_map_server_proc', 'map_server')

    def is_nav_running(self) -> bool:
        return self._proc_alive('_nav_proc')

    def stop_all_local(self):
        """Kill all locally-managed launch processes (safe to call from any thread)."""
        with self._lock:
            self._route_active = False
            self._route_queue  = []
            self._nav_state    = 'idle'
        self._kill_proc('_nav_proc',        'navigation')
        self._kill_proc('_map_server_proc', 'map_server')
        self._kill_proc('_slam_proc',       'slam_toolbox')
        _log('All local processes stopped')

    def get_launch_status(self) -> dict:
        """Returns merged local+API launch status. API status set by main_window."""
        local = {
            'slam':       self._proc_alive('_slam_proc'),
            'map_server': self._proc_alive('_map_server_proc'),
            'nav':        self._proc_alive('_nav_proc'),
        }
        api = getattr(self, '_api_launch_status', {})
        return {
            'slam':       local['slam']       or bool(api.get('slam')),
            'map_server': local['map_server'] or bool(api.get('map_server')),
            'nav':        local['nav']        or bool(api.get('navigation')),
        }

    def set_api_launch_status(self, status: dict):
        """Called by main_window when API launch/status poll returns."""
        self._api_launch_status = status

    def save_map(self, path: str):
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        proc = subprocess.Popen(
            ['ros2', 'run', 'nav2_map_server', 'map_saver_cli', '-f', path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        threading.Thread(target=self._wait_map_save, args=(proc, path), daemon=True).start()
        _log(f'Saving map to {path} ...')

    def _wait_map_save(self, proc, path):
        try:
            out, err = proc.communicate(timeout=15)
            if proc.returncode == 0:
                _log(f'Map saved: {os.path.basename(path)}.pgm/.yaml')
            else:
                _log(f'Map save failed: {err.decode().strip()[:120]}')
        except Exception as e:
            _log(f'Map save error: {e}')

    def load_map(self, yaml_path: str):
        proc = subprocess.Popen(
            ['ros2', 'service', 'call', '/map_server/load_map',
             'nav2_msgs/srv/LoadMap',
             f'{{map_url: {yaml_path}}}'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        threading.Thread(target=self._wait_load, args=(proc,), daemon=True).start()
        _log(f'Loading map: {os.path.basename(yaml_path)}')

    def _wait_load(self, proc):
        try:
            out, err = proc.communicate(timeout=10)
            if proc.returncode == 0:
                _log('Map loaded successfully')
            else:
                _log(f'Map load failed: {err.decode().strip()[:120]}')
        except Exception as e:
            _log(f'Map load error: {e}')

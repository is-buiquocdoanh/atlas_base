"""HTTP client for atlas_api REST endpoints on the robot."""
import json
import threading
import urllib.request
import urllib.error
from typing import Callable, Optional

from .node import _log


class AtlasApiClient:
    """Thin wrapper around atlas_api REST endpoints (port 8080 on robot).

    All blocking calls are safe to run in a Qt main thread only if you use
    the _async variants; synchronous helpers block until the response arrives.
    """

    def __init__(self, host: str = 'localhost:8080'):
        self.host = host

    @property
    def base(self) -> str:
        return f'http://{self.host}'

    # ------------------------------------------------------------------ #
    # low-level                                                            #
    # ------------------------------------------------------------------ #

    def _call(self, path: str, method: str = 'GET',
              data: Optional[dict] = None, timeout: int = 6) -> Optional[dict]:
        url = self.base + path
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(url, data=body, method=method)
        if body:
            req.add_header('Content-Type', 'application/json')
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read()).get('message', str(e))
            except Exception:
                msg = str(e)
            _log(f'API {method} {path} → {e.code}: {msg}')
            return None
        except Exception as e:
            _log(f'API {method} {path} error: {e}')
            return None

    def get(self, path: str, timeout: int = 6) -> Optional[dict]:
        return self._call(path, 'GET', timeout=timeout)

    def post(self, path: str, data: dict = None, timeout: int = 6) -> Optional[dict]:
        return self._call(path, 'POST', data=data or {}, timeout=timeout)

    def delete(self, path: str, timeout: int = 6) -> Optional[dict]:
        return self._call(path, 'DELETE', timeout=timeout)

    def get_bytes(self, path: str, timeout: int = 6) -> Optional[bytes]:
        """Fetch raw bytes (e.g. PNG thumbnail)."""
        url = self.base + path
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:
            _log(f'API GET bytes {path} error: {e}')
            return None

    # async helpers (call callback(result) in a daemon thread)
    def get_async(self, path: str, callback: Callable):
        threading.Thread(
            target=lambda: callback(self.get(path)), daemon=True).start()

    def post_async(self, path: str, data: dict = None,
                   callback: Callable = None):
        def _run():
            r = self.post(path, data)
            if callback:
                callback(r)
        threading.Thread(target=_run, daemon=True).start()

    def delete_async(self, path: str, callback: Callable = None):
        def _run():
            r = self.delete(path)
            if callback:
                callback(r)
        threading.Thread(target=_run, daemon=True).start()

    def get_bytes_async(self, path: str, callback: Callable):
        threading.Thread(
            target=lambda: callback(self.get_bytes(path)), daemon=True).start()

    # ------------------------------------------------------------------ #
    # mode / system                                                        #
    # ------------------------------------------------------------------ #

    def get_status(self) -> Optional[dict]:
        return self.get('/atlas/status')

    def get_launch_status(self) -> Optional[dict]:
        return self.get('/atlas/launch/status')

    def set_mode(self, mode: int, map_name: str = '') -> Optional[dict]:
        """mode: 0=stop, 1=mapping, 2=navigation, 3=incremental mapping."""
        data: dict = {'mode': mode}
        if map_name:
            data['map'] = map_name
        return self.post('/atlas/mode', data, timeout=10)

    # ------------------------------------------------------------------ #
    # navigation                                                           #
    # ------------------------------------------------------------------ #

    def send_goal(self, x: float, y: float, yaw: float) -> Optional[dict]:
        return self.post('/atlas/nav/goal', {'x': x, 'y': y, 'yaw': yaw})

    def send_goal_list(self, waypoints: list) -> Optional[dict]:
        """waypoints = [{'x':…,'y':…,'yaw':…}, …]"""
        return self.post('/atlas/nav/goal_list', waypoints)

    def cancel_nav(self) -> Optional[dict]:
        return self.post('/atlas/nav/cancel')

    def relocate(self, x: float, y: float, yaw: float) -> Optional[dict]:
        return self.post('/atlas/nav/relocate', {'x': x, 'y': y, 'yaw': yaw})

    def nav_charge_approach(self, name: str = '') -> Optional[dict]:
        return self.post('/atlas/nav/charge_approach', {'name': name} if name else {})

    def nav_charge(self, name: str = '') -> Optional[dict]:
        return self.post('/atlas/nav/charge', {'name': name} if name else {})

    def nav_dock(self, dock_name: str = '') -> Optional[dict]:
        return self.post('/atlas/nav/dock', {'dock_name': dock_name} if dock_name else {})

    def nav_dock_stop(self) -> Optional[dict]:
        return self.post('/atlas/nav/dock_stop')

    # ------------------------------------------------------------------ #
    # maps                                                                 #
    # ------------------------------------------------------------------ #

    def list_maps(self) -> list:
        r = self.get('/atlas/map/list')
        return r.get('maps', []) if r else []

    def save_map(self, alias: str) -> Optional[dict]:
        return self.post('/atlas/map/save', {'alias': alias}, timeout=20)

    def apply_map(self, name: str) -> Optional[dict]:
        return self.post('/atlas/map/apply', {'name': name})

    def delete_map(self, name: str) -> Optional[dict]:
        return self.delete(f'/atlas/map/{name}')

    def thumbnail_url(self, name: str) -> str:
        return f'{self.base}/atlas/map/thumbnail/{name}'

    def get_thumbnail(self, name: str) -> Optional[bytes]:
        return self.get_bytes(f'/atlas/map/thumbnail/{name}')

    # ------------------------------------------------------------------ #
    # waypoints (positions stored on robot)                                #
    # ------------------------------------------------------------------ #

    def get_waypoints(self) -> list:
        r = self.get('/atlas/waypoints')
        return r.get('waypoints', []) if r else []

    def upsert_waypoint(self, wp: dict) -> Optional[dict]:
        """wp = {'name', 'type', 'x', 'y', 'yaw'}"""
        return self.post('/atlas/waypoints', wp)

    def delete_waypoint(self, name: str) -> Optional[dict]:
        return self.delete(f'/atlas/waypoints/{name}')

    # ------------------------------------------------------------------ #
    # virtual walls                                                        #
    # ------------------------------------------------------------------ #

    def get_walls(self) -> list:
        r = self.get('/atlas/virtual_wall')
        return r.get('walls', []) if r else []

    def set_walls(self, walls: list) -> Optional[dict]:
        return self.post('/atlas/virtual_wall', {'walls': walls})

    def clear_walls(self) -> Optional[dict]:
        return self.delete('/atlas/virtual_wall')

    # ------------------------------------------------------------------ #
    # special areas                                                        #
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    # route execution                                                      #
    # ------------------------------------------------------------------ #

    def execute_route(self, waypoints: list, route_type: str = 'auto',
                      stop_duration: float = 5.0, auto_charge: bool = True) -> Optional[dict]:
        return self.post('/atlas/route/execute', {
            'waypoints': waypoints,
            'type': route_type,
            'stop_duration': stop_duration,
            'auto_charge': auto_charge,
        })

    def get_route_status(self) -> Optional[dict]:
        return self.get('/atlas/route/status')

    def confirm_route(self) -> Optional[dict]:
        return self.post('/atlas/route/confirm')

    def stop_route_exec(self) -> Optional[dict]:
        return self.post('/atlas/route/stop')

    def get_areas(self) -> list:
        r = self.get('/atlas/special_area')
        return r.get('areas', []) if r else []

    def set_areas(self, areas: list) -> Optional[dict]:
        return self.post('/atlas/special_area', {'areas': areas})

    def delete_area(self, area_id: str) -> Optional[dict]:
        return self.delete(f'/atlas/special_area/{area_id}')

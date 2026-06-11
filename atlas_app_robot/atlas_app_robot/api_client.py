"""Minimal HTTP client for atlas_api — used by atlas_app_robot."""
import json
import threading
import urllib.request
import urllib.error
from typing import Callable, Optional


class RobotApiClient:
    def __init__(self, host: str = 'localhost:8080'):
        self.host = host

    @property
    def base(self) -> str:
        return f'http://{self.host}'

    def _call(self, path: str, method: str = 'GET',
              data: Optional[dict] = None, timeout: int = 5) -> Optional[dict]:
        url = self.base + path
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(url, data=body, method=method)
        if body:
            req.add_header('Content-Type', 'application/json')
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except Exception:
            return None

    def get(self, path: str) -> Optional[dict]:
        return self._call(path, 'GET')

    def post(self, path: str, data: dict = None) -> Optional[dict]:
        return self._call(path, 'POST', data=data or {})

    def get_async(self, path: str, callback: Callable):
        threading.Thread(
            target=lambda: callback(self.get(path)), daemon=True).start()

    def post_async(self, path: str, data: dict = None, callback: Callable = None):
        def _run():
            r = self.post(path, data)
            if callback:
                callback(r)
        threading.Thread(target=_run, daemon=True).start()

    # ── domain helpers ─────────────────────────────────────────────────────

    def get_waypoints(self) -> list:
        r = self.get('/atlas/waypoints')
        return r.get('waypoints', []) if r else []

    def get_route_status(self) -> Optional[dict]:
        return self.get('/atlas/route/status')

    def nav_to(self, x: float, y: float, yaw: float = 0.0) -> Optional[dict]:
        return self.post('/atlas/nav/goal', {'x': x, 'y': y, 'yaw': yaw})

    def confirm_route(self) -> Optional[dict]:
        return self.post('/atlas/route/confirm')

    def cancel_nav(self) -> Optional[dict]:
        return self.post('/atlas/nav/cancel')

    def get_status(self) -> Optional[dict]:
        return self.get('/atlas/status')

from flask import Blueprint, jsonify, request
from ..ros_node import get_node, RouteExecutor
import threading

bp = Blueprint('route_api', __name__)

# Module-level active executor
_executor_lock = threading.Lock()
_executor: RouteExecutor | None = None


def _get_executor() -> RouteExecutor | None:
    with _executor_lock:
        return _executor


def _set_executor(ex: RouteExecutor | None):
    global _executor
    with _executor_lock:
        _executor = ex


# ── saved route CRUD ────────────────────────────────────────────────────────

@bp.get('/atlas/route')
def get_route():
    route = get_node().get_route()
    if route is None:
        return jsonify({'status': 'error', 'message': 'no route defined'}), 404
    return jsonify(route)


@bp.get('/atlas/route/list')
def list_routes():
    return jsonify({'routes': get_node().get_routes()})


@bp.post('/atlas/route')
def save_route():
    data = request.get_json(force=True) or {}
    if 'name' not in data or 'waypoints' not in data:
        return jsonify({'status': 'error', 'message': 'name and waypoints required'}), 400
    route = {
        'name':      str(data['name']),
        'loop':      bool(data.get('loop', False)),
        'waypoints': data['waypoints'],
    }
    get_node().upsert_route(route)
    return jsonify({'status': 'success'})


@bp.delete('/atlas/route/<name>')
def delete_route(name):
    if not get_node().delete_route(name):
        return jsonify({'status': 'error', 'message': f'route "{name}" not found'}), 404
    return jsonify({'status': 'success'})


# ── route execution ─────────────────────────────────────────────────────────

@bp.post('/atlas/route/execute')
def execute_route():
    """Start smart route execution.

    Body:
      waypoints    — list of {x, y, yaw, name}
      type         — 'auto' | 'confirm'   (default: 'auto')
      stop_duration — seconds to wait at each wp (auto mode, default 5)
      auto_charge  — bool, auto-charge after last wp (default true)
    """
    data = request.get_json(force=True) or {}
    waypoints = data.get('waypoints', [])
    if not waypoints:
        return jsonify({'status': 'error', 'message': 'waypoints required'}), 400

    route_type     = str(data.get('type', 'auto'))
    stop_duration  = float(data.get('stop_duration', 5.0))
    auto_charge    = bool(data.get('auto_charge', True))

    # Stop any existing executor
    ex = _get_executor()
    if ex:
        ex.stop()

    new_ex = RouteExecutor(
        get_node(), waypoints,
        route_type=route_type,
        stop_duration=stop_duration,
        auto_charge=auto_charge,
    )
    _set_executor(new_ex)
    new_ex.start()

    return jsonify({'status': 'success', 'type': route_type,
                    'total': len(waypoints), 'auto_charge': auto_charge})


@bp.get('/atlas/route/status')
def route_status():
    """Current execution status for polling."""
    ex = _get_executor()
    if ex is None:
        return jsonify({'status': 'idle', 'current_idx': -1, 'total': 0})
    return jsonify(ex.get_status())


@bp.post('/atlas/route/confirm')
def route_confirm():
    """Confirm to proceed to the next waypoint (type='confirm' routes)."""
    ex = _get_executor()
    if ex is None:
        return jsonify({'status': 'error', 'message': 'no active route'}), 404
    ex.confirm()
    return jsonify({'status': 'success'})


@bp.post('/atlas/route/stop')
def stop_route():
    ex = _get_executor()
    if ex:
        ex.stop()
        _set_executor(None)
    get_node().cancel_nav()
    return jsonify({'status': 'success'})


# Legacy start (kept for backward compat)
@bp.post('/atlas/route/start')
def start_route():
    data  = request.get_json(force=True) or {}
    name  = data.get('name', '')
    route = get_node().get_route(name)
    if not route:
        return jsonify({'status': 'error', 'message': f'route "{name}" not found'}), 404
    ok, msg = get_node().send_route_goal(route['waypoints'])
    if not ok:
        return jsonify({'status': 'error', 'message': msg}), 503
    return jsonify({'status': 'success'})

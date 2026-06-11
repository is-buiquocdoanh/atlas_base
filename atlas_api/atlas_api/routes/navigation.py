from flask import Blueprint, jsonify, request
from ..ros_node import get_node

bp = Blueprint('navigation', __name__)


@bp.get('/atlas/nav/status')
def nav_status():
    return jsonify(get_node().get_nav_status())


@bp.post('/atlas/nav/goal')
def nav_goal():
    data = request.get_json(force=True) or {}
    try:
        x   = float(data['x'])
        y   = float(data['y'])
        yaw = float(data.get('yaw', 0.0))
    except (KeyError, ValueError) as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

    ok, msg = get_node().send_nav_goal(x, y, yaw)
    if not ok:
        return jsonify({'status': 'error', 'message': msg}), 503
    return jsonify({'status': 'success'})


@bp.post('/atlas/nav/goal_name')
def nav_goal_name():
    data = request.get_json(force=True) or {}
    name = data.get('name', '')
    wps  = {w['name']: w for w in get_node().get_waypoints()}
    wp   = wps.get(name)
    if not wp:
        return jsonify({'status': 'error', 'message': f'waypoint "{name}" not found'}), 404
    ok, msg = get_node().send_nav_goal(wp['x'], wp['y'], wp.get('yaw', 0.0))
    if not ok:
        return jsonify({'status': 'error', 'message': msg}), 503
    return jsonify({'status': 'success'})


@bp.post('/atlas/nav/goal_list')
def nav_goal_list():
    data = request.get_json(force=True)
    if not isinstance(data, list) or len(data) == 0:
        return jsonify({'status': 'error', 'message': 'body must be a non-empty list'}), 400
    ok, msg = get_node().send_route_goal(data)
    if not ok:
        return jsonify({'status': 'error', 'message': msg}), 503
    return jsonify({'status': 'success'})


@bp.post('/atlas/nav/cancel')
def nav_cancel():
    get_node().cancel_nav()
    return jsonify({'status': 'success'})


@bp.post('/atlas/nav/relocate')
def relocate():
    data = request.get_json(force=True) or {}
    try:
        x   = float(data['x'])
        y   = float(data['y'])
        yaw = float(data.get('yaw', 0.0))
    except (KeyError, ValueError) as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    get_node().publish_initialpose(x, y, yaw)
    return jsonify({'status': 'success'})


@bp.get('/atlas/nav/path')
def nav_path():
    return jsonify({'path': get_node().get_nav_path()})


def _find_charge_wp():
    """Return the first waypoint with type 'charge', or None."""
    for w in get_node().get_waypoints():
        if w.get('type', '').lower() == 'charge':
            return w
    return None


@bp.post('/atlas/nav/charge_approach')
def nav_charge_approach():
    """Stage 1: Navigate to the waypoint with type='charge'."""
    wp = _find_charge_wp()
    if not wp:
        return jsonify({'status': 'error',
                        'message': 'No waypoint with type "charge" found. '
                                   'Create a position and set its type to Charge.'}), 404
    ok, msg = get_node().send_nav_goal(wp['x'], wp['y'], wp.get('yaw', 0.0))
    if not ok:
        return jsonify({'status': 'error', 'message': msg}), 503
    return jsonify({'status': 'success', 'stage': 'approach', 'waypoint': wp['name']})


@bp.post('/atlas/nav/charge_dock')
def nav_charge_dock():
    """Stage 2: Dock using the configured dock_method."""
    data      = request.get_json(force=True) or {}
    dock_name = data.get('dock_name')
    ok, msg   = get_node().start_dock(dock_name)
    if not ok:
        return jsonify({'status': 'error', 'message': msg}), 503
    method = get_node()._settings.get('dock_method', 'line_follow')
    return jsonify({'status': 'success', 'stage': 'dock', 'method': method})


@bp.post('/atlas/nav/dock')
def nav_dock():
    """Start docking immediately using the configured dock_method."""
    data      = request.get_json(force=True) or {}
    dock_name = data.get('dock_name')
    ok, msg   = get_node().start_dock(dock_name)
    if not ok:
        return jsonify({'status': 'error', 'message': msg}), 503
    method = get_node()._settings.get('dock_method', 'line_follow')
    return jsonify({'status': 'success', 'method': method})


@bp.post('/atlas/nav/dock_stop')
def nav_dock_stop():
    """Stop active docking subprocess."""
    get_node().stop_dock()
    return jsonify({'status': 'success'})


@bp.get('/atlas/nav/dock_status')
def nav_dock_status():
    return jsonify({
        'docking':     get_node().is_docking(),
        'dock_method': get_node()._settings.get('dock_method', 'line_follow'),
    })


@bp.post('/atlas/nav/charge')
def nav_charge():
    """Full charge sequence: navigate to type='charge' waypoint → dock automatically."""
    wp = _find_charge_wp()
    if not wp:
        return jsonify({'status': 'error',
                        'message': 'No waypoint with type "charge" found. '
                                   'Create a position and set its type to Charge.'}), 404
    ok, msg = get_node().send_charge_sequence(wp, dock_wp=None)
    if not ok:
        return jsonify({'status': 'error', 'message': msg}), 503
    method = get_node()._settings.get('dock_method', 'line_follow')
    return jsonify({'status': 'success', 'stage': 'full_sequence',
                    'approach': wp['name'], 'dock_method': method})

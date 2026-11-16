import hmac
import json
import logging
import os
import re
import uuid
from flask import Flask, g, jsonify, request
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.exceptions import HTTPException
from app.db import transaction

def create_operations_app():
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=10 * 1024 * 1024)
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    if os.getenv('TRUST_PROXY') == 'true':
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    if os.getenv('APP_ENV') == 'production':
        if not os.getenv('API_TOKEN') or not os.getenv('DIAGNOSTIC_TOKEN'):
            raise RuntimeError('Production requires API_TOKEN and DIAGNOSTIC_TOKEN')
        if os.getenv('ALERTS_ENABLED') == 'true':
            raise RuntimeError('Production alert delivery requires an implemented provider adapter')

    @app.before_request
    def before():
        supplied = request.headers.get('X-Request-ID', '')
        g.request_id = supplied if re.fullmatch(r'[a-zA-Z0-9-]{1,64}', supplied) else str(uuid.uuid4())
        if request.path.startswith('/health/'):
            return None
        expected = os.getenv('DIAGNOSTIC_TOKEN') if request.path.startswith('/ops/') else os.getenv('API_TOKEN')
        if request.path.startswith('/ops/') and not expected:
            return jsonify(error='not found'), 404
        if expected and not hmac.compare_digest(request.headers.get('Authorization',''), 'Bearer ' + expected):
            return jsonify(error='unauthorized'), 401

    @app.after_request
    def after(response):
        response.headers['X-Request-ID'] = g.get('request_id', 'system')
        # Never log URL query strings, bodies, contacts, or provider errors.
        logging.getLogger('shield').info(json.dumps({'event':'request', 'method':request.method,
            'route':str(request.url_rule), 'status':response.status_code,
            'correlation_id':g.get('request_id'), 'release':os.getenv('RELEASE_ID','development')}))
        return response

    @app.teardown_request
    def close_connections(error):
        for conn in g.pop('db_connections', []):
            conn.close()

    @app.errorhandler(Exception)
    def internal_error(error):
        if isinstance(error, HTTPException):
            return jsonify(error=error.name), error.code
        logging.getLogger('shield').error('{"event":"request_failed"}')
        return jsonify(error='internal error'), 500

    @app.get('/health/live')
    def live():
        return jsonify(status='alive')

    @app.get('/health/ready')
    def ready():
        try:
            with transaction() as conn:
                with conn.cursor() as cur:
                    cur.execute('SELECT id FROM incident_gate WHERE id=1')
                    if not cur.fetchone():
                        raise RuntimeError('schema missing')
            if app.config.get('REQUIRE_MODELS') and not app.config.get('MODELS_READY'):
                raise RuntimeError('models unavailable')
        except Exception:
            return jsonify(status='unready'), 503
        return jsonify(status='ready')

    @app.get('/ops/instance')
    def instance():
        return jsonify(instance=os.getenv('INSTANCE_ID','local'), release=os.getenv('RELEASE_ID','development'))

    @app.get('/ops/alerts/<int:incident_id>')
    @app.get('/alerts/<int:incident_id>')
    def alert_status(incident_id):
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT status,count(*) FROM alert_outbox WHERE incident_id=%s GROUP BY status', (incident_id,))
                return jsonify(dict(cur.fetchall()))

    return app

def incident_alert_status(incident_id):
    if not incident_id:
        return 'not_requested'
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT status FROM alert_outbox WHERE incident_id=%s', (incident_id,))
            states = [row[0] for row in cur.fetchall()]
    if not states:
        return 'not_requested'
    if all(state == 'delivered' for state in states):
        return 'delivered'
    if any(state in ('pending','processing','retry') for state in states):
        return 'pending'
    return 'failed'

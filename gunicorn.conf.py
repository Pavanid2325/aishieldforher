import os
bind = '0.0.0.0:5000'
workers = int(os.getenv('GUNICORN_WORKERS', '1'))
worker_class = 'sync'
timeout = 120
graceful_timeout = 125
keepalive = 2
preload_app = False
errorlog = '-'
accesslog = None  # Application emits redacted route logs; query strings contain GPS.
capture_output = True

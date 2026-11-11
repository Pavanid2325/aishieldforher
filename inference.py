"""Keep the existing inference algorithm; isolate model loading from workers/tests."""
import os

_process = None
_iot = None

def initialize(app):
    global _process, _iot
    if os.getenv('FAKE_INFERENCE') == 'true':
        if os.getenv('APP_ENV') == 'production':
            raise RuntimeError('Fake inference forbidden in production')
        _process = lambda path, accel: (0.083875, 'test transcript')
        _iot = lambda accel: 1.0 if accel > 15 else 0.7 if accel > 10 else 0.4 if accel > 5 else 0.1
    else:
        from scripts.verify_models import verify
        verify()
        from stt import process_audio_file, calculate_iot_threat
        _process, _iot = process_audio_file, calculate_iot_threat
    app.config['MODELS_READY'] = True

def process_audio_file(path, accel=0):
    return _process(path, accel)

def calculate_iot_threat(accel):
    return _iot(accel)

"""No alert sends. Probe both API replicas and round-trip one harmless worker task."""
import json
import os
import sys
import time
import urllib.request
import uuid
from alerts import probe
from db import transaction

def get(url, token=None):
    req = urllib.request.Request(url, headers={'Authorization':'Bearer '+token} if token else {})
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.load(response)

def main():
    base = sys.argv[1] if len(sys.argv)>1 else os.getenv('PUBLIC_BASE_URL', 'http://nginx')
    token = os.environ['DIAGNOSTIC_TOKEN']
    for _ in range(30):
        try:
            get(base+'/health/ready')
            break
        except Exception:
            time.sleep(2)
    else:
        raise RuntimeError('API readiness failed')
    instances = set()
    release = os.getenv('RELEASE_ID', 'development')
    for _ in range(20):
        result = get(base+'/ops/instance',token)
        if result['release'] != release:
            raise RuntimeError('Unexpected release')
        instances.add(result['instance'])
    if instances != {'api1','api2'}:
        raise RuntimeError('Both replicas were not reached')
    name = 'smoke-' + uuid.uuid4().hex
    probe.apply_async(args=[name])
    for _ in range(20):
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT 1 FROM operational_checks WHERE name=%s', (name,))
                if cur.fetchone():
                    cur.execute('DELETE FROM operational_checks WHERE name=%s', (name,))
                    print('Readiness, two replicas, release and worker round-trip passed')
                    return
        time.sleep(2)
    raise RuntimeError('Worker probe failed')

if __name__ == '__main__':
    main()

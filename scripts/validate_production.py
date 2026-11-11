import os
from pathlib import Path
from urllib.parse import urlparse

def main():
    required=('DATABASE_URL','RDS_CA_PATH','API_TOKEN','DIAGNOSTIC_TOKEN','PUBLIC_BASE_URL','RELEASE_ID')
    if any(not os.getenv(key) for key in required):
        raise SystemExit('Missing required production configuration')
    url=urlparse(os.environ['DATABASE_URL'])
    if url.scheme != 'postgresql' or url.hostname in (None,'postgres','localhost','127.0.0.1'):
        raise SystemExit('Production requires a remote PostgreSQL/RDS endpoint')
    if urlparse(os.environ['PUBLIC_BASE_URL']).scheme != 'https':
        raise SystemExit('Production requires HTTPS')
    if not Path(os.environ['RDS_CA_PATH']).is_file():
        raise SystemExit('RDS CA bundle is unavailable')
    if os.getenv('ALERTS_ENABLED','false') != 'false':
        raise SystemExit('Implement a production provider before enabling alerts')
    if os.getenv('FAKE_INFERENCE','false') != 'false':
        raise SystemExit('Production requires real inference')
    from operations import create_operations_app
    create_operations_app()
    print('Production configuration validated')

if __name__=='__main__':
    main()

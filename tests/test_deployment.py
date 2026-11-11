import os
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which('bash') if os.name != 'nt' else 'C:/Program Files/Git/bin/bash.exe'
IMAGE = '123456789012.dkr.ecr.us-east-1.amazonaws.com/shield@sha256:'+'a'*64
PREVIOUS = '123456789012.dkr.ecr.us-east-1.amazonaws.com/shield@sha256:'+'b'*64

@pytest.fixture
def deployment(tmp_path):
    if not BASH or not Path(BASH).exists():
        pytest.skip('Bash unavailable')
    for folder in ('scripts','deploy','.releases','bin'):
        (tmp_path/folder).mkdir()
    shutil.copy(ROOT/'scripts/deploy.sh',tmp_path/'scripts')
    (tmp_path/'deploy/nginx.production.conf').touch()
    (tmp_path/'.env').write_text('placeholder=true\n')
    old=PREVIOUS+' '+'b'*40
    (tmp_path/'.releases/current').write_text(old+'\n')
    docker='''#!/usr/bin/env bash
printf '%s %s\\n' "$BACKEND_IMAGE" "$*" >> calls
if [[ "$1" == login ]]; then cat >/dev/null; fi
if [[ "$1 $2" == 'image inspect' ]]; then echo "${MOCK_REVISION:-$RELEASE_ID}"; fi
if [[ "$*" == *"scripts/smoke.py"* && "$BACKEND_IMAGE" == *"sha256:aaaa"* && "${FAIL_NEW:-}" == true ]]; then exit 1; fi
exit 0
'''
    for command,content in {'docker':docker,'aws':'#!/usr/bin/env bash\necho fake-login\n','flock':'#!/usr/bin/env bash\nexit 0\n'}.items():
        path=tmp_path/'bin'/command
        path.write_text(content,newline='\n')
        path.chmod(0o755)
    env=dict(os.environ)
    # Bash on Windows converts its PATH; supply POSIX-style path inside the command.
    return tmp_path,env,old

def invoke(deployment,fail=False):
    path,env,_=deployment
    env['FAIL_NEW']='true' if fail else 'false'
    command='export PATH="$PWD/bin:$PATH"; bash scripts/deploy.sh '+IMAGE+' '+'a'*40
    return subprocess.run([BASH,'-c',command],cwd=path,env=env,capture_output=True,text=True,timeout=30)

def test_success_promotes_after_smoke(deployment):
    result=invoke(deployment)
    assert result.returncode==0,result.stdout+result.stderr
    path,_,old=deployment
    assert (path/'.releases/current').read_text().strip()==IMAGE+' '+'a'*40
    assert (path/'.releases/previous').read_text().strip()==old

def test_failed_release_restores_previous(deployment):
    result=invoke(deployment,True)
    assert result.returncode==1,result.stdout+result.stderr
    path,_,old=deployment
    assert (path/'.releases/current').read_text().strip()==old
    assert 'Previous release verified' in result.stdout
    calls=(path/'calls').read_text()
    assert PREVIOUS+' compose' in calls
    assert 'down -v' not in calls

def test_rejects_image_with_wrong_revision(deployment):
    path,env,old=deployment
    env['MOCK_REVISION']='c'*40
    result=invoke(deployment)
    assert result.returncode==2,result.stdout+result.stderr
    assert (path/'.releases/current').read_text().strip()==old
    assert 'run --rm' not in (path/'calls').read_text()

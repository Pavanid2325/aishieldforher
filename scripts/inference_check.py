"""Exercise real assets on generated silence without reading personal recordings."""
import json
import math
import tempfile
import time
import wave
from pathlib import Path
from scripts.verify_models import verify

def main():
    verify()
    started=time.monotonic()
    from stt import process_audio_file
    loaded=time.monotonic()
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder)/'silence.wav'
        with wave.open(str(path),'wb') as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(b'\0\0'*16000)
        score,text=process_audio_file(str(path),12)
    if not math.isclose(score,.083875) or not isinstance(text,str):
        raise RuntimeError('Existing inference contract changed')
    result={'event':'real_inference_check','score':score,'load_seconds':round(loaded-started,3),
            'inference_seconds':round(time.monotonic()-loaded,3)}
    try:
        import resource
        result['peak_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except ImportError:
        pass
    print(json.dumps(result))

if __name__=='__main__':
    main()

"""Machine-readable installation events, including real per-file pip bytes."""
import json
import re
import time

SOURCES = {'official':'https://pypi.org/simple', 'tuna':'https://pypi.tuna.tsinghua.edu.cn/simple'}

def emit(stage, **values):
    print(json.dumps({'type':'install_progress','stage':stage,**values},ensure_ascii=False),flush=True)

class PipProgress:
    def __init__(self, callback=emit, clock=time.monotonic):
        self.callback=callback;self.clock=clock;self.file='';self.previous=None

    def feed(self,line):
        line=line.strip()
        if line.startswith(('Downloading ', 'Using cached ')):
            self.file=line.split(' ',2)[1] if line.startswith('Downloading ') else line[len('Using cached '):].split(' ')[0]
            self.previous=None
            self.callback('download',file=self.file,downloaded=0,total=0,speed=0)
        match=re.fullmatch(r'Progress (\d+) of (\d+)',line)
        if match:
            current,total=map(int,match.groups());now=self.clock();speed=0
            if self.previous and current>=self.previous[0] and now>self.previous[1]:speed=(current-self.previous[0])/(now-self.previous[1])
            self.previous=(current,now)
            self.callback('download',file=self.file,downloaded=current,total=total,speed=speed)
            return True
        if line.startswith(('Installing collected packages:', 'Building wheel', 'Preparing metadata', 'Collecting ')):
            self.callback('packages',file=line)
        return False

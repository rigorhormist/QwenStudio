"""Embed an allowlisted application payload in the Windows executable."""
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]

def bundle(output):
    output.parent.mkdir(parents=True,exist_ok=True)
    entries={}
    for name in ('backend','web'):
        for file in (ROOT/'windows'/name).rglob('*'):
            if file.is_file() and '__pycache__' not in file.parts and not file.name.startswith('._') and file.suffix in ('.py','.js','.json','.css','.html','.svg','.png','.woff2'):
                entries[file.relative_to(ROOT/'windows').as_posix()]=file
    for name in ('requirements.txt','find-python.ps1'):entries[name]=ROOT/'windows'/name
    for name in ('LICENSE','LICENSE.model.txt','NOTICE','THIRD_PARTY_NOTICES.md'):entries[name]=ROOT/name
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,file in sorted(entries.items()):
            info=zipfile.ZipInfo(name,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,file.read_bytes())

if __name__=='__main__':
    import sys
    bundle(Path(sys.argv[1]))

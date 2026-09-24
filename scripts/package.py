"""Build release archives from an explicit allowlist; never package user data."""
import argparse
import hashlib
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMON = ('README.md', 'README.en.md', 'LICENSE', 'LICENSE.model.txt', 'NOTICE',
          'THIRD_PARTY_NOTICES.md', 'SECURITY.md', 'CHANGELOG.md', 'CONTRIBUTING.md',
          'docs', 'licenses', 'assets')
ALLOWED = {
    'windows': ('app', 'backend', 'web', 'desktop', 'assets', 'requirements.txt',
                'setup.cmd', 'setup.ps1', 'find-python.ps1', 'start.cmd', 'start.ps1', 'build.ps1', 'settings.example.json'),
    'macos': ('Qwen Studio.app', 'backend', 'web', 'native', 'assets', 'requirements.txt',
              'setup.command', 'find-python.command', 'build.sh'),
}
SKIP_PARTS = {'.venv', '__pycache__', '.git', 'obj', 'bin', 'models', 'runtime'}

def files(path):
    if path.is_file():
        yield path
    elif path.is_dir():
        for item in sorted(path.rglob('*')):
            relative = item.relative_to(path)
            if item.is_file() and not SKIP_PARTS.intersection(relative.parts) and not item.name.startswith('._') and item.name != '.DS_Store' and item.suffix not in ('.pyc', '.pdb', '.log'):
                yield item
    else:
        raise FileNotFoundError(path)

def package(platform, version, output):
    root = ROOT / platform
    expected = root / ('app/Qwen Studio.exe' if platform == 'windows' else 'Qwen Studio.app/Contents/MacOS/QwenStudio')
    if not expected.is_file():
        raise SystemExit(f'Build the {platform} desktop shell first: missing {expected}')
    suffix = 'windows-x64' if platform == 'windows' else 'macos-arm64'
    stem = f'QwenStudio-{version}-{suffix}'
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f'{stem}.zip'
    seen = set()
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for base, names in ((root, ALLOWED[platform]), (ROOT, COMMON)):
            for name in names:
                for item in files(base / name):
                    rel = item.relative_to(base)
                    target = f'{stem}/{rel.as_posix()}'
                    if target in seen:
                        continue
                    seen.add(target)
                    # Stage scripts on macOS and make Windows line endings explicit.
                    raw = item.read_bytes()
                    if item.suffix in ('.cmd', '.ps1'):
                        raw = raw.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
                    info = zipfile.ZipInfo.from_file(item, target)
                    info.compress_type = zipfile.ZIP_DEFLATED
                    z.writestr(info, raw)
    digest = hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / f'{stem}.sha256').write_text(f'{digest}  {archive.name}\n')
    print(f'{archive}: {archive.stat().st_size / 1_000_000:.1f} MB')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--platform', required=True, choices=ALLOWED)
    parser.add_argument('--version', required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-[a-z0-9.-]+)?', args.version):
        parser.error('Use a semantic version such as 2.1.0')
    package(args.platform, args.version, args.output)

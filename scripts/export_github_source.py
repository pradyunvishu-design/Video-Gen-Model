"""Export a source-only snapshot without secrets, runtime data or vendor trees.

Usage: python scripts/export_github_source.py --destination PATH
The destination must already be a Git checkout. Existing project files there
are not overwritten except for the starter README or identical source files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ('pipeline', 'scripts', 'tests', 'configs', 'n8n', 'remotion/src',
               'thumbnail_system', '.agents/skills', 'research', 'tools', 'apps/recording-studio')
ROOT_FILES = ('README.md', 'SOURCE_PACKAGE.md', 'requirements.txt', 'requirements-dev.txt', 'pytest.ini',
              '.env.example', '.env.worker.example', '.gitignore',
              'remotion/package.json', 'remotion/package-lock.json', 'remotion/tsconfig.json',
              'apps/recording-studio/.env.example', 'apps/recording-studio/.gitignore',
              'apps/recording-studio/src-tauri/.gitignore',
              '.github/workflows/recording-studio.yml')
SKIP_PARTS = {'node_modules', '__pycache__', 'vendor', 'runtime_vendor', 'feedback',
              '.git', '.cache', '.venv', 'venv', 'target', 'dist', 'gen', 'bin',
              'test-results', 'playwright-report', 'recordings'}
TEXT_EXTENSIONS = {'.py', '.cjs', '.mjs', '.js', '.jsx', '.ts', '.tsx', '.css', '.html',
                   '.md', '.json', '.yaml', '.yml', '.toml', '.ini', '.txt', '.ps1', '.sh', '.svg',
                   '.rs', '.swift', '.lock', '.plist'}
SECRET_PATTERNS = {
    'provider_key': re.compile(r'(?:sk-or-v1-|sk-proj-|mhk_live_|gh[pousr]_|github_pat_)[A-Za-z0-9_-]{20,}'),
    'google_api_key': re.compile(r'AIza[0-9A-Za-z_-]{30,}'),
    'private_key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'literal_bearer': re.compile(r'Bearer\s+[A-Za-z0-9_.-]{30,}'),
    'signed_download': re.compile(r'https?[^\s"\']+[?&](?:X-Amz-Signature|X-Goog-Signature)=', re.I),
}


def local_secrets() -> set[str]:
    """Read local environment files only to prevent their values being exported."""
    values = set()
    paths = [ROOT / '.env', ROOT / 'apps/recording-studio/.env']
    if (ROOT / 'secrets').is_dir():
        paths.extend((ROOT / 'secrets').glob('*.env'))
        paths.extend((ROOT / 'secrets').glob('.env*'))
    for path in paths:
        if not path.is_file():
            continue
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if '=' not in line or line.lstrip().startswith('#'):
                continue
            name, value = line.split('=', 1)
            value = value.strip().strip('"\'')
            if re.search(r'KEY|TOKEN|PASSWORD|SECRET', name, re.I) and len(value) >= 12:
                values.add(value)
    return values


def sanitize_workflow(obj: dict) -> tuple[dict, list[str]]:
    changes = []
    for key in ('pinData', 'staticData', 'meta', 'versionId', 'id', 'tags'):
        if key in obj:
            obj.pop(key)
            changes.append('removed_' + key)
    obj['active'] = False
    for node in obj.get('nodes', []):
        if 'credentials' in node:
            node.pop('credentials')
            changes.append('removed_node_credential_binding')
        if 'webhookId' in node:
            node.pop('webhookId')
            changes.append('removed_instance_webhook_id')
        if node.get('type') == 'n8n-nodes-base.googleSheets':
            parameters = node.get('parameters', {})
            if 'documentId' in parameters:
                parameters['documentId'] = {'__rl': True, 'value': 'REPLACE_WITH_YOUR_SPREADSHEET_ID', 'mode': 'id'}
                changes.append('replaced_private_spreadsheet_id')
            sheet = parameters.get('sheetName', {})
            if isinstance(sheet, dict) and sheet.get('cachedResultName'):
                parameters['sheetName'] = {'__rl': True, 'value': sheet['cachedResultName'], 'mode': 'name'}
                changes.append('replaced_private_sheet_gid_with_tab_name')
    return obj, sorted(set(changes))


def export(destination: Path) -> dict:
    destination = destination.resolve()
    if destination == ROOT or ROOT in destination.parents or not (destination / '.git').exists():
        raise ValueError('Destination must be a separate existing Git checkout')
    candidates = {ROOT / name for name in ROOT_FILES if (ROOT / name).is_file()}
    for directory in SOURCE_DIRS:
        base = ROOT / directory
        if not base.exists():
            continue
        for folder, directories, filenames in os.walk(base, followlinks=False):
            directories[:] = [name for name in directories
                              if name not in SKIP_PARTS and not (Path(folder) / name).is_symlink()]
            for name in filenames:
                path = Path(folder) / name
                if not path.is_symlink() and path.suffix.lower() in TEXT_EXTENSIONS:
                    candidates.add(path)
    secrets = local_secrets()
    previous_manifest = destination / 'SOURCE_EXPORT_MANIFEST.json'
    previous_files = {}
    if previous_manifest.exists():
        previous_files = {item['path']: item['sha256'] for item in json.loads(previous_manifest.read_text(encoding='utf-8'))['files']}
    prepared = []
    findings = []
    transformations = {}
    for path in sorted(candidates):
        rel = path.relative_to(ROOT).as_posix()
        if path.stat().st_size > 5_000_000:
            findings.append({'path': rel, 'kind': 'source_file_above_5mb'})
            continue
        raw = path.read_bytes()
        content = raw.decode('utf-8-sig')
        if rel == 'README.md':
            content = re.sub(r'^# .+$', '# Video-Gen-Model', content, count=1, flags=re.M)
            content = content.replace('# Video-Gen-Model\n', '# Video-Gen-Model\n\nSource snapshot of the Diffusion Daily / News Weekly video pipeline. Start with [SOURCE_PACKAGE.md](SOURCE_PACKAGE.md) for export scope, private configuration, and portability notes.\n', 1)
        if rel.startswith('n8n/') and path.suffix == '.json':
            workflow, changes = sanitize_workflow(json.loads(content))
            content = json.dumps(workflow, indent=2, ensure_ascii=False) + '\n'
            transformations[rel] = changes + ['disabled_workflow']
        if rel.startswith('.env'):
            content = re.sub(r'^N8N_BASE_URL=.*$', 'N8N_BASE_URL=https://n8n.example.com', content, flags=re.M)
        content = re.sub(r'https?://[A-Za-z0-9.-]+\.(?:ngrok-free\.(?:app|dev)|ngrok\.io|trycloudflare\.com)', 'https://video-worker.example.com', content)
        content = re.sub(r'https?://[A-Za-z0-9.-]+\.hstgr\.cloud', 'https://n8n.example.com', content)
        content = re.sub(r"https://docs\.google\.com/spreadsheets/d/[A-Za-z0-9_-]+[^\s\)\]\"<>'`]*", 'https://docs.google.com/spreadsheets/d/REPLACE_WITH_YOUR_SPREADSHEET_ID/edit', content)
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                findings.append({'path': rel, 'kind': name})
        if any(value in content for value in secrets):
            findings.append({'path': rel, 'kind': 'exact_local_secret_value'})
        output = content.encode('utf-8')
        target = destination / rel
        if target.exists() and target.read_bytes() != output:
            starter_readme = rel == 'README.md' and target.read_text().strip() == '# Video-Gen-Model'
            unchanged_prior_export = previous_files.get(rel) == hashlib.sha256(target.read_bytes()).hexdigest()
            if not starter_readme and not unchanged_prior_export:
                findings.append({'path': rel, 'kind': 'existing_destination_conflict'})
        prepared.append((target, output, rel))
    if findings:
        print(json.dumps({'status': 'blocked', 'findings': findings}, indent=2))
        raise SystemExit(2)
    files = []
    for target, content, rel in prepared:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        files.append({'path': rel, 'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()})
    report = {'status': 'exported', 'file_count': len(files), 'total_bytes': sum(f['bytes'] for f in files),
              'credential_value_scan': 'passed', 'secret_pattern_scan': 'passed',
              'excluded': ['environment secrets', 'private voice/audio samples', 'episode data and rendered media',
                           'browser profiles and sessions', 'third-party external source trees', 'downloaded vendor/runtime packages',
                           'generated research transcripts and frames', 'run logs and local progress notes', 'brand media'],
              'workflow_transformations': transformations, 'files': files}
    (destination / 'SOURCE_EXPORT_MANIFEST.json').write_text(
        json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n',
    )
    print(json.dumps({k: v for k, v in report.items() if k != 'files'}, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True)
    export(parser.parse_args().destination)

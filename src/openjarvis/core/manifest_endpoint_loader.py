"""Runtime endpoint health test seed inject loader.

Reads OpenJarvis ALL-FILES.md manifest and lightweight runtime docs to
build endpoint-seed inject sites for JarvisNeurologicalMap and NodeTester.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / 'ALL-FILES.md'

_DOC_ENDPOINTS = {
    'docs/architecture/engine.md': '/health',
    'docs/architecture/overview.md': '/health',
    'README.md': '/health',
    'OPENJARVIS_IMPLEMENTATION_CHECKLIST.md': '/health',
    'CHANGELOG.md': '/health',
    'king_wen_codebasemap.md': '/health',
    'docs/oracle-voice-emotion-spec.md': '/health',
    'docs/getting-started/configuration.md': '/health',
    'docs/deployment/docker.md': '/health',
    'docs/user-guide/cli.md': '/health',
}


class ManifestEndpointLoader:
    def __init__(self, manifest_path: Optional[Path] = None) -> None:
        self.manifest_path = manifest_path or MANIFEST
        self.entries: List[Dict[str, str]] = []
        self.seed_map: Dict[str, Dict[str, str]] = {}

    def load(self) -> List[Dict[str, str]]:
        if not self.manifest_path.exists():
            return []
        text = self.manifest_path.read_text(encoding='utf-8', errors='ignore')
        paths: List[str] = []
        for line in text.splitlines():
            if re.match(r'^\d+\|', line):
                paths.append(line.split('|', 1)[1].strip())
            elif '|' in line and not line.startswith('#'):
                cells = [c.strip() for c in line.split('|')]
                if cells and cells[0]:
                    paths.append(cells[0])
        seen = set()
        entries: List[Dict[str, str]] = []
        for p in paths:
            if p in seen or not p:
                continue
            seen.add(p)
            category = p.split('/')[0] if '/' in p else p
            endpoint_seed = 'sha256:' + hashlib.sha256(p.encode('utf-8')).hexdigest()[:16]
            endpoint = _DOC_ENDPOINTS.get(p, '/health-doc-check')
            entries.append({
                'path': p,
                'category': category,
                'endpoint_seed': endpoint_seed,
                'endpoint': endpoint,
                'health_probe': 'HTTP/health-doc-check',
            })
            self.seed_map[endpoint_seed] = entries[-1]
        self.entries = entries
        return entries


__all__ = ['ManifestEndpointLoader']

#!/usr/bin/env python3
"""AI Friend Runtime Release Packager.

Packages the lightweight standalone runtime bundle for end users (< 2 MB),
excluding website, academic benchmarks, evals, node_modules, git history, and audit docs.

Outputs:
    dist/ai-friend-runtime.tar.gz
    dist/ai-friend-runtime.zip
"""

import os
import shutil
import sys
import tarfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = REPO_ROOT / "dist"

# Exact runtime essentials needed to run the 9-agent mesh and CLI tools
RUNTIME_FILES = [
    ".env.example",
    "docker-compose.infra.yml",
    "docker-compose.prod.yml",
    "docker-compose.light.yml",
    "docker-compose.heavy.yml",
    "livekit.yaml",
    "nats-accounts.conf",
    "start.sh",
    "start.ps1",
    "start.bat",
    "LICENSE",
    "README.md",
]

RUNTIME_DIRS = [
    "bin",
    "config",
    "personal",
    "scripts",
    "backend/app",
    "backend/scripts",
    "backend/pyproject.toml",
    "backend/Dockerfile",
    "backend/Dockerfile.rust",
    "backend/voice_samples",
    "frontend/app",
    "frontend/components",
    "frontend/lib",
    "frontend/package.json",
    "frontend/prisma",
    "frontend/Dockerfile",
    "frontend/next.config.mjs",
    "frontend/tsconfig.json",
]

EXCLUDE_PATTERNS = [
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    ".next",
    "target",
    ".DS_Store",
    ".git",
    "*.tar.gz",
    "*.zip",
]


def should_exclude(path: Path) -> bool:
    for part in path.parts:
        if part in ("__pycache__", "node_modules", ".next", "target", ".git", ".venv"):
            return True
    name = path.name
    if name.endswith((".pyc", ".pyo", ".tar.gz", ".zip", ".DS_Store")):
        return True
    return False


def build_staging_dir(stage_dir: Path) -> None:
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True)

    # Copy files
    for rel_file in RUNTIME_FILES:
        src = REPO_ROOT / rel_file
        if src.exists():
            dest = stage_dir / rel_file
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

    # Copy dirs
    for rel_dir in RUNTIME_DIRS:
        src = REPO_ROOT / rel_dir
        if not src.exists():
            continue
        dest = stage_dir / rel_dir
        if src.is_file():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        elif src.is_dir():
            for root, _, files in os.walk(src):
                root_path = Path(root)
                if should_exclude(root_path):
                    continue
                for f in files:
                    file_path = root_path / f
                    if should_exclude(file_path):
                        continue
                    rel_p = file_path.relative_to(REPO_ROOT)
                    target_p = stage_dir / rel_p
                    target_p.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file_path, target_p)


def main() -> int:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    staging_dir = DIST_DIR / "ai-friend-runtime"

    print("==> Packaging AI Friend standalone lightweight runtime bundle...")
    build_staging_dir(staging_dir)

    tar_path = DIST_DIR / "ai-friend-runtime.tar.gz"
    zip_path = DIST_DIR / "ai-friend-runtime.zip"

    # Create tar.gz
    with tarfile.open(tar_path, "w:gz") as tar:
        for root, _, files in os.walk(staging_dir):
            for f in files:
                p = Path(root) / f
                arcname = p.relative_to(DIST_DIR)
                tar.add(p, arcname=str(arcname))

    # Create zip
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(staging_dir):
            for f in files:
                p = Path(root) / f
                arcname = p.relative_to(DIST_DIR)
                z.write(p, arcname=str(arcname))

    # Clean staging dir
    shutil.rmtree(staging_dir)

    tar_size_kb = tar_path.stat().st_size / 1024
    zip_size_kb = zip_path.stat().st_size / 1024

    print(f"✓ Created {tar_path.name} ({tar_size_kb:.1f} KB)")
    print(f"✓ Created {zip_path.name} ({zip_size_kb:.1f} KB)")
    print(f"==> Standalone runtime packages ready in {DIST_DIR}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())


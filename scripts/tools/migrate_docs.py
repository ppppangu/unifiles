#!/usr/bin/env python3
"""
文档迁移脚本
根据 DOCUMENTATION_REORGANIZATION_PLAN.md 中的迁移对照表执行文档迁移
"""

import shutil
from pathlib import Path
import sys

# 项目根目录
ROOT = Path(__file__).parent.parent.parent

# 迁移映射表
MIGRATIONS = [
    # 架构文档
    ("docs/architecture/01-system-architecture-overview.md", "docs/architecture/overview.md"),
    ("docs/architecture/02-api-architecture.md", "docs/architecture/api-architecture.md"),
    ("docs/architecture/03-data-flow-diagrams.md", "docs/architecture/data-flow.md"),
    ("docs/architecture/04-database-schema.md", "docs/architecture/database-schema.md"),
    ("ARCHITECTURE_DEEP_ANALYSIS.md", "docs/architecture/deep-analysis.md"),
    ("docs/ARCHITECTURE.md", "docs/architecture/three-layer-design.md"),

    # API 文档
    ("docs/API_REFERENCE.md", "docs/api/reference.md"),
    ("docs/api_design_specification.md", "docs/api/design-spec.md"),
    ("docs/api/openapi.yaml", "docs/api/openapi.yaml"),

    # 开发文档
    ("docs/DEVELOPMENT.md", "docs/development/index.md"),
    ("docs/CONTRIBUTING.md", "docs/development/contributing.md"),
    ("docs/SCRIPTS.md", "docs/development/scripts.md"),
    ("PROGRESS.md", "docs/development/progress.md"),

    # 部署文档
    ("docs/DEPLOYMENT.md", "docs/deployment/deployment.md"),
    ("docs/CICD_SETUP.md", "docs/deployment/cicd.md"),

    # 可观测性文档
    ("docs/LOGGING_STRATEGY_ANALYSIS.md", "docs/observability/logging-strategy.md"),
    ("docs/UNIFIED_LOGGING_SYSTEM_DESIGN.md", "docs/observability/logging-design.md"),
    ("docs/OTEL_INSTRUMENTATION_STRATEGY.md", "docs/observability/otel-instrumentation.md"),
    ("docs/OBSERVABILITY_IMPLEMENTATION_STATUS.md", "docs/observability/implementation-status.md"),

    # 教程文档
    ("docs/QUICK_START.md", "docs/getting-started/index.md"),
    ("docs/tutorials/01-quick-start.md", "docs/getting-started/quick-tutorial.md"),
    ("docs/tutorials/02-developer-tutorial.md", "docs/tutorials/beginner/developer-guide.md"),

    # Unifiles-doc 文档
    ("Unifiles-doc/docs/About/about.md", "docs/about/index.md"),
    ("Unifiles-doc/docs/UnifilesPeople/unifiles_people.md", "docs/about/team.md"),
    ("Unifiles-doc/docs/Release/release_note.md", "docs/releases/release-notes.md"),
]

def migrate_file(src: str, dest: str, dry_run: bool = False) -> bool:
    """迁移单个文件"""
    src_path = ROOT / src
    dest_path = ROOT / dest

    if not src_path.exists():
        print(f"SKIP: Source file not found: {src}")
        return False

    if dest_path.exists():
        print(f"SKIP: Destination file already exists: {dest}")
        return False

    # 确保目标目录存在
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    if dry_run:
        print(f"[DRY RUN] {src} -> {dest}")
    else:
        shutil.move(str(src_path), str(dest_path))
        print(f"DONE: {src} -> {dest}")

    return True

def main():
    """主函数"""
    dry_run = "--dry-run" in sys.argv

    print("=" * 60)
    print("Documentation Migration Script")
    print("=" * 60)

    if dry_run:
        print("\nDRY RUN mode - showing operations without executing\n")

    success_count = 0
    skip_count = 0

    for src, dest in MIGRATIONS:
        if migrate_file(src, dest, dry_run):
            success_count += 1
        else:
            skip_count += 1

    print("\n" + "=" * 60)
    print(f"Migration completed: {success_count} files successful, {skip_count} files skipped")
    print("=" * 60)

    if not dry_run:
        print("\nNext steps:")
        print("1. Run 'python scripts/tools/update_doc_links.py' to update document links")
        print("2. Delete empty directories and redundant files")
        print("3. Create mkdocs.yml configuration file")

if __name__ == "__main__":
    main()

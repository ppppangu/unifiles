#!/usr/bin/env python3
"""
文档链接更新脚本
自动更新文档中的内部链接，适配新的文档结构
"""

import re
from pathlib import Path
from typing import Dict, List, Tuple

# 项目根目录
ROOT = Path(__file__).parent.parent.parent

# 链接映射表 (旧路径 -> 新路径)
LINK_MAPPING = {
    # 架构文档
    "ARCHITECTURE.md": "architecture/three-layer-design.md",
    "docs/ARCHITECTURE.md": "architecture/three-layer-design.md",
    "ARCHITECTURE_DEEP_ANALYSIS.md": "architecture/deep-analysis.md",
    "docs/architecture/01-system-architecture-overview.md": "architecture/overview.md",
    "docs/architecture/02-api-architecture.md": "architecture/api-architecture.md",
    "docs/architecture/03-data-flow-diagrams.md": "architecture/data-flow.md",
    "docs/architecture/04-database-schema.md": "architecture/database-schema.md",

    # API 文档
    "API_REFERENCE.md": "api/reference.md",
    "docs/API_REFERENCE.md": "api/reference.md",
    "api_design_specification.md": "api/design-spec.md",
    "docs/api_design_specification.md": "api/design-spec.md",

    # 开发文档
    "DEVELOPMENT.md": "development/index.md",
    "docs/DEVELOPMENT.md": "development/index.md",
    "CONTRIBUTING.md": "development/contributing.md",
    "docs/CONTRIBUTING.md": "development/contributing.md",
    "SCRIPTS.md": "development/scripts.md",
    "docs/SCRIPTS.md": "development/scripts.md",
    "PROGRESS.md": "development/progress.md",

    # 部署文档
    "DEPLOYMENT.md": "deployment/deployment.md",
    "docs/DEPLOYMENT.md": "deployment/deployment.md",
    "CICD_SETUP.md": "deployment/cicd.md",
    "docs/CICD_SETUP.md": "deployment/cicd.md",

    # 可观测性文档
    "LOGGING_STRATEGY_ANALYSIS.md": "observability/logging-strategy.md",
    "docs/LOGGING_STRATEGY_ANALYSIS.md": "observability/logging-strategy.md",
    "UNIFIED_LOGGING_SYSTEM_DESIGN.md": "observability/logging-design.md",
    "docs/UNIFIED_LOGGING_SYSTEM_DESIGN.md": "observability/logging-design.md",
    "OTEL_INSTRUMENTATION_STRATEGY.md": "observability/otel-instrumentation.md",
    "docs/OTEL_INSTRUMENTATION_STRATEGY.md": "observability/otel-instrumentation.md",
    "OBSERVABILITY_IMPLEMENTATION_STATUS.md": "observability/implementation-status.md",
    "docs/OBSERVABILITY_IMPLEMENTATION_STATUS.md": "observability/implementation-status.md",

    # 快速开始
    "QUICK_START.md": "getting-started/index.md",
    "docs/QUICK_START.md": "getting-started/index.md",
    "docs/tutorials/01-quick-start.md": "getting-started/quick-tutorial.md",

    # 教程
    "docs/tutorials/02-developer-tutorial.md": "tutorials/beginner/developer-guide.md",
}

def find_markdown_files(directory: Path) -> List[Path]:
    """查找所有 Markdown 文件"""
    return list(directory.rglob("*.md"))

def extract_links(content: str) -> List[Tuple[str, str]]:
    """提取 Markdown 中的所有链接"""
    # 匹配 [text](link) 格式
    pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
    return re.findall(pattern, content)

def update_link(link: str, current_file: Path) -> str:
    """更新单个链接"""
    # 如果是外部链接或锚点，不处理
    if link.startswith(('http://', 'https://', '#', 'mailto:')):
        return link

    # 移除查询参数和锚点
    clean_link = link.split('#')[0].split('?')[0]

    # 检查是否在映射表中
    if clean_link in LINK_MAPPING:
        new_link = LINK_MAPPING[clean_link]

        # 保留原链接的锚点
        if '#' in link:
            anchor = link.split('#')[1]
            new_link = f"{new_link}#{anchor}"

        # 计算相对路径
        current_dir = current_file.parent
        docs_dir = ROOT / "docs"

        # 如果当前文件在 docs 目录下
        if str(current_file).startswith(str(docs_dir)):
            # 计算从当前文件到目标文件的相对路径
            try:
                rel_path = Path(new_link).relative_to(current_dir.relative_to(docs_dir))
                return str(rel_path).replace('\\', '/')
            except ValueError:
                # 如果无法计算相对路径，使用绝对路径（从 docs 根开始）
                return new_link

        return new_link

    return link

def update_file_links(file_path: Path, dry_run: bool = False) -> int:
    """更新单个文件中的所有链接"""
    content = file_path.read_text(encoding='utf-8')
    original_content = content

    links = extract_links(content)
    update_count = 0

    for text, link in links:
        new_link = update_link(link, file_path)
        if new_link != link:
            # 替换链接
            old_markdown = f'[{text}]({link})'
            new_markdown = f'[{text}]({new_link})'
            content = content.replace(old_markdown, new_markdown)
            update_count += 1

            if not dry_run:
                print(f"  Updated: [{text}]({link}) -> [{text}]({new_link})")

    if update_count > 0 and not dry_run:
        file_path.write_text(content, encoding='utf-8')
        print(f"DONE: Updated {update_count} link(s) in {file_path.relative_to(ROOT)}")
    elif update_count > 0 and dry_run:
        print(f"[DRY RUN] Would update {update_count} link(s) in {file_path.relative_to(ROOT)}")

    return update_count

def main():
    """主函数"""
    import sys

    # Set UTF-8 encoding for Windows console
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    dry_run = "--dry-run" in sys.argv

    print("=" * 60)
    print("Documentation Links Update Script")
    print("=" * 60)

    if dry_run:
        print("\nDRY RUN mode - showing operations without executing\n")

    docs_dir = ROOT / "docs"

    if not docs_dir.exists():
        print(f"Error: docs directory not found at {docs_dir}")
        sys.exit(1)

    markdown_files = find_markdown_files(docs_dir)
    print(f"\nFound {len(markdown_files)} Markdown files\n")

    total_updates = 0
    files_updated = 0

    for file_path in markdown_files:
        updates = update_file_links(file_path, dry_run)
        if updates > 0:
            total_updates += updates
            files_updated += 1

    print("\n" + "=" * 60)
    print(f"Update completed: {total_updates} links in {files_updated} files")
    print("=" * 60)

    if dry_run:
        print("\nRun without --dry-run to apply changes")
    else:
        print("\nAll links have been updated successfully!")

if __name__ == "__main__":
    main()

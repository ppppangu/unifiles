#!/usr/bin/env python3
"""
数据库初始化脚本

功能：
1. 检查数据库是否存在，若不存在则自动创建
2. 删除现有表结构（开发模式）
3. 按顺序执行 SQL 脚本创建数据库结构
4. 支持跳过删除步骤（生产模式）
5. 验证数据库结构完整性

用法：
    # 开发环境：完全重建数据库
    python scripts/init_db.py --drop

    # 生产环境：仅初始化（不删除现有数据）
    python scripts/init_db.py

特点：
- 自动创建数据库（如果不存在）
- 连接到 postgres 系统数据库进行数据库级操作
- 然后切换到目标数据库进行表结构操作
"""

import asyncio
import sys
from pathlib import Path

import asyncpg

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from unifiles.core.config.env_config import read_pg_config


async def execute_sql_file(conn: asyncpg.Connection, sql_file: Path):
    """执行单个 SQL 文件"""
    print(f"  📄 执行: {sql_file.name}")
    sql_content = sql_file.read_text(encoding="utf-8")

    try:
        await conn.execute(sql_content)
        print(f"  ✅ 成功: {sql_file.name}")
    except Exception as e:
        print(f"  ❌ 失败: {sql_file.name}")
        print(f"     错误: {e}")
        raise


async def check_and_create_database(db_config: dict) -> bool:
    """检查数据库是否存在，如果不存在则创建"""
    print(f"\n" + "=" * 60)
    print("  步骤 0: 检查数据库是否存在")
    print("=" * 60)
    
    target_db = db_config['database']
    
    # 先连接到 postgres 数据库来检查和创建目标数据库
    admin_dsn = f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/postgres"
    
    try:
        admin_conn = await asyncpg.connect(admin_dsn)
        
        # 检查数据库是否存在
        db_exists = await admin_conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname = $1)",
            target_db
        )
        
        if db_exists:
            print(f"  ✅ 数据库 '{target_db}' 已存在")
            await admin_conn.close()
            return True
        else:
            print(f"  ⚠️  数据库 '{target_db}' 不存在，正在创建...")
            
            # 创建数据库
            try:
                await admin_conn.execute(f'CREATE DATABASE "{target_db}"')
                print(f"  ✅ 数据库 '{target_db}' 创建成功")
                
                # 授予用户权限（如果需要）
                try:
                    await admin_conn.execute(f'GRANT ALL PRIVILEGES ON DATABASE "{target_db}" TO {db_config["user"]}')
                    print(f"  ✅ 权限授予成功")
                except Exception as e:
                    print(f"  ⚠️  权限授予失败: {e}")
                    
            except Exception as e:
                print(f"  ❌ 数据库创建失败: {e}")
                await admin_conn.close()
                return False
            
            await admin_conn.close()
            return True
            
    except Exception as e:
        print(f"  ❌ 数据库检查失败: {e}")
        return False

async def init_database(drop_existing: bool = False):
    """初始化数据库"""
    print("=" * 60)
    print("  Unifiles 数据库初始化")
    print("=" * 60)

    # 构建连接字符串
    db_config = read_pg_config()
    
    print(f"\n📡 连接信息:")
    print(f"  Host: {db_config['host']}:{db_config['port']}")
    print(f"  Database: {db_config['database']}")
    print(f"  User: {db_config['user']}")
    print(f"  Mode: {'DROP & RECREATE' if drop_existing else 'INIT ONLY'}")

    # 首先检查并创建数据库（如果需要）
    db_check_result = await check_and_create_database(db_config)
    if not db_check_result:
        print(f"\n❌ 数据库准备失败，程序退出")
        sys.exit(1)
    
    # 构建目标数据库的连接字符串
    target_dsn = f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"

    # 连接目标数据库
    try:
        conn = await asyncpg.connect(target_dsn)
        print(f"\n✅ 目标数据库连接成功")
    except Exception as e:
        print(f"\n❌ 目标数据库连接失败: {e}")
        print(f"\n请检查：")
        print(f"  1. PostgreSQL 服务是否启动")
        print(f"  2. 数据库配置是否正确（.env 文件）")
        print(f"  3. 用户名和密码是否正确")
        print(f"  4. 数据库是否已创建")
        sys.exit(1)

    try:
        sql_dir = project_root / "scripts" / "sql"

        # 步骤 1: 删除现有结构（如果指定）
        if drop_existing:
            print(f"\n" + "=" * 60)
            print("  步骤 1: 删除现有数据库结构")
            print("=" * 60)
            print(f"\n⚠️  警告: 即将删除所有表和数据！")

            drop_file = sql_dir / "000-drop-all.sql"
            if drop_file.exists():
                await execute_sql_file(conn, drop_file)
            else:
                print(f"  ⚠️  未找到删除脚本: {drop_file}")

        # 步骤 2: 按顺序执行 SQL 脚本
        print(f"\n" + "=" * 60)
        print("  步骤 2: 创建数据库结构")
        print("=" * 60)

        # SQL 文件执行顺序（按文件名排序）
        sql_files = sorted(sql_dir.glob("*.sql"))

        # 排除 drop 脚本
        sql_files = [f for f in sql_files if not f.name.startswith("000-")]

        if not sql_files:
            print(f"\n❌ 未找到 SQL 脚本文件")
            print(f"   请检查目录: {sql_dir}")
            sys.exit(1)

        print(f"\n📋 找到 {len(sql_files)} 个 SQL 脚本:\n")

        for sql_file in sql_files:
            await execute_sql_file(conn, sql_file)

        # 步骤 3: 验证
        print(f"\n" + "=" * 60)
        print("  步骤 3: 验证数据库结构")
        print("=" * 60)

        # 检查表数量
        table_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'unifiles'
            AND table_type = 'BASE TABLE'
            """
        )
        print(f"\n  ✅ 创建了 {table_count} 个表")

        # 检查扩展
        extensions = await conn.fetch(
            """
            SELECT extname, extversion
            FROM pg_extension
            WHERE extname IN ('vector', 'uuid-ossp')
            """
        )
        print(f"  ✅ PostgreSQL 扩展:")
        for ext in extensions:
            print(f"     - {ext['extname']} (v{ext['extversion']})")

        # 检查 schema
        schema_exists = await conn.fetchval(
            """
            SELECT EXISTS(
                SELECT 1 FROM information_schema.schemata
                WHERE schema_name = 'unifiles'
            )
            """
        )
        if schema_exists:
            print(f"  ✅ Schema 'unifiles' 已创建")
        else:
            print(f"  ❌ Schema 'unifiles' 未找到")

        print(f"\n" + "=" * 60)
        print("  🎉 数据库初始化完成！")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 数据库初始化失败:")
        print(f"   {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        await conn.close()
        print(f"\n📡 数据库连接已关闭")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="Unifiles 数据库初始化脚本")
    parser.add_argument(
        "--drop",
        action="store_true",
        help="删除现有数据库结构后重建（仅开发环境使用）",
    )
    args = parser.parse_args()

    if args.drop:
        print("\n⚠️  警告: 你选择了 --drop 模式，这将删除所有现有数据！")
        response = input("   确认继续？[y/N]: ")
        if response.lower() != "y":
            print("   操作已取消")
            sys.exit(0)

    asyncio.run(init_database(drop_existing=args.drop))


if __name__ == "__main__":
    main()

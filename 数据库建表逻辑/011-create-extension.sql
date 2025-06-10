/*
 * 文件名: 011-create-extension.sql
 * 作用: 创建PostgreSQL必要的扩展插件
 * 组成:
 * 1. 向量化支持: pgvector, vectorscale
 * 2. 全文检索: rum, pg_jieba(中文分词)
 * 3. 性能与缓存: pg_prewarm
 * 4. 编程能力: plpython3u
 * 5. 数据结构: ltree(层级结构)
 * 6. 安全与加密: pgcrypto
 * 7. 网络连接: http
 * 8. 任务管理: pg_background, pg_cron
 * 9. 设置相关权限
 */

-- 启用 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 启用 pg_prewarm 插件
CREATE EXTENSION IF NOT EXISTS pg_prewarm;

-- 启用 rum 插件
CREATE EXTENSION IF NOT EXISTS rum;

-- 启用 pg_jie 中文分词插件
CREATE EXTENSION IF NOT EXISTS pg_jieba;

-- 创建jieba文本搜索配置
DO $$
BEGIN
    -- 检查配置是否已存在
    IF NOT EXISTS (
        SELECT 1 FROM pg_ts_config WHERE cfgname = 'jieba'
    ) THEN
        -- 创建jieba文本搜索配置
        EXECUTE 'CREATE TEXT SEARCH CONFIGURATION jieba (PARSER = jieba)';
        EXECUTE 'ALTER TEXT SEARCH CONFIGURATION jieba ADD MAPPING FOR n,v,a,i,e,l WITH simple';
    END IF;
END
$$;

-- 启用 Python 扩展
CREATE EXTENSION IF NOT EXISTS plpython3u;

-- 启用 pg_search 拓展
CREATE EXTENSION IF NOT EXISTS pg_search;

-- 启用pg_mooncake拓展，用于管理pg_mooncake
-- CREATE EXTENSION IF NOT EXISTS pg_mooncake;

-- 启用 timescaledb 拓展
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- 启用 vectorscale 拓展
CREATE EXTENSION IF NOT EXISTS vectorscale CASCADE;

-- 启用 ltree 拓展,用于管理文档层级的分类
CREATE EXTENSION IF NOT EXISTS ltree;

-- 启用 pgcrypto 拓展,用于生成uuid
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 启用http拓展,用于互联网连接
CREATE EXTENSION IF NOT EXISTS http;

-- 启用pg_background拓展，用于任务队列
CREATE EXTENSION IF NOT EXISTS pg_background;

-- 启用pg_cron拓展，用于定时任务
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- 设置权限
GRANT EXECUTE ON FUNCTION pg_background_launch TO PUBLIC;
GRANT EXECUTE ON FUNCTION pg_background_result TO PUBLIC;
GRANT EXECUTE ON FUNCTION pg_background_detach TO PUBLIC;

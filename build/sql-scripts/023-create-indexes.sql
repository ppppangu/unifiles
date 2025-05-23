/*
 * 文件名: 023-create-indexes.sql
 * 作用: 创建数据库索引，优化查询性能
 * 组成:
 * 1. 文档表索引:
 *    - hierarchy_path: 文档层级路径GIST索引
 * 2. 成分表索引:
 *    - doc_position: 文档位置索引
 *    - tsv: 文本倒排索引
 * 3. 逻辑层级表索引:
 *    - user_id_idx: 用户ID索引
 *    - knowledge_base_id_idx: 知识库ID索引
 */

-- 文档表索引
-- 用于按文档层级路径进行查询，如查找特定分类下的所有文档
CREATE INDEX ON chunk_schema.documents USING GIST(hierarchy_path);

-- 成分表索引
-- 用于按文档位置快速查询，如获取文档的特定位置的内容
CREATE INDEX ON chunk_schema.components(document_id, doc_position);

-- 用于按成分内容进行全文搜索，如搜索包含特定关键词的文本块
CREATE INDEX ON chunk_schema.components USING RUM(tsv);

-- 逻辑层级表索引
-- 用于快速查找用户的所有标签，如获取用户的所有标签配置
CREATE INDEX IF NOT EXISTS logical_hierarchy_user_id_idx ON chunk_schema.logical_hierarchy(user_id);

-- 用于快速查找知识库的所有标签，如获取知识库的所有标签配置
CREATE INDEX IF NOT EXISTS logical_hierarchy_knowledge_base_id_idx ON chunk_schema.logical_hierarchy(knowledge_base_id); 
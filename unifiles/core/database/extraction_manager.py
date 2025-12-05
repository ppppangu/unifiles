"""
提取内容数据库管理器
管理 extracted_documents、processing_strategies 和 process_logs 表的操作
"""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from unifiles.core.logging import get_logger

logger = get_logger()

from .base_manager import BaseDBManager


class ExtractionDBManager(BaseDBManager):
    """提取内容数据库管理器"""

    async def create_or_get_processing_strategy(
        self,
        strategy_name: str,
        strategy_type: str,
        processing_config: Dict[str, Any],
    ) -> str:
        """
        创建或获取处理策略

        Args:
            strategy_name: 策略名称
            strategy_type: 策略类型 (ocr, nlp, multimodal, hybrid, custom)
            processing_config: 处理器配置，必须包含 method 和 version 字段

        Returns:
            策略ID

        Raises:
            ValueError: 如果参数无效
        """
        try:
            # 验证必需字段
            if "method" not in processing_config:
                raise ValueError("processing_config must contain 'method' field")
            if "version" not in processing_config:
                processing_config["version"] = "1.0.0"  # 默认版本

            # 清理输入
            strategy_name = self.sanitize_input(strategy_name)
            strategy_type = self.sanitize_input(strategy_type)

            # 检查是否已存在相同配置的策略
            method = processing_config.get("method")
            existing_query = f"""
                SELECT id FROM {self._schema_name}.processing_strategies
                WHERE strategy_name = $1
                AND strategy_type = $2
                AND processing_config->>'method' = $3
                AND is_active = TRUE
                LIMIT 1
            """

            existing = await self.fetch_one(
                existing_query,
                strategy_name,
                strategy_type,
                method,
                operation="strategy_check",
            )

            if existing:
                logger.info(f"Using existing processing strategy: {existing['id']}")
                return existing["id"]

            # 创建新策略
            strategy_id = str(uuid.uuid4())

            insert_query = f"""
                INSERT INTO {self._schema_name}.processing_strategies (
                    id, strategy_name, strategy_type, processing_config,
                    is_active, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
            """

            result = await self.fetch_one(
                insert_query,
                strategy_id,
                strategy_name,
                strategy_type,
                json.dumps(processing_config),  # 转换为JSON字符串
                True,
                datetime.now(),
                datetime.now(),
                operation="strategy_creation",
            )

            logger.info(f"Created new processing strategy: {strategy_id}")
            return result["id"]

        except Exception as e:
            logger.error(f"Error creating/getting processing strategy: {e}")
            raise

    async def create_extracted_document(
        self,
        file_id: str,
        user_id: str,
        extraction_strategy_id: str,
        full_markdown: str,
        structured_content: Optional[Dict[str, Any]] = None,
        total_pages: int = 0,
        total_chars: int = 0,
        total_assets: int = 0,
        extraction_metadata: Optional[Dict[str, Any]] = None,
        extraction_status: str = "completed",
        storage_config_id: Optional[str] = None,
        storage_path: Optional[str] = None,
    ) -> str:
        """
        创建提取文档记录

        Args:
            file_id: 文件ID
            user_id: 用户ID
            extraction_strategy_id: 处理策略ID
            full_markdown: 完整的Markdown内容
            structured_content: 结构化内容（可选）
            total_pages: 总页数
            total_chars: 总字符数
            total_assets: 总资源数
            extraction_metadata: 提取元数据
            extraction_status: 提取状态
            storage_config_id: 存储配置ID（可选）
            storage_path: 存储路径（可选）

        Returns:
            提取文档ID

        Raises:
            ValueError: 如果参数无效
        """
        try:
            # 清理输入
            file_id = self.sanitize_input(file_id)
            user_id = self.sanitize_input(user_id)
            extraction_strategy_id = self.sanitize_input(extraction_strategy_id)

            # 检查文件是否已有提取记录
            existing_query = f"""
                SELECT id FROM {self._schema_name}.extracted_documents
                WHERE file_id = $1 AND extraction_strategy_id = $2
                LIMIT 1
            """

            existing = await self.fetch_one(
                existing_query,
                file_id,
                extraction_strategy_id,
                operation="extraction_check",
            )

            if existing:
                logger.info(
                    f"Extracted document already exists for file {file_id}: {existing['id']}"
                )
                # 更新现有记录
                await self.update_extracted_document(
                    extraction_id=existing["id"],
                    full_markdown=full_markdown,
                    total_pages=total_pages,
                    total_chars=total_chars,
                    total_assets=total_assets,
                    extraction_metadata=extraction_metadata,
                    extraction_status=extraction_status,
                )
                return existing["id"]

            # 创建新的提取文档记录
            extraction_id = str(uuid.uuid4())

            if extraction_metadata is None:
                extraction_metadata = {}

            insert_query = f"""
                INSERT INTO {self._schema_name}.extracted_documents (
                    id, file_id, user_id, extraction_strategy_id,
                    storage_config_id, storage_path,
                    full_markdown, total_pages, total_chars, total_assets,
                    extraction_status, performance_metrics, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                RETURNING id
            """

            # 将 extraction_metadata 存储到 performance_metrics 字段
            performance_metrics = json.dumps(extraction_metadata)  # 转换为JSON字符串

            result = await self.fetch_one(
                insert_query,
                extraction_id,
                file_id,
                user_id,
                extraction_strategy_id,
                storage_config_id,
                storage_path,
                full_markdown,
                total_pages,
                total_chars,
                total_assets,
                extraction_status,
                performance_metrics,
                datetime.now(),
                user_id=user_id,
                operation="extraction_creation",
            )

            logger.info(
                f"Created extracted document: {extraction_id} for file: {file_id}"
            )
            return result["id"]

        except Exception as e:
            logger.error(f"Error creating extracted document: {e}")
            raise

    async def update_extracted_document(
        self,
        extraction_id: str,
        full_markdown: Optional[str] = None,
        total_pages: Optional[int] = None,
        total_chars: Optional[int] = None,
        total_assets: Optional[int] = None,
        extraction_metadata: Optional[Dict[str, Any]] = None,
        extraction_status: Optional[str] = None,
    ) -> None:
        """
        更新提取文档记录

        Args:
            extraction_id: 提取文档ID
            full_markdown: 完整的Markdown内容
            total_pages: 总页数
            total_chars: 总字符数
            total_assets: 总资源数
            extraction_metadata: 提取元数据
            extraction_status: 提取状态
        """
        try:
            extraction_id = self.sanitize_input(extraction_id)

            # 构建动态更新语句
            update_fields = []
            values = [extraction_id]
            param_count = 1

            if full_markdown is not None:
                param_count += 1
                update_fields.append(f"full_markdown = ${param_count}")
                values.append(full_markdown)

            if total_pages is not None:
                param_count += 1
                update_fields.append(f"total_pages = ${param_count}")
                values.append(total_pages)

            if total_chars is not None:
                param_count += 1
                update_fields.append(f"total_chars = ${param_count}")
                values.append(total_chars)

            if total_assets is not None:
                param_count += 1
                update_fields.append(f"total_assets = ${param_count}")
                values.append(total_assets)

            if extraction_metadata is not None:
                param_count += 1
                update_fields.append(f"performance_metrics = ${param_count}")
                values.append(json.dumps(extraction_metadata))  # 转换为JSON字符串

            if extraction_status is not None:
                param_count += 1
                update_fields.append(f"extraction_status = ${param_count}")
                values.append(extraction_status)

            if not update_fields:
                logger.warning("No fields to update for extracted document")
                return

            query = f"""
                UPDATE {self._schema_name}.extracted_documents
                SET {", ".join(update_fields)}
                WHERE id = $1
            """

            await self.execute_query(query, *values, operation="extraction_update")

            logger.info(f"Updated extracted document: {extraction_id}")

        except Exception as e:
            logger.error(f"Error updating extracted document: {e}")
            raise

    async def get_extracted_document(
        self, extraction_id: str, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取提取文档记录

        Args:
            extraction_id: 提取文档ID
            user_id: 用户ID（用于权限验证）

        Returns:
            提取文档记录字典，如果不存在则返回None
        """
        try:
            extraction_id = self.sanitize_input(extraction_id)

            query = f"""
                SELECT
                    ed.id, ed.file_id, ed.user_id, ed.extraction_strategy_id,
                    ed.storage_config_id, ed.storage_path,
                    ed.full_markdown, ed.total_pages, ed.total_chars, ed.total_assets,
                    ed.extraction_status, ed.performance_metrics, ed.created_at,
                    ps.strategy_name, ps.strategy_type, ps.processing_config
                FROM {self._schema_name}.extracted_documents ed
                LEFT JOIN {self._schema_name}.processing_strategies ps
                    ON ed.extraction_strategy_id = ps.id
                WHERE ed.id = $1
            """

            if user_id:
                query += " AND ed.user_id = $2"
                result = await self.fetch_one(
                    query,
                    extraction_id,
                    user_id,
                    user_id=user_id,
                    operation="extraction_query",
                )
            else:
                result = await self.fetch_one(
                    query, extraction_id, operation="extraction_query"
                )

            return result

        except Exception as e:
            logger.error(f"Error getting extracted document: {e}")
            raise

    async def get_extracted_documents_by_file(
        self, file_id: str, user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取文件的所有提取记录

        Args:
            file_id: 文件ID
            user_id: 用户ID（用于权限验证）

        Returns:
            提取文档记录列表
        """
        try:
            file_id = self.sanitize_input(file_id)

            query = f"""
                SELECT
                    ed.id, ed.file_id, ed.user_id, ed.extraction_strategy_id,
                    ed.total_pages, ed.total_chars, ed.total_assets,
                    ed.extraction_status, ed.created_at,
                    ps.strategy_name, ps.strategy_type
                FROM {self._schema_name}.extracted_documents ed
                LEFT JOIN {self._schema_name}.processing_strategies ps
                    ON ed.extraction_strategy_id = ps.id
                WHERE ed.file_id = $1
            """

            if user_id:
                query += " AND ed.user_id = $2"
                results = await self.fetch_many(
                    query,
                    file_id,
                    user_id,
                    user_id=user_id,
                    operation="extraction_list",
                )
            else:
                results = await self.fetch_many(
                    query, file_id, operation="extraction_list"
                )

            return results

        except Exception as e:
            logger.error(f"Error getting extracted documents by file: {e}")
            raise

    async def create_extracted_asset(
        self,
        extracted_document_id: str,
        asset_type: str,
        storage_path: str,
        asset_name: Optional[str] = None,
        original_filename: Optional[str] = None,
        file_size: Optional[int] = None,
        mime_type: Optional[str] = None,
        format: Optional[str] = None,
        position_in_document: Optional[int] = None,
        page_number: Optional[int] = None,
        alt_text: Optional[str] = None,
        asset_description: Optional[str] = None,
        storage_config_id: Optional[str] = None,
    ) -> str:
        """
        创建提取资源记录

        Args:
            extracted_document_id: 提取文档ID
            asset_type: 资源类型 (text, image, table, code, chart, formula)
            storage_path: 存储路径（对象路径）
            asset_name: 资源名称
            original_filename: 原始文件名
            file_size: 文件大小（字节）
            mime_type: MIME类型
            format: 文件格式
            position_in_document: 在文档中的位置序号
            page_number: 所在页码
            alt_text: 替代文本
            asset_description: 资源描述
            storage_config_id: 存储配置ID（可选）

        Returns:
            资源ID

        Raises:
            ValueError: 如果参数无效
        """
        try:
            # 清理输入
            extracted_document_id = self.sanitize_input(extracted_document_id)
            asset_type = self.sanitize_input(asset_type)
            storage_path = self.sanitize_input(storage_path)

            asset_id = str(uuid.uuid4())

            insert_query = f"""
                INSERT INTO {self._schema_name}.extracted_assets (
                    id, extracted_document_id, asset_type, asset_name,
                    original_filename, storage_config_id, storage_path,
                    file_size, mime_type, format,
                    position_in_document, page_number,
                    asset_description, alt_text,
                    created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                RETURNING id
            """

            result = await self.fetch_one(
                insert_query,
                asset_id,
                extracted_document_id,
                asset_type,
                asset_name,
                original_filename,
                storage_config_id,
                storage_path,
                file_size,
                mime_type,
                format,
                position_in_document,
                page_number,
                asset_description,
                alt_text,
                datetime.now(),
                operation="asset_creation",
            )

            logger.info(
                f"Created extracted asset: {asset_id} for document: {extracted_document_id}"
            )
            return result["id"]

        except Exception as e:
            logger.error(f"Error creating extracted asset: {e}")
            raise

    async def create_process_log(
        self,
        entity_id: str,
        entity_type: str,
        process_type: str,
        action: str,
        status: str,
        log_type: str = "log",
        log_level: str = "info",
        process_stage: Optional[str] = None,
        message: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None,
        input_params: Optional[Dict[str, Any]] = None,
        output_results: Optional[Dict[str, Any]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """
        创建处理日志记录

        Args:
            entity_id: 实体ID
            entity_type: 实体类型 (file, document, asset, chunk, etc.)
            process_type: 处理类型 (extraction, chunking, embedding, etc.)
            action: 执行的动作
            status: 状态 (started, in_progress, completed, failed, cancelled, retrying)
            log_type: 日志类型 (log, error)
            log_level: 日志级别 (debug, info, warning, error, critical)
            process_stage: 处理阶段
            message: 日志消息
            error_details: 错误详情
            input_params: 输入参数
            output_results: 输出结果
            start_time: 开始时间
            end_time: 结束时间
            user_id: 用户ID

        Returns:
            日志ID
        """
        try:
            log_id = str(uuid.uuid4())
            process_id = str(uuid.uuid4())  # 每个日志记录一个唯一的process_id

            if error_details is None:
                error_details = {}
            if input_params is None:
                input_params = {}
            if output_results is None:
                output_results = {}

            insert_query = f"""
                INSERT INTO {self._schema_name}.process_logs (
                    id, log_type, log_level, process_type, process_stage, process_id,
                    entity_type, entity_id, user_id, action, status,
                    message, error_details, input_params, output_results,
                    start_time, end_time, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
                RETURNING id
            """

            result = await self.fetch_one(
                insert_query,
                log_id,
                log_type,
                log_level,
                process_type,
                process_stage,
                process_id,
                entity_type,
                entity_id,
                user_id,
                action,
                status,
                message,
                json.dumps(error_details),  # 转换为JSON字符串
                json.dumps(input_params),  # 转换为JSON字符串
                json.dumps(output_results),  # 转换为JSON字符串
                start_time or datetime.now(),
                end_time,
                datetime.now(),
                operation="log_creation",
            )

            logger.debug(f"Created process log: {log_id}")
            return result["id"]

        except Exception as e:
            logger.error(f"Error creating process log: {e}")
            raise


# 全局实例
extraction_db_manager = ExtractionDBManager()

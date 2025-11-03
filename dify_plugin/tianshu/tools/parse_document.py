import logging
from collections.abc import Generator
from dataclasses import dataclass
from typing import Any, Dict
import os

import httpx
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

# 禁用代理
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
os.environ['no_proxy'] = 'localhost,127.0.0.1'

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s - [Parse Tool] - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


@dataclass
class Credentials:
    api_base_url: str
    api_key: str


class TianshuParseTool(Tool):

    def _get_credentials(self) -> Credentials:
        """Get and validate credentials."""
        api_base_url = self.runtime.credentials.get("api_base_url")
        api_key = self.runtime.credentials.get("api_key")

        if not api_base_url:
            logger.error("Missing api_base_url in credentials")
            raise ToolProviderCredentialValidationError("Please input API Base URL")

        if not api_key:
            logger.error("Missing api_key in credentials")
            raise ToolProviderCredentialValidationError("Please input API Key")

        return Credentials(
            api_base_url=api_base_url.rstrip("/"),
            api_key=api_key
        )

    def _invoke(self, tool_parameters: Dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        """Submit document parsing task."""
        logger.info("=" * 80)
        logger.info("开始执行文档解析任务")
        logger.info("=" * 80)

        try:
            credentials = self._get_credentials()
            logger.info(f"📡 API Base URL: {credentials.api_base_url}")

            # Get parameters
            file = tool_parameters.get("file")
            if not file:
                logger.error("❌ 缺少文件参数")
                yield self.create_text_message("File is required")
                return

            backend = tool_parameters.get("backend", "auto")
            lang = tool_parameters.get("lang", "auto")
            formula_enable = tool_parameters.get("formula_enable", True)
            table_enable = True  # Always enabled
            priority = tool_parameters.get("priority", 0)

            logger.info(f"📄 文件信息:")
            logger.info(f"   文件名: {file.filename}")
            logger.info(f"   文件大小: {len(file.blob)} bytes")
            logger.info(f"📋 解析参数:")
            logger.info(f"   backend: {backend}")
            logger.info(f"   lang: {lang}")
            logger.info(f"   formula_enable: {formula_enable}")
            logger.info(f"   priority: {priority}")

            # Prepare multipart/form-data request
            files = {
                "file": (file.filename, file.blob, "application/octet-stream")
            }
            data = {
                "backend": backend,
                "lang": lang,
                "method": "auto",
                "formula_enable": str(formula_enable).lower(),
                "table_enable": str(table_enable).lower(),
                "priority": str(priority)
            }

            # Submit task
            headers = self._get_headers(credentials)
            url = f"{credentials.api_base_url}/api/v1/tasks/submit"

            logger.info(f"📤 提交任务到: {url}")
            logger.info(f"   Headers: X-API-Key=***")

            try:
                with httpx.Client(timeout=120.0) as client:
                    response = client.post(url, headers=headers, files=files, data=data)

                logger.info(f"📥 收到响应: {response.status_code}")
                logger.debug(f"   响应内容: {response.text[:500]}")

                if response.status_code == 401:
                    logger.error("❌ 认证失败 (401)")
                    yield self.create_text_message("Authentication failed: Invalid API Key")
                    return
                elif response.status_code == 403:
                    logger.error("❌ 权限不足 (403)")
                    logger.error(f"   详情: {response.text}")
                    yield self.create_text_message(f"Permission denied (403): {response.text}")
                    return
                elif response.status_code != 200:
                    logger.error(f"❌ 任务提交失败: {response.status_code}")
                    logger.error(f"   详情: {response.text}")
                    error_detail = response.text
                    yield self.create_text_message(f"Failed to submit task: HTTP {response.status_code}. {error_detail}")
                    return

                # Parse response
                result = response.json()
                logger.debug(f"解析响应 JSON: {result}")

                if result.get("success"):
                    task_id = result.get("task_id")
                    status = result.get("status", "pending")
                    file_name = result.get("file_name", file.filename)

                    logger.info(f"✅ 任务提交成功!")
                    logger.info(f"   Task ID: {task_id}")
                    logger.info(f"   状态: {status}")
                    logger.info(f"   文件名: {file_name}")
                    logger.info("=" * 80)

                    yield self.create_json_message({
                        "task_id": task_id,
                        "message": "任务已提交，请使用 get_task_status 工具查询结果",
                        "file_name": file_name,
                        "status": status
                    })
                else:
                    error_msg = result.get("detail", "Unknown error")
                    logger.error(f"❌ 任务提交失败: {error_msg}")
                    logger.info("=" * 80)
                    yield self.create_text_message(f"Failed to submit task: {error_msg}")

            except httpx.RequestError as e:
                logger.exception(f"❌ 网络请求错误:")
                logger.info("=" * 80)
                yield self.create_text_message(f"Network error: {str(e)}")
            except Exception as e:
                logger.exception(f"❌ 未预期的错误:")
                logger.info("=" * 80)
                yield self.create_text_message(f"Unexpected error: {str(e)}")

        except Exception as e:
            yield self.create_text_message(f"Error in parse_document tool: {str(e)}")

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
        '%(asctime)s - [GetStatus Tool] - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


@dataclass
class Credentials:
    api_base_url: str
    api_key: str


class TianshuGetStatusTool(Tool):

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

    def _get_headers(self, credentials: Credentials) -> Dict[str, str]:
        """Get request headers."""
        return {
            'X-API-Key': credentials.api_key,
            'Accept': 'application/json'
        }

    def _invoke(self, tool_parameters: Dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        """Query document parsing task status."""
        logger.info("=" * 80)
        logger.info("开始查询任务状态")
        logger.info("=" * 80)

        try:
            credentials = self._get_credentials()
            logger.info(f"📡 API Base URL: {credentials.api_base_url}")

            # Get parameters
            task_id = tool_parameters.get("task_id")
            if not task_id:
                logger.error("❌ 缺少 task_id 参数")
                yield self.create_text_message("task_id is required")
                return

            format_type = tool_parameters.get("format", "markdown")
            upload_images = tool_parameters.get("upload_images", False)

            logger.info(f"🔍 查询参数:")
            logger.info(f"   Task ID: {task_id}")
            logger.info(f"   Format: {format_type}")
            logger.info(f"   Upload Images: {upload_images}")

            # Validate format parameter
            if format_type not in ["markdown", "json", "both"]:
                logger.error(f"❌ 无效的 format 参数: {format_type}")
                yield self.create_text_message(f"Invalid format: {format_type}")
                return

            # Build query parameters
            params = {
                "format": format_type,
                "upload_images": str(upload_images).lower()
            }

            # Query task status
            headers = self._get_headers(credentials)
            url = f"{credentials.api_base_url}/api/v1/tasks/{task_id}"

            logger.info(f"📤 发送查询请求: {url}")
            logger.info(f"   Params: {params}")

            try:
                with httpx.Client(timeout=120.0) as client:
                    response = client.get(url, headers=headers, params=params)

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
                elif response.status_code == 404:
                    logger.warning(f"⚠️  任务不存在: {task_id}")
                    yield self.create_text_message(f"Task not found: {task_id}")
                    return
                elif response.status_code != 200:
                    logger.error(f"❌ 查询失败: {response.status_code}")
                    logger.error(f"   详情: {response.text}")
                    error_detail = response.text
                    yield self.create_text_message(f"Failed to query task: HTTP {response.status_code}. {error_detail}")
                    return

                # Parse response
                result = response.json()
                logger.debug(f"解析响应 JSON: {result.keys() if isinstance(result, dict) else type(result)}")

                if not result.get("success"):
                    error_msg = result.get("detail", "Unknown error")
                    logger.error(f"❌ 查询失败: {error_msg}")
                    yield self.create_text_message(f"Failed to query task: {error_msg}")
                    return

                status = result.get("status", "unknown")
                task_id_returned = result.get("task_id", task_id)
                file_name = result.get("file_name", "")
                error_message = result.get("error_message")

                logger.info(f"📊 任务状态:")
                logger.info(f"   Task ID: {task_id_returned}")
                logger.info(f"   文件名: {file_name}")
                logger.info(f"   状态: {status}")

                # Build response
                response_data = {
                    "task_id": task_id_returned,
                    "status": status,
                    "file_name": file_name
                }

                if status == "completed":
                    logger.info("✅ 任务已完成!")
                    # Task completed, return parsed content
                    data = result.get("data")
                    if data:
                        if format_type in ["markdown", "both"]:
                            content = data.get("content")
                            if content:
                                logger.info(f"   Markdown 内容长度: {len(content)} 字符")
                                response_data["content"] = content
                                response_data["markdown_file"] = data.get("markdown_file")
                                response_data["images_uploaded"] = data.get("images_uploaded", False)

                        if format_type in ["json", "both"]:
                            json_content = data.get("json_content")
                            if json_content:
                                logger.info("   包含 JSON 结构化内容")
                                response_data["json_content"] = json_content
                                response_data["json_file"] = data.get("json_file")

                    logger.info("=" * 80)
                    yield self.create_json_message(response_data)
                    if response_data.get("content"):
                        yield self.create_text_message(response_data["content"])

                elif status in ["pending", "processing"]:
                    logger.info(f"⏳ 任务处理中: {status}")
                    logger.info("=" * 80)
                    # Task processing
                    response_data["message"] = "任务正在处理中" if status == "processing" else "任务等待处理中"
                    yield self.create_json_message(response_data)

                elif status == "failed":
                    logger.error(f"❌ 任务失败: {error_message}")
                    logger.info("=" * 80)
                    # Task failed
                    response_data["error"] = error_message or "Task failed"
                    yield self.create_json_message(response_data)

                else:
                    logger.warning(f"⚠️  未知状态: {status}")
                    logger.info("=" * 80)
                    # Other status
                    response_data["message"] = f"Task status: {status}"
                    if error_message:
                        response_data["error"] = error_message
                    yield self.create_json_message(response_data)

            except httpx.RequestError as e:
                logger.exception(f"❌ 网络请求错误:")
                logger.info("=" * 80)
                yield self.create_text_message(f"Network error: {str(e)}")
            except Exception as e:
                logger.exception(f"❌ 未预期的错误:")
                logger.info("=" * 80)
                yield self.create_text_message(f"Unexpected error: {str(e)}")

        except Exception as e:
            yield self.create_text_message(f"Error in get_task_status tool: {str(e)}")

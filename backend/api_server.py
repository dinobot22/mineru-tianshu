"""
MinerU Tianshu - API Server
天枢 API 服务器

企业级 AI 数据预处理平台
支持文档、图片、音频、视频等多模态数据处理
提供 RESTful API 接口用于任务提交、查询和管理
企业级认证授权: JWT Token + API Key + SSO
"""

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Depends
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from loguru import logger
import uvicorn
from typing import Optional
from datetime import datetime
import os
import re
import uuid
from urllib.parse import quote
from minio import Minio

from task_db import TaskDB

# 导入认证模块
from auth import (
    User,
    Permission,
    get_current_active_user,
    require_permission,
)
from auth.routes import router as auth_router
from auth.auth_db import AuthDB

# 初始化 FastAPI 应用
app = FastAPI(
    title="MinerU Tianshu API",
    description="天枢 - 企业级 AI 数据预处理平台 | 支持文档、图片、音频、视频等多模态数据处理 | 企业级认证授权",
    version="2.0.0",
    # 不设置 servers，让 FastAPI 自动根据请求的 Host 生成
)

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化数据库
# 确保使用环境变量中的数据库路径（与 Worker 保持一致）
db_path_env = os.getenv("DATABASE_PATH")
if db_path_env:
    db_path = str(Path(db_path_env).resolve())
    logger.info(f"📊 API Server using DATABASE_PATH: {db_path_env} -> {db_path}")
    db = TaskDB(db_path)
else:
    logger.warning("⚠️  DATABASE_PATH not set in API Server, using default")
    # 使用与 Worker 一致的默认路径
    db_path = "/app/data/db/mineru_tianshu.db"
    db = TaskDB(db_path)
auth_db = AuthDB()

# 注册认证路由
app.include_router(auth_router)

# 配置输出目录（使用共享目录，Docker 环境可访问）
OUTPUT_DIR = Path(os.getenv("OUTPUT_PATH", "/app/output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# MinIO 配置
MINIO_CONFIG = {
    "endpoint": os.getenv("MINIO_ENDPOINT", ""),
    "access_key": os.getenv("MINIO_ACCESS_KEY", ""),
    "secret_key": os.getenv("MINIO_SECRET_KEY", ""),
    "secure": True,
    "bucket_name": os.getenv("MINIO_BUCKET", ""),
}


def get_minio_client():
    """获取MinIO客户端实例"""
    return Minio(
        MINIO_CONFIG["endpoint"],
        access_key=MINIO_CONFIG["access_key"],
        secret_key=MINIO_CONFIG["secret_key"],
        secure=MINIO_CONFIG["secure"],
    )


def process_markdown_images(md_content: str, image_dir: Path, result_path: str, upload_images: bool = False):
    """
    处理 Markdown 中的图片引用

    将相对路径转换为可访问的 URL（静态文件服务或 MinIO）
    支持两种格式：
    1. Markdown 语法：![alt](path)
    2. HTML 标签：<img src="path" ...>

    Args:
        md_content: Markdown 内容
        image_dir: 图片所在目录（绝对路径，Worker 已规范化为 images/）
        result_path: 任务结果路径（从数据库获取，例如: /app/output/{file_stem}）
        upload_images: 是否上传图片到 MinIO 并替换链接

    Returns:
        处理后的 Markdown 内容
    """

    def process_image_path(image_path: str, alt_text: str = "Image") -> tuple[str, str]:
        """
        处理图片路径，返回 (新路径, 格式类型)

        Returns:
            (new_url, format_type)  format_type: 'markdown' 或 'html'
        """
        # 提取图片文件名
        image_filename = Path(image_path).name

        # 构建完整的本地图片路径
        full_image_path = image_dir / image_filename

        logger.debug(f"🔍 Processing image: {image_path} -> {full_image_path}")

        if not full_image_path.exists():
            logger.warning(f"⚠️  Image not found: {full_image_path}")
            return None, None

        # 如果需要上传到 MinIO
        if upload_images:
            try:
                minio_client = get_minio_client()
                bucket_name = MINIO_CONFIG["bucket_name"]
                minio_endpoint = MINIO_CONFIG["endpoint"]

                # 获取文件后缀
                file_extension = full_image_path.suffix
                # 生成 UUID 作为新文件名
                new_filename = f"{uuid.uuid4()}{file_extension}"

                # 上传到 MinIO
                object_name = f"images/{new_filename}"
                minio_client.fput_object(bucket_name, object_name, str(full_image_path))

                # 生成 MinIO 访问 URL
                scheme = "https" if MINIO_CONFIG["secure"] else "http"
                minio_url = f"{scheme}://{minio_endpoint}/{bucket_name}/{object_name}"

                logger.info(f"✅ Uploaded to MinIO: {object_name}")
                return minio_url, "html"
            except Exception as e:
                logger.error(f"❌ Failed to upload image to MinIO: {e}")
                # 上传失败，继续使用本地静态文件服务

        # 使用本地静态文件服务
        # result_path 格式: /app/output/{file_stem}
        # Worker 已规范化图片目录为: images/
        # 需要转换为: /api/v1/files/output/{file_stem}/images/xxx.jpg
        try:
            # 直接使用字符串替换，避免 Path 对象的编码问题
            output_dir_str = str(OUTPUT_DIR).replace("\\", "/")  # 统一使用正斜杠
            result_path_str = result_path.replace("\\", "/")

            if result_path_str.startswith(output_dir_str):
                # 提取相对路径
                relative_path = result_path_str[len(output_dir_str) :].lstrip("/")
                # 对路径进行 URL 编码（safe='/' 保留斜杠）
                encoded_relative_path = quote(relative_path, safe="/")
                # 对图片文件名进行 URL 编码
                encoded_image_filename = quote(image_filename, safe="/")
                # 构建 API 文件访问 URL（图片目录已规范化为 images/）
                static_url = f"/api/v1/files/output/{encoded_relative_path}/images/{encoded_image_filename}"
            else:
                # 如果路径不匹配，尝试直接拼接
                logger.warning(f"⚠️  result_path doesn't start with OUTPUT_DIR: {result_path}")
                encoded_image_filename = quote(image_filename, safe="/")
                static_url = f"/api/v1/files/output/images/{encoded_image_filename}"

            logger.debug(f"📸 Image URL: {static_url}")
            return static_url, "markdown"
        except Exception as e:
            logger.error(f"❌ Failed to generate static URL: {e}")
            return None, None

    # 1. 处理 Markdown 格式的图片：![alt](path)
    md_img_pattern = r"!\[([^\]]*)\]\(([^)]+)\)"

    def replace_md_image(match):
        alt_text = match.group(1)
        image_path = match.group(2)

        new_url, _ = process_image_path(image_path, alt_text)
        if new_url:
            return f"![{alt_text}]({new_url})"
        return match.group(0)

    # 2. 处理 HTML img 标签：<img src="path" ...>
    html_img_pattern = r'<img\s+([^>]*\s+)?src="([^"]+)"([^>]*)>'

    def replace_html_image(match):
        before_src = match.group(1) or ""
        image_path = match.group(2)
        after_src = match.group(3) or ""

        # 尝试提取 alt 属性
        alt_match = re.search(r'alt="([^"]*)"', before_src + after_src)
        alt_text = alt_match.group(1) if alt_match else "Image"

        new_url, format_type = process_image_path(image_path, alt_text)
        if new_url:
            # 保持 HTML 格式
            return f'<img {before_src}src="{new_url}"{after_src}>'
        return match.group(0)

    try:
        # 替换所有图片引用
        new_content = re.sub(md_img_pattern, replace_md_image, md_content)
        new_content = re.sub(html_img_pattern, replace_html_image, new_content)
        return new_content
    except Exception as e:
        logger.error(f"❌ Failed to process images: {e}")
        return md_content


@app.get("/", tags=["系统信息"])
async def root():
    """API根路径"""
    return {
        "service": "MinerU Tianshu",
        "version": "1.0.0",
        "description": "天枢 - 企业级 AI 数据预处理平台",
        "features": "文档、图片、音频、视频等多模态数据处理",
        "docs": "/docs",
    }


@app.post("/api/v1/tasks/submit", tags=["任务管理"])
async def submit_task(
    file: UploadFile = File(..., description="文件: PDF/图片/Office/HTML/音频/视频等多种格式"),
    backend: str = Form(
        "auto",
        description="处理后端: auto (自动选择) | pipeline/paddleocr-vl (文档) | sensevoice (音频) | video (视频) | fasta/genbank (专业格式)",
    ),
    lang: str = Form("auto", description="语言: auto/ch/en/korean/japan等"),
    method: str = Form("auto", description="解析方法: auto/txt/ocr"),
    formula_enable: bool = Form(True, description="是否启用公式识别"),
    table_enable: bool = Form(True, description="是否启用表格识别"),
    priority: int = Form(0, description="优先级，数字越大越优先"),
    # 视频处理专用参数
    keep_audio: bool = Form(False, description="视频处理时是否保留提取的音频文件"),
    enable_keyframe_ocr: bool = Form(False, description="是否启用视频关键帧OCR识别（实验性功能）"),
    ocr_backend: str = Form("paddleocr-vl", description="关键帧OCR引擎: paddleocr-vl"),
    keep_keyframes: bool = Form(False, description="是否保留提取的关键帧图像"),
    # 水印去除专用参数
    remove_watermark: bool = Form(False, description="是否启用水印去除（支持 PDF/图片）"),
    watermark_conf_threshold: float = Form(0.35, description="水印检测置信度阈值（0.0-1.0，推荐 0.35）"),
    watermark_dilation: int = Form(10, description="水印掩码膨胀大小（像素，推荐 10）"),
    # 认证依赖
    current_user: User = Depends(require_permission(Permission.TASK_SUBMIT)),
):
    """
    提交文档解析任务

    需要认证和 TASK_SUBMIT 权限。
    立即返回 task_id，任务在后台异步处理。
    """
    try:
        # 创建共享的上传目录（Backend 和 Worker 都能访问）
        upload_dir = Path("/app/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)

        # 生成唯一的文件名（避免冲突）
        unique_filename = f"{uuid.uuid4().hex}_{file.filename}"
        temp_file_path = upload_dir / unique_filename

        # 流式写入文件到磁盘，避免高内存使用
        with open(temp_file_path, "wb") as temp_file:
            while True:
                chunk = await file.read(1 << 23)  # 8MB chunks
                if not chunk:
                    break
                temp_file.write(chunk)

        # 创建任务 (关联用户)
        task_id = db.create_task(
            file_name=file.filename,
            file_path=str(temp_file_path),
            backend=backend,
            options={
                "lang": lang,
                "method": method,
                "formula_enable": formula_enable,
                "table_enable": table_enable,
                # 视频处理参数
                "keep_audio": keep_audio,
                "enable_keyframe_ocr": enable_keyframe_ocr,
                "ocr_backend": ocr_backend,
                "keep_keyframes": keep_keyframes,
                # 水印去除参数
                "remove_watermark": remove_watermark,
                "watermark_conf_threshold": watermark_conf_threshold,
                "watermark_dilation": watermark_dilation,
            },
            priority=priority,
            user_id=current_user.user_id,  # 关联用户
        )

        logger.info(f"✅ Task submitted: {task_id} - {file.filename}")
        logger.info(f"   User: {current_user.username} ({current_user.role.value})")
        logger.info(f"   Backend: {backend}")
        logger.info(f"   Priority: {priority}")

        return {
            "success": True,
            "task_id": task_id,
            "status": "pending",
            "message": "Task submitted successfully",
            "file_name": file.filename,
            "user_id": current_user.user_id,
            "created_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Failed to submit task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/tasks/{task_id}", tags=["任务管理"])
async def get_task_status(
    task_id: str,
    upload_images: bool = Query(False, description="是否上传图片到MinIO并替换链接（仅当任务完成时有效）"),
    format: str = Query("markdown", description="返回格式: markdown(默认)/json/both"),
    current_user: User = Depends(get_current_active_user),
):
    """
    查询任务状态和详情

    需要认证。用户只能查看自己的任务，管理员可以查看所有任务。
    当任务完成时，会自动返回解析后的内容（data 字段）
    - format=markdown: 只返回 Markdown 内容（默认）
    - format=json: 只返回 JSON 结构化数据（MinerU 和 PaddleOCR-VL 支持）
    - format=both: 同时返回 Markdown 和 JSON
    可选择是否上传图片到 MinIO 并替换为 URL
    """
    task = db.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # 权限检查: 用户只能查看自己的任务，管理员/经理可以查看所有任务
    if not current_user.has_permission(Permission.TASK_VIEW_ALL):
        if task.get("user_id") != current_user.user_id:
            raise HTTPException(status_code=403, detail="Permission denied: You can only view your own tasks")

    response = {
        "success": True,
        "task_id": task_id,
        "status": task["status"],
        "file_name": task["file_name"],
        "backend": task["backend"],
        "priority": task["priority"],
        "error_message": task["error_message"],
        "created_at": task["created_at"],
        "started_at": task["started_at"],
        "completed_at": task["completed_at"],
        "worker_id": task["worker_id"],
        "retry_count": task["retry_count"],
        "user_id": task.get("user_id"),
    }
    logger.info(f"✅ Task status: {task['status']} - (result_path: {task['result_path']})")

    # 如果任务已完成，尝试返回解析内容
    if task["status"] == "completed":
        if not task["result_path"]:
            # 结果文件已被清理
            response["data"] = None
            response["message"] = "Task completed but result files have been cleaned up (older than retention period)"
            return response

        result_dir = Path(task["result_path"])
        logger.info(f"📂 Checking result directory: {result_dir}")

        if result_dir.exists():
            logger.info("✅ Result directory exists")
            # 递归查找 Markdown 文件（MinerU 输出结构：task_id/filename/auto/*.md）
            md_files = list(result_dir.rglob("*.md"))
            # 递归查找 JSON 文件
            # MinerU 输出格式: {filename}_content_list.json (主要的结构化内容)
            # 也支持其他引擎的: content.json, result.json
            json_files = [
                f
                for f in result_dir.rglob("*.json")
                if not f.parent.name.startswith("page_")
                and (f.name in ["content.json", "result.json"] or "_content_list.json" in f.name)
            ]
            logger.info(f"📄 Found {len(md_files)} markdown files and {len(json_files)} json files")

            if md_files:
                try:
                    # 初始化 data 字段
                    response["data"] = {}

                    # 标记 JSON 是否可用
                    response["data"]["json_available"] = len(json_files) > 0

                    # 根据 format 参数决定返回内容
                    if format in ["markdown", "both"]:
                        # 选择主 Markdown 文件（优先 result.md）
                        md_file = None
                        for f in md_files:
                            if f.name == "result.md":
                                md_file = f
                                break
                        if not md_file:
                            md_file = md_files[0]

                        # 查找图片目录（Worker 已规范化为 images/）
                        image_dir = md_file.parent / "images"

                        # 缓存文件路径
                        cached_md_file = md_file.parent / "result_minio.md" if upload_images else None

                        # 如果请求 MinIO 版本且缓存存在，直接返回缓存
                        if upload_images and cached_md_file and cached_md_file.exists():
                            logger.info(f"✅ Found cached MinIO markdown: {cached_md_file.name}")
                            with open(cached_md_file, "r", encoding="utf-8") as f:
                                md_content = f.read()

                            response["data"]["markdown_file"] = cached_md_file.name
                            response["data"]["content"] = md_content
                            response["data"]["images_uploaded"] = True
                            response["data"]["from_cache"] = True
                        else:
                            # 读取原始 Markdown 内容
                            logger.info(f"📖 Reading markdown file: {md_file}")
                            with open(md_file, "r", encoding="utf-8") as f:
                                md_content = f.read()

                            logger.info(f"✅ Markdown content loaded, length: {len(md_content)} characters")

                            # 处理图片路径
                            if image_dir.exists():
                                logger.info(f"🖼️  Processing images for task {task_id}, upload_images={upload_images}")
                                logger.info(f"   Image directory: {image_dir}")
                                md_content = process_markdown_images(
                                    md_content, image_dir, task["result_path"], upload_images
                                )

                                # 如果上传到 MinIO，保存缓存文件
                                if upload_images and cached_md_file:
                                    try:
                                        cached_md_file.write_text(md_content, encoding="utf-8")
                                        logger.info(f"💾 Saved MinIO markdown cache: {cached_md_file.name}")
                                    except Exception as e:
                                        logger.warning(f"⚠️  Failed to save cache: {e}")
                            else:
                                logger.debug("ℹ️  No images directory found (task may not contain images)")

                            # 添加 Markdown 相关字段
                            response["data"]["markdown_file"] = md_file.name
                            response["data"]["content"] = md_content
                            response["data"]["images_uploaded"] = upload_images
                            response["data"]["has_images"] = image_dir.exists() if not upload_images else None
                            response["data"]["from_cache"] = False

                    # 如果用户请求 JSON 格式
                    if format in ["json", "both"] and json_files:
                        import json as json_lib

                        json_file = json_files[0]
                        logger.info(f"📖 Reading JSON file: {json_file}")
                        try:
                            with open(json_file, "r", encoding="utf-8") as f:
                                json_content = json_lib.load(f)
                            response["data"]["json_file"] = json_file.name
                            response["data"]["json_content"] = json_content
                            logger.info("✅ JSON content loaded successfully")
                        except Exception as json_e:
                            logger.warning(f"⚠️  Failed to load JSON: {json_e}")
                    elif format == "json" and not json_files:
                        # 用户请求 JSON 但没有 JSON 文件
                        logger.warning("⚠️  JSON format requested but no JSON file available")
                        response["data"]["message"] = "JSON format not available for this backend"

                    # 如果没有返回任何内容，添加提示
                    if not response["data"]:
                        response["data"] = None
                        logger.warning(f"⚠️  No data returned for format: {format}")
                    else:
                        logger.info(f"✅ Response data field added successfully (format={format})")

                except Exception as e:
                    logger.error(f"❌ Failed to read content: {e}")
                    logger.exception(e)
                    # 读取失败不影响状态查询，只是不返回 data
                    response["data"] = None
            else:
                logger.warning(f"⚠️  No markdown files found in {result_dir}")
        else:
            logger.error(f"❌ Result directory does not exist: {result_dir}")
    elif task["status"] == "completed":
        logger.warning("⚠️  Task completed but result_path is empty")
    else:
        logger.info(f"ℹ️  Task status is {task['status']}, skipping content loading")

    return response


@app.delete("/api/v1/tasks/{task_id}", tags=["任务管理"])
async def cancel_task(task_id: str, current_user: User = Depends(get_current_active_user)):
    """
    取消任务（仅限 pending 状态）

    需要认证。用户只能取消自己的任务，管理员可以取消任何任务。
    """
    task = db.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # 权限检查: 用户只能取消自己的任务，管理员可以取消任何任务
    if not current_user.has_permission(Permission.TASK_DELETE_ALL):
        if task.get("user_id") != current_user.user_id:
            raise HTTPException(status_code=403, detail="Permission denied: You can only cancel your own tasks")

    if task["status"] == "pending":
        db.update_task_status(task_id, "cancelled")

        # 删除临时文件
        file_path = Path(task["file_path"])
        if file_path.exists():
            file_path.unlink()

        logger.info(f"⏹️  Task cancelled: {task_id} by user {current_user.username}")
        return {"success": True, "message": "Task cancelled successfully"}
    else:
        raise HTTPException(status_code=400, detail=f"Cannot cancel task in {task['status']} status")


@app.get("/api/v1/queue/stats", tags=["队列管理"])
async def get_queue_stats(current_user: User = Depends(require_permission(Permission.QUEUE_VIEW))):
    """
    获取队列统计信息

    需要认证和 QUEUE_VIEW 权限。
    """
    stats = db.get_queue_stats()

    return {
        "success": True,
        "stats": stats,
        "total": sum(stats.values()),
        "timestamp": datetime.now().isoformat(),
        "user": current_user.username,
    }


@app.get("/api/v1/queue/tasks", tags=["队列管理"])
async def list_tasks(
    status: Optional[str] = Query(None, description="筛选状态: pending/processing/completed/failed"),
    limit: int = Query(100, description="返回数量限制", le=1000),
    current_user: User = Depends(get_current_active_user),
):
    """
    获取任务列表

    需要认证。普通用户只能看到自己的任务，管理员/经理可以看到所有任务。
    """
    # 检查用户权限
    can_view_all = current_user.has_permission(Permission.TASK_VIEW_ALL)

    if can_view_all:
        # 管理员/经理查看所有任务
        if status:
            tasks = db.get_tasks_by_status(status, limit)
        else:
            with db.get_cursor() as cursor:
                cursor.execute(
                    """
                    SELECT * FROM tasks
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (limit,),
                )
                tasks = [dict(row) for row in cursor.fetchall()]
    else:
        # 普通用户只能看到自己的任务
        with db.get_cursor() as cursor:
            if status:
                cursor.execute(
                    """
                    SELECT * FROM tasks
                    WHERE user_id = ? AND status = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (current_user.user_id, status, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM tasks
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (current_user.user_id, limit),
                )
            tasks = [dict(row) for row in cursor.fetchall()]

    return {"success": True, "count": len(tasks), "tasks": tasks, "can_view_all": can_view_all}


@app.post("/api/v1/admin/cleanup", tags=["系统管理"])
async def cleanup_old_tasks(
    days: int = Query(7, description="清理N天前的任务"),
    current_user: User = Depends(require_permission(Permission.QUEUE_MANAGE)),
):
    """
    清理旧任务（管理接口）

    同时删除任务的所有相关文件和数据库记录：
    - 上传的原始文件
    - 结果文件夹（包括生成的文件和所有中间文件）
    - 数据库记录

    需要管理员权限。
    """
    deleted_count = db.cleanup_old_task_records(days)

    logger.info(f"🧹 Cleaned up {deleted_count} old tasks (files and records) by {current_user.username}")

    return {
        "success": True,
        "deleted_count": deleted_count,
        "message": f"Cleaned up {deleted_count} tasks older than {days} days (files and records deleted)",
    }


@app.post("/api/v1/admin/reset-stale", tags=["系统管理"])
async def reset_stale_tasks(
    timeout_minutes: int = Query(60, description="超时时间（分钟）"),
    current_user: User = Depends(require_permission(Permission.QUEUE_MANAGE)),
):
    """
    重置超时的 processing 任务（管理接口）

    需要管理员权限。
    """
    reset_count = db.reset_stale_tasks(timeout_minutes)

    logger.info(f"🔄 Reset {reset_count} stale tasks by {current_user.username}")

    return {
        "success": True,
        "reset_count": reset_count,
        "message": f"Reset tasks processing for more than {timeout_minutes} minutes",
    }


@app.get("/api/v1/engines", tags=["系统信息"])
async def list_engines():
    """
    列出所有可用的处理引擎

    无需认证。返回系统中所有可用的处理引擎信息。
    """
    engines = {
        "document": [
            {
                "name": "pipeline",
                "display_name": "MinerU Pipeline",
                "description": "默认的 PDF/图片解析引擎，支持公式、表格等复杂结构",
                "supported_formats": [".pdf", ".png", ".jpg", ".jpeg"],
            },
        ],
        "ocr": [],
        "audio": [],
        "video": [],
        "format": [],
        "office": [
            {
                "name": "markitdown",
                "display_name": "MarkItDown",
                "description": "Office 文档和文本文件转换引擎",
                "supported_formats": [".docx", ".xlsx", ".pptx", ".doc", ".xls", ".ppt", ".html", ".txt", ".csv"],
            },
        ],
    }

    # 动态检测可用引擎
    import importlib.util

    if importlib.util.find_spec("paddleocr_vl") is not None:
        engines["ocr"].append(
            {
                "name": "paddleocr_vl",
                "display_name": "PaddleOCR-VL",
                "description": "PaddlePaddle 视觉语言 OCR 引擎",
                "supported_formats": [".pdf", ".png", ".jpg", ".jpeg"],
            }
        )

    if importlib.util.find_spec("paddleocr_vl_vllm") is not None:
        engines["ocr"].append(
            {
                "name": "paddleocr-vl-vllm",
                "display_name": "PaddleOCR-VL-VLLM",
                "description": "基于 vLLM 的高性能 PaddleOCR 引擎",
                "supported_formats": [".pdf", ".png", ".jpg", ".jpeg"],
            }
        )

    if importlib.util.find_spec("audio_engines") is not None:
        engines["audio"].append(
            {
                "name": "sensevoice",
                "display_name": "SenseVoice",
                "description": "语音识别引擎，支持多语言自动检测",
                "supported_formats": [".wav", ".mp3", ".flac", ".m4a", ".ogg"],
            }
        )

    if importlib.util.find_spec("video_engines") is not None:
        engines["video"].append(
            {
                "name": "video",
                "display_name": "Video Processing",
                "description": "视频处理引擎，支持关键帧提取和音频转录",
                "supported_formats": [".mp4", ".avi", ".mkv", ".mov", ".flv", ".wmv"],
            }
        )

    # 专业格式引擎
    try:
        from format_engines import FormatEngineRegistry

        for engine_info in FormatEngineRegistry.list_engines():
            engines["format"].append(
                {
                    "name": engine_info["name"],
                    "display_name": engine_info["name"].upper(),
                    "description": engine_info["description"],
                    "supported_formats": engine_info["extensions"],
                }
            )
    except ImportError:
        pass

    return {
        "success": True,
        "engines": engines,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/v1/health", tags=["系统信息"])
async def health_check():
    """
    健康检查接口
    """
    try:
        # 检查数据库连接
        stats = db.get_queue_stats()

        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": "connected",
            "queue_stats": stats,
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(status_code=503, content={"status": "unhealthy", "error": str(e)})


# ============================================================================
# 自定义文件服务（支持 URL 编码的中文路径）
# ============================================================================
from urllib.parse import unquote


@app.get("/v1/files/output/{file_path:path}", tags=["文件服务"])
async def serve_output_file(file_path: str):
    """
    提供输出文件的访问服务

    支持 URL 编码的中文路径
    注意：Nginx 代理会去掉 /api/ 前缀，所以这里不需要 /api/
    """
    try:
        logger.debug(f"📥 Received file request: {file_path}")
        # URL 解码
        decoded_path = unquote(file_path)
        logger.debug(f"📝 Decoded path: {decoded_path}")
        # 构建完整路径
        full_path = OUTPUT_DIR / decoded_path
        logger.debug(f"📂 Full path: {full_path}")

        # 安全检查：确保路径在 OUTPUT_DIR 内
        try:
            full_path = full_path.resolve()
            OUTPUT_DIR.resolve()
            if not str(full_path).startswith(str(OUTPUT_DIR.resolve())):
                raise HTTPException(status_code=403, detail="Access denied")
        except Exception:
            raise HTTPException(status_code=403, detail="Invalid path")

        # 检查文件是否存在
        if not full_path.exists():
            logger.warning(f"⚠️  File not found: {full_path}")
            raise HTTPException(status_code=404, detail="File not found")

        if not full_path.is_file():
            raise HTTPException(status_code=404, detail="Not a file")

        # 返回文件
        return FileResponse(path=str(full_path), media_type="application/octet-stream", filename=full_path.name)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error serving file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


logger.info(f"📁 File service mounted: /v1/files/output -> {OUTPUT_DIR}")
logger.info("   Frontend can access images via: /api/v1/files/output/{task_id}/images/xxx.jpg (Nginx will strip /api/)")


if __name__ == "__main__":
    # 从环境变量读取端口，默认为8000
    api_port = int(os.getenv("API_PORT", "8000"))

    logger.info("🚀 Starting MinerU Tianshu API Server...")
    logger.info(f"📖 API Documentation: http://localhost:{api_port}/docs")

    uvicorn.run(app, host="0.0.0.0", port=api_port, log_level="info")

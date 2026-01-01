import os
import sys
import warnings
import importlib.util
from contextlib import asynccontextmanager
from pathlib import Path
from loguru import logger
from litserve.connector import check_cuda_with_nvidia_smi


def apply_litserve_patch():
    """
    修复 litserve MCP 与 mcp>=1.1.0 不兼容问题
    完全禁用 LitServe 的内部 MCP 以避免与我们的独立 MCP Server 冲突
    """
    try:
        # Patch LitServe's MCP module to disable it completely
        import litserve.mcp as ls_mcp

        # Inject MCPServer (mcp.server.lowlevel.Server) as dummy
        if not hasattr(ls_mcp, "MCPServer"):

            class DummyMCPServer:
                def __init__(self, *args, **kwargs):
                    pass

            ls_mcp.MCPServer = DummyMCPServer
            if "litserve.mcp" in sys.modules:
                sys.modules["litserve.mcp"].MCPServer = DummyMCPServer

        # Inject StreamableHTTPSessionManager as dummy
        if not hasattr(ls_mcp, "StreamableHTTPSessionManager"):

            class DummyStreamableHTTPSessionManager:
                def __init__(self, *args, **kwargs):
                    pass

            ls_mcp.StreamableHTTPSessionManager = DummyStreamableHTTPSessionManager
            if "litserve.mcp" in sys.modules:
                sys.modules["litserve.mcp"].StreamableHTTPSessionManager = DummyStreamableHTTPSessionManager

        # Replace _LitMCPServerConnector with a complete dummy implementation
        class DummyMCPConnector:
            """完全禁用 LitServe 内置 MCP 的 Dummy 实现"""

            def __init__(self, *args, **kwargs):
                self.mcp_server = None
                self.session_manager = None
                self.request_handler = None

            @asynccontextmanager
            async def lifespan(self, app):
                """空的 lifespan context manager，不做任何事情"""
                yield  # 什么都不做，直接让服务器启动

            def connect_mcp_server(self, *args, **kwargs):
                """空的 connect_mcp_server 方法，不做任何事情"""
                pass  # 什么都不做，跳过 MCP 初始化

        # 替换 _LitMCPServerConnector 类
        ls_mcp._LitMCPServerConnector = DummyMCPConnector

        # 同时更新 sys.modules 中的引用
        if "litserve.mcp" in sys.modules:
            sys.modules["litserve.mcp"]._LitMCPServerConnector = DummyMCPConnector

    except Exception as e:
        # If patching fails, log warning and continue
        # The server might still work or fail with a clearer error message
        warnings.warn(f"Failed to patch litserve.mcp (MCP will be disabled): {e}")


def verify_pytorch_cuda():
    """
    验证 PyTorch CUDA 设置，返回是否成功
    """
    import os
    import torch
    from loguru import logger

    try:
        if torch.cuda.is_available():
            visible_devices = os.environ.get("CUDA_VISIBLE_DEVICES", "all")
            device_count = torch.cuda.device_count()
            logger.info("✅ PyTorch CUDA verified:")
            logger.info(f"   CUDA_VISIBLE_DEVICES = {visible_devices}")
            logger.info(f"   torch.cuda.device_count() = {device_count}")
            if device_count == 1:
                logger.info(f"   ✅ SUCCESS: Process isolated to 1 GPU (physical GPU {visible_devices})")
            else:
                logger.warning(f"   ⚠️  WARNING: Expected 1 GPU but found {device_count}")
        else:
            logger.warning("⚠️  CUDA not available")
    except Exception as e:
        logger.warning(f"⚠️  Failed to verify PyTorch CUDA: {e}")


def init_task_db(TaskDB, db_path_env):
    """
    初始化任务数据库，返回 TaskDB 实例
    """
    # 初始化任务数据库（从环境变量读取，兼容 Docker 和本地）
    db_path = Path(db_path_env).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"📊 DATABASE_PATH={db_path_env} → resolved={db_path}")
    task_db = TaskDB(str(db_path))  # 如 TaskDB 只接受 str

    # 验证数据库连接并输出初始统计
    try:
        stats = task_db.get_queue_stats()
        logger.info(f"📊 Database initialized: {db_path} (exists: {db_path.exists()})")
        logger.info(f"📊 TaskDB.db_path: {task_db.db_path}")
        logger.info(f"📊 Initial queue stats: {stats}")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database or get stats: {e}")
        logger.exception(e)

    return task_db


def resolve_auto_accelerator():
    """
    当 accelerator 设置为 "auto" 时，使用元数据及环境信息自动检测最合适的加速器类型(不直接导入torch)
    Return: str  检测到的加速器类型 ("cuda" 或 "cpu")
    """
    try:
        from importlib.metadata import distribution

        distribution("torch")
        torch_is_installed = True
    except Exception as e:
        torch_is_installed = False
        logger.warning(f"Torch is not installed or cannot be imported: {e}")

    if torch_is_installed and check_cuda_with_nvidia_smi() > 0:
        return "cuda"
    return "cpu"


def configure_model_source(model_source="auto"):
    """
    配置模型下载源（必须在 MinerU 初始化之前）
    从环境变量 MODEL_DOWNLOAD_SOURCE 读取配置
    支持: modelscope, huggingface, auto (默认)
    """
    # 避免重复配置/日志 (在多进程 Worker 中，环境变量会被继承)
    if os.environ.get("MINERU_MODEL_SOURCE_CONFIGURED") == "1":
        return
    # 解析 auto 模式
    if model_source == "auto":
        if importlib.util.find_spec("modelscope") is not None:
            model_source = "modelscope"
        else:
            model_source = "huggingface"

    if model_source == "modelscope":
        # 尝试使用 ModelScope（优先）
        try:
            if importlib.util.find_spec("modelscope") is not None:
                os.environ["MINERU_MODEL_SOURCE"] = "modelscope"
                logger.info("📦 Model download source: ModelScope (国内推荐)")
                logger.info("   Note: ModelScope automatically uses China mirror for faster downloads")
            else:
                raise ImportError("modelscope not found")
        except ImportError:
            if model_source == "modelscope":
                logger.warning("⚠️  ModelScope not available, falling back to HuggingFace")
            model_source = "huggingface"

    if model_source == "huggingface":
        # 配置 HuggingFace 镜像（从环境变量读取，默认使用国内镜像）
        hf_endpoint = os.getenv("HF_ENDPOINT", "https://hf-mirror.com")
        os.environ.setdefault("HF_ENDPOINT", hf_endpoint)
        logger.info(f"📦 Model download source: HuggingFace (via: {hf_endpoint})")
    elif model_source != "modelscope":
        logger.warning(f"⚠️  Unknown model download source: {model_source}")
    # 标记已配置
    os.environ["MINERU_MODEL_SOURCE_CONFIGURED"] = "1"

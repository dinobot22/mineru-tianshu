import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional
from loguru import logger


def load_env_if_not_loaded(env_file: Optional[str] = None) -> bool:
    """
    加载环境变量如果尚未加载
    Args:
        env_file: 可选的.env文件路径，如果为None则自动查找 workspace/backend/.env 或者 workspace/.env
    Returns:
        bool: 是否成功加载（True=已加载或新加载成功，False=加载失败）
    Note: 使用 MINERU_TIANSHU_ENV_LOADED 环境变量标识.env是否加载,避免重复加载及环境变量后覆盖问题
    """
    # 检查是否已加载
    if os.environ.get("MINERU_TIANSHU_ENV_LOADED") == "true":
        return True
    backend_root = Path(__file__).resolve().parent.parent
    backend_env = os.path.join(backend_root, ".env")  #  workspace/backend下的 .env
    workspace_env = os.path.join(backend_root.parent, ".env")  # workspace下的 .env
    try:
        if env_file is None:
            env_file = backend_env if os.path.exists(backend_env) else workspace_env

        if not env_file or not os.path.exists(env_file):
            error_msg = f"Critical: .env file not found at {backend_root} or {workspace_env}. Application cannot start without configuration."
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        # 实际加载
        loaded = load_dotenv(env_file)
        if loaded:
            os.environ["MINERU_TIANSHU_ENV_LOADED"] = "true"
            logger.success(f"Successfully loaded .env file from {env_file}")
            # 确保数据根目录一定存在
            if not os.environ.get("BACKEND_APP_DATA_ROOT_PATH"):
                os.environ["BACKEND_APP_DATA_ROOT_PATH"] = "./app_data"
            os.makedirs(os.getenv("BACKEND_APP_DATA_ROOT_PATH"), exist_ok=True)
            logger.info(
                f"\nData root directory created:\n"
                f"  Relative path: {os.getenv('BACKEND_APP_DATA_ROOT_PATH')}\n"
                f"  Absolute path: {os.path.abspath(os.getenv('BACKEND_APP_DATA_ROOT_PATH'))}"
            )
            # 确保数据输出目录环境变量一定存在(与老版本docker启动兼容, 命名一致性存在, 建议逐步废弃)
            if not os.environ.get("OUTPUT_PATH"):
                os.environ["OUTPUT_PATH"] = os.path.join(
                    os.getenv("BACKEND_APP_DATA_ROOT_PATH"), "mineru_tianshu_output"
                )
            os.makedirs(os.environ["OUTPUT_PATH"], exist_ok=True)
            logger.info(
                f"\nData output directory created:\n"
                f"  Relative path: {os.environ['OUTPUT_PATH']}\n"
                f"  Absolute path: {os.path.abspath(os.environ['OUTPUT_PATH'])}"
            )

            # 确保数据库路径环境变量一定存在
            if not os.environ.get("DATABASE_PATH"):
                os.environ["DATABASE_PATH"] = os.path.join(os.getenv("BACKEND_APP_DATA_ROOT_PATH"), "mineru_tianshu.db")
            logger.info(
                f"\nDatabase path set:\n"
                f"  Relative path: {os.environ['DATABASE_PATH']}\n"
                f"  Absolute path: {os.path.abspath(os.environ['DATABASE_PATH'])}"
            )
            return True

        # 理论上 load_dotenv 在文件存在时通常返回 True，但以防万一
        raise RuntimeError(f"Failed to load .env file from {env_file}")

    except Exception as e:
        logger.error(f"Error loading .env file: {e}")
        return False

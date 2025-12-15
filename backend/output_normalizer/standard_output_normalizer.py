"""
标准输出规范化器
"""

from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger
import shutil
import re
from .base_output_normalizer import BaseOutputNormalizer


class StandardOutputNormalizer(BaseOutputNormalizer):
    """
    标准输出规范化器（MinerU 等）

    将不同引擎的输出统一为标准格式：
    - result.md: 主 Markdown 文件
    - images/: 图片目录（统一名称）
    - result.json: 结构化数据（如果有）
    """

    def _normalize_local_files(self, output_dir: Path) -> Dict[str, Any]:
        result = {
            "markdown_file": None,
            "json_file": None,
            "image_dir": None,
            "image_count": 0,
        }

        # 1. 规范化 Markdown 文件
        result["markdown_file"] = self._normalize_markdown(output_dir)

        # 2. 规范化图片目录
        result["image_dir"], result["image_count"] = self._normalize_images(output_dir)

        # 3. 规范化 JSON 文件
        result["json_file"] = self._normalize_json(output_dir)

        # 4. 如果有图片目录，更新 Markdown 中的图片引用
        if result["image_dir"] and result["markdown_file"]:
            self._update_markdown_image_refs(result["markdown_file"])

        return result

    def _normalize_markdown(self, output_dir: Path) -> Optional[Path]:
        """
        规范化 Markdown 文件

        查找并重命名为标准名称：result.md
        """
        # 查找所有 .md 文件（递归）
        md_files = list(output_dir.rglob("*.md"))

        if not md_files:
            logger.warning("⚠️  No markdown files found")
            return None

        # 如果已经有 result.md，直接返回
        standard_md = output_dir / self.STANDARD_MARKDOWN_NAME
        if standard_md.exists():
            logger.info(f"✅ Standard markdown file already exists: {standard_md.name}")
            return standard_md

        # 选择最大的 .md 文件（通常是主文件）
        main_md = max(md_files, key=lambda f: f.stat().st_size)
        logger.info(f"📄 Found main markdown: {main_md.relative_to(output_dir)}")

        # 如果不在根目录，移动到根目录
        if main_md.parent != output_dir:
            logger.info("   Moving to root directory...")
            shutil.copy2(main_md, standard_md)
        else:
            # 重命名
            logger.info(f"   Renaming to {self.STANDARD_MARKDOWN_NAME}...")
            main_md.rename(standard_md)

        return standard_md

    def _normalize_images(self, output_dir: Path) -> tuple[Optional[Path], int]:
        """
        规范化图片目录

        将所有图片统一到 images/ 目录
        """
        standard_image_dir = output_dir / self.STANDARD_IMAGE_DIR

        # 查找可能的图片目录
        possible_dirs = ["imgs", "images", "img", "pictures", "pics"]
        found_dirs = []

        for dir_name in possible_dirs:
            img_dir = output_dir / dir_name
            if img_dir.exists() and img_dir.is_dir():
                found_dirs.append(img_dir)

        # 如果没有找到图片目录，查找散落的图片文件
        if not found_dirs:
            image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg"}
            image_files = [f for f in output_dir.rglob("*") if f.is_file() and f.suffix.lower() in image_extensions]

            if not image_files:
                logger.info("ℹ️  No images found")
                return None, 0

            # 创建标准图片目录并移动图片
            logger.info(f"📁 Creating standard image directory: {self.STANDARD_IMAGE_DIR}/")
            standard_image_dir.mkdir(exist_ok=True)

            for img_file in image_files:
                if img_file.parent != standard_image_dir:
                    dest = standard_image_dir / img_file.name
                    logger.debug(f"   Moving: {img_file.name}")
                    shutil.move(str(img_file), str(dest))

            return standard_image_dir, len(image_files)

        # 如果标准目录已存在，直接返回
        if standard_image_dir in found_dirs:
            image_count = len(list(standard_image_dir.iterdir()))
            logger.info(f"✅ Standard image directory already exists: {self.STANDARD_IMAGE_DIR}/")
            return standard_image_dir, image_count

        # 合并所有图片目录到标准目录
        logger.info(f"📁 Consolidating image directories to: {self.STANDARD_IMAGE_DIR}/")
        standard_image_dir.mkdir(exist_ok=True)

        total_images = 0
        for img_dir in found_dirs:
            logger.info(f"   Processing: {img_dir.name}/")
            for img_file in img_dir.iterdir():
                if img_file.is_file():
                    dest = standard_image_dir / img_file.name
                    # 处理文件名冲突
                    if dest.exists():
                        stem = img_file.stem
                        suffix = img_file.suffix
                        counter = 1
                        while dest.exists():
                            dest = standard_image_dir / f"{stem}_{counter}{suffix}"
                            counter += 1

                    shutil.move(str(img_file), str(dest))
                    total_images += 1

            # 删除空目录
            try:
                img_dir.rmdir()
                logger.debug(f"   Removed empty directory: {img_dir.name}/")
            except OSError:
                pass

        return standard_image_dir, total_images

    def _normalize_json(self, output_dir: Path) -> Optional[Path]:
        """
        规范化 JSON 文件

        查找并重命名为标准名称：result.json
        """
        # 查找所有 .json 文件（排除子目录中的临时文件）
        json_files = [
            f
            for f in output_dir.rglob("*.json")
            if not f.parent.name.startswith("page_")  # 排除 PaddleOCR-VL 的分页文件
        ]

        if not json_files:
            logger.info("ℹ️  No JSON files found")
            return None

        # 如果已经有 result.json，直接返回
        standard_json = output_dir / self.STANDARD_JSON_NAME
        if standard_json.exists():
            logger.info(f"✅ Standard JSON file already exists: {standard_json.name}")
            return standard_json

        # 选择主 JSON 文件（优先选择 content_list.json 或最大的文件）
        main_json = None
        for f in json_files:
            if "content_list" in f.name or "result" in f.name:
                main_json = f
                break

        if not main_json:
            main_json = max(json_files, key=lambda f: f.stat().st_size)

        logger.info(f"📄 Found main JSON: {main_json.relative_to(output_dir)}")

        # 如果不在根目录，移动到根目录
        if main_json.parent != output_dir:
            logger.info("   Moving to root directory...")
            shutil.copy2(main_json, standard_json)
        else:
            # 重命名
            logger.info(f"   Renaming to {self.STANDARD_JSON_NAME}...")
            main_json.rename(standard_json)

        return standard_json

    def _update_markdown_image_refs(self, markdown_file: Path):
        """
        更新 Markdown 文件中的图片引用

        将所有图片路径统一为 images/xxx.jpg 格式
        支持两种格式：
        1. Markdown 语法：![alt](path)
        2. HTML 标签：<img src="path" ...>
        """
        try:
            content = markdown_file.read_text(encoding="utf-8")

            # 1. 匹配 Markdown 图片语法：![alt](path)
            md_img_pattern = r"!\[([^\]]*)\]\(([^)]+)\)"

            def replace_md_path(match):
                alt_text = match.group(1)
                img_path = match.group(2)

                # 提取文件名
                img_filename = Path(img_path).name

                # 统一为 images/filename 格式
                new_path = f"{self.STANDARD_IMAGE_DIR}/{img_filename}"

                return f"![{alt_text}]({new_path})"

            # 2. 匹配 HTML img 标签：<img src="path" ...>
            html_img_pattern = r'<img\s+([^>]*\s+)?src="([^"]+)"([^>]*)>'

            def replace_html_path(match):
                before_src = match.group(1) or ""
                img_path = match.group(2)
                after_src = match.group(3) or ""

                # 提取文件名
                img_filename = Path(img_path).name

                # 统一为 images/filename 格式
                new_path = f"{self.STANDARD_IMAGE_DIR}/{img_filename}"

                return f'<img {before_src}src="{new_path}"{after_src}>'

            # 替换所有图片引用
            new_content = re.sub(md_img_pattern, replace_md_path, content)
            new_content = re.sub(html_img_pattern, replace_html_path, new_content)

            # 只有内容变化时才写入
            if new_content != content:
                markdown_file.write_text(new_content, encoding="utf-8")
                logger.info(f"✅ Updated image references in {markdown_file.name}")
            else:
                logger.debug(f"ℹ️  No image references to update in {markdown_file.name}")

        except Exception as e:
            logger.warning(f"⚠️  Failed to update image references: {e}")

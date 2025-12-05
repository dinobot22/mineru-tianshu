"""
输出结果规范化模块

统一不同解析引擎的输出格式，确保：
1. Markdown 文件名统一为 result.md
2. 图片目录统一为 images/
3. 图片引用路径统一为 images/xxx.jpg
4. JSON 文件名统一为 result.json
5. 自动上传图片到 RustFS 对象存储并替换 URL

支持的引擎：
- MinerU (pipeline)
- PaddleOCR-VL
- SenseVoice
- Video Processing
- Format Engines (FASTA, GenBank, etc.)
"""

from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger
import shutil
import re
import json


class OutputNormalizer:
    """
    输出结果规范化器

    将不同引擎的输出统一为标准格式：
    - result.md: 主 Markdown 文件
    - images/: 图片目录（统一名称）
    - result.json: 结构化数据（如果有）
    """

    # 标准输出文件名
    STANDARD_MARKDOWN_NAME = "result.md"
    STANDARD_JSON_NAME = "result.json"
    STANDARD_IMAGE_DIR = "images"

    def __init__(self, output_dir: Path):
        """
        初始化规范化器

        Args:
            output_dir: 输出目录（引擎的原始输出目录）

        注意：RustFS 自动上传已集成为基础功能，始终启用
        """
        self.output_dir = Path(output_dir)
        if not self.output_dir.exists():
            raise ValueError(f"Output directory does not exist: {output_dir}")

        self._rustfs_client = None

    def normalize(self) -> Dict[str, Any]:
        """
        规范化输出目录

        Returns:
            规范化后的文件信息
        """
        logger.info(f"🔧 Normalizing output directory: {self.output_dir}")

        result = {
            "markdown_file": None,
            "json_file": None,
            "image_dir": None,
            "image_count": 0,
            "rustfs_enabled": False,
            "images_uploaded": False,
        }

        # 1. 规范化 Markdown 文件
        result["markdown_file"] = self._normalize_markdown()

        # 2. 规范化图片目录
        result["image_dir"], result["image_count"] = self._normalize_images()

        # 3. 规范化 JSON 文件
        result["json_file"] = self._normalize_json()

        # 4. 如果有图片目录，更新 Markdown 中的图片引用
        if result["image_dir"] and result["markdown_file"]:
            self._update_markdown_image_refs(result["markdown_file"])

        # 5. 自动上传图片到 RustFS 并替换 URL（基础功能，始终启用）
        if result["image_dir"] and result["image_count"] > 0:
            try:
                logger.info(f"📤 Uploading {result['image_count']} images to RustFS...")
                url_mapping = self._upload_images_to_rustfs(result["image_dir"])

                if url_mapping:
                    # 替换 Markdown 中的图片路径
                    if result["markdown_file"]:
                        self._replace_markdown_urls(result["markdown_file"], url_mapping)

                    # 替换 JSON 中的图片路径
                    if result["json_file"]:
                        self._replace_json_urls(result["json_file"], url_mapping)

                    result["rustfs_enabled"] = True
                    result["images_uploaded"] = True
                    logger.info(f"✅ Images uploaded to RustFS: {len(url_mapping)}/{result['image_count']}")
                else:
                    logger.warning("⚠️  No images uploaded (url_mapping empty)")
                    result["rustfs_enabled"] = False
                    result["images_uploaded"] = False
            except Exception as e:
                logger.error(f"❌ Failed to upload images to RustFS: {e}")
                logger.error(f"   Error details: {type(e).__name__}: {str(e)}")
                result["rustfs_enabled"] = False
                result["images_uploaded"] = False
                # RustFS 上传失败不应中断主流程，继续使用本地路径
                logger.warning("⚠️  Continuing with local image paths (RustFS upload failed)")
        else:
            logger.debug("ℹ️  No images to upload")
            result["rustfs_enabled"] = False
            result["images_uploaded"] = False

        logger.info("✅ Normalization complete:")
        logger.info(f"   Markdown: {result['markdown_file']}")
        logger.info(f"   Images: {result['image_count']} files in {result['image_dir']}")
        logger.info(f"   JSON: {result['json_file']}")
        logger.info(f"   RustFS: {result['rustfs_enabled']} (uploaded: {result['images_uploaded']})")

        return result

    def _normalize_markdown(self) -> Optional[Path]:
        """
        规范化 Markdown 文件

        查找并重命名为标准名称：result.md
        """
        # 查找所有 .md 文件（递归）
        md_files = list(self.output_dir.rglob("*.md"))

        if not md_files:
            logger.warning("⚠️  No markdown files found")
            return None

        # 如果已经有 result.md，直接返回
        standard_md = self.output_dir / self.STANDARD_MARKDOWN_NAME
        if standard_md.exists():
            logger.info(f"✅ Standard markdown file already exists: {standard_md.name}")
            return standard_md

        # 选择最大的 .md 文件（通常是主文件）
        main_md = max(md_files, key=lambda f: f.stat().st_size)
        logger.info(f"📄 Found main markdown: {main_md.relative_to(self.output_dir)}")

        # 如果不在根目录，移动到根目录
        if main_md.parent != self.output_dir:
            logger.info("   Moving to root directory...")
            shutil.copy2(main_md, standard_md)
        else:
            # 重命名
            logger.info(f"   Renaming to {self.STANDARD_MARKDOWN_NAME}...")
            main_md.rename(standard_md)

        return standard_md

    def _normalize_images(self) -> tuple[Optional[Path], int]:
        """
        规范化图片目录

        将所有图片统一到 images/ 目录
        """
        standard_image_dir = self.output_dir / self.STANDARD_IMAGE_DIR

        # 查找可能的图片目录
        possible_dirs = ["imgs", "images", "img", "pictures", "pics"]
        found_dirs = []

        for dir_name in possible_dirs:
            img_dir = self.output_dir / dir_name
            if img_dir.exists() and img_dir.is_dir():
                found_dirs.append(img_dir)

        # 如果没有找到图片目录，查找散落的图片文件
        if not found_dirs:
            image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg"}
            image_files = [
                f for f in self.output_dir.rglob("*") if f.is_file() and f.suffix.lower() in image_extensions
            ]

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

    def _normalize_json(self) -> Optional[Path]:
        """
        规范化 JSON 文件

        查找并重命名为标准名称：result.json
        """
        # 查找所有 .json 文件（排除子目录中的临时文件）
        json_files = [
            f
            for f in self.output_dir.rglob("*.json")
            if not f.parent.name.startswith("page_")  # 排除 PaddleOCR-VL 的分页文件
        ]

        if not json_files:
            logger.info("ℹ️  No JSON files found")
            return None

        # 如果已经有 result.json，直接返回
        standard_json = self.output_dir / self.STANDARD_JSON_NAME
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

        logger.info(f"📄 Found main JSON: {main_json.relative_to(self.output_dir)}")

        # 如果不在根目录，移动到根目录
        if main_json.parent != self.output_dir:
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

    def _upload_images_to_rustfs(self, image_dir: Path) -> Dict[str, str]:
        """
        上传图片到 RustFS 对象存储

        Args:
            image_dir: 图片目录

        Returns:
            {本地文件名: RustFS URL} 的映射字典
        """
        # 延迟导入，避免在不需要时初始化
        try:
            from storage import RustFSClient

            if self._rustfs_client is None:
                self._rustfs_client = RustFSClient()

            # 直接上传，使用日期前缀 (YYYYMMDD/短uuid.ext)
            logger.info(f"📤 Uploading images to RustFS: {image_dir}")
            url_mapping = self._rustfs_client.upload_directory(
                str(image_dir),
                prefix=None,  # 不使用额外前缀，直接用日期分组
            )

            return url_mapping

        except Exception as e:
            logger.error(f"❌ Failed to initialize RustFS client: {e}")
            raise

    def _replace_markdown_urls(self, md_file: Path, url_mapping: Dict[str, str]):
        """
        替换 Markdown 中的图片路径为 RustFS URL

        Args:
            md_file: Markdown 文件
            url_mapping: {本地文件名: RustFS URL} 映射
        """
        try:
            content = md_file.read_text(encoding="utf-8")
            original_content = content
            replaced_count = 0

            logger.debug(f"🔍 Replacing URLs in {md_file.name}")
            logger.debug(f"   URL mapping: {url_mapping}")

            # 替换所有图片引用（统一转换为 HTML 格式，更通用）
            for filename, url in url_mapping.items():
                # 方式1: Markdown 格式 -> HTML 格式
                # ![alt](images/xxx.jpg) -> <img src="https://..." alt="alt">
                pattern1 = rf"!\[(.*?)\]\({self.STANDARD_IMAGE_DIR}/{re.escape(filename)}\)"
                matches1 = re.findall(pattern1, content)
                if matches1:
                    logger.debug(f"   Found Markdown pattern: {pattern1}")
                    logger.debug(f"   Matches: {matches1}")

                # 转换为 HTML 格式（更通用，前端渲染友好）
                def markdown_to_html(match):
                    alt_text = match.group(1) or filename
                    return f'<img src="{url}" alt="{alt_text}">'

                new_content = re.sub(pattern1, markdown_to_html, content)
                if new_content != content:
                    replaced_count += 1
                    logger.debug(f"   ✅ Replaced Markdown -> HTML: {filename} -> {url}")
                content = new_content

                # 方式2: HTML 格式 -> 更新 URL
                # <img src="images/xxx.jpg"> -> <img src="https://...">
                pattern2 = rf'<img([^>]*?)src=["\']({self.STANDARD_IMAGE_DIR}/{re.escape(filename)})["\']([^>]*?)>'
                matches2 = re.findall(pattern2, content)
                if matches2:
                    logger.debug(f"   Found HTML pattern: {pattern2}")
                    logger.debug(f"   Matches: {matches2}")

                new_content = re.sub(pattern2, rf'<img\1src="{url}"\3>', content)
                if new_content != content:
                    replaced_count += 1
                    logger.debug(f"   ✅ Replaced HTML: {filename} -> {url}")
                content = new_content

            if content != original_content:
                md_file.write_text(content, encoding="utf-8")
                logger.info(f"✅ Replaced {replaced_count} image URLs in {md_file.name}")
            else:
                logger.warning(f"⚠️  No replacements made in {md_file.name}")
                logger.debug(f"   Content preview (first 500 chars):\n{original_content[:500]}")

        except Exception as e:
            logger.error(f"❌ Failed to replace URLs in Markdown: {e}")
            raise

    def _replace_json_urls(self, json_file: Path, url_mapping: Dict[str, str]):
        """
        替换 JSON 中的图片路径为 RustFS URL

        Args:
            json_file: JSON 文件
            url_mapping: {本地文件名: RustFS URL} 映射
        """
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            replaced_count = 0
            logger.debug(f"🔍 Replacing URLs in {json_file.name}")

            # 递归替换 JSON 中的所有图片路径
            def replace_paths(obj, path=""):
                nonlocal replaced_count
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        if isinstance(value, str):
                            # 检查是否是图片路径
                            for filename, url in url_mapping.items():
                                if filename in value and self.STANDARD_IMAGE_DIR in value:
                                    old_value = obj[key]
                                    obj[key] = url
                                    replaced_count += 1
                                    logger.debug(f"   ✅ Replaced JSON[{path}.{key}]: {old_value} -> {url}")
                                    break
                        else:
                            replace_paths(value, f"{path}.{key}")
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        replace_paths(item, f"{path}[{i}]")

            replace_paths(data)

            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            if replaced_count > 0:
                logger.info(f"✅ Replaced {replaced_count} image URLs in {json_file.name}")
            else:
                logger.warning(f"⚠️  No replacements made in {json_file.name}")

        except Exception as e:
            logger.error(f"❌ Failed to replace URLs in JSON: {e}")
            raise


def normalize_paddleocr_output(output_dir: Path) -> Dict[str, Any]:
    """
    专门处理 PaddleOCR-VL 的输出规范化

    处理步骤：
    1. 为每页的图片添加页码前缀（page1_xxx.jpg），避免多页图片名称冲突
    2. 合并所有页的 JSON，并为 image 块添加 img_path 字段
    3. 更新 Markdown 中的图片引用路径

    Args:
        output_dir: PaddleOCR-VL 输出目录（包含 page_N 子目录）

    Returns:
        规范化后的文件信息
    """
    output_dir = Path(output_dir)
    logger.info(f"🤖 Normalizing PaddleOCR-VL output: {output_dir}")

    STANDARD_IMAGE_DIR = "images"
    STANDARD_JSON_NAME = "result.json"

    # 1. 处理图片：重命名并移动到 images/ 目录
    standard_image_dir = output_dir / STANDARD_IMAGE_DIR
    standard_image_dir.mkdir(exist_ok=True)

    image_mapping = {}  # {page_idx: {原始名: 新名}}
    image_counter = 1  # 全局累进编号

    page_dirs = sorted(output_dir.glob("page_*"))

    for page_dir in page_dirs:
        # 提取页码（page_1 -> 1）
        try:
            page_num = int(page_dir.name.split("_")[1])
        except (IndexError, ValueError):
            logger.warning(f"⚠️  Invalid page directory: {page_dir.name}")
            continue

        # 查找该页的 imgs 目录
        imgs_dir = page_dir / "imgs"
        if not imgs_dir.exists():
            continue

        page_mapping = {}
        logger.info(f"📁 Processing {page_dir.name}/imgs/")

        # 处理该页的所有图片
        for img_file in imgs_dir.iterdir():
            if not img_file.is_file():
                continue

            # 生成新文件名：image_001.jpg, image_002.jpg, ...
            file_ext = img_file.suffix
            new_name = f"image_{image_counter:03d}{file_ext}"
            new_path = standard_image_dir / new_name

            # 移动图片
            shutil.move(str(img_file), str(new_path))
            page_mapping[img_file.name] = new_name
            image_counter += 1
            logger.debug(f"   {img_file.name} -> {new_name}")

        image_mapping[page_num - 1] = page_mapping  # page_idx 从 0 开始

        # 删除空的 imgs 目录
        try:
            imgs_dir.rmdir()
        except OSError:
            pass

    logger.info(f"✅ Renamed {image_counter - 1} images with sequential numbering")

    # 2. 处理 JSON：合并所有页并添加 img_path 字段
    all_pages_data = []

    for page_dir in page_dirs:
        # 查找该页的 JSON 文件（格式：*_res.json）
        json_files = list(page_dir.glob("*_res.json"))

        if not json_files:
            logger.warning(f"⚠️  No JSON file in {page_dir.name}")
            continue

        json_file = json_files[0]

        try:
            with open(json_file, "r", encoding="utf-8") as f:
                page_data = json.load(f)

            # 获取页码
            page_idx = page_data.get("page_index", 0)

            # 为图片块添加 img_path 字段
            if "parsing_res_list" in page_data:
                page_img_mapping = image_mapping.get(page_idx, {})

                for block in page_data["parsing_res_list"]:
                    if block.get("block_label") == "image":
                        # 根据 bbox 生成图片文件名（PaddleOCR 的命名规则）
                        bbox = block.get("block_bbox", [])
                        if len(bbox) == 4:
                            # 图片文件名格式：img_in_image_box_{x1}_{y1}_{x2}_{y2}.jpg
                            img_name = f"img_in_image_box_{bbox[0]}_{bbox[1]}_{bbox[2]}_{bbox[3]}.jpg"

                            # 查找对应的新文件名
                            if img_name in page_img_mapping:
                                new_img_name = page_img_mapping[img_name]
                                # 添加 img_path 字段（参考 MinerU 格式）
                                block["img_path"] = f"{STANDARD_IMAGE_DIR}/{new_img_name}"
                                logger.debug(f"   Added img_path: {block['img_path']}")

            all_pages_data.append(page_data)
            logger.info(f"✅ Processed {json_file.name}")

        except Exception as e:
            logger.warning(f"⚠️  Failed to process {json_file}: {e}")
            continue

    # 保存合并后的 JSON
    if all_pages_data:
        standard_json = output_dir / STANDARD_JSON_NAME
        combined_data = {
            "pages": all_pages_data,
            "total_pages": len(all_pages_data),
            "format": "paddleocr-vl",
        }

        with open(standard_json, "w", encoding="utf-8") as f:
            json.dump(combined_data, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ Created {STANDARD_JSON_NAME} with {len(all_pages_data)} pages")

    # 3. 处理 Markdown：更新图片引用
    # 查找 result.md 文件
    md_files = list(output_dir.rglob("*.md"))
    if md_files:
        # 选择最大的 .md 文件（通常是主文件）
        main_md = max(md_files, key=lambda f: f.stat().st_size)

        # 如果不在根目录，移动到根目录
        standard_md = output_dir / "result.md"
        if main_md != standard_md:
            if main_md.parent != output_dir:
                shutil.copy2(main_md, standard_md)
            else:
                main_md.rename(standard_md)
            main_md = standard_md

        # 更新 Markdown 中的图片引用
        try:
            content = main_md.read_text(encoding="utf-8")

            # 构建完整的图片映射（所有页的图片）
            full_image_mapping = {}
            for page_mapping in image_mapping.values():
                full_image_mapping.update(page_mapping)

            # 替换 Markdown 图片语法：![alt](path)
            md_img_pattern = r"!\[([^\]]*)\]\(([^)]+)\)"

            def replace_md_path(match):
                alt_text = match.group(1)
                img_path = match.group(2)
                img_filename = Path(img_path).name

                # 查找新文件名
                if img_filename in full_image_mapping:
                    new_name = full_image_mapping[img_filename]
                    return f"![{alt_text}]({STANDARD_IMAGE_DIR}/{new_name})"
                return match.group(0)

            # 替换 HTML img 标签：<img src="path" ...>
            html_img_pattern = r'<img\s+([^>]*\s+)?src="([^"]+)"([^>]*)>'

            def replace_html_path(match):
                before_src = match.group(1) or ""
                img_path = match.group(2)
                after_src = match.group(3) or ""
                img_filename = Path(img_path).name

                # 查找新文件名
                if img_filename in full_image_mapping:
                    new_name = full_image_mapping[img_filename]
                    return f'<img {before_src}src="{STANDARD_IMAGE_DIR}/{new_name}"{after_src}>'
                return match.group(0)

            # 执行替换
            new_content = re.sub(md_img_pattern, replace_md_path, content)
            new_content = re.sub(html_img_pattern, replace_html_path, new_content)

            if new_content != content:
                main_md.write_text(new_content, encoding="utf-8")
                logger.info(f"✅ Updated image references in {main_md.name}")

        except Exception as e:
            logger.warning(f"⚠️  Failed to update markdown image references: {e}")

    logger.info("✅ PaddleOCR-VL normalization complete")

    return {
        "markdown_file": standard_md if md_files else None,
        "json_file": output_dir / STANDARD_JSON_NAME if all_pages_data else None,
        "image_dir": standard_image_dir,
        "image_count": image_counter - 1,
    }


def normalize_output(output_dir: Path) -> Dict[str, Any]:
    """
    便捷函数：规范化输出目录

    自动检测输出类型并选择合适的规范化方法：
    - 如果检测到 page_N 目录，使用 PaddleOCR-VL 专用规范化
    - 否则使用通用规范化

    Args:
        output_dir: 输出目录

    Returns:
        规范化后的文件信息
    """
    output_dir = Path(output_dir)

    # 检测是否是 PaddleOCR-VL 输出（有 page_N 子目录）
    page_dirs = list(output_dir.glob("page_*"))

    if page_dirs:
        logger.info("🤖 Detected PaddleOCR-VL output format")
        return normalize_paddleocr_output(output_dir)
    else:
        # 通用规范化
        normalizer = OutputNormalizer(output_dir)
        return normalizer.normalize()

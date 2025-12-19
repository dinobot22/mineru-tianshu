"""
SenseVoice 语音识别引擎
基于阿里达摩院的 SenseVoiceSmall 模型
支持：
- 多语言识别（中文、英文、日文、韩文等）
- 说话人分离（Speaker Diarization，基于 FunASR 1.2.7）
- 情感识别
- 时间戳对齐

说话人分离实现方案：
使用 FunASR 1.2.7 自带的说话人分离功能：
  1. FunASR CAM++ 模型进行说话人嵌入提取
  2. FunASR SOND 模型进行说话人聚类分离
  3. SenseVoice 对整段音频进行语音识别
  4. 根据说话人时间戳合并识别结果

优势：
  - FunASR 原生支持，无需额外依赖
  - 统一框架，减少兼容性问题
  - 性能更好，维护更简单
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from threading import Lock
from loguru import logger


class SenseVoiceEngine:
    """
    SenseVoice 语音识别引擎（单例模式）

    特性：
    - 基于 FunASR 框架
    - 支持多语言自动识别
    - 支持说话人分离（基于 FunASR 1.2.7 的原生 speaker diarization）
    - GPU 加速
    """

    _instance: Optional["SenseVoiceEngine"] = None
    _lock = Lock()
    _sensevoice_model = None  # SenseVoice 模型（不支持说话人分离）
    _paraformer_model = None  # Paraformer 模型（支持说话人分离）
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        model_dir: str = "iic/SenseVoiceSmall",
        cache_dir: Optional[str] = None,
        device: str = "cuda:0",
        enable_speaker_diarization: bool = False,
        use_paraformer_for_diarization: bool = False,
    ):
        """
        初始化 SenseVoice 引擎（只执行一次）

        Args:
            model_dir: 模型路径或ModelScope模型ID
            cache_dir: 模型缓存目录
            device: 设备 (cuda:0, cuda:1, cpu 等)
            enable_speaker_diarization: 是否启用说话人分离（默认关闭，需要从 API 参数控制）
            use_paraformer_for_diarization: 是否使用 Paraformer 模型进行说话人分离（SenseVoice 不支持时间戳）
        """
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            self.model_dir = model_dir
            self.device = device  # 保存 device 参数
            self.enable_speaker_diarization = enable_speaker_diarization
            self.use_paraformer_for_diarization = use_paraformer_for_diarization

            # 说话人分离说明
            if enable_speaker_diarization:
                logger.info("⚠️  说话人分离需要时间戳支持，将在首次使用时加载 Paraformer 模型")

            # 默认缓存目录：项目根目录/models/sensevoice
            if cache_dir is None:
                project_root = Path(__file__).parent.parent.parent
                self.cache_dir = str(project_root / "models" / "sensevoice")
            else:
                self.cache_dir = cache_dir

            # 确保缓存目录存在（带错误处理）
            try:
                Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
            except (OSError, PermissionError) as e:
                # 如果主缓存目录无法创建（如只读文件系统），使用临时目录
                import tempfile

                self.cache_dir = str(Path(tempfile.gettempdir()) / "sensevoice_cache")
                logger.warning(f"⚠️  Failed to create cache directory, using temp: {self.cache_dir}")
                logger.warning(f"   Original error: {e}")
                try:
                    Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
                except Exception as e2:
                    logger.error(f"❌ Failed to create temp cache directory: {e2}")
                    raise RuntimeError(f"Cannot create cache directory: {e2}") from e2

            self._initialized = True

            logger.info("🔧 SenseVoice Engine initialized")
            logger.info(f"   Model: {self.model_dir}")
            logger.info(f"   Device: {self.device}")
            logger.info(f"   Cache: {self.cache_dir}")
            logger.info(
                f"   Speaker Diarization: {'✅ Enabled (FunASR Native)' if enable_speaker_diarization else '❌ Disabled'}"
            )

    def _load_model(self, enable_sd: bool = False):
        """
        延迟加载模型（根据需求加载 SenseVoice 或 Paraformer）

        Args:
            enable_sd: 是否需要说话人分离支持

        Returns:
            对应的模型实例
        """
        with self._lock:
            logger.info("=" * 60)

            try:
                from funasr import AutoModel

                # 如果需要说话人分离，加载 Paraformer 模型
                if enable_sd:
                    if self._paraformer_model is None:
                        logger.info("📥 Loading Paraformer Model (with Speaker Diarization)...")
                        logger.info("=" * 60)
                        logger.info("🤖 Loading Paraformer + CAM++ + Punc models...")

                        # 使用 Paraformer 模型（支持时间戳和说话人分离）
                        # 参考：https://github.com/lukeewin/AudioSeparationGUI
                        self._paraformer_model = AutoModel(
                            model="iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
                            vad_model="fsmn-vad",
                            vad_kwargs={"max_single_segment_time": 30000},
                            punc_model="ct-punc",  # 标点模型（说话人分离必需）
                            spk_model="iic/speech_campplus_sv_zh-cn_16k-common",  # 说话人嵌入模型
                            device=self.device,
                        )

                        logger.info("=" * 60)
                        logger.info("✅ Paraformer Model loaded successfully!")
                        logger.info("   Features:")
                        logger.info("   - Multi-language ASR (zh-cn)")
                        logger.info("   - Timestamp Support ✅")
                        logger.info("   - Speaker Diarization (CAM++) ✅")
                        logger.info("   - Punctuation Prediction")
                        logger.info("=" * 60)
                    else:
                        logger.debug("♻️  Using cached Paraformer model")

                    return self._paraformer_model

                else:
                    # 不需要说话人分离，使用 SenseVoice 模型
                    if self._sensevoice_model is None:
                        logger.info("📥 Loading SenseVoice Model...")
                        logger.info("=" * 60)
                        logger.info(f"🤖 Loading model from: {self.model_dir}")

                        self._sensevoice_model = AutoModel(
                            model=self.model_dir,
                            trust_remote_code=True,
                            remote_code="./model.py",
                            vad_model="fsmn-vad",
                            vad_kwargs={"max_single_segment_time": 30000},
                            device=self.device,
                        )

                        logger.info("=" * 60)
                        logger.info("✅ SenseVoice Model loaded successfully!")
                        logger.info("   Features:")
                        logger.info("   - Multi-language ASR (zh/en/ja/ko/yue)")
                        logger.info("   - Emotion Recognition")
                        logger.info("=" * 60)
                    else:
                        logger.debug("♻️  Using cached SenseVoice model")

                    return self._sensevoice_model

            except Exception as e:
                logger.error("=" * 80)
                logger.error("❌ 模型加载失败:")
                logger.error(f"   错误类型: {type(e).__name__}")
                logger.error(f"   错误信息: {e}")
                logger.error("")
                logger.error("💡 排查建议:")
                logger.error("   1. 安装 FunASR:")
                logger.error("      pip install funasr>=1.2.7")
                logger.error("   2. 检查网络连接（首次使用需要下载模型）")
                logger.error("   3. 检查 GPU 可用性")
                logger.error("   4. 模型会自动从 ModelScope 下载")
                logger.error("=" * 80)

                import traceback

                logger.debug("完整堆栈跟踪:")
                logger.debug(traceback.format_exc())

                raise

    def parse(
        self, audio_path: str, output_path: str, language: str = "auto", use_itn: bool = True, **kwargs
    ) -> Dict[str, Any]:
        """
        语音识别（支持 FunASR 原生说话人分离）

        Args:
            audio_path: 音频文件路径
            output_path: 输出目录
            language: 语言代码 (auto/zh/en/ja/ko/yue)
            use_itn: 是否使用逆文本归一化（数字、日期等）
            **kwargs: 其他参数
                - enable_speaker_diarization: 是否启用说话人分离（覆盖初始化设置）

        Returns:
            解析结果（JSON格式，包含说话人信息）
        """
        audio_path = Path(audio_path)
        output_path = Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)

        # 检查是否启用说话人分离（可通过参数覆盖）
        enable_sd = kwargs.get("enable_speaker_diarization", self.enable_speaker_diarization)

        logger.info(f"🎙️  SenseVoice processing: {audio_path.name}")
        logger.info(f"   Language: {language}")
        logger.info(f"   Speaker Diarization: {'✅ Enabled (Paraformer)' if enable_sd else '❌ Disabled (SenseVoice)'}")

        # 加载模型（根据 enable_sd 决定加载 SenseVoice 还是 Paraformer）
        model = self._load_model(enable_sd=enable_sd)

        # 执行推理
        try:
            logger.info("🚀 开始语音识别...")

            # 如果启用说话人分离，使用 Paraformer + CAM++
            if enable_sd:
                logger.info("🎯 使用 Paraformer 说话人分离模式...")
                parsed_result = self._parse_with_funasr_diarization(audio_path, model, None, language, use_itn)
            else:
                logger.info("🎯 使用 SenseVoice 基础识别模式...")
                # FunASR 推理（基础模式）
                result = model.generate(
                    input=str(audio_path),
                    cache={},
                    language=language,
                    use_itn=use_itn,
                    batch_size=60,
                    merge_vad=True,  # 合并VAD结果
                    merge_length_s=15,  # 合并长度
                )

                logger.info("✅ SenseVoice completed")

                # 解析结果
                parsed_result = self._parse_result(result, audio_path)

            # 生成 Markdown
            markdown_content = self._generate_markdown(parsed_result)

            # 保存为统一的 content.md（主结果）
            content_md_file = output_path / "content.md"
            content_md_file.write_text(markdown_content, encoding="utf-8")
            logger.info("📄 Main result saved: content.md")

            # 同时保留原始命名的文件（用于调试/备份）
            original_md_file = output_path / f"{audio_path.stem}.md"
            original_md_file.write_text(markdown_content, encoding="utf-8")
            logger.info(f"📄 Backup saved: {original_md_file.name}")

            # 保存为统一的 content.json（主结果）
            content_json_file = output_path / "content.json"
            with open(content_json_file, "w", encoding="utf-8") as f:
                json.dump(parsed_result, f, ensure_ascii=False, indent=2)
            logger.info("📄 Main JSON saved: content.json")

            # 同时保留原始命名的文件（用于调试/备份）
            original_json_file = output_path / f"{audio_path.stem}.json"
            with open(original_json_file, "w", encoding="utf-8") as f:
                json.dump(parsed_result, f, ensure_ascii=False, indent=2)
            logger.info(f"📄 Backup JSON saved: {original_json_file.name}")

            return {
                "success": True,
                "output_path": str(output_path),
                "markdown": markdown_content,
                "markdown_file": str(content_md_file),
                "json_file": str(content_json_file),
                "json_data": parsed_result,
            }

        except Exception as e:
            logger.error("=" * 80)
            logger.error("❌ 语音识别失败:")
            logger.error(f"   错误类型: {type(e).__name__}")
            logger.error(f"   错误信息: {e}")
            logger.error("=" * 80)

            import traceback

            logger.debug("完整堆栈跟踪:")
            logger.debug(traceback.format_exc())

            raise

    def _parse_with_funasr_diarization(
        self, audio_path: Path, asr_model, sd_model, language: str, use_itn: bool
    ) -> Dict[str, Any]:
        """
        使用 FunASR 原生说话人分离 + SenseVoice 进行语音识别

        流程：
        1. 使用 FunASR 的 spk_mode 参数启用说话人分离
        2. SenseVoice 对音频进行语音识别，同时 CAM++ 模型提取说话人特征
        3. FunASR 自动为每个语音段分配说话人标签
        4. 解析结果并保留说话人信息

        Args:
            audio_path: 音频文件路径
            asr_model: SenseVoice ASR 模型（已加载 CAM++ 说话人模型）
            sd_model: 说话人分离模型（未使用，保留参数兼容性）
            language: 语言代码
            use_itn: 是否使用逆文本归一化

        Returns:
            标准化的 JSON 结果
        """
        try:
            # 使用 FunASR Paraformer + CAM++ 进行说话人分离
            logger.info("   [1/2] Paraformer 进行语音识别 + 说话人分离...")

            # 关键参数：
            # - batch_size_s: 批处理大小（秒）
            # - sentence_timestamp: 启用句子级时间戳（说话人分离必需）
            asr_result = asr_model.generate(
                input=str(audio_path),
                batch_size_s=300,  # 批处理大小（秒）
                sentence_timestamp=True,  # 启用句子级时间戳（关键！）
                is_final=True,  # 最终结果
            )

            logger.info("   [2/2] 解析说话人分离结果...")

            # 解析 Paraformer 结果（包含 sentence_info 和说话人信息）
            parsed_result = self._parse_paraformer_result(asr_result, audio_path)

            # 统计说话人数量
            segments = parsed_result.get("segments", [])
            speakers = set(seg.get("speaker", "SPEAKER_00") for seg in segments if seg.get("speaker"))
            speaker_count = len(speakers) if speakers else 1

            logger.info(f"✅ 说话人分离完成，检测到 {speaker_count} 位说话人（Paraformer + CAM++）")

            parsed_result["metadata"]["speaker_diarization_enabled"] = True
            parsed_result["metadata"]["speaker_diarization_method"] = "Paraformer + CAM++ (sentence-level)"
            parsed_result["metadata"]["speaker_count"] = speaker_count

            return parsed_result

        except Exception as e:
            logger.error(f"❌ FunASR 说话人分离失败: {e}")
            logger.warning("⚠️  回退到基础识别模式...")

            import traceback

            logger.debug(traceback.format_exc())

            # 回退到基础模式（不使用说话人分离）
            result = asr_model.generate(
                input=str(audio_path),
                cache={},
                language=language,
                use_itn=use_itn,
                batch_size=60,
                merge_vad=True,
                merge_length_s=15,
            )

            return self._parse_result(result, audio_path)

    def _parse_paraformer_result(self, result: List[Dict], audio_path: Path) -> Dict[str, Any]:
        """
        解析 Paraformer 的结果（包含 sentence_info 和说话人信息）

        Paraformer 返回格式：
        {
            'text': '完整文本',
            'sentence_info': [
                {'text': '句子1', 'start': 0, 'end': 1000, 'spk': 0},
                {'text': '句子2', 'start': 1000, 'end': 2000, 'spk': 1},
                ...
            ]
        }

        Args:
            result: Paraformer 返回的结果列表
            audio_path: 音频文件路径

        Returns:
            标准化的 JSON 结果（包含说话人信息）
        """
        if not result or len(result) == 0:
            return {
                "format": "audio",
                "audio_file": audio_path.name,
                "transcript": "",
                "segments": [],
                "metadata": {
                    "duration": 0,
                    "language": "zh-cn",
                    "speaker_count": 0,
                },
            }

        # 获取第一个结果
        first_result = result[0]

        # 提取完整文本
        transcript = first_result.get("text", "")

        # 提取句子级信息（包含说话人标签）
        sentence_info = first_result.get("sentence_info", [])

        # 构建语音段列表
        segments = []
        for sentence in sentence_info:
            text = sentence.get("text", "")
            start_ms = sentence.get("start", 0)  # 毫秒
            end_ms = sentence.get("end", 0)  # 毫秒
            spk = sentence.get("spk", 0)  # 说话人 ID（整数）

            # 格式化说话人标签
            speaker = f"SPEAKER_{spk:02d}"

            segments.append(
                {
                    "start": start_ms / 1000.0,  # 转换为秒
                    "end": end_ms / 1000.0,
                    "text": text,
                    "speaker": speaker,
                    "language": "zh-cn",  # Paraformer 主要支持中文
                    "emotion": "neutral",  # Paraformer 不支持情感识别
                }
            )

        # 计算总时长
        duration = segments[-1]["end"] if segments else 0

        # 统计说话人数量
        speakers = set(seg.get("speaker", "SPEAKER_00") for seg in segments)
        speaker_count = len(speakers)

        return {
            "format": "audio",
            "audio_file": audio_path.name,
            "transcript": transcript,
            "segments": segments,
            "metadata": {
                "duration": duration,
                "language": "zh-cn",
                "speaker_count": speaker_count,
                "emotion_enabled": False,  # Paraformer 不支持情感
            },
        }

    def _parse_result_with_speaker(self, result: List[Dict], audio_path: Path) -> Dict[str, Any]:
        """
        解析 FunASR 的原始结果为标准化格式（包含说话人信息）

        Args:
            result: FunASR 返回的结果列表（包含说话人标签）
            audio_path: 音频文件路径

        Returns:
            标准化的 JSON 结果（包含说话人信息）
        """
        if not result or len(result) == 0:
            return {
                "format": "audio",
                "audio_file": audio_path.name,
                "transcript": "",
                "segments": [],
                "metadata": {
                    "duration": 0,
                    "language": "unknown",
                    "speaker_count": 0,
                },
            }

        # 获取第一个结果（通常只有一个）
        first_result = result[0]

        # 提取文本
        transcript = first_result.get("text", "")

        # 提取时间戳（如果有）
        timestamp = first_result.get("timestamp", [])

        # 提取语言标签
        language_tags = first_result.get("language", [])

        # 提取情感标签
        emotion_tags = first_result.get("emotion", [])

        # 提取说话人标签（FunASR 返回的说话人 ID）
        speaker_tags = first_result.get("spk", [])  # 或者 "speaker"，取决于 FunASR 版本

        # 构建语音段列表
        segments = []
        if timestamp:
            # timestamp 格式: [[word_index, start_ms, end_ms], ...]
            for i, ts in enumerate(timestamp):
                # ts 可能是 [start, end] 或 [word_idx, start, end]
                if len(ts) == 3:
                    word_idx, start_ms, end_ms = ts
                elif len(ts) == 2:
                    start_ms, end_ms = ts
                    word_idx = i
                else:
                    continue

                # 从完整文本中提取对应的词（简化处理）
                words = transcript.split()
                if word_idx < len(words):
                    text = words[word_idx]
                else:
                    text = ""

                # 获取语言和情感（如果有）
                lang = language_tags[i] if i < len(language_tags) else "unknown"
                emotion = emotion_tags[i] if i < len(emotion_tags) else "neutral"

                # 获取说话人标签（关键：从 FunASR 结果中提取）
                speaker = speaker_tags[i] if i < len(speaker_tags) else "SPEAKER_00"
                # 格式化说话人标签
                if isinstance(speaker, int):
                    speaker = f"SPEAKER_{speaker:02d}"
                elif not isinstance(speaker, str):
                    speaker = f"SPEAKER_{str(speaker)}"

                segments.append(
                    {
                        "start": start_ms / 1000.0,  # 转换为秒
                        "end": end_ms / 1000.0,
                        "text": text,
                        "language": lang,
                        "emotion": emotion,
                        "speaker": speaker,  # 添加说话人标签
                    }
                )
        else:
            # 没有时间戳信息，创建一个单一段落
            speaker = speaker_tags[0] if speaker_tags else "SPEAKER_00"
            if isinstance(speaker, int):
                speaker = f"SPEAKER_{speaker:02d}"

            segments.append(
                {
                    "start": 0,
                    "end": 0,
                    "text": transcript,
                    "language": language_tags[0] if language_tags else "unknown",
                    "emotion": emotion_tags[0] if emotion_tags else "neutral",
                    "speaker": speaker,
                }
            )

        # 计算总时长
        duration = segments[-1]["end"] if segments else 0

        # 检测语言
        detected_language = language_tags[0] if language_tags else "auto"

        # 统计说话人数量
        speakers = set(seg.get("speaker", "SPEAKER_00") for seg in segments)
        speaker_count = len(speakers)

        return {
            "format": "audio",
            "audio_file": audio_path.name,
            "transcript": transcript,
            "segments": segments,
            "metadata": {
                "duration": duration,
                "language": detected_language,
                "speaker_count": speaker_count,
                "emotion_enabled": bool(emotion_tags),
            },
        }

    def _parse_result(self, result: List[Dict], audio_path: Path) -> Dict[str, Any]:
        """
        解析 FunASR 的原始结果为标准化格式

        Args:
            result: FunASR 返回的结果列表
            audio_path: 音频文件路径

        Returns:
            标准化的 JSON 结果
        """
        if not result or len(result) == 0:
            return {
                "format": "audio",
                "audio_file": audio_path.name,
                "transcript": "",
                "segments": [],
                "metadata": {
                    "duration": 0,
                    "language": "unknown",
                    "speaker_count": 0,
                },
            }

        # 获取第一个结果（通常只有一个）
        first_result = result[0]

        # 提取文本
        transcript = first_result.get("text", "")

        # 提取时间戳（如果有）
        timestamp = first_result.get("timestamp", [])

        # 提取语言标签
        language_tags = first_result.get("language", [])

        # 提取情感标签
        emotion_tags = first_result.get("emotion", [])

        # 构建语音段列表
        segments = []
        if timestamp:
            # timestamp 格式: [[word_index, start_ms, end_ms], ...]
            for i, ts in enumerate(timestamp):
                # ts 可能是 [start, end] 或 [word_idx, start, end]
                if len(ts) == 3:
                    word_idx, start_ms, end_ms = ts
                elif len(ts) == 2:
                    start_ms, end_ms = ts
                    word_idx = i
                else:
                    continue

                # 从完整文本中提取对应的词（简化处理）
                words = transcript.split()
                if word_idx < len(words):
                    text = words[word_idx]
                else:
                    text = ""

                # 获取语言和情感（如果有）
                lang = language_tags[i] if i < len(language_tags) else "unknown"
                emotion = emotion_tags[i] if i < len(emotion_tags) else "neutral"

                segments.append(
                    {
                        "start": start_ms / 1000.0,  # 转换为秒
                        "end": end_ms / 1000.0,
                        "text": text,
                        "language": lang,
                        "emotion": emotion,
                    }
                )
        else:
            # 没有时间戳信息，创建一个单一段落
            segments.append(
                {
                    "start": 0,
                    "end": 0,
                    "text": transcript,
                    "language": language_tags[0] if language_tags else "unknown",
                    "emotion": emotion_tags[0] if emotion_tags else "neutral",
                }
            )

        # 计算总时长
        duration = segments[-1]["end"] if segments else 0

        # 检测语言
        detected_language = language_tags[0] if language_tags else "auto"

        return {
            "format": "audio",
            "audio_file": audio_path.name,
            "transcript": transcript,
            "segments": segments,
            "metadata": {
                "duration": duration,
                "language": detected_language,
                "speaker_count": 1,  # 基础模式默认为1个说话人
                "emotion_enabled": bool(emotion_tags),
            },
        }

    def _generate_markdown(self, parsed_result: Dict[str, Any]) -> str:
        """
        生成 Markdown 格式的转录文本

        Args:
            parsed_result: 标准化的 JSON 结果

        Returns:
            Markdown 格式的文本
        """
        lines = []

        # 标题
        lines.append("# 音频转录结果\n")
        lines.append(f"**文件**: {parsed_result['audio_file']}\n")

        # 元数据
        metadata = parsed_result.get("metadata", {})
        lines.append("## 元数据\n")
        lines.append(f"- **时长**: {metadata.get('duration', 0):.2f} 秒")
        lines.append(f"- **语言**: {metadata.get('language', 'unknown')}")
        lines.append(f"- **说话人数量**: {metadata.get('speaker_count', 1)}")

        if metadata.get("speaker_diarization_enabled"):
            lines.append(f"- **说话人分离**: ✅ 已启用 ({metadata.get('speaker_diarization_method', 'FunASR')})")

        if metadata.get("emotion_enabled"):
            lines.append("- **情感识别**: ✅ 已启用")

        lines.append("")

        # 完整转录文本
        lines.append("## 完整转录\n")
        lines.append(parsed_result.get("transcript", ""))
        lines.append("")

        # 详细时间戳（仅当有有效时间戳时才显示）
        segments = parsed_result.get("segments", [])
        # 检查是否有有效的时间戳（至少有一个 segment 的 start 或 end 不为 0）
        has_valid_timestamps = any(seg.get("start", 0) != 0 or seg.get("end", 0) != 0 for seg in segments)

        if segments and has_valid_timestamps:
            lines.append("## 详细时间戳\n")

            for seg in segments:
                start = seg.get("start", 0)
                end = seg.get("end", 0)
                text = seg.get("text", "")
                speaker = seg.get("speaker", "")
                emotion = seg.get("emotion", "")

                # 格式化时间戳
                timestamp = f"[{self._format_time(start)} --> {self._format_time(end)}]"

                # 添加说话人标签
                speaker_tag = f"**{speaker}**: " if speaker else ""

                # 添加情感标签
                emotion_tag = f" *({emotion})*" if emotion and emotion != "neutral" else ""

                lines.append(f"{timestamp} {speaker_tag}{text}{emotion_tag}")

            lines.append("")

        return "\n".join(lines)

    def _format_time(self, seconds: float) -> str:
        """
        格式化时间（秒 -> HH:MM:SS.mmm）

        Args:
            seconds: 秒数

        Returns:
            格式化的时间字符串
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
        else:
            return f"{minutes:02d}:{secs:06.3f}"

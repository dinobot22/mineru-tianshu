<template>
  <div>
    <!-- 页面标题 -->
    <div class="mb-4 lg:mb-6">
      <h1 class="text-xl lg:text-2xl font-bold text-gray-900">{{ $t('task.submitTask') }}</h1>
      <p class="mt-1 text-sm text-gray-600">{{ $t('task.processingOptions') }}</p>
    </div>

    <div class="max-w-5xl mx-auto">
      <!-- 文件上传 -->
      <div class="card mb-6">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">{{ $t('task.selectFile') }}</h2>
        <FileUploader
          ref="fileUploader"
          :multiple="true"
          :acceptHint="$t('task.supportedFormatsHint')"
          @update:files="onFilesChange"
        />
      </div>

      <!-- 配置选项 -->
      <div class="card mb-4 lg:mb-6">
        <h2 class="text-base lg:text-lg font-semibold text-gray-900 mb-4">{{ $t('task.processingOptions') }}</h2>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 lg:gap-6">
          <!-- Backend 选择 -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">
              {{ $t('task.backend') }}
            </label>
            <select
              v-model="config.backend"
              @change="onBackendChange"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="auto">{{ $t('task.backendAuto') }}</option>
              <optgroup :label="$t('task.groupDocParsing')">
                <option value="pipeline">{{ $t('task.backendPipeline') }}</option>
                <option value="paddleocr-vl">{{ $t('task.backendPaddleOCR') }}</option>
                <option value="paddleocr-vl-vllm">{{ $t('task.backendPaddleOCRVLLM') }}</option>
                <option value="vlm-transformers">{{ $t('task.backendVLMTransformers') }}</option>
                <option value="vlm-vllm-engine">{{ $t('task.backendVLMEngine') }}</option>
              </optgroup>
              <optgroup :label="$t('task.groupAudioVideo')">
                <option value="sensevoice">{{ $t('task.backendSenseVoice') }}</option>
                <option value="video">{{ $t('task.backendVideo') }}</option>
              </optgroup>
              <optgroup :label="$t('task.groupProfessional')">
                <option value="fasta">{{ $t('task.backendFasta') }}</option>
                <option value="genbank">{{ $t('task.backendGenBank') }}</option>
              </optgroup>
            </select>
            <p v-if="config.backend === 'auto'" class="mt-1 text-xs text-gray-500">
              {{ $t('task.backendAutoHint') }}
            </p>

            <p v-if="config.backend === 'paddleocr-vl'" class="mt-1 text-xs text-gray-500">
              {{ $t('task.backendPaddleOCRHint') }}
            </p>
            <p v-if="config.backend === 'paddleocr-vl-vllm'" class="mt-1 text-xs text-gray-500">
              {{ $t('task.backendPaddleOCRVLLMHint') }}
            </p>
            <p v-if="config.backend === 'sensevoice'" class="mt-1 text-xs text-gray-500">
              {{ $t('task.backendSenseVoiceHint') }}
            </p>
            <p v-if="config.backend === 'video'" class="mt-1 text-xs text-gray-500">
              {{ $t('task.backendVideoHint') }}
            </p>
            <p v-if="config.backend === 'fasta'" class="mt-1 text-xs text-gray-500">
              {{ $t('task.backendFastaHint') }}
            </p>
            <p v-if="config.backend === 'genbank'" class="mt-1 text-xs text-gray-500">
              {{ $t('task.backendGenBankHint') }}
            </p>
          </div>

          <!-- 语言选择 -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">
              {{ $t('task.language') }}
            </label>
            <select
              v-model="config.lang"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="auto">{{ $t('task.langAuto') }}</option>
              <option value="ch">{{ $t('task.langChinese') }}</option>
              <option value="en">{{ $t('task.langEnglish') }}</option>
              <option value="korean">{{ $t('task.langKorean') }}</option>
              <option value="japan">{{ $t('task.langJapanese') }}</option>
            </select>
            <p class="mt-1 text-xs text-gray-500">
              {{ $t('task.langHint') }}
            </p>
          </div>

          <!-- 解析方法 -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">
              {{ $t('task.method') }}
            </label>
            <select
              v-model="config.method"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="auto">{{ $t('task.methodAuto') }}</option>
              <option value="txt">{{ $t('task.methodText') }}</option>
              <option value="ocr">{{ $t('task.methodOCR') }}</option>
            </select>
          </div>

          <!-- 优先级 -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">
              {{ $t('task.priorityLabel') }}
              <span class="text-gray-500 font-normal">{{ $t('task.priorityHint') }}</span>
            </label>
            <input
              v-model.number="config.priority"
              type="number"
              min="0"
              max="100"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
        </div>

        <!-- 提示信息 -->
        <div v-if="['pipeline', 'paddleocr-vl', 'paddleocr-vl-vllm'].includes(config.backend)" class="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <p class="text-sm text-blue-800">
            {{ $t('task.tipBothFormats', { backend: config.backend === 'pipeline' ? 'MinerU' : config.backend === 'paddleocr-vl' ? 'PaddleOCR-VL' : 'PaddleOCR-VL-VLLM' }) }}
          </p>
        </div>

        <!-- Video 专属配置 -->
        <div v-if="config.backend === 'video'" class="mt-6 pt-6 border-t border-gray-200">
          <h3 class="text-base font-semibold text-gray-900 mb-4">{{ $t('task.videoOptions') }}</h3>

          <div class="space-y-4">
            <!-- 音频选项 -->
            <div>
              <label class="flex items-center">
                <input
                  v-model="config.keep_audio"
                  type="checkbox"
                  class="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                />
                <span class="ml-2 text-sm text-gray-700">{{ $t('task.keepAudio') }}</span>
              </label>
              <p class="text-xs text-gray-500 ml-6 mt-1">
                {{ $t('task.keepAudioHint') }}
              </p>
            </div>

            <!-- 关键帧OCR选项 -->
            <div class="pt-4 border-t border-gray-100">
              <label class="flex items-center">
                <input
                  v-model="config.enable_keyframe_ocr"
                  type="checkbox"
                  class="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                />
                <span class="ml-2 text-sm text-gray-700 font-medium">
                  {{ $t('task.enableKeyframeOCR') }}
                  <span class="ml-1 px-1.5 py-0.5 text-xs bg-blue-100 text-blue-700 rounded">{{ $t('task.enableKeyframeOCRBadge') }}</span>
                </span>
              </label>
              <p class="text-xs text-gray-500 ml-6 mt-1">
                {{ $t('task.enableKeyframeOCRHint') }}
              </p>

              <!-- 关键帧OCR子选项 -->
              <div v-if="config.enable_keyframe_ocr" class="ml-6 mt-3 space-y-3 pl-4 border-l-2 border-primary-200">
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-2">
                    {{ $t('task.ocrEngine') }}
                  </label>
                  <select
                    v-model="config.ocr_backend"
                    class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                  >
                    <option value="paddleocr-vl">{{ $t('task.ocrEngineRecommended') }}</option>
                  </select>
                </div>

                <label class="flex items-center">
                  <input
                    v-model="config.keep_keyframes"
                    type="checkbox"
                    class="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                  />
                  <span class="ml-2 text-sm text-gray-700">{{ $t('task.keepKeyframes') }}</span>
                </label>
              </div>
            </div>
          </div>
        </div>

        <!-- PaddleOCR-VL 专属配置 -->
        <div v-if="config.backend === 'paddleocr-vl'" class="mt-6 pt-6 border-t border-gray-200">
          <div class="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
            <h3 class="text-sm font-semibold text-blue-900 mb-2">{{ $t('task.paddleOCREnhanced') }}</h3>
            <ul class="text-xs text-blue-800 space-y-1">
              <li>{{ $t('task.paddleOCRFeature1') }}</li>
              <li>{{ $t('task.paddleOCRFeature2') }}</li>
              <li>{{ $t('task.paddleOCRFeature3') }}</li>
              <li>{{ $t('task.paddleOCRFeature4') }}</li>
            </ul>
          </div>

          <div class="text-sm text-gray-600">
            <p class="mb-2">{{ $t('task.paddleOCRTipTitle') }} <strong></strong></p>
            <ul class="list-disc list-inside space-y-1 text-xs">
              <li>{{ $t('task.paddleOCRTip1') }}</li>
              <li>{{ $t('task.paddleOCRTip2') }}</li>
              <li>{{ $t('task.paddleOCRTip3') }}</li>
              <li>{{ $t('task.paddleOCRTip4') }}</li>
            </ul>
          </div>
        </div>

        <!-- 功能开关（仅 Pipeline） -->
        <div v-if="config.backend === 'pipeline'" class="mt-6 space-y-3">
          <label class="flex items-center">
            <input
              v-model="config.formula_enable"
              type="checkbox"
              class="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
            />
            <span class="ml-2 text-sm text-gray-700">{{ $t('task.enableFormulaRecognition') }}</span>
          </label>

          <label class="flex items-center">
            <input
              v-model="config.table_enable"
              type="checkbox"
              class="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
            />
            <span class="ml-2 text-sm text-gray-700">{{ $t('task.enableTableRecognition') }}</span>
          </label>
        </div>

        <!-- 水印去除配置（PDF/图片） -->
        <div v-if="['pipeline', 'paddleocr-vl', 'paddleocr-vl-vllm'].includes(config.backend)" class="mt-6 pt-6 border-t border-gray-200">
          <h3 class="text-base font-semibold text-gray-900 mb-4">{{ $t('task.watermarkOptions') }}</h3>

          <div class="space-y-4">
            <!-- 水印去除开关 -->
            <div>
              <label class="flex items-center">
                <input
                  v-model="config.remove_watermark"
                  type="checkbox"
                  class="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                />
                <span class="ml-2 text-sm text-gray-700 font-medium">
                  {{ $t('task.enableWatermarkRemoval') }}
                  <span class="ml-1 px-1.5 py-0.5 text-xs bg-purple-100 text-purple-700 rounded">{{ $t('task.watermarkBadge') }}</span>
                </span>
              </label>
              <p class="text-xs text-gray-500 ml-6 mt-1">
                {{ $t('task.watermarkHint') }}
              </p>
            </div>

            <!-- 高级选项 -->
            <div v-if="config.remove_watermark" class="ml-6 mt-3 space-y-3 pl-4 border-l-2 border-purple-200">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                  {{ $t('task.watermarkConfidence') }}
                  <span class="text-gray-500 font-normal text-xs">（{{ config.watermark_conf_threshold }}）</span>
                </label>
                <input
                  v-model.number="config.watermark_conf_threshold"
                  type="range"
                  min="0.1"
                  max="0.9"
                  step="0.05"
                  class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-purple-600"
                />
                <div class="flex justify-between text-xs text-gray-500 mt-1">
                  <span>{{ $t('task.watermarkConfidenceMore') }}</span>
                  <span>{{ $t('task.watermarkConfidenceRecommended') }}</span>
                  <span>{{ $t('task.watermarkConfidenceLess') }}</span>
                </div>
                <p class="text-xs text-gray-500 mt-1">
                  {{ $t('task.watermarkConfidenceHint') }}
                </p>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                  {{ $t('task.watermarkDilation') }}
                  <span class="text-gray-500 font-normal text-xs">{{ $t('task.watermarkDilationPixels', { value: config.watermark_dilation }) }}</span>
                </label>
                <input
                  v-model.number="config.watermark_dilation"
                  type="range"
                  min="0"
                  max="30"
                  step="5"
                  class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-purple-600"
                />
                <div class="flex justify-between text-xs text-gray-500 mt-1">
                  <span>{{ $t('task.watermarkDilationExact') }}</span>
                  <span>{{ $t('task.watermarkDilationRecommended') }}</span>
                  <span>{{ $t('task.watermarkDilationExpand') }}</span>
                </div>
                <p class="text-xs text-gray-500 mt-1">
                  {{ $t('task.watermarkDilationHint') }}
                </p>
              </div>
            </div>

            <!-- PDF 处理说明 -->
            <div v-if="config.remove_watermark" class="bg-purple-50 border border-purple-200 rounded-lg p-3 mt-3">
              <p class="text-xs text-purple-800">
                <strong>{{ $t('task.watermarkPDFTitle') }}</strong>
              </p>
              <ul class="text-xs text-purple-700 mt-1 ml-4 list-disc space-y-0.5">
                <li>{{ $t('task.watermarkPDFTip1') }}</li>
                <li>{{ $t('task.watermarkPDFTip2') }}</li>
                <li>{{ $t('task.watermarkPDFTip3') }}</li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      <!-- 错误提示 -->
      <div v-if="errorMessage" class="card bg-red-50 border-red-200 mb-6">
        <div class="flex items-start">
          <AlertCircle class="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <div class="ml-3 flex-1">
            <h3 class="text-sm font-medium text-red-800">{{ $t('common.error') }}</h3>
            <p class="mt-1 text-sm text-red-700">{{ errorMessage }}</p>
          </div>
          <button
            @click="errorMessage = ''"
            class="ml-auto -mr-1 -mt-1 p-1 text-red-600 hover:text-red-800"
          >
            <X class="w-5 h-5" />
          </button>
        </div>
      </div>

      <!-- 提交按钮 -->
      <div class="flex flex-col sm:flex-row justify-end gap-2 sm:gap-3">
        <router-link to="/" class="btn btn-secondary text-center">
          {{ $t('common.cancel') }}
        </router-link>
        <button
          @click="submitTasks"
          :disabled="files.length === 0 || submitting"
          class="btn btn-primary disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
        >
          <Loader v-if="submitting" class="w-4 h-4 mr-2 animate-spin" />
          <Upload v-else class="w-4 h-4 mr-2" />
          {{ submitting ? $t('common.loading') : `${$t('task.submitTask')} (${files.length})` }}
        </button>
      </div>

      <!-- 提交进度 -->
      <div v-if="submitting || submitProgress.length > 0" class="card mt-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">{{ $t('common.progress') }}</h3>
        <div class="space-y-2">
          <div
            v-for="(progress, index) in submitProgress"
            :key="index"
            class="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
          >
            <div class="flex items-center flex-1">
              <FileText class="w-5 h-5 text-gray-400 flex-shrink-0" />
              <span class="ml-3 text-sm text-gray-900">{{ progress.fileName }}</span>
            </div>
            <div class="flex items-center">
              <CheckCircle v-if="progress.success" class="w-5 h-5 text-green-600" />
              <XCircle v-else-if="progress.error" class="w-5 h-5 text-red-600" />
              <Loader v-else class="w-5 h-5 text-primary-600 animate-spin" />
              <span v-if="progress.taskId" class="ml-2 text-xs text-gray-500">
                {{ progress.taskId }}
              </span>
            </div>
          </div>
        </div>

        <!-- 完成后的操作 -->
        <div v-if="!submitting && submitProgress.length > 0" class="mt-4 flex justify-end gap-3">
          <button
            @click="resetForm"
            class="btn btn-secondary"
          >
            {{ $t('common.continue') }}
          </button>
          <router-link to="/tasks" class="btn btn-primary">
            {{ $t('task.taskList') }}
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useTaskStore } from '@/stores'
import FileUploader from '@/components/FileUploader.vue'
import {
  Upload,
  Loader,
  AlertCircle,
  X,
  FileText,
  CheckCircle,
  XCircle,
} from 'lucide-vue-next'
import type { Backend, Language, ParseMethod } from '@/api/types'

const { t } = useI18n()
const router = useRouter()
const taskStore = useTaskStore()

const fileUploader = ref<InstanceType<typeof FileUploader>>()
const files = ref<File[]>([])
const submitting = ref(false)
const errorMessage = ref('')

interface SubmitProgress {
  fileName: string
  success: boolean
  error: boolean
  taskId?: string
}

const submitProgress = ref<SubmitProgress[]>([])

const config = reactive({
  backend: 'auto' as Backend,  // 默认自动选择引擎
  lang: 'auto' as Language,  // 默认自动检测语言
  method: 'auto' as ParseMethod,
  formula_enable: true,
  table_enable: true,
  priority: 0,
  // Video 专属配置
  keep_audio: false,
  enable_keyframe_ocr: false,
  ocr_backend: 'paddleocr-vl',
  keep_keyframes: false,
  // 水印去除配置
  remove_watermark: false,
  watermark_conf_threshold: 0.35,
  watermark_dilation: 10,
})

function onFilesChange(newFiles: File[]) {
  files.value = newFiles
}

function onBackendChange() {
  // 根据选择的引擎调整语言设置
  if (config.backend === 'pipeline') {
    // MinerU Pipeline 不支持 auto，默认使用中文
    config.lang = 'ch'
  } else if (['fasta', 'genbank'].includes(config.backend)) {
    // 专业格式引擎不需要语言选择
    config.lang = 'en'
  } else {
    // 其他引擎（auto/音频/视频/OCR）默认自动检测
    config.lang = 'auto'
  }
}

async function submitTasks() {
  if (files.value.length === 0) {
    errorMessage.value = t('task.pleaseSelectFile')
    return
  }

  submitting.value = true
  errorMessage.value = ''
  submitProgress.value = files.value.map(f => ({
    fileName: f.name,
    success: false,
    error: false,
  }))

  // 批量提交任务
  for (let i = 0; i < files.value.length; i++) {
    const file = files.value[i]
    try {
      const response = await taskStore.submitTask({
        file,
        ...config,
      })
      submitProgress.value[i].success = true
      submitProgress.value[i].taskId = response.task_id
    } catch (err: any) {
      submitProgress.value[i].error = true
      console.error(`Failed to submit ${file.name}:`, err)
    }
  }

  submitting.value = false

  // 检查是否全部成功
  const allSuccess = submitProgress.value.every(p => p.success)
  if (allSuccess && files.value.length === 1) {
    // 单个文件且成功，跳转到详情页
    const taskId = submitProgress.value[0].taskId!
    router.push(`/tasks/${taskId}`)
  }
}

function resetForm() {
  files.value = []
  submitProgress.value = []
  errorMessage.value = ''
  fileUploader.value?.clearFiles()
}
</script>

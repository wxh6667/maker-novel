<template>
  <div v-if="show" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
    <div class="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[80vh] overflow-hidden flex flex-col">
      <!-- 弹窗头部 -->
      <div class="flex items-center justify-between p-6 border-b border-gray-200">
        <div class="flex items-center gap-3">
            <div class="w-10 h-10 bg-purple-500 rounded-full flex items-center justify-center flex-shrink-0">
                <svg class="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M10 2a6 6 0 00-6 6v3.586l-1.707 1.707A1 1 0 003 15v1a1 1 0 001 1h12a1 1 0 001-1v-1a1 1 0 00-.293-.707L16 11.586V8a6 6 0 00-6-6zM8.05 17a2 2 0 103.9 0H8.05z"></path>
                </svg>
            </div>
            <div>
              <h3 class="text-xl font-bold text-gray-900">AI 评审详情</h3>
              <p v-if="evaluationModel" class="text-xs text-gray-500 mt-0.5">
                评审模型: {{ evaluationModel }}
              </p>
            </div>
        </div>
        <button
          @click="$emit('close')"
          class="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
          </svg>
        </button>
      </div>

      <!-- 弹窗内容 -->
      <div class="p-6 overflow-y-auto max-h-[calc(80vh-130px)]">
        <div v-if="parsedEvaluation" class="space-y-6 text-sm">
            <div class="bg-purple-50 border border-purple-200 rounded-xl p-4">
              <p class="font-semibold text-purple-800 text-base">🏆 最佳选择：版本 {{ parsedEvaluation.best_choice }}</p>
              <p class="text-purple-700 mt-2">{{ parsedEvaluation.reason_for_choice }}</p>
            </div>

            <!-- 新格式：versions 数组 -->
            <div v-if="parsedEvaluation.versions && Array.isArray(parsedEvaluation.versions)" class="space-y-4">
              <div v-for="evalResult in parsedEvaluation.versions" :key="evalResult.version_index" class="bg-gray-50 p-4 rounded-lg border border-gray-200">
                <div class="flex items-center justify-between mb-2">
                  <div class="flex items-center gap-3">
                    <h5 class="font-bold text-gray-800 text-lg">版本 {{ evalResult.version_index }} 评估</h5>
                    <!-- 分数显示 -->
                    <span
                      class="px-3 py-1 rounded-full text-sm font-semibold"
                      :class="getScoreClass(evalResult.score)"
                    >
                      {{ evalResult.score }} 分
                    </span>
                  </div>
                  <div class="flex items-center gap-2">
                    <button
                      v-if="getContentForVersion(evalResult.version_index)"
                      @click="toggleContent(evalResult.version_index)"
                      class="px-3 py-1 text-xs bg-gray-100 text-gray-600 rounded-full hover:bg-gray-200 transition-colors"
                    >
                      {{ expandedVersions.has(evalResult.version_index) ? '收起内容' : '查看内容' }}
                    </button>
                    <button
                      v-if="evalResult.cons && evalResult.cons.length > 0"
                      @click="$emit('rewrite-version', evalResult.version_index)"
                      :disabled="rewriting"
                      class="px-3 py-1 text-xs bg-amber-100 text-amber-700 rounded-full hover:bg-amber-200 transition-colors disabled:opacity-50"
                    >
                      重写此版本
                    </button>
                  </div>
                </div>
                <!-- 版本内容展示 -->
                <div
                  v-if="expandedVersions.has(evalResult.version_index) && getContentForVersion(evalResult.version_index)"
                  class="mb-3 p-3 bg-white border border-gray-200 rounded-lg max-h-60 overflow-y-auto"
                >
                  <p class="text-xs text-gray-500 mb-2">生成内容:</p>
                  <div class="whitespace-pre-wrap text-gray-700 text-sm leading-relaxed">{{ getContentForVersion(evalResult.version_index) }}</div>
                </div>
                <p class="text-xs text-gray-500 mb-3">
                  <span v-if="getModelForVersion(evalResult.version_index)">
                    生成模型: {{ getModelForVersion(evalResult.version_index) }}
                  </span>
                  <span v-if="getModelForVersion(evalResult.version_index) && getWordCountForVersion(evalResult.version_index)"> · </span>
                  <span v-if="getWordCountForVersion(evalResult.version_index)">
                    字数: {{ getWordCountForVersion(evalResult.version_index).toLocaleString() }}
                  </span>
                </p>
                <div class="prose prose-sm max-w-none text-gray-700 space-y-3">
                  <div>
                    <p class="font-semibold text-gray-800">综合评价:</p>
                    <p>{{ evalResult.overall_review }}</p>
                  </div>
                  <div>
                    <p class="font-semibold text-gray-800">优点:</p>
                    <ul class="list-disc pl-5 space-y-1">
                      <li v-for="(pro, i) in evalResult.pros" :key="`pro-${i}`">{{ pro }}</li>
                    </ul>
                  </div>
                  <div>
                    <p class="font-semibold text-gray-800">缺点:</p>
                    <ul class="list-disc pl-5 space-y-1">
                      <li v-for="(con, i) in evalResult.cons" :key="`con-${i}`">
                        <!-- 支持新格式（对象）和旧格式（字符串） -->
                        <template v-if="typeof con === 'object' && con !== null">
                          <span class="font-medium text-amber-700">[{{ con.location }}]</span> {{ con.issue }}
                          <span v-if="con.suggestion" class="text-gray-500 text-xs block mt-0.5">→ {{ con.suggestion }}</span>
                        </template>
                        <template v-else>{{ con }}</template>
                      </li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>

            <!-- 旧格式：evaluation 对象 -->
            <div v-else-if="parsedEvaluation.evaluation" class="space-y-4">
              <div v-for="(evalResult, versionName) in parsedEvaluation.evaluation" :key="versionName" class="bg-gray-50 p-4 rounded-lg border border-gray-200">
                <div class="flex items-center justify-between mb-2">
                  <div class="flex items-center gap-3">
                    <h5 class="font-bold text-gray-800 text-lg">版本 {{ String(versionName).replace('version', '') }} 评估</h5>
                    <!-- 分数显示（如果有） -->
                    <span
                      v-if="evalResult.score !== undefined"
                      class="px-3 py-1 rounded-full text-sm font-semibold"
                      :class="getScoreClass(evalResult.score)"
                    >
                      {{ evalResult.score }} 分
                    </span>
                  </div>
                  <button
                    v-if="evalResult.cons && evalResult.cons.length > 0"
                    @click="$emit('rewrite-version', getVersionNumber(versionName))"
                    :disabled="rewriting"
                    class="px-3 py-1 text-xs bg-amber-100 text-amber-700 rounded-full hover:bg-amber-200 transition-colors disabled:opacity-50"
                  >
                    重写此版本
                  </button>
                </div>
                <p class="text-xs text-gray-500 mb-3">
                  <span v-if="getModelForVersion(getVersionNumber(versionName))">
                    生成模型: {{ getModelForVersion(getVersionNumber(versionName)) }}
                  </span>
                  <span v-if="getModelForVersion(getVersionNumber(versionName)) && getWordCountForVersion(getVersionNumber(versionName))"> · </span>
                  <span v-if="getWordCountForVersion(getVersionNumber(versionName))">
                    字数: {{ getWordCountForVersion(getVersionNumber(versionName)).toLocaleString() }}
                  </span>
                </p>
                <div class="prose prose-sm max-w-none text-gray-700 space-y-3">
                  <div>
                    <p class="font-semibold text-gray-800">综合评价:</p>
                    <p>{{ evalResult.overall_review }}</p>
                  </div>
                  <div>
                    <p class="font-semibold text-gray-800">优点:</p>
                    <ul class="list-disc pl-5 space-y-1">
                      <li v-for="(pro, i) in evalResult.pros" :key="`pro-${i}`">{{ pro }}</li>
                    </ul>
                  </div>
                  <div>
                    <p class="font-semibold text-gray-800">缺点:</p>
                    <ul class="list-disc pl-5 space-y-1">
                      <li v-for="(con, i) in evalResult.cons" :key="`con-${i}`">
                        <template v-if="typeof con === 'object' && con !== null">
                          <span class="font-medium text-amber-700">[{{ con.location }}]</span> {{ con.issue }}
                          <span v-if="con.suggestion" class="text-gray-500 text-xs block mt-0.5">→ {{ con.suggestion }}</span>
                        </template>
                        <template v-else>{{ con }}</template>
                      </li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div
            v-else
            class="prose prose-sm max-w-none prose-headings:mt-2 prose-headings:mb-1 prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0 text-gray-800"
            v-html="parseMarkdown(evaluation)"
          ></div>
      </div>

      <!-- 弹窗底部操作按钮 -->
      <div class="flex items-center justify-between p-6 border-t border-gray-200 bg-gray-50">
        <div class="flex items-center gap-2">
          <button
              v-if="parsedEvaluation && hasIssues"
              @click="$emit('rewrite')"
              :disabled="rewriting"
              class="px-4 py-2 bg-amber-500 text-white rounded-lg hover:bg-amber-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 text-sm"
          >
              <svg v-if="rewriting" class="w-4 h-4 animate-spin" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
              </svg>
              {{ rewriting ? '重写中...' : '全部重写' }}
          </button>
        </div>
        <button
            @click="$emit('close')"
            class="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
        >
            关闭
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import DOMPurify from 'dompurify'

interface VersionInfo {
  content: string
  provider?: string | null
  model?: string | null
  style?: string | null
}

interface Props {
  show: boolean
  evaluation: string | null
  versions?: VersionInfo[] | null
  rewriting?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  rewriting: false,
  versions: null
})

defineEmits(['close', 'rewrite', 'rewrite-version'])

// 展开的版本内容
const expandedVersions = ref<Set<number>>(new Set())

const toggleContent = (versionIndex: number) => {
  if (expandedVersions.value.has(versionIndex)) {
    expandedVersions.value.delete(versionIndex)
  } else {
    expandedVersions.value.add(versionIndex)
  }
  // 触发响应式更新
  expandedVersions.value = new Set(expandedVersions.value)
}

// 根据版本号获取内容
const getContentForVersion = (versionNumber: number): string | null => {
  if (!props.versions || versionNumber < 1 || versionNumber > props.versions.length) {
    return null
  }
  return props.versions[versionNumber - 1]?.content || null
}

// 从版本名称中提取版本号
const getVersionNumber = (versionName: string | number): number => {
  const str = String(versionName)
  const match = str.match(/\d+/)
  return match ? parseInt(match[0], 10) : 1
}

// 根据版本号获取模型名称
const getModelForVersion = (versionNumber: number): string | null => {
  if (!props.versions || versionNumber < 1 || versionNumber > props.versions.length) {
    return null
  }
  const version = props.versions[versionNumber - 1]
  return version?.model || version?.provider || null
}

// 根据版本号获取字数
const getWordCountForVersion = (versionNumber: number): number => {
  if (!props.versions || versionNumber < 1 || versionNumber > props.versions.length) {
    return 0
  }
  const content = props.versions[versionNumber - 1]?.content || ''
  return content.length
}

// 根据分数返回样式类
const getScoreClass = (score: number): string => {
  if (score >= 90) return 'bg-emerald-100 text-emerald-700'
  if (score >= 80) return 'bg-blue-100 text-blue-700'
  if (score >= 70) return 'bg-yellow-100 text-yellow-700'
  if (score >= 60) return 'bg-orange-100 text-orange-700'
  return 'bg-red-100 text-red-700'
}


const parsedEvaluation = computed(() => {
  if (!props.evaluation) return null
  try {
    // First, try to parse the whole string as JSON
    let data = JSON.parse(props.evaluation);
    // If successful and it's a string, parse it again (for double-encoded JSON)
    if (typeof data === 'string') {
      data = JSON.parse(data);
    }
    return data;
  } catch (error) {
    console.error('Failed to parse evaluation JSON:', error)
    return null
  }
})

// 获取评审模型名称
const evaluationModel = computed(() => {
  if (!parsedEvaluation.value) return null
  return parsedEvaluation.value._evaluation_model || null
})

// 检查是否有缺点需要改进
const hasIssues = computed(() => {
  if (!parsedEvaluation.value) return false

  // 新格式：versions 数组
  if (parsedEvaluation.value.versions && Array.isArray(parsedEvaluation.value.versions)) {
    for (const version of parsedEvaluation.value.versions) {
      if (version.cons && version.cons.length > 0) {
        return true
      }
    }
    return false
  }

  // 旧格式：evaluation 对象
  if (parsedEvaluation.value.evaluation) {
    const evaluations = parsedEvaluation.value.evaluation
    for (const key in evaluations) {
      const evalResult = evaluations[key]
      if (evalResult.cons && evalResult.cons.length > 0) {
        return true
      }
    }
  }
  return false
})

const parseMarkdown = (text: string | null): string => {
  if (!text) return ''
  let parsed = text
    .replace(/\\n/g, '\n')
    .replace(/\\"/g, '"')
    .replace(/\\'/g, "'")
    .replace(/\\\\/g, '\\')
  parsed = parsed.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
  parsed = parsed.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>')
  parsed = parsed.replace(/^([A-Z])\)\s*\*\*(.*?)\*\*(.*)/gm, '<div class="mb-2"><span class="inline-flex items-center justify-center w-6 h-6 bg-indigo-100 text-indigo-600 text-sm font-bold rounded-full mr-2">$1</span><strong>$2</strong>$3</div>')
  parsed = parsed.replace(/\n/g, '<br>')
  parsed = parsed.replace(/(<br\s*\/?>\s*){2,}/g, '</p><p class="mt-2">')
  if (!parsed.includes('<p>')) {
    parsed = `<p>${parsed}</p>`
  }
  return DOMPurify.sanitize(parsed)
}
</script>

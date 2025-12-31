<template>
  <div class="h-screen flex flex-col bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
    <WDHeader
      :project="project"
      :progress="progress"
      :completed-chapters="completedChapters"
      :total-chapters="totalChapters"
      @go-back="goBack"
      @view-project-detail="viewProjectDetail"
      @toggle-sidebar="toggleSidebar"
    />

    <!-- 主要内容区域 -->
    <div class="flex-1 w-full px-4 sm:px-6 lg:px-8 py-6 overflow-hidden">
      <!-- 加载状态 -->
      <div v-if="novelStore.isLoading" class="h-full flex justify-center items-center">
        <div class="text-center">
          <div class="w-12 h-12 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mx-auto mb-4"></div>
          <p class="text-gray-600">正在加载项目数据...</p>
        </div>
      </div>

      <!-- 错误状态 -->
      <div v-else-if="novelStore.error" class="text-center py-20">
        <div class="bg-red-50 border border-red-200 rounded-xl p-8 max-w-md mx-auto">
          <svg class="w-12 h-12 text-red-400 mx-auto mb-4" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path>
          </svg>
          <h3 class="text-lg font-semibold text-red-900 mb-2">加载失败</h3>
          <p class="text-red-700 mb-4">{{ novelStore.error }}</p>
          <button
            @click="loadProject"
            class="px-6 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
          >
            重新加载
          </button>
        </div>
      </div>

      <!-- 主要内容 -->
      <div v-else-if="project" class="h-full flex gap-6">
        <WDSidebar
          :project="project"
          :sidebar-open="sidebarOpen"
          :selected-chapter-number="selectedChapterNumber"
          :generating-chapter="generatingChapter"
          :evaluating-chapter="evaluatingChapter"
          :is-generating-outline="isGeneratingOutline"
          @close-sidebar="closeSidebar"
          @select-chapter="selectChapter"
          @generate-chapter="(n) => openRewriteModal(n)"
          @edit-chapter="openEditChapterModal"
          @delete-chapter="deleteChapter"
          @generate-outline="generateOutline"
          @auto-create="handleAutoCreate"
        />

        <div class="flex-1 min-w-0">
          <WDWorkspace
            :project="project"
            :selected-chapter-number="selectedChapterNumber"
          :generating-chapter="generatingChapter"
          :evaluating-chapter="evaluatingChapter"
          :show-version-selector="showVersionSelector"
          :chapter-generation-result="chapterGenerationResult"
          :selected-version-index="selectedVersionIndex"
          :available-versions="availableVersions"
          :is-selecting-version="isSelectingVersion"
          @regenerate-chapter="() => selectedChapterNumber && openRewriteModal(selectedChapterNumber)"
          @evaluate-chapter="evaluateChapter"
          @hide-version-selector="hideVersionSelector"
          @update:selected-version-index="selectedVersionIndex = $event"
          @show-version-detail="showVersionDetail"
          @confirm-version-selection="confirmVersionSelection"
          @generate-chapter="generateChapter"
          @show-evaluation-detail="showEvaluationDetailModal = true"
          @fetch-chapter-status="fetchChapterStatus"
          @edit-chapter="editChapterContent"
          @show-version-selector="openVersionSelector"
          @cancel-evaluation="cancelEvaluation"
          />
        </div>
      </div>
    </div>
    <WDVersionDetailModal
      :show="showVersionDetailModal"
      :detail-version-index="detailVersionIndex"
      :version="availableVersions[detailVersionIndex] || null"
      :is-current="isCurrentVersion(detailVersionIndex)"
      @close="closeVersionDetail"
      @select-version="selectVersionFromDetail"
    />
    <WDEvaluationDetailModal
      :show="showEvaluationDetailModal"
      :evaluation="selectedChapter?.evaluation || null"
      :versions="selectedChapter?.versions || null"
      :rewriting="isRewriting"
      @close="showEvaluationDetailModal = false"
      @rewrite="handleRewriteFromFeedback"
      @rewrite-version="handleRewriteVersion"
    />
    <WDEditChapterModal
      :show="showEditChapterModal"
      :chapter="editingChapter"
      @close="showEditChapterModal = false"
      @save="saveChapterChanges"
    />
    <WDGenerateOutlineModal
      :show="showGenerateOutlineModal"
      @close="showGenerateOutlineModal = false"
      @generate="handleGenerateOutline"
    />
    <WDRewriteOptionModal
      v-model:visible="showRewriteModal"
      :chapter-number="rewriteTargetChapter || 0"
      :default-notes="rewriteDefaultNotes"
      @confirm="handleUnifiedRewrite"
    />
    <!-- 连续创作进度展示 -->
    <div
      v-if="isAutoCreating || autoCreateProgress.message"
      class="fixed bottom-6 right-6 z-50 w-80 max-w-[90vw] rounded-xl border border-indigo-100 bg-white/95 shadow-lg backdrop-blur px-4 py-3"
    >
      <div class="flex items-center justify-between">
        <div class="text-sm font-medium text-gray-700">连续创作</div>
        <!-- 停止按钮（创作中显示） -->
        <button
          v-if="isAutoCreating"
          @click="handleStopAutoCreate"
          class="px-3 py-1 text-xs font-medium bg-red-500 text-white rounded hover:bg-red-600 transition-colors"
        >
          停止
        </button>
        <!-- 关闭按钮（完成后显示） -->
        <button
          v-else
          @click="autoCreateProgress.message = ''"
          class="text-gray-400 hover:text-gray-600"
        >
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
          </svg>
        </button>
      </div>
      <div class="mt-1 text-sm text-gray-600">{{ autoCreateProgress.message || '连续创作处理中...' }}</div>
      <div v-if="autoCreateProgress.totalChapters" class="mt-2">
        <div class="flex justify-between text-xs text-gray-500 mb-1">
          <span>进度</span>
          <span>{{ autoCreateProgress.completedChapters }} / {{ autoCreateProgress.totalChapters }}</span>
        </div>
        <div class="w-full bg-gray-200 rounded-full h-1.5">
          <div
            class="bg-indigo-600 h-1.5 rounded-full transition-all duration-300"
            :style="{ width: `${(autoCreateProgress.completedChapters / autoCreateProgress.totalChapters) * 100}%` }"
          ></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useNovelStore } from '@/stores/novel'
import { NovelAPI } from '@/api/novel'
import type { Chapter, ChapterOutline, ChapterGenerationResponse, ChapterVersion } from '@/api/novel'
import { globalAlert } from '@/composables/useAlert'
import Tooltip from '@/components/Tooltip.vue'
import WDHeader from '@/components/writing-desk/WDHeader.vue'
import WDSidebar from '@/components/writing-desk/WDSidebar.vue'
import WDWorkspace from '@/components/writing-desk/WDWorkspace.vue'
import WDVersionDetailModal from '@/components/writing-desk/WDVersionDetailModal.vue'
import WDEvaluationDetailModal from '@/components/writing-desk/WDEvaluationDetailModal.vue'
import WDEditChapterModal from '@/components/writing-desk/WDEditChapterModal.vue'
import WDGenerateOutlineModal from '@/components/writing-desk/WDGenerateOutlineModal.vue'
import WDRewriteOptionModal from '@/components/writing-desk/WDRewriteOptionModal.vue'

interface Props {
  id: string
}

const props = defineProps<Props>()
const router = useRouter()
const novelStore = useNovelStore()

// 状态管理
const selectedChapterNumber = ref<number | null>(null)
const chapterGenerationResult = ref<ChapterGenerationResponse | null>(null)
const selectedVersionIndex = ref<number>(0)
const generatingChapter = ref<number | null>(null)
const sidebarOpen = ref(false)
const showVersionDetailModal = ref(false)
const detailVersionIndex = ref<number>(0)
const showEvaluationDetailModal = ref(false)
const isRewriting = ref(false)
const showEditChapterModal = ref(false)
const editingChapter = ref<ChapterOutline | null>(null)
const isGeneratingOutline = ref(false)
const showGenerateOutlineModal = ref(false)
const manualShowVersionSelector = ref(false)

// 重写模态框状态
const showRewriteModal = ref(false)
const rewriteTargetChapter = ref<number | null>(null)
const rewriteDefaultNotes = ref('')
const rewriteTargetProvider = ref<string | undefined>(undefined)

// 连续创作状态
const isAutoCreating = ref(false)
const autoCreateProgress = ref({
  message: '',
  chapter: null as number | null,
  totalChapters: 0,
  completedChapters: 0
})

// 计算属性
const project = computed(() => novelStore.currentProject)

const selectedChapter = computed(() => {
  if (!project.value || selectedChapterNumber.value === null) return null
  return project.value.chapters.find(ch => ch.chapter_number === selectedChapterNumber.value) || null
})

const showVersionSelector = computed(() => {
  if (manualShowVersionSelector.value) return true
  if (!selectedChapter.value) return false
  const status = selectedChapter.value.generation_status
  return status === 'waiting_for_confirm' || status === 'evaluating' || status === 'evaluation_failed' || status === 'selecting'
})

const evaluatingChapter = computed(() => {
  if (selectedChapter.value?.generation_status === 'evaluating') {
    return selectedChapter.value.chapter_number
  }
  return null
})

const isSelectingVersion = computed(() => {
  return selectedChapter.value?.generation_status === 'selecting'
})

const selectedChapterOutline = computed(() => {
  if (!project.value?.blueprint?.chapter_outline || selectedChapterNumber.value === null) return null
  return project.value.blueprint.chapter_outline.find(ch => ch.chapter_number === selectedChapterNumber.value) || null
})

const progress = computed(() => {
  if (!project.value?.blueprint?.chapter_outline) return 0
  const totalChapters = project.value.blueprint.chapter_outline.length
  const completedChapters = project.value.chapters.filter(ch => ch.content).length
  return Math.round((completedChapters / totalChapters) * 100)
})

const totalChapters = computed(() => {
  return project.value?.blueprint?.chapter_outline?.length || 0
})

const completedChapters = computed(() => {
  return project.value?.chapters?.filter(ch => ch.content)?.length || 0
})

const isCurrentVersion = (versionIndex: number) => {
  if (!selectedChapter.value?.content || !availableVersions.value?.[versionIndex]?.content) return false

  // 使用cleanVersionContent函数清理内容进行比较
  const cleanCurrentContent = cleanVersionContent(selectedChapter.value.content)
  const cleanVersionContentStr = cleanVersionContent(availableVersions.value[versionIndex].content)

  return cleanCurrentContent === cleanVersionContentStr
}

const cleanVersionContent = (content: string): string => {
  if (!content) return ''

  // 尝试解析JSON，看是否是完整的章节对象
  try {
    const parsed = JSON.parse(content)
    if (parsed && typeof parsed === 'object' && parsed.content) {
      // 如果是章节对象，提取content字段
      content = parsed.content
    }
  } catch (error) {
    // 如果不是JSON，继续处理字符串
  }

  // 去掉开头和结尾的引号
  let cleaned = content.replace(/^"|"$/g, '')

  // 处理转义字符
  cleaned = cleaned.replace(/\\n/g, '\n')  // 换行符
  cleaned = cleaned.replace(/\\"/g, '"')   // 引号
  cleaned = cleaned.replace(/\\t/g, '\t')  // 制表符
  cleaned = cleaned.replace(/\\\\/g, '\\') // 反斜杠

  return cleaned
}

const canGenerateChapter = (chapterNumber: number) => {
  if (!project.value?.blueprint?.chapter_outline) return false

  // 检查前面所有章节是否都已成功生成
  const outlines = project.value.blueprint.chapter_outline.sort((a, b) => a.chapter_number - b.chapter_number)
  
  for (const outline of outlines) {
    if (outline.chapter_number >= chapterNumber) break
    
    const chapter = project.value?.chapters.find(ch => ch.chapter_number === outline.chapter_number)
    if (!chapter || chapter.generation_status !== 'successful') {
      return false // 前面有章节未完成
    }
  }

  // 检查当前章节是否已经完成
  const currentChapter = project.value?.chapters.find(ch => ch.chapter_number === chapterNumber)
  if (currentChapter && currentChapter.generation_status === 'successful') {
    return true // 已完成的章节可以重新生成
  }

  return true // 前面章节都完成了，可以生成当前章节
}

const isChapterFailed = (chapterNumber: number) => {
  if (!project.value?.chapters) return false
  const chapter = project.value.chapters.find(ch => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'failed'
}

const hasChapterInProgress = (chapterNumber: number) => {
  if (!project.value?.chapters) return false
  const chapter = project.value.chapters.find(ch => ch.chapter_number === chapterNumber)
  // waiting_for_confirm状态表示等待选择版本 = 进行中状态
  return chapter && chapter.generation_status === 'waiting_for_confirm'
}

// 可用版本列表 (合并生成结果和已有版本)
const availableVersions = computed(() => {
  // 优先使用新生成的版本（对象数组格式）
  if (chapterGenerationResult.value?.versions) {
    return chapterGenerationResult.value.versions
  }

  // 使用章节已有的版本
  if (selectedChapter.value?.versions && Array.isArray(selectedChapter.value.versions)) {
    const convertedVersions = selectedChapter.value.versions.map((version: any) => {
      // 后端现在返回 {content, provider} 对象格式
      if (typeof version === 'object' && version !== null) {
        return {
          content: version.content || '',
          provider: version.provider || undefined,
          style: '标准'
        }
      }
      // 兼容旧格式：字符串（可能是JSON字符串）
      if (typeof version === 'string') {
        try {
          const versionObj = JSON.parse(version)
          return {
            content: versionObj.content || version,
            provider: versionObj.provider || undefined,
            style: '标准'
          }
        } catch {
          return {
            content: version,
            style: '标准'
          }
        }
      }
      return { content: '', style: '标准' }
    })
    return convertedVersions
  }

  return []
})


// 方法
const goBack = () => {
  router.push('/workspace')
}

const viewProjectDetail = () => {
  if (project.value) {
    router.push(`/detail/${project.value.id}`)
  }
}

const toggleSidebar = () => {
  sidebarOpen.value = !sidebarOpen.value
}

const closeSidebar = () => {
  sidebarOpen.value = false
}

const loadProject = async () => {
  try {
    await novelStore.loadProject(props.id)
  } catch (error) {
    console.error('加载项目失败:', error)
  }
}

const fetchChapterStatus = async () => {
  if (selectedChapterNumber.value === null) {
    return
  }
  try {
    await novelStore.loadChapter(selectedChapterNumber.value)
  } catch (error) {
    // 轮询章节状态失败，静默处理
  }
}


// 显示版本详情
const showVersionDetail = (versionIndex: number) => {
  detailVersionIndex.value = versionIndex
  showVersionDetailModal.value = true
}

// 关闭版本详情弹窗
const closeVersionDetail = () => {
  showVersionDetailModal.value = false
}

// 隐藏版本选择器，返回内容视图
const hideVersionSelector = () => {
  manualShowVersionSelector.value = false
  chapterGenerationResult.value = null
  selectedVersionIndex.value = 0
}

// 手动打开版本选择器
const openVersionSelector = () => {
  manualShowVersionSelector.value = true
}

const selectChapter = (chapterNumber: number) => {
  selectedChapterNumber.value = chapterNumber
  chapterGenerationResult.value = null
  selectedVersionIndex.value = 0
  manualShowVersionSelector.value = false
  closeSidebar()
}

const generateChapter = async (chapterNumber: number, writingNotes?: string) => {
  // 检查前面章节是否都已完成（前置条件必须满足）
  if (!canGenerateChapter(chapterNumber)) {
    // 找出第一个未完成的章节
    const outlines = project.value?.blueprint?.chapter_outline?.sort((a, b) => a.chapter_number - b.chapter_number) || []
    let blockedBy = 0
    for (const outline of outlines) {
      if (outline.chapter_number >= chapterNumber) break
      const ch = project.value?.chapters.find(c => c.chapter_number === outline.chapter_number)
      if (!ch || ch.generation_status !== 'successful') {
        blockedBy = outline.chapter_number
        break
      }
    }
    globalAlert.showError(`请先完成第 ${blockedBy} 章`, '生成受限')
    return
  }

  try {
    generatingChapter.value = chapterNumber
    selectedChapterNumber.value = chapterNumber

    // 在本地更新章节状态为generating
    if (project.value?.chapters) {
      const chapter = project.value.chapters.find(ch => ch.chapter_number === chapterNumber)
      if (chapter) {
        chapter.generation_status = 'generating'
      } else {
        // If chapter does not exist, create a temporary one to show generating state
        const outline = project.value.blueprint?.chapter_outline?.find(o => o.chapter_number === chapterNumber)
        project.value.chapters.push({
          chapter_number: chapterNumber,
          title: outline?.title || '加载中...',
          summary: outline?.summary || '',
          content: '',
          versions: [],
          evaluation: null,
          generation_status: 'generating'
        } as Chapter)
      }
    }

    await novelStore.generateChapter(chapterNumber, writingNotes)

    // 强制刷新项目数据，确保 UI 更新
    await novelStore.loadProject(props.id, true)

    chapterGenerationResult.value = null
    selectedVersionIndex.value = 0
  } catch (error) {
    console.error('生成章节失败:', error)

    // 错误状态的本地更新仍然是必要的，以立即反映UI
    if (project.value?.chapters) {
      const chapter = project.value.chapters.find(ch => ch.chapter_number === chapterNumber)
      if (chapter) {
        chapter.generation_status = 'failed'
      }
    }

    globalAlert.showError(`生成章节失败: ${error instanceof Error ? error.message : '未知错误'}`, '生成失败')
  } finally {
    generatingChapter.value = null
  }
}

const regenerateChapter = async () => {
  if (selectedChapterNumber.value !== null) {
    await generateChapter(selectedChapterNumber.value)
  }
}

const selectVersion = async (versionIndex: number) => {
  if (selectedChapterNumber.value === null || !availableVersions.value?.[versionIndex]?.content) {
    return
  }

  try {
    // 在本地立即更新状态以反映UI
    if (project.value?.chapters) {
      const chapter = project.value.chapters.find(ch => ch.chapter_number === selectedChapterNumber.value)
      if (chapter) {
        chapter.generation_status = 'selecting'
      }
    }

    selectedVersionIndex.value = versionIndex
    await novelStore.selectChapterVersion(selectedChapterNumber.value, versionIndex)

    // 状态更新将由 store 自动触发，本地无需手动更新
    // 轮询机制会处理状态变更，成功后会自动隐藏选择器
    // showVersionSelector.value = false
    chapterGenerationResult.value = null
    globalAlert.showSuccess('版本已确认', '操作成功')
  } catch (error) {
    console.error('选择章节版本失败:', error)
    // 错误状态下恢复章节状态
    if (project.value?.chapters) {
      const chapter = project.value.chapters.find(ch => ch.chapter_number === selectedChapterNumber.value)
      if (chapter) {
        chapter.generation_status = 'waiting_for_confirm' // Or the previous state
      }
    }
    globalAlert.showError(`选择章节版本失败: ${error instanceof Error ? error.message : '未知错误'}`, '选择失败')
  }
}

// 从详情弹窗中选择版本
const selectVersionFromDetail = async () => {
  selectedVersionIndex.value = detailVersionIndex.value
  await selectVersion(detailVersionIndex.value)
  closeVersionDetail()
}

const confirmVersionSelection = async () => {
  await selectVersion(selectedVersionIndex.value)
}

const openEditChapterModal = (chapter: ChapterOutline) => {
  editingChapter.value = chapter
  showEditChapterModal.value = true
}

const saveChapterChanges = async (updatedChapter: ChapterOutline) => {
  try {
    await novelStore.updateChapterOutline(updatedChapter)
    globalAlert.showSuccess('章节大纲已更新', '保存成功')
  } catch (error) {
    console.error('更新章节大纲失败:', error)
    globalAlert.showError(`更新章节大纲失败: ${error instanceof Error ? error.message : '未知错误'}`, '保存失败')
  } finally {
    showEditChapterModal.value = false
  }
}

const evaluateChapter = async () => {
  if (selectedChapterNumber.value !== null) {
    try {
      // 在本地更新章节状态为evaluating以立即反映在UI上
      if (project.value?.chapters) {
        const chapter = project.value.chapters.find(ch => ch.chapter_number === selectedChapterNumber.value)
        if (chapter) {
          chapter.generation_status = 'evaluating'
        }
      }

      // 显示评审进度提示
      globalAlert.showInfo('AI正在评审章节内容，请稍候...', '评审中')

      await novelStore.evaluateChapter(selectedChapterNumber.value)

      // 评审完成后自动打开评审详情弹窗
      showEvaluationDetailModal.value = true
      globalAlert.showSuccess('章节评审结果已生成，请查看详情', '评审成功')
    } catch (error) {
      console.error('评审章节失败:', error)

      // 错误状态下恢复章节状态
      if (project.value?.chapters) {
        const chapter = project.value.chapters.find(ch => ch.chapter_number === selectedChapterNumber.value)
        if (chapter) {
          chapter.generation_status = 'successful' // 恢复为成功状态
        }
      }

      globalAlert.showError(`评审章节失败: ${error instanceof Error ? error.message : '未知错误'}`, '评审失败')
    }
  }
}

const cancelEvaluation = async () => {
  if (selectedChapterNumber.value !== null) {
    try {
      await novelStore.cancelEvaluation(selectedChapterNumber.value)
      globalAlert.showSuccess('已取消评审', '操作成功')
    } catch (error) {
      console.error('取消评审失败:', error)
      globalAlert.showError(`取消评审失败: ${error instanceof Error ? error.message : '未知错误'}`)
    }
  }
}

const openRewriteModal = (chapterNumber: number, notes: string = '', provider?: string) => {
  rewriteTargetChapter.value = chapterNumber
  rewriteDefaultNotes.value = notes
  rewriteTargetProvider.value = provider
  showRewriteModal.value = true
}

const handleUnifiedRewrite = async (options: { mode: 'normal' | 'smart', writingNotes: string, scoreThreshold: number, maxAttempts: number }) => {
  if (rewriteTargetChapter.value === null) return

  const chapterNumber = rewriteTargetChapter.value

  if (options.mode === 'normal') {
    await generateChapter(chapterNumber, options.writingNotes || undefined)
    return
  }

  // Smart Mode (Review Loop)
  isRewriting.value = true
  try {
    // Ensure sidebar closes if open
    closeSidebar()
    
    // Update local status
    novelStore.updateChapterStatus(chapterNumber, 'generating')

    globalAlert.showInfo('正在进行智能重写...', '重写中')

    const result = await NovelAPI.generateWithReview(
      props.id,
      chapterNumber,
      {
        writing_notes: options.writingNotes,
        score_threshold: options.scoreThreshold,
        max_attempts: options.maxAttempts,
        auto_select_best: true,
        rewrite_provider: rewriteTargetProvider.value
      }
    )

    await novelStore.loadProject(props.id, true)

    if (result.success) {
      globalAlert.showSuccess(
        `重写完成！最终评分: ${result.final_score || '-'}，尝试次数: ${result.attempts_used}`,
        '重写成功'
      )
    } else {
      globalAlert.showWarning(
        `重写完成但未达到目标分数。最终评分: ${result.final_score || '-'}`,
        '重写完成'
      )
    }
  } catch (error) {
    console.error('智能重写失败:', error)
    globalAlert.showError(`重写失败: ${error instanceof Error ? error.message : '未知错误'}`, '重写失败')
    
    // Restore status
    novelStore.updateChapterStatus(chapterNumber, 'successful')
  } finally {
    isRewriting.value = false
  }
}

// 根据评审反馈重写章节 (仅打开弹窗)
const handleRewriteFromFeedback = () => {
  if (selectedChapterNumber.value === null) return

  // 关闭评审弹窗
  showEvaluationDetailModal.value = false
  
  // 提取缺点作为建议
  let notes = ''
  const chapter = selectedChapter.value
  if (chapter?.evaluation) {
     try {
        const evalData = JSON.parse(chapter.evaluation)
        // 简单提取所有缺点
        const allCons: string[] = []
        if (evalData.versions && Array.isArray(evalData.versions)) {
           evalData.versions.forEach((v: any) => {
              if (v.cons) v.cons.forEach((c: any) => allCons.push(typeof c === 'string' ? c : c.issue))
           })
        }
        if (allCons.length > 0) {
           notes = `请解决以下问题：\n- ${allCons.slice(0, 5).join('\n- ')}`
        }
     } catch (e) {}
  }

  openRewriteModal(selectedChapterNumber.value, notes)
}

// 根据特定版本的反馈重写 (仅打开弹窗)
const handleRewriteVersion = (versionNumber: number) => {
  if (selectedChapterNumber.value === null) return

  // 从评审结果中提取该版本的缺点
  const chapter = selectedChapter.value
  if (!chapter?.evaluation) return

  let writingNotes = ''
  let provider: string | undefined = undefined

  // 获取该版本的 provider
  const versions = availableVersions.value
  if (versions && versions.length >= versionNumber) {
    provider = versions[versionNumber - 1]?.provider
  }

  try {
    const evalData = JSON.parse(chapter.evaluation)

    // 使用新格式 versions[]
    if (evalData.versions && Array.isArray(evalData.versions)) {
      const versionData = evalData.versions.find(
        (v: { version_index: number }) => v.version_index === versionNumber
      )
      if (versionData?.cons && versionData.cons.length > 0) {
        const formattedCons = versionData.cons.map((con: { location?: string; issue?: string; suggestion?: string }) => {
          const parts = []
          if (con.location) parts.push(`位置：${con.location}`)
          if (con.issue) parts.push(`问题：${con.issue}`)
          if (con.suggestion) parts.push(`建议：${con.suggestion}`)
          return parts.length > 0 ? `- ${parts.join(' | ')}` : null
        }).filter(Boolean)
        if (formattedCons.length > 0) {
          writingNotes = `请避免以下问题：\n${formattedCons.join('\n')}`
        }
      }
    }
  } catch (e) {
    console.error('解析评审结果失败:', e)
  }

  showEvaluationDetailModal.value = false
  openRewriteModal(selectedChapterNumber.value, writingNotes, provider)
}

const deleteChapter = async (chapterNumbers: number | number[]) => {
  const numbersToDelete = Array.isArray(chapterNumbers) ? chapterNumbers : [chapterNumbers]
  const confirmationMessage = numbersToDelete.length > 1
    ? `您确定要删除选中的 ${numbersToDelete.length} 个章节吗？这个操作无法撤销。`
    : `您确定要删除第 ${numbersToDelete[0]} 章吗？这个操作无法撤销。`

  const confirmed = await globalAlert.showConfirm(confirmationMessage, '删除确认')
  if (confirmed) {
    try {
      await novelStore.deleteChapter(numbersToDelete)
      globalAlert.showSuccess('章节已删除', '操作成功')
      // If the currently selected chapter was deleted, unselect it
      if (selectedChapterNumber.value && numbersToDelete.includes(selectedChapterNumber.value)) {
        selectedChapterNumber.value = null
      }
    } catch (error) {
      console.error('删除章节失败:', error)
      globalAlert.showError(`删除章节失败: ${error instanceof Error ? error.message : '未知错误'}`, '删除失败')
    }
  }
}

const generateOutline = async () => {
  showGenerateOutlineModal.value = true
}

const editChapterContent = async (data: { chapterNumber: number, content: string }) => {
  if (!project.value) return

  try {
    await novelStore.editChapterContent(project.value.id, data.chapterNumber, data.content)
    globalAlert.showSuccess('章节内容已更新', '保存成功')
  } catch (error) {
    console.error('编辑章节内容失败:', error)
    globalAlert.showError(`编辑章节内容失败: ${error instanceof Error ? error.message : '未知错误'}`, '保存失败')
  }
}

const handleGenerateOutline = async (numChapters: number) => {
  if (!project.value) return
  isGeneratingOutline.value = true
  try {
    const startChapter = (project.value.blueprint?.chapter_outline?.length || 0) + 1
    await novelStore.generateChapterOutline(startChapter, numChapters)
    globalAlert.showSuccess('新的章节大纲已生成', '操作成功')
  } catch (error) {
    console.error('生成大纲失败:', error)
    globalAlert.showError(`生成大纲失败: ${error instanceof Error ? error.message : '未知错误'}`, '生成失败')
  } finally {
    isGeneratingOutline.value = false
  }
}

// 停止连续创作
const handleStopAutoCreate = async () => {
  if (!project.value || !isAutoCreating.value) return

  try {
    autoCreateProgress.value.message = '正在停止...'
    await NovelAPI.stopAutoCreate(project.value.id)
    // SSE 会收到 "stopped" 事件，自动处理状态更新
  } catch (error) {
    const message = error instanceof Error ? error.message : '停止失败'
    globalAlert.showError(message, '停止连续创作失败')
  }
}

// 连续创作处理函数
const handleAutoCreate = async () => {
  if (!project.value || isAutoCreating.value) return

  isAutoCreating.value = true
  autoCreateProgress.value = {
    message: '准备开始连续创作...',
    chapter: null,
    totalChapters: 0,
    completedChapters: 0
  }

  try {
    const response = await NovelAPI.autoCreateChapters(project.value.id)
    if (!response.body) {
      throw new Error('未收到响应流')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // 解析 SSE 事件
      let boundaryIndex = buffer.indexOf('\n\n')
      while (boundaryIndex !== -1) {
        const rawEvent = buffer.slice(0, boundaryIndex)
        buffer = buffer.slice(boundaryIndex + 2)

        const lines = rawEvent.split('\n')
        let eventType = 'message'
        const dataLines: string[] = []

        for (const line of lines) {
          if (line.startsWith('event:')) {
            eventType = line.slice(6).trim()
          } else if (line.startsWith('data:')) {
            dataLines.push(line.slice(5).trim())
          }
        }

        if (dataLines.length > 0) {
          const dataText = dataLines.join('\n')
          let payload: any = dataText
          try {
            payload = JSON.parse(dataText)
          } catch {
            // 保持字符串
          }

          // 处理不同类型的事件
          switch (eventType) {
            case 'start':
              autoCreateProgress.value = {
                ...autoCreateProgress.value,
                totalChapters: payload.total_chapters ?? 0,
                message: `开始连续创作：第${payload.start_chapter}章 - 第${payload.end_chapter}章`
              }
              break
            case 'progress':
              autoCreateProgress.value = {
                ...autoCreateProgress.value,
                chapter: payload.chapter ?? null,
                message: payload.message || '连续创作处理中...'
              }
              // 同步章节状态到页面
              if (payload && typeof payload === 'object') {
                const chapterNumber = typeof payload.chapter === 'number' ? payload.chapter : Number(payload.chapter)
                const statusMap: Record<string, 'generating' | 'evaluating' | 'selecting' | 'ingesting'> = {
                  generating: 'generating',
                  evaluating: 'evaluating',
                  selecting: 'selecting',
                  ingesting: 'ingesting'
                }
                const status = statusMap[payload.stage]
                if (Number.isFinite(chapterNumber) && chapterNumber > 0 && status) {
                  novelStore.updateChapterStatus(chapterNumber, status)
                }
              }
              break
            case 'chapter_done':
              autoCreateProgress.value = {
                ...autoCreateProgress.value,
                chapter: payload.chapter ?? null,
                completedChapters: autoCreateProgress.value.completedChapters + 1,
                message: `第${payload.chapter}章完成 (评分: ${payload.score ?? '-'})`
              }
              // 增量更新章节数据
              novelStore.updateChapterData(Number(payload.chapter), payload.chapter_data)
              break
            case 'chapter_error':
              autoCreateProgress.value = {
                ...autoCreateProgress.value,
                chapter: payload.chapter ?? null,
                message: `第${payload.chapter}章失败：${payload.message || '未知错误'}`
              }
              break
            case 'complete':
              autoCreateProgress.value = {
                ...autoCreateProgress.value,
                completedChapters: payload.chapters_created ?? autoCreateProgress.value.completedChapters,
                message: payload.message || '连续创作完成'
              }
              await novelStore.loadProject(props.id, true)
              globalAlert.showSuccess(autoCreateProgress.value.message, '连续创作完成')
              break
            case 'error':
              autoCreateProgress.value = {
                ...autoCreateProgress.value,
                message: payload.message || '连续创作流程异常中断'
              }
              globalAlert.showError(autoCreateProgress.value.message, '连续创作异常')
              break
            case 'stopped':
              autoCreateProgress.value = {
                ...autoCreateProgress.value,
                completedChapters: payload.chapters_created ?? autoCreateProgress.value.completedChapters,
                message: payload.message || '已停止连续创作'
              }
              await novelStore.loadProject(props.id, true)
              globalAlert.showInfo(autoCreateProgress.value.message, '连续创作已停止')
              break
          }
        }

        boundaryIndex = buffer.indexOf('\n\n')
      }
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : '连续创作失败'
    autoCreateProgress.value = {
      ...autoCreateProgress.value,
      message
    }
    globalAlert.showError(message, '连续创作失败')
  } finally {
    isAutoCreating.value = false
  }
}

onMounted(() => {
  loadProject()
})
</script>

<style scoped>
/* 自定义样式 */
.line-clamp-1 {
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 自定义滚动条 */
::-webkit-scrollbar {
  width: 6px;
}

::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: #a1a1a1;
}

/* 动画效果 */
.fade-in {
  animation: fadeIn 0.6s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>

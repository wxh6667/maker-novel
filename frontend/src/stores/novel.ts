import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { NovelProject, NovelProjectSummary, ConverseResponse, BlueprintGenerationResponse, Blueprint, DeleteNovelsResponse, ChapterOutline, Chapter } from '@/api/novel'
import { NovelAPI } from '@/api/novel'

export const useNovelStore = defineStore('novel', () => {
  // State
  const projects = ref<NovelProjectSummary[]>([])
  const currentProject = ref<NovelProject | null>(null)
  const currentConversationState = ref<any>({})
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const projectsCount = computed(() => projects.value.length)
  const hasCurrentProject = computed(() => currentProject.value !== null)

  // Actions
  async function loadProjects() {
    isLoading.value = true
    error.value = null
    try {
      projects.value = await NovelAPI.getAllNovels()
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载项目失败'
    } finally {
      isLoading.value = false
    }
  }

  async function createProject(title: string, initialPrompt: string) {
    isLoading.value = true
    error.value = null
    try {
      const project = await NovelAPI.createNovel(title, initialPrompt)
      currentProject.value = project
      currentConversationState.value = {}
      return project
    } catch (err) {
      error.value = err instanceof Error ? err.message : '创建项目失败'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function loadProject(projectId: string, silent: boolean = false) {
    if (!silent) {
      isLoading.value = true
    }
    error.value = null
    try {
      currentProject.value = await NovelAPI.getNovel(projectId)
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载项目失败'
    } finally {
      if (!silent) {
        isLoading.value = false
      }
    }
  }

  async function loadChapter(chapterNumber: number) {
    error.value = null
    try {
      if (!currentProject.value) {
        throw new Error('没有当前项目')
      }
      const chapter = await NovelAPI.getChapter(currentProject.value.id, chapterNumber)
      const project = currentProject.value
      if (!Array.isArray(project.chapters)) {
        project.chapters = []
      }
      const index = project.chapters.findIndex(ch => ch.chapter_number === chapterNumber)
      if (index >= 0) {
        project.chapters.splice(index, 1, chapter)
      } else {
        project.chapters.push(chapter)
      }
      project.chapters.sort((a, b) => a.chapter_number - b.chapter_number)
      return chapter
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载章节失败'
      throw err
    }
  }

  // 局部更新章节状态（用于连续创作进度同步）
  function updateChapterStatus(chapterNumber: number, status: Chapter['generation_status']) {
    if (!currentProject.value) return
    const project = currentProject.value
    if (!Array.isArray(project.chapters)) {
      project.chapters = []
    }
    const chapter = project.chapters.find(ch => ch.chapter_number === chapterNumber)
    if (chapter) {
      chapter.generation_status = status
      return
    }
    // 章节不存在时，创建占位章节
    const outline = project.blueprint?.chapter_outline?.find(ch => ch.chapter_number === chapterNumber)
    project.chapters.push({
      chapter_number: chapterNumber,
      title: outline?.title || `第${chapterNumber}章`,
      summary: outline?.summary || '',
      content: null,
      versions: null,
      evaluation: null,
      generation_status: status
    } as Chapter)
    project.chapters.sort((a, b) => a.chapter_number - b.chapter_number)
  }

  // 增量更新章节数据（用于 SSE 事件）
  function updateChapterData(chapterNumber: number, data: any) {
    if (!currentProject.value) return
    const project = currentProject.value
    if (!Array.isArray(project.chapters)) {
      project.chapters = []
    }
    const chapter = project.chapters.find(ch => ch.chapter_number === chapterNumber)
    
    if (chapter) {
      Object.assign(chapter, data)
      // 兼容后端字段名不一致的情况
      if (data.status) chapter.generation_status = data.status
      if (data.real_summary) chapter.summary = data.real_summary
    } else if (data.title || data.content) {
      // 如果章节不存在且包含关键数据，则作为新章节添加
      // 确保generation_status存在
      if (data.status && !data.generation_status) data.generation_status = data.status
      if (data.real_summary && !data.summary) data.summary = data.real_summary
      project.chapters.push(data)
      project.chapters.sort((a, b) => a.chapter_number - b.chapter_number)
    }
  }

  async function sendConversation(userInput: any): Promise<ConverseResponse> {
    isLoading.value = true
    error.value = null
    try {
      if (!currentProject.value) {
        throw new Error('没有当前项目')
      }
      const response = await NovelAPI.converseConcept(
        currentProject.value.id,
        userInput,
        currentConversationState.value
      )
      currentConversationState.value = response.conversation_state
      return response
    } catch (err) {
      error.value = err instanceof Error ? err.message : '对话失败'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function generateBlueprint(): Promise<BlueprintGenerationResponse> {
    // Generate blueprint from conversation history
    isLoading.value = true
    error.value = null
    try {
      if (!currentProject.value) {
        throw new Error('没有当前项目')
      }
      return await NovelAPI.generateBlueprint(currentProject.value.id)
    } catch (err) {
      error.value = err instanceof Error ? err.message : '生成蓝图失败'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function saveBlueprint(blueprint: Blueprint) {
    isLoading.value = true
    error.value = null
    try {
      if (!currentProject.value) {
        throw new Error('没有当前项目')
      }
      if (!blueprint) {
        throw new Error('缺少蓝图数据')
      }
      currentProject.value = await NovelAPI.saveBlueprint(currentProject.value.id, blueprint)
    } catch (err) {
      error.value = err instanceof Error ? err.message : '保存蓝图失败'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function generateChapter(chapterNumber: number, writingNotes?: string): Promise<NovelProject> {
    // 注意：这里不设置全局 isLoading，因为 WritingDesk.vue 有自己的局部加载状态
    error.value = null
    try {
      if (!currentProject.value) {
        throw new Error('没有当前项目')
      }
      const updatedProject = await NovelAPI.generateChapter(currentProject.value.id, chapterNumber, writingNotes)
      currentProject.value = updatedProject // 更新 store 中的当前项目
      return updatedProject
    } catch (err) {
      error.value = err instanceof Error ? err.message : '生成章节失败'
      throw err
    }
  }

  async function evaluateChapter(chapterNumber: number): Promise<NovelProject> {
    error.value = null
    try {
      if (!currentProject.value) {
        throw new Error('没有当前项目')
      }
      const updatedProject = await NovelAPI.evaluateChapter(currentProject.value.id, chapterNumber)
      currentProject.value = updatedProject
      return updatedProject
    } catch (err) {
      error.value = err instanceof Error ? err.message : '评估章节失败'
      throw err
    }
  }

  async function cancelEvaluation(chapterNumber: number): Promise<NovelProject> {
    error.value = null
    try {
      if (!currentProject.value) {
        throw new Error('没有当前项目')
      }
      const updatedProject = await NovelAPI.cancelEvaluation(currentProject.value.id, chapterNumber)
      currentProject.value = updatedProject
      return updatedProject
    } catch (err) {
      error.value = err instanceof Error ? err.message : '取消评审失败'
      throw err
    }
  }

  async function selectChapterVersion(chapterNumber: number, versionIndex: number) {
    // 不设置全局 isLoading，让调用方处理局部加载状态
    error.value = null
    try {
      if (!currentProject.value) {
        throw new Error('没有当前项目')
      }
      const updatedProject = await NovelAPI.selectChapterVersion(
        currentProject.value.id,
        chapterNumber,
        versionIndex
      )
      currentProject.value = updatedProject // 更新 store
    } catch (err) {
      error.value = err instanceof Error ? err.message : '选择章节版本失败'
      throw err
    }
  }

  async function deleteProjects(projectIds: string[]): Promise<DeleteNovelsResponse> {
    isLoading.value = true
    error.value = null
    try {
      const response = await NovelAPI.deleteNovels(projectIds)
      
      // 从本地项目列表中移除已删除的项目
      projects.value = projects.value.filter(project => !projectIds.includes(project.id))
      
      // 如果当前项目被删除，清空当前项目
      if (currentProject.value && projectIds.includes(currentProject.value.id)) {
        currentProject.value = null
        currentConversationState.value = {}
      }
      
      return response
    } catch (err) {
      error.value = err instanceof Error ? err.message : '删除项目失败'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function updateChapterOutline(chapterOutline: ChapterOutline) {
    // 不设置全局 isLoading，让调用方处理局部加载状态
    error.value = null
    try {
      if (!currentProject.value) {
        throw new Error('没有当前项目')
      }
      const updatedProject = await NovelAPI.updateChapterOutline(
        currentProject.value.id,
        chapterOutline
      )
      currentProject.value = updatedProject // 更新 store
    } catch (err) {
      error.value = err instanceof Error ? err.message : '更新章节大纲失败'
      throw err
    }
  }

  async function deleteChapter(chapterNumbers: number | number[]) {
    error.value = null
    try {
      if (!currentProject.value) {
        throw new Error('没有当前项目')
      }
      const numbersToDelete = Array.isArray(chapterNumbers) ? chapterNumbers : [chapterNumbers]
      const updatedProject = await NovelAPI.deleteChapter(
        currentProject.value.id,
        numbersToDelete
      )
      currentProject.value = updatedProject // 更新 store
    } catch (err) {
      error.value = err instanceof Error ? err.message : '删除章节失败'
      throw err
    }
  }

  async function generateChapterOutline(startChapter: number, numChapters: number) {
    error.value = null
    try {
      if (!currentProject.value) {
        throw new Error('没有当前项目')
      }
      const updatedProject = await NovelAPI.generateChapterOutline(
        currentProject.value.id,
        startChapter,
        numChapters
      )
      currentProject.value = updatedProject // 更新 store
    } catch (err) {
      error.value = err instanceof Error ? err.message : '生成大纲失败'
      throw err
    }
  }

  async function editChapterContent(projectId: string, chapterNumber: number, content: string) {
    error.value = null
    try {
      const updatedProject = await NovelAPI.editChapterContent(projectId, chapterNumber, content)
      currentProject.value = updatedProject // 更新 store
    } catch (err) {
      error.value = err instanceof Error ? err.message : '编辑章节内容失败'
      throw err
    }
  }

  function clearError() {
    error.value = null
  }

  function setCurrentProject(project: NovelProject | null) {
    currentProject.value = project
  }

  return {
    // State
    projects,
    currentProject,
    currentConversationState,
    isLoading,
    error,
    // Getters
    projectsCount,
    hasCurrentProject,
    // Actions
    loadProjects,
    createProject,
    loadProject,
    loadChapter,
    updateChapterStatus,
    updateChapterData,
    sendConversation,
    generateBlueprint,
    saveBlueprint,
    generateChapter,
    evaluateChapter,
    cancelEvaluation,
    selectChapterVersion,
    deleteProjects,
    updateChapterOutline,
    deleteChapter,
    generateChapterOutline,
    editChapterContent,
    clearError,
    setCurrentProject
  }
})

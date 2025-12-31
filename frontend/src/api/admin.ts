import { useAuthStore } from '@/stores/auth'
import router from '@/router'
import type { NovelSectionResponse, NovelSectionType } from '@/api/novel'

// API 配置
export const API_BASE_URL = import.meta.env.MODE === 'production' ? '' : 'http://127.0.0.1:9527'
export const ADMIN_API_PREFIX = '/api/admin'

// 统一请求封装
const request = async (url: string, options: RequestInit = {}) => {
  const authStore = useAuthStore()
  const headers = new Headers({
    'Content-Type': 'application/json',
    ...options.headers
  })

  if (authStore.isAuthenticated && authStore.token) {
    headers.set('Authorization', `Bearer ${authStore.token}`)
  }

  const response = await fetch(url, { ...options, headers })

  if (response.status === 401) {
    authStore.logout()
    router.push('/login')
    throw new Error('会话已过期，请重新登录')
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    let message = `请求失败，状态码: ${response.status}`
    if (errorData.detail) {
      if (typeof errorData.detail === 'string') {
        message = errorData.detail
      } else if (Array.isArray(errorData.detail)) {
        // Pydantic 验证错误格式，包含字段名
        message = errorData.detail.map((e: any) => {
          const field = e.loc ? e.loc.join('.') : ''
          const msg = e.msg || e.message || JSON.stringify(e)
          return field ? `${field}: ${msg}` : msg
        }).join('; ')
      }
    }
    throw new Error(message)
  }

  if (response.status === 204) {
    return
  }

  return response.json()
}

const adminRequest = (path: string, options: RequestInit = {}) =>
  request(`${API_BASE_URL}${ADMIN_API_PREFIX}${path}`, options)

// 类型定义
export interface Statistics {
  novel_count: number
  user_count: number
  api_request_count: number
}

export interface AdminUser {
  id: number
  username: string
  email?: string | null
  is_admin: boolean
}

export interface NovelProjectSummary {
  id: string
  title: string
  genre: string
  last_edited: string
  completed_chapters: number
  total_chapters: number
}

export interface AdminNovelSummary extends NovelProjectSummary {
  owner_id: number
  owner_username: string
}

export interface Chapter {
  chapter_number: number
  title: string
  summary: string
  content?: string | null
  status?: string
  version_id?: string | number | null
  versions?: any[]
  word_count?: number
}

export interface NovelProject {
  id: string
  user_id: number
  title: string
  initial_prompt: string
  conversation_history: any[]
  blueprint?: any
  chapters: Chapter[]
}

export interface PromptItem {
  id: number
  name: string
  title?: string | null
  content: string
}

export interface PromptCreatePayload {
  name: string
  content: string
  title?: string
}

export type PromptUpdatePayload = Partial<Omit<PromptCreatePayload, 'name'>>

export interface UpdateLog {
  id: number
  content: string
  created_at: string
  created_by?: string | null
  is_pinned: boolean
}

export interface UpdateLogPayload {
  content?: string
  is_pinned?: boolean
}

export interface DailyRequestLimit {
  limit: number
}

export interface SystemConfig {
  key: string
  value: string
  description?: string | null
}

export interface SystemConfigUpsertPayload {
  value: string
  description?: string | null
}

export type SystemConfigUpdatePayload = Partial<SystemConfigUpsertPayload>

export class AdminAPI {
  private static request(path: string, options: RequestInit = {}) {
    return adminRequest(path, options)
  }

  // Overview
  static getStatistics(): Promise<Statistics> {
    return this.request('/stats')
  }

  // Users
  static listUsers(): Promise<AdminUser[]> {
    return this.request('/users')
  }

  // Novels
  static listNovels(): Promise<AdminNovelSummary[]> {
    return this.request('/novel-projects')
  }

  static getNovelDetails(projectId: string): Promise<NovelProject> {
    return this.request(`/novel-projects/${projectId}`)
  }

  static getNovelSection(projectId: string, section: NovelSectionType): Promise<NovelSectionResponse> {
    return this.request(`/novel-projects/${projectId}/sections/${section}`)
  }

  static getNovelChapter(projectId: string, chapterNumber: number): Promise<Chapter> {
    return this.request(`/novel-projects/${projectId}/chapters/${chapterNumber}`)
  }

  // Prompts
  static listPrompts(): Promise<PromptItem[]> {
    return this.request('/prompts')
  }

  static createPrompt(payload: PromptCreatePayload): Promise<PromptItem> {
    return this.request('/prompts', {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  }

  static getPrompt(id: number): Promise<PromptItem> {
    return this.request(`/prompts/${id}`)
  }

  static updatePrompt(id: number, payload: PromptUpdatePayload): Promise<PromptItem> {
    return this.request(`/prompts/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    })
  }

  static deletePrompt(id: number): Promise<void> {
    return this.request(`/prompts/${id}`, {
      method: 'DELETE'
    })
  }

  // Update logs
  static listUpdateLogs(): Promise<UpdateLog[]> {
    return this.request('/update-logs')
  }

  static createUpdateLog(payload: UpdateLogPayload & { content: string }): Promise<UpdateLog> {
    return this.request('/update-logs', {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  }

  static updateUpdateLog(id: number, payload: UpdateLogPayload): Promise<UpdateLog> {
    return this.request(`/update-logs/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    })
  }

  static deleteUpdateLog(id: number): Promise<void> {
    return this.request(`/update-logs/${id}`, {
      method: 'DELETE'
    })
  }

  // Settings
  static getDailyRequestLimit(): Promise<DailyRequestLimit> {
    return this.request('/settings/daily-request-limit')
  }

  static setDailyRequestLimit(limit: number): Promise<DailyRequestLimit> {
    return this.request('/settings/daily-request-limit', {
      method: 'PUT',
      body: JSON.stringify({ limit })
    })
  }

  static listSystemConfigs(): Promise<SystemConfig[]> {
    return this.request('/system-configs')
  }

  static upsertSystemConfig(key: string, payload: SystemConfigUpsertPayload): Promise<SystemConfig> {
    return this.request(`/system-configs/${key}`, {
      method: 'PUT',
      body: JSON.stringify({ key, ...payload })
    })
  }

  static patchSystemConfig(key: string, payload: SystemConfigUpdatePayload): Promise<SystemConfig> {
    return this.request(`/system-configs/${key}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    })
  }

  static deleteSystemConfig(key: string): Promise<void> {
    return this.request(`/system-configs/${key}`, {
      method: 'DELETE'
    })
  }

  static changePassword(oldPassword: string, newPassword: string): Promise<void> {
    return this.request('/password', {
      method: 'POST',
      body: JSON.stringify({
        old_password: oldPassword,
        new_password: newPassword
      })
    })
  }
}

import { useAuthStore } from '@/stores/auth';

const API_PREFIX = '/api';
const LLM_BASE = `${API_PREFIX}/llm-config`;

export type NodeBindings = Record<string, string>;

const getHeaders = () => {
  const authStore = useAuthStore();
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${authStore.token}`,
  };
};

// ============ 节点绑定 API ============

export const getAvailableProviders = async (): Promise<string[]> => {
  const response = await fetch(`${LLM_BASE}/providers`, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (!response.ok) {
    throw new Error('获取 Provider 列表失败');
  }
  const data = await response.json();
  return data.providers || [];
};

export const getNodeBindings = async (): Promise<NodeBindings> => {
  const response = await fetch(`${LLM_BASE}/nodes`, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (!response.ok) {
    throw new Error('获取节点绑定失败');
  }
  return response.json();
};

export const setNodeBinding = async (node: string, provider_name: string): Promise<NodeBindings> => {
  const response = await fetch(`${LLM_BASE}/nodes/${encodeURIComponent(node)}`, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify({ provider_name }),
  });
  if (!response.ok) {
    throw new Error('设置节点绑定失败');
  }
  return response.json();
};

// ============ Provider 管理 API ============

export interface ProviderConfig {
  name: string;
  model: string;
  provider: string | null;
  base_url: string | null;
  temperature: number | null;
  max_tokens: number | null;
  timeout: number | null;
  has_api_key: boolean;
  support_json_mode: boolean | null;
  support_stream: boolean | null;
  proxy: string | null;
  embed_api_type: string | null;
}

export interface ProviderCreate {
  name: string;
  model: string;
  provider?: string | null;
  base_url?: string | null;
  temperature?: number | null;
  max_tokens?: number | null;
  timeout?: number | null;
  api_key?: string | null;
  support_json_mode?: boolean;
  support_stream?: boolean;
  proxy?: string | null;
  embed_api_type?: string;
}

export interface ProviderTestResponse {
  ok: boolean;
  latency_ms: number;
  model: string | null;
  base_url: string | null;
  response_preview: string | null;
  error: string | null;
}

export const getAllProviderDetails = async (): Promise<ProviderConfig[]> => {
  const response = await fetch(`${LLM_BASE}/providers/details`, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (!response.ok) {
    throw new Error('获取 Provider 详情失败');
  }
  const data = await response.json();
  return data.providers || [];
};

export const createProvider = async (config: ProviderCreate): Promise<ProviderConfig> => {
  const response = await fetch(`${LLM_BASE}/providers`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(config),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || '创建 Provider 失败');
  }
  return response.json();
};

export const updateProvider = async (name: string, config: ProviderCreate): Promise<ProviderConfig> => {
  const response = await fetch(`${LLM_BASE}/providers/${encodeURIComponent(name)}`, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify(config),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || '更新 Provider 失败');
  }
  return response.json();
};

export const deleteProvider = async (name: string): Promise<void> => {
  const response = await fetch(`${LLM_BASE}/providers/${encodeURIComponent(name)}`, {
    method: 'DELETE',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || '删除 Provider 失败');
  }
};

export const testProviderConnection = async (name: string): Promise<ProviderTestResponse> => {
  const response = await fetch(`${LLM_BASE}/providers/${encodeURIComponent(name)}/test`, {
    method: 'POST',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || '测试连接失败');
  }
  return response.json();
};

export interface ProviderJsonTestResponse extends ProviderTestResponse {
  json_valid: boolean;
}

export const testProviderJsonMode = async (name: string): Promise<ProviderJsonTestResponse> => {
  const response = await fetch(`${LLM_BASE}/providers/${encodeURIComponent(name)}/test-json`, {
    method: 'POST',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'JSON 模式测试失败');
  }
  return response.json();
};

// ============ 写作模型配置 API ============

export interface WritingModelItem {
  name: string;
  temperature: number | null;
  revision_temperature: number | null;  // 修订任务温度
}

export interface WritingModelsResponse {
  models: WritingModelItem[];
}

export const getWritingModels = async (): Promise<WritingModelItem[]> => {
  const response = await fetch(`${LLM_BASE}/writing-models`, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (!response.ok) {
    throw new Error('获取写作模型配置失败');
  }
  const data: WritingModelsResponse = await response.json();
  return data.models || [];
};

export const setWritingModels = async (models: WritingModelItem[]): Promise<WritingModelItem[]> => {
  const response = await fetch(`${LLM_BASE}/writing-models`, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify({ models }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || '保存写作模型配置失败');
  }
  const data: WritingModelsResponse = await response.json();
  return data.models || [];
};

// ============ 分数阈值配置 API ============

export interface ScoreThresholdConfig {
  score_threshold_early: number;  // 前三章阈值
  score_threshold_normal: number; // 后续章节阈值
  max_rewrite_attempts: number;   // 最大重写次数
}

export const getScoreThresholds = async (): Promise<ScoreThresholdConfig> => {
  const response = await fetch(`${LLM_BASE}/score-thresholds`, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (!response.ok) {
    throw new Error('获取分数阈值配置失败');
  }
  return response.json();
};

export const setScoreThresholds = async (config: ScoreThresholdConfig): Promise<ScoreThresholdConfig> => {
  const response = await fetch(`${LLM_BASE}/score-thresholds`, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify(config),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || '保存分数阈值配置失败');
  }
  return response.json();
};

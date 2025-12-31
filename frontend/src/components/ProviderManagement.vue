<template>
  <div class="bg-white/70 backdrop-blur-xl rounded-2xl shadow-lg p-8">
    <div class="flex items-center justify-between mb-6">
      <h2 class="text-2xl font-bold text-gray-800">模型配置</h2>
      <button
        type="button"
        class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
        @click="openCreate"
      >
        新增配置
      </button>
    </div>
    <div v-if="loading" class="text-sm text-gray-500">加载中...</div>
    <div v-else-if="error" class="text-sm text-amber-700">{{ error }}</div>
    <div v-else class="grid gap-4 md:grid-cols-2">
      <div
        v-for="item in providers"
        :key="item.name"
        class="border border-gray-200 rounded-xl p-4 bg-white shadow-sm"
      >
        <div class="flex items-start justify-between gap-3">
          <div>
            <p class="text-sm font-semibold text-gray-800">{{ item.name }}</p>
            <p class="text-xs text-gray-500 mt-1">模型: {{ item.model || '-' }}</p>
            <p class="text-xs text-gray-500 mt-1 break-all">接口地址: {{ item.base_url || '-' }}</p>
          </div>
          <span
            class="text-[11px] px-2 py-1 rounded-full"
            :class="item.has_api_key ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-600'"
          >
            {{ item.has_api_key ? '已配置密钥' : '未配置密钥' }}
          </span>
        </div>
        <div class="mt-3 text-xs text-gray-500">
          类型: {{ item.provider || '-' }}
          <span class="mx-2">·</span>
          温度: {{ item.temperature ?? '-' }}
          <span class="mx-2">·</span>
          最大令牌: {{ item.max_tokens ?? '-' }}
          <span class="mx-2">·</span>
          超时: {{ item.timeout ?? '-' }}s
        </div>
        <!-- 测试结果显示 -->
        <div
          v-if="testResults[item.name]"
          class="mt-3 rounded-lg border px-3 py-2"
          :class="testResults[item.name].ok ? 'border-emerald-200 bg-emerald-50' : 'border-amber-200 bg-amber-50'"
        >
          <p class="text-xs font-medium" :class="testResults[item.name].ok ? 'text-emerald-700' : 'text-amber-700'">
            {{ testResults[item.name].ok ? '连接成功' : '连接失败' }}
          </p>
          <p class="text-xs text-gray-600 mt-1">
            耗时 {{ testResults[item.name].latency_ms }}ms
          </p>
          <p v-if="testResults[item.name].response_preview" class="text-xs text-gray-600 mt-1 break-all">
            响应预览: {{ testResults[item.name].response_preview }}
          </p>
          <p v-if="testResults[item.name].error" class="text-xs text-amber-700 mt-1 break-all">
            {{ testResults[item.name].error }}
          </p>
        </div>
        <!-- JSON 测试结果显示 -->
        <div
          v-if="jsonTestResults[item.name]"
          class="mt-3 rounded-lg border px-3 py-2"
          :class="jsonTestResults[item.name].json_valid ? 'border-emerald-200 bg-emerald-50' : 'border-amber-200 bg-amber-50'"
        >
          <p class="text-xs font-medium" :class="jsonTestResults[item.name].json_valid ? 'text-emerald-700' : 'text-amber-700'">
            {{ jsonTestResults[item.name].json_valid ? 'JSON 模式正常' : 'JSON 模式异常' }}
          </p>
          <p class="text-xs text-gray-600 mt-1">
            耗时 {{ jsonTestResults[item.name].latency_ms }}ms
          </p>
          <p v-if="jsonTestResults[item.name].response_preview" class="text-xs text-gray-600 mt-1 break-all">
            响应: {{ jsonTestResults[item.name].response_preview }}
          </p>
          <p v-if="jsonTestResults[item.name].error" class="text-xs text-amber-700 mt-1 break-all">
            {{ jsonTestResults[item.name].error }}
          </p>
        </div>
        <div class="mt-4 flex justify-end gap-2">
          <button
            type="button"
            class="px-3 py-1.5 text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 text-xs disabled:opacity-60"
            :disabled="testing === item.name"
            @click="handleTest(item)"
          >
            {{ testing === item.name ? '测试中...' : '测试连接' }}
          </button>
          <button
            type="button"
            class="px-3 py-1.5 text-amber-600 border border-amber-600 rounded-lg hover:bg-amber-50 text-xs disabled:opacity-60"
            :disabled="testingJson === item.name"
            @click="handleJsonTest(item)"
          >
            {{ testingJson === item.name ? '测试中...' : 'JSON测试' }}
          </button>
          <button
            type="button"
            class="px-3 py-1.5 text-indigo-600 border border-indigo-600 rounded-lg hover:bg-indigo-50 text-xs"
            @click="openEdit(item)"
          >
            编辑
          </button>
          <button
            type="button"
            class="px-3 py-1.5 text-white bg-red-600 rounded-lg hover:bg-red-700 text-xs disabled:opacity-60"
            :disabled="deleting === item.name"
            @click="handleDelete(item)"
          >
            {{ deleting === item.name ? '删除中...' : '删除' }}
          </button>
        </div>
      </div>
      <div v-if="!providers.length" class="text-sm text-gray-500">暂无配置，请点击"新增配置"添加。</div>
    </div>

    <!-- 节点绑定配置 -->
    <div class="border-t border-gray-200 mt-8 pt-6">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-gray-800">节点绑定</h3>
        <span class="text-xs text-gray-500">修改后立即生效</span>
      </div>
      <p class="text-xs text-gray-500 mb-4">
        节点用于区分业务阶段（概念、蓝图、写作等），可绑定到不同的模型配置。
      </p>
      <div v-if="nodesLoading" class="text-sm text-gray-500">加载节点配置中...</div>
      <div v-else class="overflow-hidden rounded-lg border border-gray-200">
        <table class="min-w-full text-sm">
          <thead class="bg-gray-50 text-gray-600">
            <tr>
              <th class="px-4 py-2 text-left font-medium">节点</th>
              <th class="px-4 py-2 text-left font-medium">绑定模型</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100 bg-white">
            <tr v-for="node in nodeList" :key="node.key">
              <td class="px-4 py-2">
                <div class="max-w-[220px]">
                  <p class="text-sm font-medium text-gray-700 truncate" :title="node.label">{{ node.label }}</p>
                  <p class="text-xs text-gray-500 truncate" :title="node.key">{{ node.key }}</p>
                </div>
              </td>
              <td class="px-4 py-2">
                <select
                  v-model="nodeBindings[node.key]"
                  @change="handleNodeBindingChange(node.key)"
                  class="w-full min-w-[320px] px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                  :title="nodeBindings[node.key] || '未绑定'"
                >
                  <option value="" disabled>未绑定</option>
                  <option v-for="provider in providerNames" :key="provider" :value="provider" :title="provider">
                    {{ provider }}
                  </option>
                </select>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-if="nodesError" class="px-4 py-2 text-xs text-amber-700">{{ nodesError }}</p>
      </div>
    </div>

    <!-- 写作模型多选配置 -->
    <div class="border-t border-gray-200 mt-8 pt-6">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-gray-800">写作模型 (多选)</h3>
        <button
          type="button"
          class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors text-sm disabled:opacity-60"
          :disabled="savingWritingModels"
          @click="handleSaveWritingModels"
        >
          {{ savingWritingModels ? '保存中...' : '保存配置' }}
        </button>
      </div>
      <p class="text-xs text-gray-500 mb-4">
        选择多个模型用于并行生成章节版本，每个模型可单独配置温度。温度为"默认"时使用模型配置中的温度。
      </p>
      <div v-if="writingModelsLoading" class="text-sm text-gray-500">加载写作模型配置中...</div>
      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        <div
          v-for="provider in providers"
          :key="provider.name"
          class="border rounded-lg transition-colors"
          :class="isModelSelected(provider.name) ? 'border-indigo-400 bg-indigo-50' : 'border-gray-200 hover:bg-gray-50'"
        >
          <label class="flex items-center gap-3 p-3 cursor-pointer">
            <input
              type="checkbox"
              :checked="isModelSelected(provider.name)"
              @change="toggleModelSelection(provider.name)"
              class="w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
            >
            <div class="flex-1 min-w-0">
              <p class="text-sm font-medium text-gray-800 truncate">{{ provider.name }}</p>
              <p class="text-xs text-gray-500 truncate">{{ provider.model || '-' }}</p>
            </div>
          </label>
          <!-- 选中后显示温度控制 -->
          <div v-if="isModelSelected(provider.name)" class="px-3 pb-3 pt-1 border-t border-indigo-200 space-y-2">
            <!-- 创作温度 -->
            <div class="flex items-center gap-2">
              <span class="text-xs text-gray-600 whitespace-nowrap">创作温度:</span>
              <input
                type="range"
                min="0"
                max="2"
                step="0.1"
                :value="getModelTemperature(provider.name) ?? 0.7"
                @input="setModelTemperature(provider.name, parseFloat(($event.target as HTMLInputElement).value))"
                class="flex-1 h-1 accent-indigo-600"
              >
              <span class="text-xs text-indigo-600 w-10 text-right">{{ formatTemperature(getModelTemperature(provider.name)) }}</span>
              <button
                type="button"
                class="text-xs text-gray-500 hover:text-indigo-600"
                @click="setModelTemperature(provider.name, null)"
                title="使用模型默认温度"
              >
                重置
              </button>
            </div>
            <!-- 修订温度 -->
            <div class="flex items-center gap-2">
              <span class="text-xs text-gray-600 whitespace-nowrap">修订温度:</span>
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                :value="getModelRevisionTemperature(provider.name) ?? 0.3"
                @input="setModelRevisionTemperature(provider.name, parseFloat(($event.target as HTMLInputElement).value))"
                class="flex-1 h-1 accent-amber-600"
              >
              <span class="text-xs text-amber-600 w-10 text-right">{{ formatTemperature(getModelRevisionTemperature(provider.name)) }}</span>
              <button
                type="button"
                class="text-xs text-gray-500 hover:text-amber-600"
                @click="setModelRevisionTemperature(provider.name, 0.3)"
                title="重置为默认修订温度0.3"
              >
                重置
              </button>
            </div>
          </div>
        </div>
      </div>
      <p v-if="writingModelsError" class="text-xs text-amber-700 mt-2">{{ writingModelsError }}</p>
      <p v-if="selectedWritingModels.length > 0" class="text-xs text-indigo-600 mt-3">
        已选择 {{ selectedWritingModels.length }} 个模型，生成章节时将并行产出 {{ selectedWritingModels.length }} 个版本
      </p>
    </div>

    <!-- 分数阈值配置 -->
    <div class="border-t border-gray-200 mt-8 pt-6">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-gray-800">连续创作质量控制</h3>
        <button
          type="button"
          class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors text-sm disabled:opacity-60"
          :disabled="savingScoreThresholds"
          @click="handleSaveScoreThresholds"
        >
          {{ savingScoreThresholds ? '保存中...' : '保存配置' }}
        </button>
      </div>
      <p class="text-xs text-gray-500 mb-4">
        连续创作时，章节评分低于阈值将触发重写。超过最大重写次数后停止连续创作。
      </p>
      <div v-if="scoreThresholdsLoading" class="text-sm text-gray-500">加载分数阈值配置中...</div>
      <div v-else class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div class="border border-gray-200 rounded-lg p-4 bg-white">
          <label class="block text-sm font-medium text-gray-700 mb-2">前三章分数阈值</label>
          <input
            v-model.number="scoreThresholds.score_threshold_early"
            type="number"
            min="0"
            max="100"
            class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
          >
          <p class="mt-1 text-xs text-gray-500">第1-3章需要达到的最低分数（0-100）</p>
        </div>
        <div class="border border-gray-200 rounded-lg p-4 bg-white">
          <label class="block text-sm font-medium text-gray-700 mb-2">后续章节分数阈值</label>
          <input
            v-model.number="scoreThresholds.score_threshold_normal"
            type="number"
            min="0"
            max="100"
            class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
          >
          <p class="mt-1 text-xs text-gray-500">第4章及以后需要达到的最低分数（0-100）</p>
        </div>
        <div class="border border-gray-200 rounded-lg p-4 bg-white">
          <label class="block text-sm font-medium text-gray-700 mb-2">最大重写次数</label>
          <input
            v-model.number="scoreThresholds.max_rewrite_attempts"
            type="number"
            min="1"
            max="10"
            class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
          >
          <p class="mt-1 text-xs text-gray-500">每章最多重写次数，超过后停止连续创作</p>
        </div>
      </div>
      <p v-if="scoreThresholdsError" class="text-xs text-amber-700 mt-2">{{ scoreThresholdsError }}</p>
    </div>

    <!-- 弹窗 Teleport 到 body，避免父元素影响定位 -->
    <Teleport to="body">
      <div v-if="showForm" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
        <div class="w-full max-w-2xl bg-white rounded-2xl shadow-xl p-6 max-h-[90vh] overflow-y-auto">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-semibold text-gray-800">{{ isEdit ? '编辑配置' : '新增配置' }}</h3>
          <button class="text-gray-400 hover:text-gray-600" type="button" @click="closeForm">✕</button>
        </div>
        <form class="grid grid-cols-1 gap-4 md:grid-cols-2" @submit.prevent="handleSubmit">
          <div>
            <label class="block text-sm font-medium text-gray-700">名称 *</label>
            <input
              v-model="form.name"
              :disabled="isEdit"
              class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm sm:text-sm"
              placeholder="配置名称（唯一标识）"
            >
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700">模型 *</label>
            <input
              v-model="form.model"
              class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm sm:text-sm"
              placeholder="如 gpt-4o、claude-3-5-sonnet"
            >
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700">类型</label>
            <input
              v-model="form.provider"
              class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm sm:text-sm"
              placeholder="openai_compat"
            >
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700">接口地址</label>
            <input
              v-model="form.base_url"
              class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm sm:text-sm"
              placeholder="https://api.example.com/v1"
            >
          </div>
          <div class="md:col-span-2">
            <label class="block text-sm font-medium text-gray-700">API 密钥</label>
            <input
              v-model="form.api_key"
              class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm sm:text-sm"
              placeholder="留空则不修改/不设置"
            >
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700">温度</label>
            <input
              v-model="form.temperature"
              type="number"
              step="0.1"
              class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm sm:text-sm"
              placeholder="0.0 - 2.0"
            >
            <p class="mt-1 text-xs text-gray-500">
              控制输出随机性：低温(0-0.3)更稳定精确，高温(0.7-1.0)更有创意。推荐写作用0.7-0.9
            </p>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700">最大令牌数</label>
            <input
              v-model="form.max_tokens"
              type="number"
              class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm sm:text-sm"
              placeholder="如 4096"
            >
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700">超时时间 (秒)</label>
            <input
              v-model="form.timeout"
              type="number"
              class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm sm:text-sm"
              placeholder="如 300"
            >
          </div>
          <div class="flex items-center gap-3">
            <input
              id="support_json_mode"
              v-model="form.support_json_mode"
              type="checkbox"
              class="w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
            >
            <label for="support_json_mode" class="text-sm font-medium text-gray-700">支持 JSON 模式</label>
            <span class="text-xs text-gray-500">（部分站点不支持，可关闭）</span>
          </div>
          <div class="flex items-center gap-3">
            <input
              id="support_stream"
              v-model="form.support_stream"
              type="checkbox"
              class="w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
            >
            <label for="support_stream" class="text-sm font-medium text-gray-700">支持流式输出</label>
            <span class="text-xs text-gray-500">（关闭后自动降级为非流式）</span>
          </div>
          <div class="md:col-span-2">
            <label class="block text-sm font-medium text-gray-700">代理地址</label>
            <input
              v-model="form.proxy"
              class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm sm:text-sm"
              placeholder="如 socks5://127.0.0.1:1080"
            >
            <p class="mt-1 text-xs text-gray-500">
              支持 SOCKS5 代理，用于 Embedding 请求。格式: socks5://host:port
            </p>
          </div>
          <div v-if="isEmbeddingModel">
            <label class="block text-sm font-medium text-gray-700">Embedding API 类型</label>
            <select
              v-model="form.embed_api_type"
              class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm sm:text-sm"
            >
              <option value="openai">OpenAI 兼容</option>
              <option value="gemini">Google Gemini</option>
            </select>
            <p class="mt-1 text-xs text-gray-500">
              选择 Embedding 接口格式。Gemini 使用 Google 原生 API 格式
            </p>
          </div>
          <div class="md:col-span-2 flex justify-end gap-2 pt-2">
            <button type="button" class="px-4 py-2 border border-gray-300 rounded-lg text-sm" @click="closeForm">取消</button>
            <button type="submit" class="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm disabled:opacity-60" :disabled="saving">
              {{ saving ? '保存中...' : '保存' }}
            </button>
          </div>
        </form>
        <p v-if="formError" class="text-xs text-amber-700 mt-3">{{ formError }}</p>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from 'vue';
import { globalAlert } from '@/composables/useAlert';
import {
  getAllProviderDetails,
  createProvider,
  updateProvider,
  deleteProvider,
  testProviderConnection,
  testProviderJsonMode,
  getAvailableProviders,
  getNodeBindings,
  setNodeBinding,
  getWritingModels,
  setWritingModels,
  getScoreThresholds,
  setScoreThresholds,
  type ProviderConfig,
  type ProviderCreate,
  type ProviderTestResponse,
  type ProviderJsonTestResponse,
  type WritingModelItem,
  type ScoreThresholdConfig,
} from '@/api/llm';

type FormState = {
  name: string;
  model: string;
  provider: string;
  base_url: string;
  api_key: string;
  temperature: string;
  max_tokens: string;
  timeout: string;
  support_json_mode: boolean;
  support_stream: boolean;
  proxy: string;
  embed_api_type: string;
};

const nodeList = [
  { key: 'concept', label: '概念对话' },
  { key: 'blueprint', label: '蓝图生成' },
  { key: 'evaluation', label: '章节评估' },
  { key: 'outline', label: '章节大纲' },
  { key: 'summary', label: '摘要生成' },
  { key: 'embedding', label: '向量嵌入' },
];

const emptyForm = (): FormState => ({
  name: '',
  model: '',
  provider: '',
  base_url: '',
  api_key: '',
  temperature: '',
  max_tokens: '',
  timeout: '',
  support_json_mode: true,
  support_stream: true,
  proxy: '',
  embed_api_type: 'openai',
});

const providers = ref<ProviderConfig[]>([]);
const providerNames = computed(() => providers.value.map(p => p.name));
const loading = ref(false);
const error = ref<string | null>(null);

// 判断当前编辑的模型是否为 embedding 模型
const isEmbeddingModel = computed(() =>
  form.value.model.toLowerCase().includes('embedding')
);
const deleting = ref<string | null>(null);
const testing = ref<string | null>(null);
const testingJson = ref<string | null>(null);
const testResults = ref<Record<string, ProviderTestResponse>>({});
const jsonTestResults = ref<Record<string, ProviderJsonTestResponse>>({});

const nodeBindings = ref<Record<string, string>>({});
const nodesLoading = ref(false);
const nodesError = ref<string | null>(null);

// 写作模型多选相关状态
const selectedWritingModels = ref<WritingModelItem[]>([]);
const writingModelsLoading = ref(false);
const writingModelsError = ref<string | null>(null);
const savingWritingModels = ref(false);

// 分数阈值配置相关状态
const scoreThresholds = ref<ScoreThresholdConfig>({
  score_threshold_early: 95,
  score_threshold_normal: 90,
  max_rewrite_attempts: 3,
});
const scoreThresholdsLoading = ref(false);
const scoreThresholdsError = ref<string | null>(null);
const savingScoreThresholds = ref(false);

// 辅助函数：检查模型是否被选中
const isModelSelected = (providerName: string) => {
  return selectedWritingModels.value.some(m => m.name === providerName);
};

// 辅助函数：切换模型选中状态
const toggleModelSelection = (providerName: string) => {
  const idx = selectedWritingModels.value.findIndex(m => m.name === providerName);
  if (idx >= 0) {
    selectedWritingModels.value.splice(idx, 1);
  } else {
    selectedWritingModels.value.push({ name: providerName, temperature: null, revision_temperature: 0.3 });
  }
};

// 辅助函数：获取模型温度
const getModelTemperature = (providerName: string): number | null => {
  const model = selectedWritingModels.value.find(m => m.name === providerName);
  return model?.temperature ?? null;
};

// 辅助函数：设置模型温度
const setModelTemperature = (providerName: string, temperature: number | null) => {
  const model = selectedWritingModels.value.find(m => m.name === providerName);
  if (model) {
    model.temperature = temperature;
  }
};

// 辅助函数：获取模型修订温度
const getModelRevisionTemperature = (providerName: string): number | null => {
  const model = selectedWritingModels.value.find(m => m.name === providerName);
  return model?.revision_temperature ?? 0.3;
};

// 辅助函数：设置模型修订温度
const setModelRevisionTemperature = (providerName: string, temperature: number | null) => {
  const model = selectedWritingModels.value.find(m => m.name === providerName);
  if (model) {
    model.revision_temperature = temperature;
  }
};

// 辅助函数：格式化温度显示
const formatTemperature = (temp: number | null): string => {
  return temp === null ? '默认' : temp.toFixed(1);
};

const showForm = ref(false);
const isEdit = ref(false);
const editingName = ref<string | null>(null);
const saving = ref(false);
const formError = ref<string | null>(null);
const form = ref<FormState>(emptyForm());

const loadProviders = async () => {
  loading.value = true;
  error.value = null;
  try {
    providers.value = await getAllProviderDetails();
  } catch (err: any) {
    error.value = err?.message || '加载失败';
  } finally {
    loading.value = false;
  }
};

const loadNodeBindings = async () => {
  nodesLoading.value = true;
  nodesError.value = null;
  try {
    const bindings = await getNodeBindings();
    const normalized: Record<string, string> = { ...bindings };
    nodeList.forEach((node) => {
      if (!(node.key in normalized)) {
        normalized[node.key] = '';
      }
    });
    nodeBindings.value = normalized;
  } catch (err: any) {
    nodesError.value = err?.message || '节点绑定加载失败';
  } finally {
    nodesLoading.value = false;
  }
};

// 加载写作模型配置
const loadWritingModels = async () => {
  writingModelsLoading.value = true;
  writingModelsError.value = null;
  try {
    selectedWritingModels.value = await getWritingModels();
  } catch (err: any) {
    writingModelsError.value = err?.message || '写作模型配置加载失败';
  } finally {
    writingModelsLoading.value = false;
  }
};

// 保存写作模型配置
const handleSaveWritingModels = async () => {
  savingWritingModels.value = true;
  writingModelsError.value = null;
  try {
    await setWritingModels(selectedWritingModels.value);
  } catch (err: any) {
    writingModelsError.value = err?.message || '保存写作模型配置失败';
  } finally {
    savingWritingModels.value = false;
  }
};

// 加载分数阈值配置
const loadScoreThresholds = async () => {
  scoreThresholdsLoading.value = true;
  scoreThresholdsError.value = null;
  try {
    scoreThresholds.value = await getScoreThresholds();
  } catch (err: any) {
    scoreThresholdsError.value = err?.message || '分数阈值配置加载失败';
  } finally {
    scoreThresholdsLoading.value = false;
  }
};

// 保存分数阈值配置
const handleSaveScoreThresholds = async () => {
  savingScoreThresholds.value = true;
  scoreThresholdsError.value = null;
  try {
    await setScoreThresholds(scoreThresholds.value);
  } catch (err: any) {
    scoreThresholdsError.value = err?.message || '保存分数阈值配置失败';
  } finally {
    savingScoreThresholds.value = false;
  }
};

onMounted(async () => {
  await Promise.all([loadProviders(), loadNodeBindings(), loadWritingModels(), loadScoreThresholds()]);
});

const openCreate = () => {
  isEdit.value = false;
  editingName.value = null;
  form.value = emptyForm();
  formError.value = null;
  showForm.value = true;
};

const openEdit = (item: ProviderConfig) => {
  isEdit.value = true;
  editingName.value = item.name;
  form.value = {
    name: item.name,
    model: item.model || '',
    provider: item.provider || '',
    base_url: item.base_url || '',
    api_key: '',
    temperature: item.temperature?.toString() ?? '',
    max_tokens: item.max_tokens?.toString() ?? '',
    timeout: item.timeout?.toString() ?? '',
    support_json_mode: item.support_json_mode ?? true,
    support_stream: item.support_stream ?? true,
    proxy: item.proxy || '',
    embed_api_type: item.embed_api_type || 'openai',
  };
  formError.value = null;
  showForm.value = true;
};

const closeForm = () => {
  showForm.value = false;
  formError.value = null;
};

// 返回 trimmed 字符串，空字符串表示清空（后端识别）
const toOptionalString = (value: string | null | undefined): string | null => {
  if (value == null) return null;
  return String(value).trim();
};

const toOptionalNumber = (value: string | number | null | undefined, isInt = false) => {
  if (value == null || value === '') return null;
  const num = isInt ? parseInt(String(value), 10) : Number(value);
  return Number.isFinite(num) ? num : null;
};

const buildPayload = (): ProviderCreate | null => {
  const name = form.value.name.trim();
  const model = form.value.model.trim();
  if (!name || !model) {
    formError.value = '名称和模型为必填项';
    return null;
  }
  return {
    name,
    model,
    provider: toOptionalString(form.value.provider),
    base_url: toOptionalString(form.value.base_url),
    api_key: toOptionalString(form.value.api_key),
    temperature: toOptionalNumber(form.value.temperature),
    max_tokens: toOptionalNumber(form.value.max_tokens, true),
    timeout: toOptionalNumber(form.value.timeout, true),
    support_json_mode: form.value.support_json_mode,
    support_stream: form.value.support_stream,
    proxy: toOptionalString(form.value.proxy),
    embed_api_type: form.value.embed_api_type || 'openai',
  };
};

const handleSubmit = async () => {
  if (saving.value) return;
  formError.value = null;
  const payload = buildPayload();
  if (!payload) return;
  saving.value = true;
  try {
    if (isEdit.value && editingName.value) {
      await updateProvider(editingName.value, payload);
    } else {
      await createProvider(payload);
    }
    showForm.value = false;
    await loadProviders();
  } catch (err: any) {
    formError.value = err?.message || '保存失败';
  } finally {
    saving.value = false;
  }
};

const handleDelete = async (item: ProviderConfig) => {
  const confirmed = await globalAlert.showConfirm(`确定删除配置 "${item.name}" 吗？`, '删除确认');
  if (!confirmed) return;
  deleting.value = item.name;
  error.value = null;
  try {
    await deleteProvider(item.name);
    providers.value = providers.value.filter((p) => p.name !== item.name);
    // 清除测试结果
    delete testResults.value[item.name];
  } catch (err: any) {
    error.value = err?.message || '删除失败';
  } finally {
    deleting.value = null;
  }
};

const handleTest = async (item: ProviderConfig) => {
  testing.value = item.name;
  // 清除之前的测试结果
  delete testResults.value[item.name];
  try {
    const result = await testProviderConnection(item.name);
    testResults.value[item.name] = result;
  } catch (err: any) {
    testResults.value[item.name] = {
      ok: false,
      latency_ms: 0,
      model: item.model,
      base_url: item.base_url,
      response_preview: null,
      error: err?.message || '测试失败',
    };
  } finally {
    testing.value = null;
  }
};

const handleJsonTest = async (item: ProviderConfig) => {
  testingJson.value = item.name;
  delete jsonTestResults.value[item.name];
  try {
    const result = await testProviderJsonMode(item.name);
    jsonTestResults.value[item.name] = result;
  } catch (err: any) {
    jsonTestResults.value[item.name] = {
      ok: false,
      latency_ms: 0,
      model: item.model,
      base_url: item.base_url,
      response_preview: null,
      json_valid: false,
      error: err?.message || 'JSON 测试失败',
    };
  } finally {
    testingJson.value = null;
  }
};

const handleNodeBindingChange = async (node: string) => {
  const provider = nodeBindings.value[node];
  if (!provider) {
    return;
  }
  nodesError.value = null;
  try {
    const updated = await setNodeBinding(node, provider);
    nodeBindings.value = { ...nodeBindings.value, ...updated };
  } catch (err: any) {
    nodesError.value = err?.message || '节点绑定保存失败';
  }
};
</script>

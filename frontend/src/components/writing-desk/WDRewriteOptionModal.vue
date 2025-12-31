<template>
  <div v-if="visible" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
    <div class="bg-white rounded-2xl shadow-xl w-full max-w-lg overflow-hidden flex flex-col">
      <div class="flex items-center justify-between p-6 border-b border-gray-200">
        <h3 class="text-lg font-bold text-gray-900">重写第 {{ chapterNumber }} 章</h3>
        <button @click="close" class="text-gray-400 hover:text-gray-600 transition-colors">
          <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path></svg>
        </button>
      </div>

      <div class="p-6 space-y-6">
        <!-- 模式选择 -->
        <div>
          <label class="text-sm font-medium text-gray-700 mb-2 block">重写模式</label>
          <div class="grid grid-cols-2 gap-3">
            <button
              @click="mode = 'normal'"
              :class="['px-4 py-3 rounded-lg border text-sm font-medium transition-all', mode === 'normal' ? 'border-indigo-600 bg-indigo-50 text-indigo-700' : 'border-gray-200 hover:border-gray-300 text-gray-600']"
            >
              🚀 普通生成
              <span class="block text-xs font-normal mt-1 opacity-75">快速生成新版本</span>
            </button>
            <button
              @click="mode = 'smart'"
              :class="['px-4 py-3 rounded-lg border text-sm font-medium transition-all', mode === 'smart' ? 'border-purple-600 bg-purple-50 text-purple-700' : 'border-gray-200 hover:border-gray-300 text-gray-600']"
            >
              🧠 智能重写
              <span class="block text-xs font-normal mt-1 opacity-75">生成+评审+自动优化</span>
            </button>
          </div>
        </div>

        <!-- 智能参数 -->
        <div v-if="mode === 'smart'" class="grid grid-cols-2 gap-4 bg-gray-50 p-4 rounded-lg">
          <div>
            <label class="text-xs font-medium text-gray-500 mb-1 block">最低评分要求</label>
            <input v-model.number="scoreThreshold" type="number" min="1" max="100" class="w-full px-3 py-1.5 text-sm border border-gray-300 rounded focus:ring-purple-500 focus:border-purple-500">
          </div>
          <div>
            <label class="text-xs font-medium text-gray-500 mb-1 block">最大尝试次数</label>
            <input v-model.number="maxAttempts" type="number" min="1" max="5" class="w-full px-3 py-1.5 text-sm border border-gray-300 rounded focus:ring-purple-500 focus:border-purple-500">
          </div>
        </div>

        <!-- 写作指导 -->
        <div>
          <label class="text-sm font-medium text-gray-700 mb-2 block">写作指导 (Optional)</label>
          <textarea
            v-model="writingNotes"
            rows="4"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-indigo-500 focus:border-indigo-500 resize-none"
            placeholder="输入具体的修改意见，例如：增加环境描写，让对话更紧凑..."
          ></textarea>
        </div>
      </div>

      <div class="p-6 border-t border-gray-200 flex justify-end gap-3 bg-gray-50">
        <button @click="close" class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50">取消</button>
        <button @click="confirm" class="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 shadow-sm">开始重写</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  visible: boolean
  chapterNumber: number
  defaultNotes?: string
}>()

const emit = defineEmits(['update:visible', 'confirm'])

const mode = ref<'normal' | 'smart'>('smart')
const writingNotes = ref('')
const scoreThreshold = ref(75)
const maxAttempts = ref(2)

watch(() => props.visible, (val) => {
  if (val) {
    writingNotes.value = props.defaultNotes || ''
    mode.value = props.defaultNotes ? 'smart' : 'normal'
  }
})

const close = () => emit('update:visible', false)

const confirm = () => {
  emit('confirm', {
    mode: mode.value,
    writingNotes: writingNotes.value,
    scoreThreshold: scoreThreshold.value,
    maxAttempts: maxAttempts.value
  })
  close()
}
</script>

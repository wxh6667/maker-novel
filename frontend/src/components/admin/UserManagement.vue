<template>
  <n-card :bordered="false" class="admin-card">
    <template #header>
      <div class="card-header">
        <span class="card-title">用户管理</span>
        <n-space :size="12">
          <n-input
            v-model:value="keyword"
            clearable
            round
            placeholder="搜索用户名或邮箱"
            @update:value="handleSearch"
            class="search-input"
          />
          <n-button quaternary size="small" @click="fetchUsers" :loading="loading">
            刷新
          </n-button>
        </n-space>
      </div>
    </template>

    <n-space vertical size="large">
      <n-alert v-if="error" type="error" closable @close="error = null">
        {{ error }}
      </n-alert>

      <n-spin :show="loading">
        <n-data-table
          :columns="columns"
          :data="filteredUsers"
          :bordered="false"
          :pagination="pagination"
          :row-key="rowKey"
          class="user-table"
        />
      </n-spin>
    </n-space>
  </n-card>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NDataTable,
  NInput,
  NSpin,
  NTag,
  NSpace,
  type DataTableColumns
} from 'naive-ui'

import { AdminAPI, type AdminUser } from '@/api/admin'

const users = ref<AdminUser[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const keyword = ref('')

const pagination = reactive({
  page: 1,
  pageSize: 10,
  showSizePicker: false
})

const columns: DataTableColumns<AdminUser> = [
  {
    title: 'ID',
    key: 'id',
    sorter: (a, b) => a.id - b.id,
    width: 80
  },
  {
    title: '用户名',
    key: 'username',
    ellipsis: { tooltip: true }
  },
  {
    title: '邮箱',
    key: 'email',
    ellipsis: { tooltip: true },
    render(row) {
      return row.email || '—'
    }
  },
  {
    title: '权限',
    key: 'is_admin',
    align: 'center',
    render(row) {
      return h(
        NTag,
        {
          type: row.is_admin ? 'success' : 'default',
          bordered: false,
          size: 'small'
        },
        { default: () => (row.is_admin ? '管理员' : '普通用户') }
      )
    }
  }
]

const filteredUsers = computed(() => {
  if (!keyword.value.trim()) {
    return users.value
  }
  const q = keyword.value.trim().toLowerCase()
  return users.value.filter(
    (user) =>
      user.username.toLowerCase().includes(q) ||
      (user.email && user.email.toLowerCase().includes(q))
  )
})

const rowKey = (row: AdminUser) => row.id

const fetchUsers = async () => {
  loading.value = true
  error.value = null
  try {
    users.value = await AdminAPI.listUsers()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '获取用户数据失败'
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.page = 1
}

onMounted(fetchUsers)
</script>

<style scoped>
.admin-card {
  width: 100%;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.card-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: #1f2937;
}

.search-input {
  width: min(230px, 60vw);
}

@media (max-width: 767px) {
  .card-header {
    flex-direction: column;
    align-items: stretch;
  }

  .card-title {
    font-size: 1.125rem;
  }

  .search-input {
    width: 100%;
  }
}
</style>

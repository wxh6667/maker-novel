<script setup lang="ts">
import { RouterView } from 'vue-router'
import CustomAlert from '@/components/CustomAlert.vue'
import { globalAlert } from '@/composables/useAlert'
</script>

<template>
  <div>
    <RouterView />

    <!-- 全局提示框 -->
    <CustomAlert
      v-for="alert in globalAlert.alerts.value"
      :key="alert.id"
      :visible="alert.visible"
      :type="alert.type"
      :title="alert.title"
      :message="alert.message"
      :show-cancel="alert.showCancel"
      :confirm-text="alert.confirmText"
      :cancel-text="alert.cancelText"
      @confirm="globalAlert.closeAlert(alert.id, true)"
      @cancel="globalAlert.closeAlert(alert.id, false)"
      @close="globalAlert.closeAlert(alert.id, false)"
    />
  </div>
</template>

<style scoped>
</style>

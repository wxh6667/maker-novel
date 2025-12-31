<template>
  <div class="min-h-screen p-4 relative">
    <div class="absolute top-4 left-4">
      <router-link
        to="/"
        class="px-4 py-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors flex items-center gap-2"
      >
        &larr; 返回
      </router-link>
    </div>
    <div class="max-w-6xl mx-auto mt-16">
      <ProviderManagement />
    </div>
  </div>
</template>

<script setup lang="ts">
import ProviderManagement from '@/components/ProviderManagement.vue';
</script>

<template>
  <h1 class="typewriter text-4xl md:text-5xl font-extrabold text-center text-gray-800 tracking-wider" :style="{ '--char-count': fullText.length }">
    {{ displayedText }}
  </h1>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';

const props = defineProps({
  text: {
    type: String,
    required: true,
  },
});

const fullText = props.text;
const displayedText = ref('');
let index = 0;

onMounted(() => {
  const interval = setInterval(() => {
    if (index < fullText.length) {
      displayedText.value += fullText.charAt(index);
      index++;
    } else {
      clearInterval(interval);
    }
  }, 150); // Adjust typing speed here
});
</script>

<style scoped>
.typewriter {
  display: inline-block;
  overflow: hidden;
  white-space: nowrap;
  border-right: 0.1em solid #333; /* Blinking cursor */
  animation: typing 2s steps(var(--char-count, 10), end), blink-caret 0.75s step-end infinite;
  width: 100%;
}

/* Typing effect */
@keyframes typing {
  from {
    width: 0;
  }
  to {
    width: 100%;
  }
}

/* Cursor blinking effect */
@keyframes blink-caret {
  from,
  to {
    border-color: transparent;
  }
  50% {
    border-color: #333;
  }
}
</style>

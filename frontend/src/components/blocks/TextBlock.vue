<script setup lang="ts">
defineProps<{
  block: {
    block_type: 'text_block'
    content: string
    format?: 'plain' | 'markdown'
  }
}>()
</script>

<template>
  <el-card shadow="hover" class="text-block">
    <div 
      class="content"
      :class="{ 'markdown-content': block.format === 'markdown' }"
      v-html="block.content"
    ></div>
  </el-card>
</template>

<style scoped>
.text-block {
  max-width: 100%;
}

.content {
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.markdown-content {
  white-space: normal;
}
</style>

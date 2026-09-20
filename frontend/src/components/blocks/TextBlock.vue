<script setup lang="ts">
import { computed } from 'vue'
import DOMPurify from 'dompurify'
import MarkdownRenderer from '@/components/llm-markdown-render/MarkdownRenderer.vue'

const props = defineProps<{
  block: {
    block_type: 'text_block'
    content: string
    format?: 'plain' | 'markdown'
  }
}>();

// 纯文本模式：DOMPurify 净化后渲染（防模型/上游接口返回的脚本注入）
// markdown 模式：复用 MarkdownRenderer（底层 markdown-it html:false，原生 HTML 不执行）
const safeHtml = computed(() =>
  DOMPurify.sanitize(props.block.content ?? '', {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'br', 'p', 'ul', 'ol', 'li', 'code', 'pre'],
    ALLOWED_ATTR: [],
  }),
);
const isMarkdown = computed(() => props.block.format === 'markdown');
</script>

<template>
  <el-card shadow="hover" class="text-block">
    <div v-if="isMarkdown" class="content markdown-content">
      <MarkdownRenderer :content="props.block.content" />
    </div>
    <div
      v-else
      class="content"
      v-html="safeHtml"
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

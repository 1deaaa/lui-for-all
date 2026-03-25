<script setup lang="ts">
import { computed } from 'vue'
import type { UIBlock } from '@/vite-env.d'

// 导入各个 Block 组件
import TextBlock from './blocks/TextBlock.vue'
import MetricCard from './blocks/MetricCard.vue'
import DataTable from './blocks/DataTable.vue'
import EchartCard from './blocks/EchartCard.vue'
import ConfirmPanel from './blocks/ConfirmPanel.vue'
import FilterForm from './blocks/FilterForm.vue'
import TimelineCard from './blocks/TimelineCard.vue'
import DiffCard from './blocks/DiffCard.vue'

const props = defineProps<{
  block: UIBlock
}>()

// 根据 block_type 确定组件
const blockComponent = computed(() => {
  switch (props.block.block_type) {
    case 'text_block':
      return TextBlock
    case 'metric_card':
      return MetricCard
    case 'data_table':
      return DataTable
    case 'echart_card':
      return EchartCard
    case 'confirm_panel':
      return ConfirmPanel
    case 'filter_form':
      return FilterForm
    case 'timeline_card':
      return TimelineCard
    case 'diff_card':
      return DiffCard
    default:
      return TextBlock
  }
})
</script>

<template>
  <div class="block-renderer">
    <!-- @vue-ignore -->
    <component :is="blockComponent" :block="block" />
  </div>
</template>

<style scoped>
.block-renderer {
  margin-bottom: 16px;
}
</style>

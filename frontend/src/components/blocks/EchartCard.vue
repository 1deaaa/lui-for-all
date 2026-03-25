<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import * as echarts from 'echarts'

const props = defineProps<{
  block: {
    block_type: 'echart_card'
    title?: string
    chart_type: string
    option: Record<string, any>
    height: number
  }
}>()

const chartRef = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null

// 合并默认配置
const chartOption = computed(() => {
  return {
    tooltip: {
      trigger: 'axis',
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true,
    },
    ...props.block.option,
  }
})

// 初始化图表
function initChart() {
  if (!chartRef.value) return
  
  chartInstance = echarts.init(chartRef.value)
  chartInstance.setOption(chartOption.value)
}

// 更新图表
function updateChart() {
  if (chartInstance) {
    chartInstance.setOption(chartOption.value)
  }
}

// 监听配置变化
watch(() => props.block.option, updateChart, { deep: true })

onMounted(() => {
  initChart()
})
</script>

<template>
  <el-card shadow="hover" class="echart-card">
    <template #header v-if="block.title">
      <span>{{ block.title }}</span>
    </template>
    
    <div 
      ref="chartRef" 
      class="chart-container"
      :style="{ height: `${block.height || 300}px` }"
    ></div>
  </el-card>
</template>

<style scoped>
.echart-card {
  max-width: 100%;
}

.chart-container {
  width: 100%;
}
</style>

<template>
  <div class="echarts-block" :style="wrapperStyle">
    <div
      v-show="loading"
      class="loading-overlay"
    >
      <span class="loading-text">图表渲染中</span>
      <div class="wiggle-box"></div>
    </div>
    <div class="echarts-container" ref="echartsContainer" :style="containerStyle"></div>
    <button class="download-btn" @click="downloadChart" title="下载图表">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M8 1V10M8 10L5 7M8 10L11 7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M3 10V12C3 13.1046 3.89543 14 5 14H11C12.1046 14 13 13.1046 13 12V10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
      </svg>
    </button>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import {
  TooltipComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  DatasetComponent,
  ToolboxComponent,
  VisualMapComponent,
  SingleAxisComponent,
  DataZoomComponent,
  GraphicComponent,
  MarkPointComponent,
  MarkLineComponent,
  MarkAreaComponent,
  TimelineComponent,
  GridSimpleComponent,
  BrushComponent,
  CalendarComponent,
} from 'echarts/components'
import { BarChart, LineChart, PieChart, ScatterChart, RadarChart, TreeChart, TreemapChart, GraphChart, GaugeChart, FunnelChart, ParallelChart, SankeyChart, BoxplotChart, CandlestickChart, EffectScatterChart, LinesChart, HeatmapChart, PictorialBarChart, ThemeRiverChart, SunburstChart } from 'echarts/charts'
import { UniversalTransition } from 'echarts/features'
import { CanvasRenderer } from 'echarts/renderers'
import 'echarts-wordcloud'

echarts.use([
  TooltipComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  DatasetComponent,
  ToolboxComponent,
  VisualMapComponent,
  SingleAxisComponent,
  DataZoomComponent,
  GraphicComponent,
  MarkPointComponent,
  MarkLineComponent,
  MarkAreaComponent,
  TimelineComponent,
  GridSimpleComponent,
  BrushComponent,
  CalendarComponent,
  BarChart,
  LineChart,
  PieChart,
  ScatterChart,
  RadarChart,
  TreeChart,
  TreemapChart,
  GraphChart,
  GaugeChart,
  FunnelChart,
  ParallelChart,
  SankeyChart,
  BoxplotChart,
  CandlestickChart,
  EffectScatterChart,
  LinesChart,
  HeatmapChart,
  PictorialBarChart,
  ThemeRiverChart,
  SunburstChart,
  UniversalTransition,
  CanvasRenderer,
])

const props = defineProps({
  config: {
    type: String,
    default: '{}',
  },
})
const loading = ref<boolean>(true)
const option = ref()
const echartsContainer = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null
let observer: ResizeObserver
const containerStyle = ref<Record<string, string>>({})
const wrapperStyle = ref<Record<string, string>>({ display: 'block', width: '100%', maxWidth: '100%', position: 'relative', background: '#fff' })

const computeDesiredWidth = (opt: any): number | null => {
  if (!opt || typeof opt !== 'object') return null
  // Heuristic based on category axis length
  const getLen = (axis: any): number => {
    if (!axis) return 0
    const a = Array.isArray(axis) ? axis : axis
    const data = a?.data
    return Array.isArray(data) ? data.length : 0
  }
  const xLen = getLen(opt.xAxis)
  const yLen = getLen(opt.yAxis)
  let desired: number | null = null
  if (xLen > 0) desired = Math.max(600, Math.min(2400, xLen * 80))
  // Horizontal bar charts often use yAxis categories
  if (!desired && yLen > 0) desired = Math.max(600, Math.min(2400, yLen * 80))
  return desired
}

const renderCharts = () => {
  if (!echartsContainer.value) return

  if (!chart) {
    const rect = echartsContainer.value.getBoundingClientRect()
    if (rect.width === 0) {
      setTimeout(renderCharts, 50)
      return
    }
    chart = echarts.init(echartsContainer.value)

    observer = new ResizeObserver(() => {
      chart?.resize()
    })
    observer.observe(echartsContainer.value)
  }

  if (option.value) {
    loading.value = false
    chart?.setOption(option.value)
    // update container min width heuristically and resize
    const desired = computeDesiredWidth(option.value)
    if (desired) {
      containerStyle.value = { minWidth: `${desired}px` }
    } else {
      containerStyle.value = {}
    }
    // No need to call resize manually, ResizeObserver will handle it.
    // nextTick(() => chart?.resize())
  }
}

watch(
  () => props.config,
  (val) => {
    try {
      // 通过正则表达式精确提取从第一个 { 到最后一个 } 的完整JSON对象字符串
      const match = val.match(/\{[\s\S]*\}/);
      if (!match) {
        throw new Error("在传入的配置中找不到有效的JSON对象");
      }
      const jsonStr = match;
      
      // 使用 new Function() 来解析包含函数的JS对象字符串，比eval更安全
      const func = new Function(`return (${jsonStr})`);
      option.value = func();
      renderCharts()
    } catch (err) {
      console.error('解析Echarts配置失败:', err, val);
      loading.value = true
    }
  },
  { immediate: true },
)

// 下载图表为图片
const downloadChart = () => {
  if (!chart) return
  
  try {
    // 获取图表的图片数据URL
    const dataUrl = chart.getDataURL({
      type: 'png',
      pixelRatio: 2, // 高分辨率
      backgroundColor: '#fff'
    })
    
    // 创建下载链接
    const link = document.createElement('a')
    link.download = 'echarts-chart.png'
    link.href = dataUrl
    link.click()
  } catch (error) {
    console.error('下载图表失败:', error)
  }
}

onMounted(() => {
  renderCharts()
})
onBeforeUnmount(() => {
  observer?.disconnect()
  chart?.dispose()
})

// 暴露方法给父组件
defineExpose({
  downloadChart
})
</script>

<style scoped>
.echarts-block {
  position: relative;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  margin: 16px 0;
  padding: 8px;
  overflow: hidden; /* 防止跨容器溢出叠加 */
  isolation: isolate; /* 独立堆叠上下文 */
  background: #fff;
}
.echarts-container {
  min-height: 400px;
  width: 100%;
}
.echarts-container canvas { display: block; }
.loading-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  z-index: 10;
  pointer-events: none;
  background: linear-gradient(90deg, rgba(0,0,0,0.02), rgba(0,0,0,0));
}
.loading-text {
  font-weight: 700;
  font-size: 1.1rem;
  background: linear-gradient(90deg, #22c55e, #3b82f6, #8b5cf6);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: pulse 1.2s ease-in-out infinite;
}
.wiggle-box {
  width: 20px;
  height: 20px;
  border-radius: 4px;
  background: #22c55e;
  animation: wiggle 1s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}
@keyframes wiggle {
  0%, 100% { transform: translateX(0); }
  50% { transform: translateX(6px); }
}

.download-btn {
  position: absolute;
  top: 12px;
  right: 12px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 6px;
  cursor: pointer;
  z-index: 10;
  transition: all 0.2s ease;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.download-btn:hover {
  background: #fff;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
}

.download-btn svg {
  display: block;
  color: #6b7280;
}
</style>
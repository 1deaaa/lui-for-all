<template>
  <div class="mermaid-block" :style="wrapperStyle">
    <!-- 加载状态 -->
    <div v-show="loading && !error" class="loading-overlay">
      <span class="loading-text">{{ t('charts.mermaidRendering') }}</span>
      <div class="wiggle-box blue"></div>
    </div>

    <!-- 错误状态 -->
    <div v-show="error" class="error-overlay">
      <div class="text-red-500">
        <svg class="h-12 w-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"
          />
        </svg>
      </div>
      <span class="text-red-600 font-medium">{{ t('charts.mermaidRenderFailed') }}</span>
      <button
        @click="retryRender"
        class="retry-btn"
      >
        {{ t('charts.retry') }}
      </button>
    </div>

    <div class="mermaid-container" :style="containerStyle" ref="mermaidContainer"></div>
    <button class="download-btn" @click="downloadChart" :title="t('charts.downloadChart')">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M8 1V10M8 10L5 7M8 10L11 7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M3 10V12C3 13.1046 3.89543 14 5 14H11C12.1046 14 13 13.1046 13 12V10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
      </svg>
    </button>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch, onBeforeUnmount } from 'vue'
import mermaid from 'mermaid'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  config: {
    type: String,
    default: '',
  },
})
const { t } = useI18n()

// 初始加载状态取决于是否有配置内容
const loading = ref<boolean>(!!props.config?.trim())
const error = ref<boolean>(false)
const mermaidContainer = ref<HTMLDivElement>()
let renderTimer: ReturnType<typeof setTimeout> | null = null
const wrapperStyle = ref<Record<string, string>>({ display: 'block', width: '100%', maxWidth: '100%', position: 'relative', background: '#fff' })
const containerStyle = ref<Record<string, string>>({})
const genRenderId = () =>
  `mermaid-${(globalThis.crypto && 'randomUUID' in globalThis.crypto)
    ? (globalThis.crypto as any).randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`}`

const htmlDecode = (s: string) =>
  s
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&#39;|&apos;/g, "'")

const normalizeMermaidCode = (src: string) => {
  let code = src
  // Normalize line breaks
  code = code.replace(/\r\n?|\u2028|\u2029/g, '\n')
  // Decode HTML entities possibly introduced by upstream
  code = htmlDecode(code)
  // Replace non-breaking and thin spaces with normal space
  code = code.replace(/[\u00A0\u2000-\u200B]/g, ' ')
  // Ensure key directives start on their own line if squashed
  const tokens = [
    'x-axis',
    'y-axis',
    'title',
    'data:',
    'quadrant-1',
    'quadrant-2',
    'quadrant-3',
    'quadrant-4',
    'section',
    'dateFormat',
    'excludes',
    'axisFormat',
    'tickInterval',
    'todayMarker',
  ]
  const tokenPattern = new RegExp(`(?<!^)\s+(?=${tokens.map(t => t.replace(/[.*+?^${}()|[\]\\-]/g, '\\$&')).join('|')})`, 'gm')
  code = code.replace(tokenPattern, '\n')
  return code
}

const computeDesiredWidth = (code: string): number | null => {
  if (!code) return null
  const lines = code.split(/\r?\n/).map(l => l.trim()).filter(Boolean)
  const maxChars = Math.max(0, ...lines.map(l => l.length))
  const participants = lines.filter(l => /^participant\s+/i.test(l)).length
  const ganttTasks = lines.filter(l => /:\s*(done|active|crit|\d+d|\d+h)/i.test(l)).length
  let base = Math.max(maxChars * 9, participants * 180, ganttTasks * 140)
  if (!base || !isFinite(base)) return null
  return Math.max(600, Math.min(2400, Math.round(base)))
}

// 初始化mermaid
mermaid.initialize({
  startOnLoad: false,
  theme: 'default',
  securityLevel: 'loose',
  flowchart: {
    useMaxWidth: true,
  },
})

const renderChart = async () => {
  if (!mermaidContainer.value) {
    return
  }

  // 如果没有配置内容，不显示图表但也不显示加载状态
  if (!props.config || !props.config.trim()) {
    loading.value = false
    error.value = false
    if (mermaidContainer.value) {
      mermaidContainer.value.innerHTML = ''
    }
    return
  }

  const raw = props.config.trim()
  let code = normalizeMermaidCode(raw)
  let triedFallback = false

  try {
    // 开始渲染时显示加载状态
    loading.value = true
    error.value = false

    // 清空容器
    mermaidContainer.value.innerHTML = ''

    // 渲染mermaid图表
    const { svg } = await mermaid.render(genRenderId(), code)

    // 将生成的SVG插入到容器中
    mermaidContainer.value.innerHTML = svg

    // 估算并设置最小宽度，便于横向滚动展示完整图
    const desired = computeDesiredWidth(code)
    if (desired) {
      containerStyle.value = { minWidth: `${desired}px`, width: '100%' }
    } else {
      containerStyle.value = { width: '100%' }
    }

    // 渲染完成，隐藏加载状态
    loading.value = false
  } catch (err) {
    // One-time aggressive fallback: split long lines by 2+ spaces for quadrant/er diagrams
    if (!triedFallback) {
      triedFallback = true
      const looksQuadrant = /\bquadrant/i.test(code)
      const looksER = /\berDiagram\b/i.test(code)
      if (looksQuadrant || looksER) {
        try {
          const fallback = code
            // Insert newlines before well-known directives again
            .replace(/\s{2,}(x-axis|y-axis|title|data:|quadrant-[1-4])\b/gi, '\n$1')
            // Break overly long lines on '  '
            .replace(/([^\n]{120,}?)\s{2,}/g, '$1\n')
          const { svg } = await mermaid.render(genRenderId(), fallback)
          mermaidContainer.value.innerHTML = svg
          const desired = computeDesiredWidth(fallback)
          containerStyle.value = desired ? { minWidth: `${desired}px`, width: '100%' } : { width: '100%' }
          loading.value = false
          error.value = false
          return
        } catch (e2) {
          console.error('Mermaid fallback render error:', e2)
        }
      }
    }

    console.error('Mermaid rendering error:', err)
    error.value = true
    loading.value = false
    if (mermaidContainer.value) mermaidContainer.value.innerHTML = ''
  }
}

// 防抖渲染函数
const debouncedRender = () => {
  if (renderTimer) {
    clearTimeout(renderTimer)
  }
  renderTimer = setTimeout(() => {
    renderChart()
  }, 300) // 300ms 防抖
}

const retryRender = () => {
  renderChart()
}

watch(
  () => props.config,
  () => {
    // 当配置改变时，立即显示加载状态
    if (props.config && props.config.trim()) {
      loading.value = true
      error.value = false
    }
    debouncedRender()
  },
  { immediate: true },
)

// 下载图表为图片
const downloadChart = async () => {
  if (!mermaidContainer.value) return
  
  try {
    // 获取SVG元素
    const svgElement = mermaidContainer.value.querySelector('svg')
    if (!svgElement) {
      console.error('未找到SVG元素')
      return
    }
    
    // 获取SVG的XML内容
    const svgData = new XMLSerializer().serializeToString(svgElement)
    
    // 创建Canvas元素
    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')
    if (!ctx) {
      console.error('无法获取Canvas上下文')
      return
    }
    
    // 创建Image对象
    const img = new Image()
    
    // 设置Canvas大小
    const rect = svgElement.getBoundingClientRect()
    canvas.width = rect.width * 2  // 两倍分辨率
    canvas.height = rect.height * 2
    
    // 设置图片源
    const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' })
    const url = URL.createObjectURL(svgBlob)
    
    img.onload = () => {
      // 绘制到Canvas
      ctx.fillStyle = '#ffffff'
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
      
      // 转换为图片数据URL
      const pngData = canvas.toDataURL('image/png')
      
      // 创建下载链接
      const link = document.createElement('a')
      link.download = 'mermaid-chart.png'
      link.href = pngData
      link.click()
      
      // 清理
      URL.revokeObjectURL(url)
    }
    
    img.onerror = () => {
      console.error('图片加载失败')
      URL.revokeObjectURL(url)
    }
    
    img.src = url
  } catch (error) {
    console.error('下载图表失败:', error)
  }
}

onMounted(() => {
  // 组件挂载时，如果有配置就显示加载状态
  if (props.config && props.config.trim()) {
    loading.value = true
    error.value = false
  }
  renderChart()
})

onBeforeUnmount(() => {
  if (renderTimer) {
    clearTimeout(renderTimer)
  }
})

// 暴露方法给父组件
defineExpose({
  downloadChart
})
</script>

<style scoped>
.mermaid-block {
  position: relative;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  margin: 16px 0;
  padding: 8px;
  overflow: hidden; /* 防止跨容器溢出叠加 */
  isolation: isolate; /* 独立堆叠上下文，避免滤镜/marker 交叉影响 */
}
.mermaid-container {
  min-height: 400px;
  width: 100%;
  position: relative;
}
.mermaid-container svg {
  display: block;
  max-width: 100%;
}
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
  background: #3b82f6;
  animation: wiggle 1s ease-in-out infinite;
}
.wiggle-box.blue { background: #3b82f6; }
.error-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  z-index: 10;
  background: #fef2f2;
}
.retry-btn {
  padding: 8px 16px;
  background: #ef4444;
  color: #fff;
  border-radius: 6px;
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

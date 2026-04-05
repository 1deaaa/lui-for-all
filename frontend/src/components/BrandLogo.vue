<template>
  <svg class="brand-logo" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" :width="size" :height="size">
    <defs>
      <!-- 
        负空间掩码：中央留白区让四角星独立悬浮，
        掩码圆的半径经过精算，恰好包裹星芒尖端并留出 2px 视觉呼吸间距
      -->
      <mask :id="maskId">
        <rect width="100" height="100" fill="white" />
        <!-- 椭圆掩码：沿四角星对角线方向微微拉伸，让星芒尖角处的间隙更均匀 -->
        <circle cx="50" cy="50" r="24" fill="black" />
      </mask>
    </defs>
    
    <!-- 
      ═══════════════════════════════════════════════
      LUI-for-All 品牌标识 · 终极版
      ═══════════════════════════════════════════════
      概念：自然语言穿透代码结构的颠覆性隐喻
      
      ① 外轮廓 = 等距正方体的角尖朝正下方的投影（正六边形）
         → 象征代码世界的严谨结构
      ② 内部 Y 型骨架 = 立方体的三条朝向观察者的前端棱边
         → 赋予平面以空间深度（伪立体核心技法）
      ③ 背侧虚线 = 立方体不可见面的三条隐藏棱
         → 暗示被 AI 洞察的隐藏结构
      ④ 中央四芒星 = 智能核心
         → 悬浮在负空间中，利用掩码斩断周围骨架线，
            模拟无滤镜的纯矢量"发光"效果
    -->
    
    <!-- ─── 层 1：外轮廓六边形（等距正方体投影边界） ─── -->
    <polygon 
      points="50,6 88,28 88,72 50,94 12,72 12,28" 
      fill="none" 
      stroke="currentColor" 
      stroke-width="3.5" 
      stroke-linejoin="round" 
    />
    
    <!-- ─── 层 2：内部空间骨架（被中央光芒掩码切割） ─── -->
    <g :mask="`url(#${maskId})`">
      <!-- 背侧隐线：立方体远端三条不可见棱边（低透明度虚线） -->
      <line x1="50" y1="50" x2="50" y2="6" stroke="currentColor" stroke-width="1.2" opacity="0.22" stroke-dasharray="3,4" />
      <line x1="50" y1="50" x2="88" y2="72" stroke="currentColor" stroke-width="1.2" opacity="0.22" stroke-dasharray="3,4" />
      <line x1="50" y1="50" x2="12" y2="72" stroke="currentColor" stroke-width="1.2" opacity="0.22" stroke-dasharray="3,4" />
      
      <!-- 前端阳线：立方体朝向观察者的三条实体棱边（Y 型放射） -->
      <line x1="50" y1="50" x2="88" y2="28" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" />
      <line x1="50" y1="50" x2="50" y2="94" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" />
      <line x1="50" y1="50" x2="12" y2="28" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" />
    </g>

    <!-- ─── 层 3：AI 四芒智能星（贝塞尔曲线 + 负空间发光） ─── -->
    <!-- 
      四条三次贝塞尔曲线，控制点精心调校：
      - 内收控制点位于 (50±4, 50±4) → 星芒根部极细锐
      - 外尖端距中心 22px → 芒尖恰好触碰掩码边界，形成无缝"光芒切断骨架"效果
    -->
    <path 
      d="
        M 50 28
        C 46 46, 46 46, 28 50
        C 46 54, 46 54, 50 72
        C 54 54, 54 54, 72 50
        C 54 46, 54 46, 50 28
        Z
      " 
      fill="currentColor" 
    />
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps({
  size: {
    type: [Number, String],
    default: 28
  }
})

// 为每个实例生成唯一 mask ID，避免多个 Logo 同时渲染时 SVG mask 冲突
const maskId = computed(() => `lui-glow-mask-${Math.random().toString(36).slice(2, 8)}`)
</script>

<style scoped>
.brand-logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
</style>

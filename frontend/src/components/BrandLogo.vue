<template>
  <svg class="brand-logo" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" :width="size" :height="size">
    <defs>
      <!-- 使用负空间掩码，制造出发光四角星排开周围结构的纯净发光感 -->
      <mask id="lui-glow-mask">
        <rect width="100" height="100" fill="white" />
        <circle cx="50" cy="50" r="28" fill="black" />
      </mask>
    </defs>
    
    <!-- 
      平面伪立体的最高境界：等距视角结构线框
      一个纯正方体，由一个角直面（正下方），角向正前方突出，视觉中心精确处于(50,50)
    -->
    
    <!-- 外部轮廓六边形：等距立体正方体的 2D 外边界线 -->
    <polygon points="50,8 86.37,29 86.37,71 50,92 13.63,71 13.63,29" fill="none" stroke="currentColor" stroke-width="4.5" stroke-linejoin="round" />
    
    <!-- 内部空间骨架被中央的光芒推开（包裹在Mask下） -->
    <g mask="url(#lui-glow-mask)">
      <!-- 远端不可见界面的背侧延长线（带来透视与深度的交织感） -->
      <line x1="50" y1="50" x2="50" y2="8" stroke="currentColor" stroke-width="1.5" opacity="0.35" stroke-linecap="round" />
      <line x1="50" y1="50" x2="86.37" y2="71" stroke="currentColor" stroke-width="1.5" opacity="0.35" stroke-linecap="round" />
      <line x1="50" y1="50" x2="13.63" y2="71" stroke="currentColor" stroke-width="1.5" opacity="0.35" stroke-linecap="round" />
      
      <!-- 前端直面视觉的三条阳线棱边（Y型放射） -->
      <line x1="50" y1="50" x2="86.37" y2="29" stroke="currentColor" stroke-width="4.5" stroke-linecap="round" />
      <line x1="50" y1="50" x2="50" y2="92" stroke="currentColor" stroke-width="4.5" stroke-linecap="round" />
      <line x1="50" y1="50" x2="13.63" y2="29" stroke="currentColor" stroke-width="4.5" stroke-linecap="round" />
    </g>

    <!-- 
      象征“AI 智能”内驱力的完美平滑四芒星
      利用二次贝塞尔曲线的张力悬浮于镂空的心脏之中，与四角透视光芒交相呼应
    -->
    <path d="M 50 24 Q 50 50 76 50 Q 50 50 50 76 Q 50 50 24 50 Q 50 50 50 24 Z" fill="currentColor" />
  </svg>
</template>

<script setup lang="ts">
defineProps({
  size: {
    type: [Number, String],
    default: 28
  }
})
</script>

<style scoped>
.brand-logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
</style>

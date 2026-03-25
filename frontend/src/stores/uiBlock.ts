import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { UIBlock } from '@/vite-env.d'

export const useUiBlockStore = defineStore('uiBlock', () => {
  // 当前显示的 UI Blocks
  const blocks = ref<UIBlock[]>([])
  const activeBlockIndex = ref<number>(0)

  // 添加 Block
  function addBlock(block: UIBlock) {
    blocks.value.push(block)
    activeBlockIndex.value = blocks.value.length - 1
  }

  // 清空 Blocks
  function clearBlocks() {
    blocks.value = []
    activeBlockIndex.value = 0
  }

  // 设置活跃 Block
  function setActiveBlock(index: number) {
    if (index >= 0 && index < blocks.value.length) {
      activeBlockIndex.value = index
    }
  }

  // 移除指定 Block
  function removeBlock(index: number) {
    if (index >= 0 && index < blocks.value.length) {
      blocks.value.splice(index, 1)
      if (activeBlockIndex.value >= blocks.value.length) {
        activeBlockIndex.value = Math.max(0, blocks.value.length - 1)
      }
    }
  }

  return {
    blocks,
    activeBlockIndex,
    addBlock,
    clearBlocks,
    setActiveBlock,
    removeBlock,
  }
})

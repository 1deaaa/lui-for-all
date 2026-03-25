<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps<{
  block: {
    block_type: 'data_table'
    title?: string
    columns: Array<{
      key: string
      label: string
      width?: number
      sortable?: boolean
      type?: string
    }>
    rows: Array<Record<string, any>>
    total: number
    page: number
    page_size: number
  }
}>()

// 当前页
const currentPage = ref(props.block.page || 1)
const pageSize = ref(props.block.page_size || 10)

// 计算分页后的数据
const paginatedRows = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return props.block.rows.slice(start, end)
})

// 页码变化
function handlePageChange(page: number) {
  currentPage.value = page
}
</script>

<template>
  <el-card shadow="hover" class="data-table">
    <template #header v-if="block.title">
      <span>{{ block.title }}</span>
    </template>
    
    <el-table :data="paginatedRows" style="width: 100%">
      <el-table-column
        v-for="col in block.columns"
        :key="col.key"
        :prop="col.key"
        :label="col.label"
        :width="col.width"
        :sortable="col.sortable"
      >
        <template #default="{ row }">
          <template v-if="col.type === 'tag'">
            <el-tag size="small">{{ row[col.key] }}</el-tag>
          </template>
          <template v-else-if="col.type === 'link'">
            <el-link type="primary" :href="row[col.key]">{{ row[col.key] }}</el-link>
          </template>
          <template v-else>
            {{ row[col.key] }}
          </template>
        </template>
      </el-table-column>
    </el-table>
    
    <div class="pagination" v-if="block.total > block.page_size">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="block.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @current-change="handlePageChange"
      />
    </div>
  </el-card>
</template>

<style scoped>
.data-table {
  max-width: 100%;
}

.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>

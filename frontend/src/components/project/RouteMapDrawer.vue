<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { Check, Close } from '@element-plus/icons-vue'
import { Icon } from '@iconify/vue'

import { useProjectStore } from '@/stores/project'

const projectStore = useProjectStore()

const projectId = computed(() => projectStore.currentProject?.id || '')
const routeMap = computed(() => projectStore.currentRouteMap)
const capabilities = computed(() => projectStore.currentCapabilities)
const isLoading = computed(() => projectStore.isDetailsLoading)

const isReady = computed(() => routeMap.value && capabilities.value.length > 0)

const visible = ref(false)

const openDrawer = () => {
  visible.value = true
}

// 搜索过滤
const searchKeyword = ref('')
const filteredRoutes = computed(() => {
  let list = routeMap.value?.routes || []
  const kw = searchKeyword.value.trim().toLowerCase()
  if (kw) {
    list = list.filter((r: any) => 
      (r.path || '').toLowerCase().includes(kw) ||
      (r.summary || '').toLowerCase().includes(kw) ||
      (r.method || '').toLowerCase().includes(kw)
    )
  }
  return list
})

const currentPage = ref(1)
const pageSize = ref(25)

watch(searchKeyword, () => {
  currentPage.value = 1
})

const pagedRoutes = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredRoutes.value.slice(start, start + pageSize.value)
})

// 解析已识别和未识别路由
const identifiedRouteMap = computed(() => {
  const map = new Map<string, any>()
  for (const cap of capabilities.value) {
    for (const r of cap.backed_by_routes || []) {
      map.set(r.route_id, cap)
    }
  }
  return map
})

// 判断特定路由是否被纳管
function getAssignedCapability(routeId: string) {
  return identifiedRouteMap.value.get(routeId)
}

function getMethodType(method: string): string {
  if (method === 'GET') return 'success'
  if (method === 'DELETE') return 'danger'
  if (method === 'POST') return 'warning'
  return 'info'
}

// 修改权限更新
const updatingMap = ref<Record<string, boolean>>({})

async function handlePermissionChange(cap: any, newPermission: string) {
  updatingMap.value[cap.capability_id] = true
  try {
    await axios.patch(`/api/projects/${projectId.value}/capabilities/${cap.capability_id}`, {
      permission_level: newPermission
    })
    ElMessage.success('权限更新成功')
    cap.permission_level = newPermission
  } catch (err: any) {
    ElMessage.error('更新失败: ' + (err?.response?.data?.detail || err.message))
  } finally {
    updatingMap.value[cap.capability_id] = false
  }
}

const permissionOptions = [
  { value: 'none', label: '无权限控制' },
  { value: 'authenticated', label: '需登录 (Authenticated)' },
  { value: 'operator', label: '操作员 (Operator)' },
  { value: 'admin', label: '管理员 (Admin)' }
]

function getRowClassName({ row }: { row: { route_id: string } }): string {
  return getAssignedCapability(row.route_id) ? 'identified-row' : 'ignored-row'
}
</script>

<template>
  <div class="route-map-analyzer">
    <!-- Trigger Button -->
    <el-button
      type="info"
      plain
      class="analyzer-trigger-btn custom-analyzer-btn"
      :disabled="isLoading || !isReady"
      @click="openDrawer"
      :title="isLoading ? '正在预加载项目全量接口数据...' : (isReady ? '查看当前项目全量接口映射图谱' : '项目正准备中...无接口数据')"
    >
      <Icon v-if="isLoading" icon="solar:spinner-bold-duotone" class="btn-icon is-loading" />
      <Icon v-else icon="solar:route-bold-duotone" class="btn-icon" />
      <span>{{ isLoading ? '预加载中' : '查看路由图谱' }}</span>
    </el-button>

    <el-drawer
      v-model="visible"
      size="75%"
      :with-header="false"
      class="route-map-drawer"
    >
      <div class="drawer-content">
        <!-- 搜索与控制面板 -->
        <div class="search-bar">
          <el-input 
            v-model="searchKeyword" 
            placeholder="搜索：输入 URL 路径、方法类型或业务摘要..."
            clearable
            class="top-search-input"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>

        <div class="drawer-header-stats">
          <div class="stat-box">
            <Icon icon="solar:route-bold-duotone" class="stat-icon" />
            <div class="stat-info">
              <span class="stat-num">{{ routeMap?.routes?.length || 0 }}</span>
              <span class="stat-label">总路由数</span>
            </div>
          </div>
          <div class="stat-box success-box">
            <Icon icon="solar:brain-bold-duotone" class="stat-icon" />
            <div class="stat-info">
              <span class="stat-num">{{ identifiedRouteMap.size }}</span>
              <span class="stat-label">AI 已识别调度</span>
            </div>
          </div>
          <div class="stat-box unknown-box">
            <Icon icon="solar:ghost-bold-duotone" class="stat-icon" />
            <div class="stat-info">
              <span class="stat-num">{{ (routeMap?.routes?.length || 0) - identifiedRouteMap.size }}</span>
              <span class="stat-label">未识别/被忽略</span>
            </div>
          </div>
        </div>

        <div class="table-wrapper">
          <el-table 
            :data="pagedRoutes" 
            style="width: 100%" 
            height="100%"
            class="custom-table"
            :row-class-name="getRowClassName"
          >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="expanded-params-container">
              <div v-if="row.parameters?.length > 0" class="param-section">
                <div class="param-title">URL / Query 参数:</div>
                <div v-for="p in row.parameters" :key="p.name" class="param-item">
                  <span class="param-name">{{ p.name }}</span>
                  <el-tag size="small" type="info" class="param-type">{{ p.type_hint }}</el-tag>
                  <span v-if="p.required" class="param-req">必填</span>
                  <span class="param-desc">{{ p.description || p.example || '无描述' }}</span>
                </div>
              </div>
              <div v-if="row.request_body_fields?.length > 0" class="param-section">
                <div class="param-title">Body 请求架构 ({{ row.request_body_ref }}):</div>
                <div v-for="p in row.request_body_fields" :key="p.name" class="param-item">
                  <span class="param-name">{{ p.name }}</span>
                  <el-tag size="small" type="info" class="param-type">{{ p.type_hint }}</el-tag>
                  <span v-if="p.required" class="param-req">必填</span>
                  <span class="param-desc">{{ p.description || p.example || '无描述' }}</span>
                </div>
              </div>
              <div v-if="!row.parameters?.length && !row.request_body_fields?.length" class="param-empty">
                此路由目前无需任何显式参数
              </div>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column label="AI 识别状态" width="160">
          <template #default="{ row }">
            <div class="status-cell" v-if="getAssignedCapability(row.route_id)">
              <el-icon class="status-icon success" size="18"><Check /></el-icon>
              <span class="status-text success">AI已接管</span>
            </div>
            <div class="status-cell" v-else>
              <el-icon class="status-icon ignore" size="18"><Close /></el-icon>
              <span class="status-text ignore">AI未发现</span>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column label="操作权限 (仅纳管项可配)" width="200">
          <template #default="{ row }">
            <template v-if="getAssignedCapability(row.route_id)">
              <div class="select-wrapper">
                <el-select 
                  size="small" 
                  :model-value="getAssignedCapability(row.route_id).permission_level"
                  @change="(val: string) => handlePermissionChange(getAssignedCapability(row.route_id), val)"
                  :loading="updatingMap[getAssignedCapability(row.route_id).capability_id]"
                  class="permission-select"
                >
                  <el-option
                    v-for="item in permissionOptions"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value"
                  />
                </el-select>
              </div>
            </template>
            <span v-else class="ignore-hint">- 忽略项无权限 -</span>
          </template>
        </el-table-column>

        <el-table-column prop="method" label="方 法" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="getMethodType(row.method)" class="method-tag">{{ row.method }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="path" label="路径 (Path)" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <code class="path-text">{{ row.path }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="summary" label="业务摘要" min-width="200" show-overflow-tooltip />
          </el-table>
        </div>

        <div class="pagination-container">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[15, 25, 50, 100]"
            layout="total, sizes, prev, pager, next"
            :total="filteredRoutes.length"
          />
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.custom-analyzer-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  background: transparent;
  color: #0f0f0f;
  border: 1px solid #e5e5e5;
  padding: 10px 18px;
  height: 38px;
  border-radius: 0;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
.custom-analyzer-btn:hover:not(:disabled) {
  background: #f5f5f5;
  border-color: #0f0f0f;
  transform: scale(1.02);
}
.custom-analyzer-btn:active:not(:disabled) {
  transform: scale(0.97);
}
.custom-analyzer-btn .btn-icon {
  font-size: 18px;
}
.custom-analyzer-btn .is-loading {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

.search-bar {
  margin-bottom: 20px;
  flex-shrink: 0;
}
.top-search-input :deep(.el-input__wrapper) {
  padding: 8px 16px;
  font-size: 15px;
  box-shadow: 0 0 0 1px #e5e5e5 inset !important;
  border-radius: 4px;
}
.top-search-input :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px #0f0f0f inset !important;
}

.route-map-drawer :deep(.el-drawer__body) {
  padding: 0;
  overflow: hidden;
}

.drawer-content {
  padding: 24px 24px;
  height: 100vh;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
}

/* 顶部统计 */
.drawer-header-stats {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
  flex-shrink: 0;
}
.stat-box {
  flex: 1;
  background: #f9f9f9;
  border-radius: 6px;
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 16px;
  transition: all 0.3s ease;
  border: 1px solid transparent;
}
.stat-box:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.05);
  border-color: #e5e5e5;
}
.stat-icon {
  font-size: 32px;
  color: #737373;
}
.success-box .stat-icon { color: #10B981; }
.unknown-box .stat-icon { color: #A3A3A3; }

.stat-info { display: flex; flex-direction: column; }
.stat-num { font-size: 24px; font-weight: 700; color: #0f0f0f; }
.stat-label { font-size: 12px; color: #737373; margin-top: 2px; }

/* 表格定制 */
.custom-table {
  border: 1px solid #e5e5e5;
  border-radius: 4px;
}
:deep(.el-table__row) {
  transition: background-color 0.3s ease;
}
:deep(.ignored-row) {
  opacity: 0.65;
  filter: grayscale(1);
}
:deep(.ignored-row:hover) {
  opacity: 1;
  filter: none;
}

.status-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}
.status-text { font-size: 13px; font-weight: 600; }
.status-icon.success { color: #10B981; }
.status-text.success { color: #10B981; }
.status-icon.ignore { color: #A3A3A3; }
.status-text.ignore { color: #A3A3A3; }

.permission-select {
  width: 100%;
}
.select-wrapper {
  animation: fadeIn 0.3s ease;
}

.ignore-hint {
  font-size: 12px;
  color: #a3a3a3;
  font-style: italic;
}

.method-tag {
  font-weight: 700;
  border-radius: 2px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.path-text {
  font-family: var(--font-mono);
  font-size: 13px;
  color: #1a1a1a;
  background: #f4f4f5;
  padding: 2px 6px;
  border-radius: 4px;
  word-break: break-all;
}

.table-wrapper {
  flex: 1;
  min-height: 0;
  border-radius: 4px;
}

.pagination-container {
  display: flex;
  justify-content: flex-end;
  flex-shrink: 0;
  padding-top: 16px;
  padding-bottom: 8px;
}

/* 扩展参数面板 */
.expanded-params-container {
  padding: 16px 40px;
  background: #fafafa;
  border-top: 1px dashed #ebebeb;
  border-bottom: 1px dashed #ebebeb;
  animation: slideDown 0.3s ease-out;
}
.param-section {
  margin-bottom: 16px;
}
.param-section:last-child {
  margin-bottom: 0;
}
.param-title {
  font-size: 13px;
  font-weight: 700;
  color: #52525B;
  margin-bottom: 8px;
}
.param-item {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 6px;
  font-size: 13px;
}
.param-name {
  font-family: var(--font-mono);
  color: #0f0f0f;
  font-weight: 600;
  min-width: 120px;
}
.param-type { border-radius: 2px; }
.param-req { color: #EF4444; font-size: 12px; font-weight: 600; }
.param-desc { color: #71717A; flex: 1; }
.param-empty {
  font-size: 13px;
  color: #a3a3a3;
  font-style: italic;
  padding: 12px 0;
}

/* 动画 */
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
@keyframes slideDown {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}

/* 覆盖 el-select 的蓝光焦点 */
:deep(.el-select .el-input.is-focus .el-input__wrapper) {
  box-shadow: 0 0 0 1px #0f0f0f inset !important;
}

@media (max-width: 768px) {
  .custom-analyzer-btn {
    padding: 0 10px;
  }
  .custom-analyzer-btn span {
    display: none;
  }
}
</style>

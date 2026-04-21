<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { useProjectStore } from '@/stores/project'

const props = defineProps<{
  projectId: string
  projectName: string
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
  (e: 'changed'): void
}>()

const projectStore = useProjectStore()
const { t } = useI18n()

// ── 角色画像列表 ──
interface RoleProfile {
  id: string
  name: string
  description: string | null
  probe_username: string
  probe_status: string
  probe_error: string | null
  route_count: number
  accessible_count: number
  is_default?: boolean
}

interface AccessibilityRecord {
  id: string
  route_id: string
  accessible: boolean
  probe_status_code: number | null
  probe_method: string | null
  manually_overridden: boolean
}

const profiles = ref<RoleProfile[]>([])
const loading = ref(false)
const userLoginEnabled = ref(false)
const defaultProfileId = ref<string | null>(null)

// ── 创建表单 ──
const showCreateForm = ref(false)
const createLoading = ref(false)
const newProfile = ref({
  name: '',
  description: '',
  probe_username: '',
  probe_password: '',
})

// ── 探测详情 ──
const detailProfileId = ref<string | null>(null)
const detailLoading = ref(false)
const detailAccessibility = ref<AccessibilityRecord[]>([])
const detailProfile = ref<RoleProfile | null>(null)

// ── 抽屉打开时加载 ──
watch(() => props.visible, async (val) => {
  if (val && props.projectId) {
    await loadProfiles()
  } else {
    detailProfileId.value = null
    showCreateForm.value = false
  }
})

async function loadProfiles() {
  loading.value = true
  try {
    const profileList: any[] = await projectStore.listRoleProfiles(props.projectId)
    profiles.value = profileList
    // 从 list 返回值中找到 is_default 的画像
    const defaultProfile = profileList.find((p: any) => p.is_default)
    defaultProfileId.value = defaultProfile?.id ?? null
    // 从项目数据读取 user_login_enabled
    const proj = projectStore.projects.find((p) => p.id === props.projectId) as any
    userLoginEnabled.value = proj?.user_login_enabled ?? false
  } catch (e: any) {
    ElMessage.error(t('roleProfiles.messages.loadFailed'))
  } finally {
    loading.value = false
  }
}

// ── 开启/关闭用户登录 ──
async function toggleUserLogin(val: boolean) {
  try {
    await projectStore.updateProjectSettings(props.projectId, { user_login_enabled: val })
    userLoginEnabled.value = val
    ElMessage.success(val ? t('roleProfiles.messages.userLoginEnabled') : t('roleProfiles.messages.userLoginDisabled'))
    emit('changed')
  } catch {
    ElMessage.error(t('roleProfiles.messages.updateFailed'))
  }
}

// ── 创建角色画像 ──
async function submitCreate() {
  if (!newProfile.value.name || !newProfile.value.probe_username || !newProfile.value.probe_password) {
    ElMessage.warning(t('roleProfiles.messages.requiredFields'))
    return
  }
  createLoading.value = true
  try {
    await projectStore.createRoleProfile(props.projectId, newProfile.value)
    ElMessage.success(t('roleProfiles.messages.createSuccess'))
    newProfile.value = { name: '', description: '', probe_username: '', probe_password: '' }
    showCreateForm.value = false
    await loadProfiles()
    emit('changed')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || t('roleProfiles.messages.createFailed'))
  } finally {
    createLoading.value = false
  }
}

// ── 重新探测 ──
async function handleReprobe(profile: RoleProfile) {
  try {
    await projectStore.reprobeRoleProfile(props.projectId, profile.id)
    ElMessage.success(t('roleProfiles.messages.reprobeStarted'))
    profile.probe_status = 'pending'
    // 轮询更新状态
    const pollId = setInterval(async () => {
      try {
        const list: any[] = await projectStore.listRoleProfiles(props.projectId)
        const updated = list.find((p: any) => p.id === profile.id)
        if (updated && updated.probe_status !== 'probing' && updated.probe_status !== 'pending') {
          Object.assign(profile, updated)
          clearInterval(pollId)
          if (detailProfileId.value === profile.id) {
            await loadDetail(profile.id)
          }
        }
      } catch { /* ignore */ }
    }, 2000)
  } catch {
    ElMessage.error(t('roleProfiles.messages.reprobeFailed'))
  }
}

// ── 删除画像 ──
async function handleDelete(profile: RoleProfile) {
  try {
    await ElMessageBox.confirm(
      t('roleProfiles.dialogs.deleteConfirm.message', { name: profile.name }),
      t('roleProfiles.dialogs.deleteConfirm.title'),
      { confirmButtonText: t('roleProfiles.dialogs.deleteConfirm.confirm'), cancelButtonText: t('common.cancel'), type: 'warning' }
    )
    await projectStore.deleteRoleProfile(props.projectId, profile.id)
    ElMessage.success(t('roleProfiles.messages.deleteSuccess'))
    if (detailProfileId.value === profile.id) {
      detailProfileId.value = null
    }
    await loadProfiles()
    emit('changed')
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(t('roleProfiles.messages.deleteFailed'))
  }
}

// ── 设为默认角色 ──
async function handleSetDefault(profile: RoleProfile) {
  try {
    await projectStore.setDefaultRole(props.projectId, profile.id)
    defaultProfileId.value = profile.id
    ElMessage.success(t('roleProfiles.messages.setDefaultSuccess', { name: profile.name }))
    emit('changed')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || t('roleProfiles.messages.setDefaultFailed'))
  }
}

// ── 查看探测详情 ──
async function loadDetail(profileId: string) {
  detailProfileId.value = profileId
  detailLoading.value = true
  try {
    const data = await projectStore.getRoleProfile(props.projectId, profileId)
    detailProfile.value = data
    detailAccessibility.value = data.accessibility || []
  } catch {
    ElMessage.error(t('roleProfiles.messages.detailLoadFailed'))
  } finally {
    detailLoading.value = false
  }
}

// ── 手动修正可达性 ──
async function toggleAccessibility(record: AccessibilityRecord) {
  const newVal = !record.accessible
  try {
    await projectStore.updateRouteAccessibility(props.projectId, detailProfileId.value!, record.route_id, newVal)
    record.accessible = newVal
    record.manually_overridden = true
    ElMessage.success(t('roleProfiles.messages.accessibilityUpdated'))
  } catch {
    ElMessage.error(t('roleProfiles.messages.accessibilityUpdateFailed'))
  }
}

// ── 探测状态样式 ──
function probeStatusType(status: string): string {
  switch (status) {
    case 'completed': return 'success'
    case 'probing': case 'pending': return 'warning'
    case 'failed': return 'danger'
    default: return 'info'
  }
}

function probeStatusText(status: string): string {
  const map: Record<string, string> = {
    pending: t('roleProfiles.status.pending'),
    probing: t('roleProfiles.status.probing'),
    completed: t('roleProfiles.status.completed'),
    failed: t('roleProfiles.status.failed'),
    stale: t('roleProfiles.status.stale'),
  }
  return map[status] || status
}

function httpStatusClass(code: number | null): string {
  if (code === null) return 'status-unknown'
  if (code < 400) return 'status-ok'
  if (code === 401 || code === 403) return 'status-denied'
  return 'status-error'
}
</script>

<template>
  <el-drawer
    :model-value="visible"
    @update:model-value="emit('update:visible', $event)"
    :title="t('roleProfiles.drawerTitle', { name: projectName })"
    direction="rtl"
    size="640px"
    :destroy-on-close="true"
  >
    <!-- 用户登录开关 -->
    <div class="login-toggle">
      <el-switch
        :model-value="userLoginEnabled"
        @change="toggleUserLogin"
        active-text=""
        inactive-text=""
      />
      <span class="toggle-label">{{ t('roleProfiles.userLoginToggle') }}</span>
      <el-tooltip :content="t('roleProfiles.userLoginToggleHint')" placement="top">
        <el-icon class="hint-icon"><InfoFilled /></el-icon>
      </el-tooltip>
    </div>

    <!-- 角色画像列表 -->
    <div class="profiles-section">
      <div class="section-header">
        <h3>{{ t('roleProfiles.profilesList') }}</h3>
        <el-button size="small" type="primary" @click="showCreateForm = !showCreateForm">
          {{ showCreateForm ? t('roleProfiles.createForm.cancel') : t('roleProfiles.createForm.trigger') }}
        </el-button>
      </div>

      <!-- 创建表单 -->
      <el-collapse-transition>
        <div v-if="showCreateForm" class="create-form">
          <el-form label-width="90px" size="default">
            <el-form-item :label="t('roleProfiles.createForm.name')">
              <el-input v-model="newProfile.name" :placeholder="t('roleProfiles.createForm.namePlaceholder')" />
            </el-form-item>
            <el-form-item :label="t('roleProfiles.createForm.description')">
              <el-input v-model="newProfile.description" :placeholder="t('roleProfiles.createForm.descriptionPlaceholder')" />
            </el-form-item>
            <el-form-item :label="t('roleProfiles.createForm.username')">
              <el-input v-model="newProfile.probe_username" :placeholder="t('roleProfiles.createForm.usernamePlaceholder')" />
            </el-form-item>
            <el-form-item :label="t('roleProfiles.createForm.password')">
              <el-input v-model="newProfile.probe_password" type="password" show-password :placeholder="t('roleProfiles.createForm.passwordPlaceholder')" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="createLoading" @click="submitCreate">
                {{ t('roleProfiles.createForm.submit') }}
              </el-button>
            </el-form-item>
          </el-form>
          <el-alert
            :title="t('roleProfiles.createForm.hint')"
            type="info"
            show-icon
            :closable="false"
            style="margin-bottom: 12px;"
          />
        </div>
      </el-collapse-transition>

      <!-- 列表 -->
      <div v-loading="loading" class="profile-list">
        <el-empty v-if="profiles.length === 0 && !loading" :description="t('roleProfiles.emptyProfiles')" />

        <div v-for="profile in profiles" :key="profile.id" class="profile-card" :class="{ 'is-default': defaultProfileId === profile.id }">
          <div class="profile-header">
            <div class="profile-title">
              <span class="profile-name">{{ profile.name }}</span>
              <el-tag v-if="defaultProfileId === profile.id" type="success" size="small">{{ t('roleProfiles.defaultTag') }}</el-tag>
              <el-tag :type="probeStatusType(profile.probe_status)" size="small">{{ probeStatusText(profile.probe_status) }}</el-tag>
            </div>
            <div class="profile-actions">
              <el-button size="small" @click="loadDetail(profile.id)" :disabled="profile.probe_status === 'pending' || profile.probe_status === 'probing'">
                {{ t('roleProfiles.actions.viewDetail') }}
              </el-button>
              <el-button size="small" @click="handleReprobe(profile)" :loading="profile.probe_status === 'probing' || profile.probe_status === 'pending'">
                {{ t('roleProfiles.actions.reprobe') }}
              </el-button>
              <el-dropdown trigger="click" @command="(cmd: string) => cmd === 'default' ? handleSetDefault(profile) : handleDelete(profile)">
                <el-button size="small" plain>···</el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="default" :disabled="defaultProfileId === profile.id || profile.probe_status !== 'completed'">
                      {{ t('roleProfiles.actions.setDefault') }}
                    </el-dropdown-item>
                    <el-dropdown-item command="delete" divided>
                      <span style="color: var(--el-color-danger)">{{ t('roleProfiles.actions.delete') }}</span>
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </div>
          <div class="profile-meta">
            <span class="meta-item">{{ t('roleProfiles.probeUser') }}: <strong>{{ profile.probe_username }}</strong></span>
            <span v-if="profile.probe_status === 'completed'" class="meta-item">
              {{ t('roleProfiles.routeStats', { total: profile.route_count, accessible: profile.accessible_count }) }}
            </span>
          </div>
          <div v-if="profile.probe_error" class="probe-error">
            <el-icon><WarningFilled /></el-icon> {{ profile.probe_error }}
          </div>
        </div>
      </div>
    </div>

    <!-- 探测详情 -->
    <el-collapse-transition>
      <div v-if="detailProfileId && detailProfile" class="detail-section">
        <div class="section-header">
          <h3>{{ t('roleProfiles.detailTitle', { name: detailProfile.name }) }}</h3>
          <el-button size="small" @click="detailProfileId = null">{{ t('roleProfiles.detailClose') }}</el-button>
        </div>
        <div v-loading="detailLoading">
          <div class="detail-stats">
            <el-statistic :title="t('roleProfiles.statTotal')" :value="detailProfile.route_count" />
            <el-statistic :title="t('roleProfiles.statAccessible')" :value="detailProfile.accessible_count" />
            <el-statistic :title="t('roleProfiles.statDenied')" :value="detailProfile.route_count - detailProfile.accessible_count" />
          </div>

          <el-table :data="detailAccessibility" size="small" stripe max-height="400" style="margin-top: 12px;">
            <el-table-column prop="route_id" :label="t('roleProfiles.table.route')" min-width="200">
              <template #default="{ row }">
                <span class="route-id-text">{{ row.route_id }}</span>
              </template>
            </el-table-column>
            <el-table-column :label="t('roleProfiles.table.statusCode')" width="100" align="center">
              <template #default="{ row }">
                <span :class="httpStatusClass(row.probe_status_code)">{{ row.probe_status_code ?? '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column :label="t('roleProfiles.table.accessible')" width="90" align="center">
              <template #default="{ row }">
                <el-switch
                  :model-value="row.accessible"
                  @change="toggleAccessibility(row)"
                  size="small"
                  inline-prompt
                  :active-text="t('roleProfiles.yes')"
                  :inactive-text="t('roleProfiles.no')"
                />
              </template>
            </el-table-column>
            <el-table-column :label="t('roleProfiles.table.overridden')" width="80" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.manually_overridden" type="warning" size="small">{{ t('roleProfiles.yes') }}</el-tag>
                <span v-else class="text-muted">—</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </el-collapse-transition>
  </el-drawer>
</template>

<style scoped>
.login-toggle {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  margin-bottom: 20px;
  background: #fafafa;
  border: 1px solid #e5e5e5;
  border-radius: 0;
}

.toggle-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary, #0f0f0f);
}

.hint-icon {
  color: var(--color-text-secondary, #737373);
  cursor: help;
}

.profiles-section,
.detail-section {
  padding: 0 4px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary, #0f0f0f);
}

.create-form {
  padding: 16px;
  margin-bottom: 16px;
  background: #fafafa;
  border: 1px solid #e5e5e5;
  border-radius: 0;
}

.profile-list {
  min-height: 60px;
}

.profile-card {
  padding: 16px;
  margin-bottom: 12px;
  border: 1px solid #e5e5e5;
  border-radius: 0;
  background: #fff;
  transition: border-color 0.2s;
}

.profile-card.is-default {
  border-left: 3px solid var(--el-color-success);
}

.profile-card:hover {
  border-color: #a3a3a3;
}

.profile-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  flex-wrap: wrap;
}

.profile-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.profile-name {
  font-weight: 600;
  font-size: 15px;
  color: var(--color-text-primary, #0f0f0f);
}

.profile-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.profile-meta {
  display: flex;
  gap: 16px;
  margin-top: 8px;
  font-size: 13px;
  color: var(--color-text-secondary, #737373);
}

.meta-item strong {
  color: var(--color-text-primary, #0f0f0f);
}

.probe-error {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  padding: 8px 10px;
  background: #fffafa;
  border: 1px solid #ffcccc;
  font-size: 12px;
  color: #cc0000;
}

.detail-section {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid #e5e5e5;
}

.detail-stats {
  display: flex;
  gap: 32px;
  padding: 12px 0;
}

.route-id-text {
  font-family: var(--font-mono, monospace);
  font-size: 12px;
  word-break: break-all;
}

.status-ok { color: var(--el-color-success); font-weight: 600; }
.status-denied { color: var(--el-color-danger); font-weight: 600; }
.status-error { color: var(--el-color-warning); font-weight: 600; }
.status-unknown { color: var(--color-text-secondary, #737373); }
.text-muted { color: var(--color-text-secondary, #737373); }

:deep(.el-drawer__header) {
  margin-bottom: 0;
  padding: 16px 20px;
  border-bottom: 1px solid #e5e5e5;
}

:deep(.el-drawer__body) {
  padding: 20px;
}

:deep(.el-tag) {
  border-radius: 0 !important;
}
</style>

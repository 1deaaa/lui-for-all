<script setup lang="ts">
import { ref } from 'vue'

// 设置表单
const settings = ref({
  llm_api_base: 'https://api.devlens.top/v1',
  llm_model_id: 'gpt-5.4',
  target_base_url: 'http://localhost:6687',
  safety_default_action: 'confirm',
})

const saving = ref(false)

// 保存设置
async function saveSettings() {
  saving.value = true
  try {
    // TODO: 调用后端 API 保存设置
    await new Promise(resolve => setTimeout(resolve, 1000))
    console.log('设置已保存:', settings.value)
  } catch (error) {
    console.error('保存设置失败:', error)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="settings-page">
    <div class="page-header">
      <h2>系统设置</h2>
    </div>

    <el-card class="settings-card">
      <el-form :model="settings" label-width="120px">
        <el-divider content-position="left">LLM 配置</el-divider>
        
        <el-form-item label="API 端点">
          <el-input v-model="settings.llm_api_base" placeholder="LLM API 端点" />
        </el-form-item>
        
        <el-form-item label="模型 ID">
          <el-input v-model="settings.llm_model_id" placeholder="模型 ID" />
        </el-form-item>

        <el-divider content-position="left">目标项目配置</el-divider>
        
        <el-form-item label="API 地址">
          <el-input v-model="settings.target_base_url" placeholder="目标项目 API 地址" />
        </el-form-item>

        <el-divider content-position="left">安全配置</el-divider>
        
        <el-form-item label="默认动作">
          <el-select v-model="settings.safety_default_action">
            <el-option label="允许" value="allow" />
            <el-option label="确认" value="confirm" />
            <el-option label="阻断" value="block" />
          </el-select>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="saveSettings" :loading="saving">
            保存设置
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.settings-page {
  height: 100%;
  overflow-y: auto;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
}

.settings-card {
  max-width: 600px;
}
</style>

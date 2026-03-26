<template>
  <div class="settings-view">
    <h2>系统配置</h2>
    <div class="section">
      <el-form label-width="120px" style="max-width: 800px">
        <el-form-item label="模板路径">
          <el-input
            v-model="templatePath"
            placeholder="如 D:\word_templates 或 /opt/shanhai/word_templates，留空使用默认"
            clearable
          >
            <template #append>
              <el-button type="primary" :loading="templatePathSaving" @click="saveTemplatePath">
                保存
              </el-button>
            </template>
          </el-input>
        </el-form-item>
      </el-form>
      <p style="margin-top: 16px">模板目录结构（资金类别 × 工程类别 × 采购类型 × 采购方式）</p>
      <el-table :data="templateStructure" style="margin-top: 16px">
        <el-table-column prop="path" label="路径" />
        <el-table-column prop="files" label="模板文件">
          <template #default="{ row }">
            <span v-if="row.files.length">{{ row.files.join(', ') }}</span>
            <el-tag v-else type="info" size="small">空</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useRealtimeSync, EventType } from '@/composables/useRealtimeSync'
import { getTemplateStructure, getTemplateConfig, updateTemplateConfig } from '@/api/templates'

/** 后端 FastAPI：detail 可能是字符串或校验错误数组，统一成可读文案 */
function apiErrorMessage(e: any, fallback: string): string {
  const d = e?.response?.data?.detail
  if (typeof d === 'string' && d.trim()) return d
  if (Array.isArray(d) && d.length) {
    return d.map((x: any) => (typeof x?.msg === 'string' ? x.msg : JSON.stringify(x))).join('；')
  }
  if (e?.message === 'Network Error') return '网络异常，请确认后端已启动且地址正确'
  const st = e?.response?.status
  if (st === 403) return '无权限（需系统管理员登录）'
  if (st === 401) return '登录已失效，请重新登录'
  if (st) return `${fallback}（HTTP ${st}）`
  return fallback
}

const templateStructure = ref<{ path: string; files: string[] }[]>([])
const templatePath = ref('')
const templatePathSaving = ref(false)

useRealtimeSync({
  context: { scope: 'settings' },
  onEvent: (e) => {
    const events = [EventType.TEMPLATE_UPDATED, EventType.CONFIG_CHANGED]
    if (events.includes(e.type as string)) {
      loadTemplates()
    }
  },
})

onMounted(async () => {
  await loadTemplates()
})

async function loadTemplates() {
  try {
    const config = await getTemplateConfig()
    templatePath.value = config.word_templates_dir || ''
    templateStructure.value = await getTemplateStructure()
  } catch {
    ElMessage.error('加载模板结构失败')
  }
}

async function saveTemplatePath() {
  templatePathSaving.value = true
  try {
    await updateTemplateConfig(templatePath.value)
    ElMessage.success('模板路径已保存')
    await loadTemplates()
  } catch (e: any) {
    ElMessage.error(apiErrorMessage(e, '保存失败'))
  } finally {
    templatePathSaving.value = false
  }
}
</script>

<style scoped lang="scss">
.settings-view {
  h2 {
    margin-bottom: 16px;
    font-size: 18px;
  }
  .section {
    margin-top: 16px;
  }
}
</style>

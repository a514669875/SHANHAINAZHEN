<template>
  <div class="archive-view">
    <h2>归档管理</h2>
    <el-form inline>
      <el-form-item label="工程">
        <el-select
          v-model="selectedProjectId"
          placeholder="选择工程（可搜索）"
          filterable
          clearable
          class="archive-project-select"
          @change="loadProcurements"
        >
          <el-option
            v-for="p in projects"
            :key="p.id"
            :label="`${p.project_id || ''} ${p.project_name || ''}`.trim() || '未命名'"
            :value="p.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="采购项目">
        <el-select
          v-model="selectedProcurementId"
          placeholder="选择采购项目（可搜索）"
          filterable
          clearable
          class="archive-procurement-select"
          :style="{ width: procurementSelectWidth }"
        >
          <el-option
            v-for="p in procurements"
            :key="p.id"
            :label="`${p.contract_number || ''} ${p.project_name || ''}`.trim() || '未命名'"
            :value="p.id"
          />
        </el-select>
      </el-form-item>
    </el-form>
    <div v-if="selectedProcurementId" class="upload-area">
      <div v-if="archiveStatus" class="archive-progress">
        {{ archiveStatus.is_dual
          ? `已上传 ${archiveStatus.uploaded}/${archiveStatus.required} 份合同（五选二）`
          : `已上传 ${archiveStatus.uploaded}/${archiveStatus.required} 份合同`
        }}
      </div>
      <el-upload
        :auto-upload="false"
        :on-change="handleFileChange"
        drag
      >
        <el-icon><UploadFilled /></el-icon>
        <div>拖拽文件到此处或点击上传</div>
      </el-upload>
      <template v-if="selectedProcurement?.is_dual">
        <div style="margin-top: 8px; display: flex; gap: 16px;">
          <el-checkbox
            v-model="isContractSection1"
            :disabled="!!(archiveStatus && archiveStatus.uploaded >= archiveStatus.required)"
          >
            此文件为一标段合同文件
          </el-checkbox>
          <el-checkbox
            v-model="isContractSection2"
            :disabled="!!(archiveStatus && archiveStatus.uploaded >= archiveStatus.required)"
          >
            此文件为二标段合同文件
          </el-checkbox>
        </div>
      </template>
      <el-checkbox
        v-else
        v-model="isContract"
        :disabled="!!(archiveStatus && archiveStatus.uploaded >= archiveStatus.required)"
        style="margin-top: 8px"
      >
        此文件为合同文件
      </el-checkbox>
    </div>
    <el-table :data="files" style="margin-top: 16px">
      <el-table-column prop="file_name" label="文件名" />
      <el-table-column prop="file_type" label="类型" width="100" />
      <el-table-column prop="file_size" label="大小" width="100" />
      <el-table-column prop="is_contract" label="合同文件" width="80">
        <template #default="{ row }">{{ row.is_contract ? '是' : '否' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="80">
        <template #default="{ row }">
          <el-button type="danger" link size="small" @click="deleteFile(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listProjects } from '@/api/projects'
import { listProcurements } from '@/api/procurements'
import request from '@/api/request'
import { useBreadcrumbStore } from '@/store/breadcrumb'

const route = useRoute()
const bc = useBreadcrumbStore()
const projects = ref<any[]>([])
const procurements = ref<any[]>([])
const selectedProjectId = ref<number | null>(null)
const selectedProcurementId = ref<number | null>(null)
const files = ref<any[]>([])
const isContract = ref(false)
const isContractSection1 = ref(false)
const isContractSection2 = ref(false)
const archiveStatus = ref<{ required: number; uploaded: number; is_dual: boolean } | null>(null)

const selectedProject = computed(() => projects.value.find((p) => p.id === selectedProjectId.value))
const selectedProcurement = computed(() => procurements.value.find((p) => p.id === selectedProcurementId.value))

const selectedProcurementLabel = computed(() => {
  const p = selectedProcurement.value
  if (!p) return ''
  return `${p.contract_number || ''} ${p.project_name || ''}`.trim() || '未命名'
})

const procurementSelectWidth = computed(() => {
  const label = selectedProcurementLabel.value
  const minWidth = 240
  if (!label) return `${minWidth}px`
  const charWidth = 14
  const padding = 48
  const w = Math.max(minWidth, label.length * charWidth + padding)
  return `${w}px`
})

const initFromQuery = ref(false)

onMounted(async () => {
  projects.value = await listProjects({ page: 1, page_size: 100 })
  const qProjectId = route.query.project_id
  const qProcurementId = route.query.procurement_id
  if (qProjectId && qProcurementId) {
    initFromQuery.value = true
    selectedProjectId.value = Number(qProjectId)
    procurements.value = await listProcurements(Number(qProjectId), false)
    selectedProcurementId.value = Number(qProcurementId)
    initFromQuery.value = false
    loadFiles()
    loadArchiveStatus()
    updateBreadcrumb()
  }
})

watch(selectedProjectId, () => {
  if (initFromQuery.value) return
  selectedProcurementId.value = null
  procurements.value = []
  files.value = []
  if (selectedProjectId.value) loadProcurements()
})

watch(selectedProcurementId, () => {
  files.value = []
  archiveStatus.value = null
  isContract.value = false
  isContractSection1.value = false
  isContractSection2.value = false
  if (selectedProcurementId.value) {
    loadFiles()
    loadArchiveStatus()
  }
  updateBreadcrumb()
})
watch(selectedProjectId, () => updateBreadcrumb(), { immediate: true })

function updateBreadcrumb() {
  const proj = selectedProject.value
  const proc = selectedProcurement.value
  bc.setArchiveContext({
    projectId: proj?.id ?? null,
    projectNumber: proj?.project_id ?? '',
    projectName: proj?.project_name ?? '',
    procurementId: proc?.id ?? null,
    procurementName: proc?.project_name ?? proc?.contract_number ?? '',
  })
}

async function loadProcurements() {
  if (!selectedProjectId.value) return
  procurements.value = await listProcurements(selectedProjectId.value, false)
}

async function loadFiles() {
  if (!selectedProcurementId.value) return
  try {
    files.value = await request.get('/files', { params: { procurement_id: selectedProcurementId.value } })
  } catch {
    files.value = []
  }
}

async function loadArchiveStatus() {
  if (!selectedProcurementId.value) return
  try {
    archiveStatus.value = await request.get('/files/archive-status', { params: { procurement_id: selectedProcurementId.value } })
  } catch {
    archiveStatus.value = null
  }
}

async function handleFileChange(file: any) {
  if (!selectedProcurementId.value) return
  const proc = selectedProcurement.value
  const exists = files.value.some((f) => f.file_name === file.name)
  if (exists) {
    ElMessage.error(`文件名「${file.name}」已存在，请重命名后上传`)
    return
  }
  let procurementId = selectedProcurementId.value
  let isContractVal = isContract.value
  if (proc?.is_dual && proc?.dual_ids) {
    if (isContractSection1.value && !isContractSection2.value) {
      procurementId = proc.dual_ids[0]
      isContractVal = true
    } else if (isContractSection2.value && !isContractSection1.value) {
      procurementId = proc.dual_ids[1]
      isContractVal = true
    } else if (isContractSection1.value && isContractSection2.value) {
      ElMessage.warning('请只勾选一个标段')
      return
    } else {
      isContractVal = false
    }
  }
  const form = new FormData()
  form.append('file', file.raw)
  form.append('procurement_id', String(procurementId))
  form.append('is_contract', String(isContractVal))
  try {
    await request.post('/files/upload', form)
    ElMessage.success('上传成功')
    isContractSection1.value = false
    isContractSection2.value = false
    loadFiles()
    loadArchiveStatus()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '上传失败')
  }
}

async function deleteFile(row: any) {
  try {
    await ElMessageBox.confirm('确定删除该文件？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await request.delete(`/files/${row.id}`)
    ElMessage.success('已删除')
    loadFiles()
    loadArchiveStatus()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.detail || '删除失败')
    }
  }
}
</script>

<style scoped lang="scss">
.archive-view {
  h2 { margin-bottom: 16px; }
  .archive-project-select { width: 400px !important; }
  .archive-progress {
    margin-bottom: 12px;
    color: var(--el-text-color-regular);
    font-size: 14px;
  }
}
</style>

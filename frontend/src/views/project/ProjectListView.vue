<template>
  <div class="project-list-view">
    <div class="page-header">
      <h2>工程项目清单</h2>
      <el-input
        v-model="searchKeyword"
        placeholder="搜索工程编号/名称"
        class="search-input"
        clearable
        @keyup.enter="loadData"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
    </div>
    <div class="action-bar">
      <el-button type="primary" @click="showAdd">新增工程</el-button>
      <el-button type="danger" :disabled="!selectedIds.length" @click="handleBatchDelete">删除</el-button>
      <el-button @click="handleExport">导出EXCEL</el-button>
    </div>
    <div class="table-scroll-wrapper">
    <el-table
      :data="tableData"
      border
      max-height="calc(100vh - 280px)"
      @row-dblclick="handleRowDblClick"
      @selection-change="handleSelectionChange"
    >
      <el-table-column type="selection" width="50" :resizable="false" />
      <el-table-column prop="id" label="序号" width="60" :resizable="false" />
      <el-table-column prop="funding_type" label="资金类别" width="90" resizable />
      <el-table-column prop="project_type" label="工程类别" width="110" resizable>
        <template #default="{ row }">{{ row.funding_type === '自有资金' ? '-' : (row.project_type || '-') }}</template>
      </el-table-column>
      <el-table-column prop="project_number" label="项目编号" width="100" resizable />
      <el-table-column prop="project_id" label="工程编号" width="120" resizable />
      <el-table-column prop="project_name" label="工程名称" min-width="120" resizable />
      <el-table-column prop="department" label="实施部门" width="100" resizable />
      <el-table-column prop="site_manager" label="现场管理员" width="100" resizable />
      <el-table-column prop="site_manager_phone" label="联系方式" width="120" resizable />
      <el-table-column prop="construction_unit" label="发包单位" width="100" resizable />
      <el-table-column prop="total_contract_price" label="总包合同价" width="110" resizable>
        <template #default="{ row }">{{ formatContractPrice(row.total_contract_price) }}</template>
      </el-table-column>
      <el-table-column prop="project_duration" label="工程工期" width="120" resizable />
      <el-table-column prop="funding_source" label="资金来源" width="100" resizable />
      <el-table-column prop="procurement_officers" label="经办人" width="120" resizable>
        <template #default="{ row }">
          <span style="white-space: pre-line">{{ getOfficerDisplay(row.procurement_officers) }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="create_date" label="创建日期" width="110" resizable>
        <template #default="{ row }">{{ formatDateYMD(row.create_date) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right" :resizable="false">
        <template #default="{ row }">
          <el-button link type="primary" @click="editProject(row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>
    </div>
    <div class="pagination">
      <span>共 {{ total }} 条记录</span>
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="prev, pager, next, jumper, sizes"
      />
    </div>
    <p class="tip">双击工程项可进入该工程的采购项目清单</p>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑工程项目' : '新建工程项目'" width="880" :close-on-click-modal="false">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="140px">
        <el-divider content-position="left">基本信息</el-divider>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="工程编号" prop="project_id">
              <el-input v-model="form.project_id" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="工程名称" prop="project_name">
              <el-input v-model="form.project_name" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="项目编号" prop="project_number">
              <el-input v-model="form.project_number" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="资金类别" prop="funding_type">
              <el-select v-model="form.funding_type" style="width: 100%">
                <el-option label="工程类" value="工程类" />
                <el-option label="自有资金" value="自有资金" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item v-if="form.funding_type === '工程类'" label="工程类别" prop="project_type">
          <el-select v-model="form.project_type" style="width: 100%">
            <el-option label="集团内项目" value="集团内项目" />
            <el-option label="集团外项目" value="集团外项目" />
          </el-select>
        </el-form-item>
        <el-divider content-position="left">项目信息</el-divider>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="项目实施部门" prop="department">
              <el-input v-model="form.department" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="项目现场管理员" prop="site_manager">
              <el-input v-model="form.site_manager" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="联系方式" prop="site_manager_phone">
              <el-input v-model="form.site_manager_phone" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="发包单位" prop="construction_unit">
              <el-input v-model="form.construction_unit" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-divider content-position="left">合同信息</el-divider>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="总包合同价" prop="total_contract_price">
              <NumericInput v-model="form.total_contract_price" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="工程工期" prop="project_duration">
              <el-input v-model="form.project_duration" placeholder="用户输入" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="资金来源" prop="funding_source">
              <el-select v-model="form.funding_source" style="width: 100%">
                <el-option label="财政资金" value="财政资金" />
                <el-option label="企业自筹" value="企业自筹" />
                <el-option label="自有资金" value="自有资金" />
                <el-option label="部分自有资金、部分财政资金" value="部分自有资金、部分财政资金" />
                <el-option label="其他" value="其他" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="项目地址" prop="project_address">
          <el-input v-model="form.project_address" />
        </el-form-item>
        <el-form-item label="材料（设备）采购经办人" prop="procurement_officers">
          <el-select
            v-model="officerIds"
            multiple
            placeholder="选择经办人"
            style="width: 100%"
          >
            <el-option
              v-for="u in userList"
              :key="u.id"
              :label="u.real_name || u.username"
              :value="String(u.id)"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveProject">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import {
  listProjects,
  countProjects,
  createProject,
  updateProject,
  deleteProject,
  exportProjectsExcel,
} from '@/api/projects'
import { listUsers } from '@/api/users'
import type { Project, ProjectCreate } from '@/api/projects'
import { formatDateYMD, formatNumericLocale, formatContractPrice } from '@/utils/format'
import NumericInput from '@/components/NumericInput.vue'
import { useRealtimeSync, EventType } from '@/composables/useRealtimeSync'

const router = useRouter()
const tableData = ref<Project[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const searchKeyword = ref('')
const selectedIds = ref<number[]>([])
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const userList = ref<{ id: number; username: string; real_name?: string }[]>([])

const officerIds = ref<string[]>([])
const officerDisplayMap = computed(() => {
  const m: Record<string, string> = {}
  for (const u of userList.value) {
    m[String(u.id)] = u.real_name || u.username
  }
  return m
})
function getOfficerDisplay(ids: string | undefined) {
  if (!ids) return '-'
  return ids.split(',').map((id) => officerDisplayMap.value[id.trim()] || id).filter(Boolean).join('\n')
}
const form = reactive<ProjectCreate & { project_address?: string; project_duration?: string }>({
  funding_type: '工程类',
  project_type: '集团内项目',
  project_number: '',
  project_id: '',
  project_name: '',
  department: '',
  site_manager: '',
  site_manager_phone: '',
  construction_unit: '',
  total_contract_price: 0,
  project_duration: '',
  funding_source: '自有资金',
  project_address: '',
  procurement_officers: '',
})

watch(officerIds, (ids) => {
  form.procurement_officers = ids.join(',')
})

watch(() => form.funding_type, (v) => {
  if (v === '自有资金') form.project_type = ''
})

const rules: FormRules = {
  project_id: [{ required: true, message: '请输入工程编号', trigger: 'blur' }],
  project_name: [{ required: true, message: '请输入工程名称', trigger: 'blur' }],
  project_number: [{ required: true, message: '请输入项目编号', trigger: 'blur' }],
  funding_type: [{ required: true, message: '请选择资金类别', trigger: 'change' }],
  project_type: [{
    validator: (_rule: any, v: string, cb: (e?: Error) => void) => {
      if (form.funding_type === '工程类' && !v) cb(new Error('请选择工程类别'))
      else cb()
    },
    trigger: 'change',
  }],
  department: [{ required: true, message: '请输入实施部门', trigger: 'blur' }],
  site_manager: [{ required: true, message: '请输入现场管理员', trigger: 'blur' }],
  construction_unit: [{ required: true, message: '请输入发包单位', trigger: 'blur' }],
  total_contract_price: [{ required: true, message: '请输入总包合同价', trigger: 'blur' }],
  funding_source: [{ required: true, message: '请选择资金来源', trigger: 'change' }],
  procurement_officers: [{ required: true, message: '请选择经办人', trigger: 'change' }],
}

useRealtimeSync({
  context: { scope: 'project_list' },
  onEvent: (e) => {
    const projectEvents = [EventType.PROJECT_CREATED, EventType.PROJECT_UPDATED, EventType.PROJECT_DELETED]
    if (projectEvents.includes(e.type as string)) {
      loadData()
    }
  },
})

onMounted(() => {
  loadData()
  loadUsers()
})

watch([currentPage, pageSize, searchKeyword], () => loadData())

async function loadData() {
  try {
    const [items, countRes] = await Promise.all([
      listProjects({
        keyword: searchKeyword.value,
        page: currentPage.value,
        page_size: pageSize.value,
      }),
      countProjects(searchKeyword.value),
    ])
    tableData.value = items
    total.value = countRes.total
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '加载失败')
  }
}

async function loadUsers() {
  try {
    userList.value = await listUsers()
  } catch {
    // ignore
  }
}

function handleSelectionChange(selection: Project[]) {
  selectedIds.value = selection.map((s) => s.id)
}

function handleRowDblClick(row: Project) {
  router.push({ path: '/procurements', query: { project_id: String(row.id) } })
}

function showAdd() {
  editingId.value = null
  Object.assign(form, {
    funding_type: '工程类',
    project_type: '集团内项目',
    project_number: '',
    project_id: '',
    project_name: '',
    department: '',
    site_manager: '',
    site_manager_phone: '',
    construction_unit: '',
    total_contract_price: 0,
    project_duration: '',
    funding_source: '自有资金',
    project_address: '',
    procurement_officers: '',
  })
  officerIds.value = []
  dialogVisible.value = true
}

function editProject(row: Project) {
  editingId.value = row.id
  Object.assign(form, {
    ...row,
    project_address: row.project_address || '',
    project_duration: row.project_duration || '',
  })
  officerIds.value = row.procurement_officers ? row.procurement_officers.split(',').filter(Boolean) : []
  dialogVisible.value = true
}

async function saveProject() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    try {
      if (editingId.value) {
        await updateProject(editingId.value, form)
        ElMessage.success('更新成功')
      } else {
        await createProject(form)
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false
      await loadData()
    } catch (e: any) {
      ElMessage.error(e.response?.data?.detail || '保存失败')
    }
  })
}

async function handleBatchDelete() {
  await ElMessageBox.confirm(`确定删除选中的 ${selectedIds.value.length} 项？`, '确认', {
    type: 'warning',
  })
  try {
    for (const id of selectedIds.value) {
      await deleteProject(id)
    }
    ElMessage.success('删除成功')
    await loadData()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

async function handleExport() {
  if (!selectedIds.value.length) {
    ElMessage.warning('请先勾选要导出的工程项目')
    return
  }
  try {
    const blob = await exportProjectsExcel(selectedIds.value)
    const url = URL.createObjectURL(blob as any)
    const a = document.createElement('a')
    a.href = url
    a.download = 'projects.xlsx'
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || e.message || '导出失败')
  }
}
</script>

<style scoped lang="scss">
.project-list-view {
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    h2 {
      font-size: 18px;
    }
    .search-input {
      width: 240px;
    }
  }
  .action-bar {
    margin-bottom: 16px;
  }
  .pagination {
    margin-top: 16px;
    display: flex;
    align-items: center;
    gap: 16px;
  }
  .tip {
    margin-top: 8px;
    font-size: 12px;
    color: #6B7280;
  }
  .table-scroll-wrapper {
    overflow-x: auto;
    width: 100%;
  }
}
</style>

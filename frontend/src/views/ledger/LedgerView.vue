<template>
  <div class="ledger-view">
    <div class="page-header">
      <h2>智能台账</h2>
      <el-input
        v-model="searchKeyword"
        placeholder="合同编号/供应商/工程名称"
        clearable
        style="width: 240px"
        @keyup.enter="loadData"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
    </div>
    <div class="action-bar">
      <el-upload
        :show-file-list="false"
        :before-upload="handleImport"
        accept=".xlsx,.xls"
      >
        <el-button>导入EXCEL</el-button>
      </el-upload>
      <el-button @click="handleExport">导出EXCEL</el-button>
    </div>
    <div class="table-scroll-wrapper">
    <el-table
      :data="tableData"
      style="width: 100%"
      border
      row-key="id"
      max-height="calc(100vh - 220px)"
      @row-dblclick="goToProcurement"
      @selection-change="handleSelectionChange"
      @sort-change="handleSortChange"
      @filter-change="handleFilterChange"
    >
      <el-table-column type="selection" width="50" :resizable="false" />
      <el-table-column type="index" label="序号" width="60" :index="(i) => (currentPage - 1) * pageSize + i + 1" :resizable="false" />
      <el-table-column
        prop="funding_type"
        label="资金类别"
        width="90"
        resizable
        column-key="funding_type"
        :filters="fundingTypeFilters"
        :filtered-value="fundingTypeFilter ? [fundingTypeFilter] : []"
        :filter-method="() => true"
      />
      <el-table-column
        prop="group_type"
        label="集团内/外"
        width="90"
        resizable
        column-key="group_type"
        :filters="groupTypeFilters"
        :filtered-value="groupTypeFilter ? [groupTypeFilter] : []"
        :filter-method="() => true"
      />
      <el-table-column
        prop="procurement_method"
        label="采购方式"
        width="100"
        resizable
        column-key="procurement_method"
        :filters="procurementMethodFilters"
        :filtered-value="procurementMethodFilter ? [procurementMethodFilter] : []"
        :filter-method="() => true"
      />
      <el-table-column prop="department" label="项目实施部门" width="120" resizable />
      <el-table-column prop="project_number" label="项目编号" width="110" resizable />
      <el-table-column prop="contract_number" label="合同编号" width="140" resizable>
        <template #default="{ row }">
          <span v-if="row.file_preview_url" class="contract-number-link" @click.stop="openPreview(row.file_preview_url)">{{ row.contract_number }}</span>
          <span v-else>{{ row.contract_number }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="project_name" label="工程名称" min-width="120" resizable />
      <el-table-column prop="procurement_name" label="采购项目名称" min-width="120" resizable />
      <el-table-column prop="supplier" label="供应商" width="120" resizable />
      <el-table-column prop="contract_price" label="合同价" width="100" resizable sortable="custom">
        <template #default="{ row }">{{ formatContractPrice(row.contract_price) }}</template>
      </el-table-column>
      <el-table-column prop="sign_date" label="签订日期" width="110" resizable sortable="custom">
        <template #default="{ row }">{{ formatDateYMD(row.sign_date) }}</template>
      </el-table-column>
      <el-table-column prop="content" label="采购内容" min-width="100" resizable />
      <el-table-column prop="control_price" label="采购控制价" width="110" resizable>
        <template #default="{ row }">{{ formatContractPrice(row.control_price) }}</template>
      </el-table-column>
      <el-table-column prop="funding_source" label="资金来源" width="100" resizable />
      <el-table-column prop="officer" label="经办人" width="100" resizable>
        <template #default="{ row }">
          <span style="white-space: pre-line">{{ row.officer || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="parent_contract_number" label="所属主合同" width="120" resizable>
        <template #default="{ row }">
          <span v-if="row.parent_contract_preview_url" class="contract-number-link" @click.stop="openPreview(row.parent_contract_preview_url)">{{ row.parent_contract_number || '-' }}</span>
          <span v-else style="white-space: pre-line">{{ row.parent_contract_number || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="supplement_contracts" label="补充协议" width="120" resizable>
        <template #default="{ row }">
          <span v-if="row.supplement_contracts_list?.length">
            <template v-for="(item, idx) in row.supplement_contracts_list" :key="idx">
              <span v-if="item.url" class="contract-number-link" @click.stop="openPreview(item.url)">{{ item.cn }}</span>
              <span v-else>{{ item.cn }}</span>
              <br v-if="idx < row.supplement_contracts_list.length - 1" />
            </template>
          </span>
          <span v-else style="white-space: pre-line">{{ row.supplement_contracts || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="create_time" label="录入时间" width="160" resizable sortable="custom">
        <template #default="{ row }">{{ formatDateYMD(row.create_time) }}</template>
      </el-table-column>
    </el-table>
    </div>
    <div class="pagination">
      <span>共 {{ total }} 条记录</span>
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        layout="prev, pager, next, jumper"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { listLedger, exportLedgerExcel, importLedgerExcel } from '@/api/ledger'
import { formatDateYMD, formatNumericLocale, formatContractPrice } from '@/utils/format'

const router = useRouter()

const tableData = ref<any[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const searchKeyword = ref('')
const selectedRows = ref<any[]>([])
const sortBy = ref('')
const sortOrder = ref<'ascending' | 'descending'>('ascending')
const fundingTypeFilter = ref('')
const groupTypeFilter = ref('')
const procurementMethodFilter = ref('')

const fundingTypeFilters = [
  { text: '全部', value: '' },
  { text: '工程类', value: '工程类' },
  { text: '自有资金', value: '自有资金' },
]
const groupTypeFilters = [
  { text: '全部', value: '' },
  { text: '集团内项目', value: '集团内项目' },
  { text: '集团外项目', value: '集团外项目' },
]
const procurementMethodFilters = [
  { text: '全部', value: '' },
  { text: '直接采购', value: '直接采购' },
  { text: '单一来源', value: '单一来源' },
  { text: '邀请询比', value: '邀请询比' },
  { text: '补充协议', value: '补充协议' },
  { text: '五选二', value: '五选二' },
]

function handleSelectionChange(rows: any[]) {
  selectedRows.value = rows
}

function handleSortChange({ prop, order }: { prop?: string; order?: string }) {
  sortBy.value = prop || ''
  sortOrder.value = (order === 'descending' ? 'descending' : 'ascending') as 'ascending' | 'descending'
  currentPage.value = 1
  loadData()
}

function handleFilterChange(filters: Record<string, string[]>) {
  fundingTypeFilter.value = filters.funding_type?.[0] || ''
  groupTypeFilter.value = filters.group_type?.[0] || ''
  procurementMethodFilter.value = filters.procurement_method?.[0] || ''
  currentPage.value = 1
  loadData()
}

onMounted(loadData)
watch([currentPage, pageSize, searchKeyword], loadData)

async function loadData() {
  try {
    const params: Record<string, unknown> = {
      keyword: searchKeyword.value,
      page: currentPage.value,
      page_size: pageSize.value,
    }
    if (sortBy.value) {
      params.sort_by = sortBy.value
      params.sort_order = sortOrder.value
    }
    if (fundingTypeFilter.value) params.funding_type = fundingTypeFilter.value
    if (groupTypeFilter.value) params.group_type = groupTypeFilter.value
    if (procurementMethodFilter.value) params.procurement_method = procurementMethodFilter.value
    const res = await listLedger(params)
    tableData.value = res.items
    total.value = res.total
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '加载失败')
  }
}

async function openPreview(url: string) {
  if (!url) return
  try {
    const token = localStorage.getItem('token')
    const fullUrl = url.startsWith('/') ? `${window.location.origin}${url}` : url
    const res = await fetch(fullUrl, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
    if (!res.ok) throw new Error(res.status === 401 ? '未登录或登录已过期' : '打开失败')
    const blob = await res.blob()
    const blobUrl = URL.createObjectURL(blob)
    window.open(blobUrl, '_blank')
  } catch (e: any) {
    ElMessage.error(e.message || '打开文件失败')
  }
}

function goToProcurement(row: any) {
  if (row.project_id && row.procurement_id) {
    router.push({
      path: '/procurements',
      query: { project_id: String(row.project_id), procurement_id: String(row.procurement_id) },
    })
  } else {
    ElMessage.warning('无法跳转')
  }
}

async function handleImport(file: File) {
  try {
    const res = await importLedgerExcel(file)
    ElMessage.success(`导入成功，新增 ${res.created || 0} 条`)
    loadData()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '导入失败')
  }
  return false
}

async function handleExport() {
  const ids = selectedRows.value.map((r) => r.id)
  if (!ids.length) {
    ElMessage.warning('请先勾选要导出的台账项')
    return
  }
  try {
    const blob = await exportLedgerExcel(ids)
    const url = URL.createObjectURL(blob as any)
    const a = document.createElement('a')
    a.href = url
    a.download = 'ledger.xlsx'
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || e.message || '导出失败')
  }
}
</script>

<style scoped lang="scss">
.ledger-view {
  .page-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 16px;
    h2 { font-size: 18px; }
  }
  .action-bar {
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .contract-number-link {
    color: var(--el-color-primary);
    cursor: pointer;
  }
  .contract-number-link:hover { text-decoration: underline; }
  .pagination {
    margin-top: 16px;
    display: flex;
    align-items: center;
    gap: 16px;
  }
  .table-scroll-wrapper { overflow-x: auto; width: 100%; }
}
</style>

<template>
  <div class="procurement-list-view">
    <div class="page-header">
      <el-form-item label="工程项目" class="project-select-item">
        <el-select
          v-model="selectedProjectId"
          :placeholder="projectSelectPlaceholder"
          filterable
          remote
          clearable
          :remote-method="loadProjectsForSelect"
          :loading="projectsLoading"
          class="procurement-project-select"
          @change="onProjectChange"
          @focus="onProjectSelectFocus"
        >
          <el-option
            v-for="p in projects"
            :key="p.id"
            :label="`${p.project_id || ''} ${p.project_name || ''}`.trim() || '未命名'"
            :value="p.id"
          />
        </el-select>
      </el-form-item>
      <div class="header-search-col">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索项目名称/合同编号/供应商"
          class="search-input"
          clearable
          @keyup.enter="loadProcurements"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <div v-if="selectedProjectId" class="table-total-above-grid">共 {{ upperTotal }} 条</div>
      </div>
    </div>
    <div class="action-bar">
      <el-button type="primary" :disabled="!selectedProjectId" @click="showAddProcurement">新增采购</el-button>
      <el-button type="danger" :disabled="!selectedProjectId || !selectedIds.length" @click="handleBatchDelete">删除</el-button>
      <el-button :disabled="!selectedProjectId" @click="handleExport">导出EXCEL</el-button>
    </div>

    <!-- 上区域：采购项目清单表格 -->
    <div ref="upperAreaRef" class="split-upper" :style="{ height: upperHeight + 'px' }">
      <div class="table-scroll-wrapper">
        <el-table
          ref="tableRef"
          :data="filteredProcurements"
          row-key="id"
          border
          :max-height="upperHeight - 80"
          highlight-current-row
          @row-dblclick="showOverview"
          @row-click="onRowClick"
          @selection-change="handleSelectionChange"
        >
          <el-table-column type="selection" width="50" reserve-selection :resizable="false" />
          <el-table-column prop="project_id_display" label="工程编号" width="120" resizable>
            <template #default>{{ project?.project_id || '-' }}</template>
          </el-table-column>
          <el-table-column prop="procurement_type" label="采购类型" width="100" resizable />
          <el-table-column prop="procurement_method" label="采购方式" width="100" resizable />
          <el-table-column prop="project_name" label="采购项目名称" min-width="100" width="140" resizable />
          <el-table-column prop="content" label="采购内容" width="100" resizable />
          <el-table-column prop="supplier" label="供应商" width="120" resizable>
            <template #default="{ row }"><span style="white-space: pre-line">{{ row.supplier || '-' }}</span></template>
          </el-table-column>
          <el-table-column prop="contract_price" label="合同价" width="100" resizable>
            <template #default="{ row }"><span style="white-space: pre-line">{{ row.contract_price_display ?? (row.contract_price != null ? formatContractPrice(row.contract_price) : '/') }}</span></template>
          </el-table-column>
          <el-table-column prop="sign_date" label="签订日期" width="110" resizable>
            <template #default="{ row }">{{ formatDateYMD(row.sign_date) }}</template>
          </el-table-column>
          <el-table-column prop="control_price" label="控制价" width="100" resizable>
            <template #default="{ row }">{{ formatContractPrice(row.control_price) }}</template>
          </el-table-column>
          <el-table-column prop="remark" label="备注" min-width="140" width="180" resizable>
            <template #default="{ row }">
              <el-input
                v-model="row.remark"
                type="textarea"
                :autosize="{ minRows: 1, maxRows: 8 }"
                clearable
                placeholder="可直接填写备注"
                class="remark-input"
                :disabled="!!remarkSavingMap[row.id]"
                @blur="saveRemarkInline(row)"
              />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right" :resizable="false">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click.stop="editProcurementRow(row)">编辑</el-button>
              <el-button type="danger" link size="small" @click.stop="handleDeleteProcurement(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- 可拖拽分隔线 -->
    <div
      class="split-handle"
      @mousedown="startDrag"
    >
      <span class="split-handle-bar">⋮⋮</span>
    </div>

    <!-- 下区域：文件管理（流程文件/归档文件） -->
    <div class="split-lower">
      <el-tabs v-model="activeFileTab">
        <el-tab-pane label="流程文件" name="process">
          <div class="file-toolbar">
            <template v-if="selectedProcurementForFiles">
              <el-button size="small" @click="openProcessFolder">打开本地目录</el-button>
              <span class="tip-text">流程文件存放于采购项目专属文件夹</span>
            </template>
            <span v-else class="tip-text">请在上方表格选择采购项目以查看文件</span>
          </div>
          <el-table :data="processFiles" size="small" row-key="name" :max-height="processFileTableMaxHeight" @selection-change="handleProcessFileSelectionChange">
            <el-table-column type="selection" width="50" />
            <el-table-column prop="name" label="文件名" min-width="120">
              <template #default="{ row }">
                <span class="file-name-link" @click="openProcessFileForEdit(row)">{{ row.name }}</span>
              </template>
            </el-table-column>
            <el-table-column label="同步状态" width="140">
              <template #default="{ row }">
                <el-tag v-if="row.sync_status === 'SYNCED'" type="success" size="small">已同步</el-tag>
                <el-tag v-else-if="row.sync_status === 'USER_MODIFIED'" type="warning" size="small">被手动修改</el-tag>
                <el-tag v-else-if="row.sync_status === 'OUTDATED_MANUAL_MERGE_REQUIRED'" type="danger" size="small">需人工合并</el-tag>
                <el-tag v-else type="info" size="small">已同步</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="类型" width="80">
              <template #default>流程文件</template>
            </el-table-column>
            <el-table-column prop="size" label="大小" width="100" />
            <el-table-column label="操作" min-width="220">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="previewProcessFile(row)">预览</el-button>
                <el-button
                  v-if="row.sync_status !== 'USER_MODIFIED' && row.sync_status !== 'OUTDATED_MANUAL_MERGE_REQUIRED'"
                  link
                  type="warning"
                  size="small"
                  @click="markProcessFileModified(row)"
                >
                  我已手动修改
                </el-button>
                <el-button
                  v-if="row.sync_status === 'OUTDATED_MANUAL_MERGE_REQUIRED'"
                  link
                  type="success"
                  size="small"
                  @click="confirmProcessFileMerge(row)"
                >
                  确认更新并完成合并
                </el-button>
                <el-button link type="danger" size="small" @click="deleteProcessFile(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="file-pagination">
            <span>共 {{ processFiles.length }} 条记录</span>
          </div>
        </el-tab-pane>
        <el-tab-pane label="归档文件" name="archive">
          <div class="file-toolbar">
            <template v-if="selectedProcurementForFiles">
              <el-button type="primary" size="small" @click="showUploadArchive">上传</el-button>
              <el-button size="small" @click="openArchiveFolder">打开本地目录</el-button>
            </template>
            <span v-else class="tip-text">请在上方表格选择采购项目</span>
          </div>
          <el-table :data="archiveFiles" size="small" row-key="id" @selection-change="handleArchiveFileSelectionChange">
            <el-table-column type="selection" width="50" />
            <el-table-column prop="file_name" label="文件名" min-width="120" />
            <el-table-column label="上传时间" width="110">
              <template #default="{ row }">{{ formatUploadTime(row.upload_time) }}</template>
            </el-table-column>
            <el-table-column prop="file_type" label="类型" width="100" />
            <el-table-column prop="file_size" label="大小" width="100">
              <template #default="{ row }">{{ formatFileSize(row.file_size) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="previewArchiveFile(row)">预览</el-button>
                <el-button type="danger" link size="small" @click="deleteArchiveFile(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="file-pagination">
            <span>共 {{ archiveFiles.length }} 条记录</span>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <el-dialog v-model="dialogVisible" :title="editingProcurementId ? '编辑采购项目' : '新增采购项目'" width="1000" destroy-on-close :close-on-click-modal="false">
      <el-steps :active="currentStep" finish-status="success" align-center>
        <el-step title="采购方式" />
        <el-step title="项目信息" />
        <el-step title="供应商" />
        <el-step title="流程时间" />
      </el-steps>
      <div class="step-content">
        <div v-show="currentStep === 0">
          <el-form :model="form.step1" label-width="120px">
            <el-form-item label="采购类型">
              <el-select v-model="form.step1.procurement_type" style="width: 100%" :disabled="!!editingProcurementId">
                <el-option label="材料采购" value="材料采购" />
                <el-option label="材料租赁" value="材料租赁" />
                <el-option label="设备采购" value="设备采购" />
                <el-option label="机械租赁" value="机械租赁" />
              </el-select>
            </el-form-item>
            <el-form-item label="采购方式">
              <el-select v-model="form.step1.procurement_method" style="width: 100%" :disabled="!!editingProcurementId" @change="onMethodChange">
                <el-option label="邀请询比" value="邀请询比" />
                <el-option label="单一来源" value="单一来源" />
                <el-option label="直接采购" value="直接采购" />
                <el-option label="五选二" value="五选二" />
                <el-option label="补充协议" value="补充协议" />
              </el-select>
            </el-form-item>
            <template v-if="form.step1.procurement_method === '补充协议'">
              <el-form-item label="主合同为五选二项目">
                <el-checkbox v-model="form.supplement_is_dual" :disabled="!!editingProcurementId" @change="onSupplementIsDualChange">勾选</el-checkbox>
              </el-form-item>
              <el-form-item v-if="form.supplement_is_dual" label="标段">
                <el-select v-model="form.contract_section" placeholder="选择标段" style="width: 100%" :disabled="!!editingProcurementId" @change="onContractSectionChange">
                  <el-option label="一标段" value="一标段" />
                  <el-option label="二标段" value="二标段" />
                </el-select>
              </el-form-item>
              <el-form-item :label="form.supplement_is_dual ? '主合同' : '选择主合同'">
                <el-select
                  v-model="form.parent_contract_id"
                  :placeholder="form.supplement_is_dual ? '选择主合同编号' : '选择主合同'"
                  filterable
                  style="width: 100%"
                  :disabled="!!editingProcurementId"
                  @change="onParentContractSelect"
                >
                  <el-option
                    v-for="p in filteredParentContractOptions"
                    :key="p.id"
                    :label="p.contract_number || String(p.id)"
                    :value="p.id"
                  />
                </el-select>
              </el-form-item>
            </template>
          </el-form>
        </div>
        <div v-show="currentStep === 1">
          <el-form v-if="form.step1.procurement_method === '补充协议'" :model="form" label-width="180px">
            <el-form-item label="工程名称">
              <el-input :model-value="project?.project_name || form.step2.project_name" disabled />
            </el-form-item>
            <el-form-item label="工程编号">
              <el-input :model-value="form.step2.project_id" disabled />
            </el-form-item>
            <el-form-item label="主合同编号">
              <el-input :model-value="parentContractInfo?.contract_number" disabled />
            </el-form-item>
            <el-form-item label="原合同价（元）">
              <el-input :model-value="parentContractInfo?.original_price?.toLocaleString()" disabled />
            </el-form-item>
            <el-form-item label="采购项目名称">
              <el-input v-model="form.supplement_procurement_project_name" placeholder="默认与主合同采购项目名称一致，可修改" />
            </el-form-item>
            <el-form-item label="控制价（元）">
              <NumericInput v-model="form.supplement_control_price" style="width: 100%" />
            </el-form-item>
            <el-form-item label="新增金额（元）" required>
              <NumericInput v-model="form.supplement_amount" style="width: 100%" />
            </el-form-item>
            <el-form-item label="补充内容" required>
              <el-input v-model="form.supplement_content" type="textarea" :rows="3" />
            </el-form-item>
            <el-form-item label="补充协议日期">
              <el-input v-model="form.step2.sign_date" placeholder="如 2026.3.15" />
            </el-form-item>
          </el-form>
          <el-form v-else :model="form.step2" label-width="180px">
            <el-form-item label="采购类型">
              <el-input v-model="form.step2.procurement_type" disabled />
            </el-form-item>
            <el-form-item label="采购方式">
              <el-input v-model="form.step2.procurement_method" disabled />
            </el-form-item>
            <el-form-item label="类别">
              <el-radio-group v-model="form.step2.leibie">
                <el-radio label="专业分包类" />
                <el-radio label="劳务分包类" />
                <el-radio label="材料物资类" />
                <el-radio label="设备租赁类" />
                <el-radio label="服务类" />
              </el-radio-group>
            </el-form-item>
            <el-form-item label="工程名称">
              <el-input v-model="form.step2.project_name" disabled>
                <template #append><el-button @click="copyToClipboard(form.step2.project_name)">复制</el-button></template>
              </el-input>
            </el-form-item>
            <el-form-item label="项目编号">
              <el-input v-model="form.step2.project_number" disabled>
                <template #append><el-button @click="copyToClipboard(form.step2.project_number)">复制</el-button></template>
              </el-input>
            </el-form-item>
            <el-form-item label="工程编号">
              <el-input v-model="form.step2.project_id" disabled>
                <template #append><el-button @click="copyToClipboard(form.step2.project_id)">复制</el-button></template>
              </el-input>
            </el-form-item>
            <el-form-item label="发包单位">
              <el-input v-model="form.step2.construction_unit" disabled>
                <template #append><el-button @click="copyToClipboard(form.step2.construction_unit)">复制</el-button></template>
              </el-input>
            </el-form-item>
            <el-form-item label="发包方联系人">
              <el-input v-model="form.step2.construction_contact_person" disabled>
                <template #append><el-button @click="copyToClipboard(form.step2.construction_contact_person || '')">复制</el-button></template>
              </el-input>
            </el-form-item>
            <el-form-item label="发包方联系方式">
              <el-input v-model="form.step2.construction_contact_phone" disabled>
                <template #append><el-button @click="copyToClipboard(form.step2.construction_contact_phone || '')">复制</el-button></template>
              </el-input>
            </el-form-item>
            <el-form-item label="总包合同价">
              <el-input :model-value="form.step2.total_contract_price?.toLocaleString()" disabled>
                <template #append><el-button @click="copyToClipboard(String(form.step2.total_contract_price))">复制</el-button></template>
              </el-input>
            </el-form-item>
            <el-form-item label="采购项目名称">
              <el-input v-model="form.step2.procurement_project_name" />
            </el-form-item>
            <template v-if="form.step1.procurement_method === '五选二'">
              <el-form-item label="一标段名">
                <el-input v-model="form.step2.biaoduanming1" />
              </el-form-item>
              <el-form-item label="二标段名">
                <el-input v-model="form.step2.biaoduanming2" />
              </el-form-item>
            </template>
            <el-form-item label="采购内容">
              <el-input v-model="form.step2.content" />
            </el-form-item>
            <el-form-item label="控制价（元）">
              <NumericInput v-model="form.step2.control_price" style="width: 100%" />
            </el-form-item>
            <template v-if="form.step1.procurement_method === '五选二'">
              <el-form-item label="控制价标1（元）">
                <NumericInput v-model="form.step2.kongzhijia_biao1" style="width: 100%" />
              </el-form-item>
              <el-form-item label="控制价标2（元）">
                <NumericInput v-model="form.step2.kongzhijia_biao2" style="width: 100%" />
              </el-form-item>
            </template>
            <el-form-item label="采购预算（万元）">
              <el-input :model-value="((form.step2.control_price ?? 0) / 10000).toFixed(2)" disabled />
            </el-form-item>
            <el-form-item v-if="form.step1.procurement_method !== '直接采购'" label="计税方式">
              <el-radio-group v-model="form.step2.tax_method">
                <el-radio label="一般计税方法计算" />
                <el-radio label="简易计税方法计算" />
              </el-radio-group>
            </el-form-item>
            <el-form-item v-if="form.step1.procurement_method !== '直接采购'" label="合同文本格式">
              <el-radio-group v-model="form.step2.contract_format">
                <el-radio label="采用公司印发的合同标准文本编制" />
                <el-radio label="采用非公司印发的合同标准文本编制" />
              </el-radio-group>
            </el-form-item>
            <el-form-item label="合同是否使用公司标准范本">
              <el-radio-group v-model="form.step2.use_standard_contract">
                <el-radio label="是" />
                <el-radio label="否，但合同已经过法律审核，并有相关证明资料" />
              </el-radio-group>
            </el-form-item>
            <el-form-item label="是否经过公司招采程序">
              <el-radio-group v-model="form.step2.passed_procurement">
                <el-radio label="是" />
                <el-radio label="否，原因：/" />
              </el-radio-group>
            </el-form-item>
            <el-form-item label="是否经过审核校对">
              <el-radio-group v-model="form.step2.reviewed">
                <el-radio label="是" />
                <el-radio label="否" />
              </el-radio-group>
            </el-form-item>
            <el-form-item v-if="form.step1.procurement_method === '直接采购'" label="合同签订时间">
              <el-input v-model="form.step2.sign_date" placeholder="如 2026.3.15" style="width: 100%" />
            </el-form-item>
            <template v-if="form.step1.procurement_method !== '直接采购'">
            <el-form-item label="公告日期">
              <span class="date-inputs">
                <el-input v-model="form.step2.gonggao_year" placeholder="年" style="width: 80px" />
                <span>/</span>
                <el-input v-model="form.step2.gonggao_month" placeholder="月" style="width: 60px" />
                <span>/</span>
                <el-input v-model="form.step2.gonggao_day" placeholder="日" style="width: 60px" />
              </span>
            </el-form-item>
            <el-form-item label="意向报名截止日期">
              <span class="date-inputs">
                <el-input v-model="form.step2.yixiang_baoming_jiezhi_year" placeholder="年" style="width: 80px" />
                <span>/</span>
                <el-input v-model="form.step2.yixiang_baoming_jiezhi_month" placeholder="月" style="width: 60px" />
                <span>/</span>
                <el-input v-model="form.step2.yixiang_baoming_jiezhi_day" placeholder="日" style="width: 60px" />
              </span>
            </el-form-item>
            <el-form-item label="交易文件封面年月">
              <span class="date-inputs">
                <el-input v-model="form.step2.jiaoyi_fengmian_year" placeholder="年" style="width: 80px" />
                <span>/</span>
                <el-input v-model="form.step2.jiaoyi_fengmian_month" placeholder="月" style="width: 60px" />
              </span>
            </el-form-item>
            <el-form-item label="交易文件日期">
              <span class="date-inputs">
                <el-input v-model="form.step2.jiaoyi_wenjian_year" placeholder="年" style="width: 80px" />
                <span>/</span>
                <el-input v-model="form.step2.jiaoyi_wenjian_month" placeholder="月" style="width: 60px" />
                <span>/</span>
                <el-input v-model="form.step2.jiaoyi_wenjian_day" placeholder="日" style="width: 60px" />
              </span>
            </el-form-item>
            <el-form-item label="交易文件获取截止日期">
              <span class="date-inputs">
                <el-input v-model="form.step2.jiaoyi_wenjian_huoqv_jiezhi_year" placeholder="年" style="width: 80px" />
                <span>/</span>
                <el-input v-model="form.step2.jiaoyi_wenjian_huoqv_jiezhi_month" placeholder="月" style="width: 60px" />
                <span>/</span>
                <el-input v-model="form.step2.jiaoyi_wenjian_huoqv_jiezhi_day" placeholder="日" style="width: 60px" />
              </span>
            </el-form-item>
            <el-form-item label="响应文件递交截止日期">
              <span class="date-inputs">
                <el-input v-model="form.step2.xiangying_dijiao_jiezhi_year" placeholder="年" style="width: 80px" />
                <span>/</span>
                <el-input v-model="form.step2.xiangying_dijiao_jiezhi_month" placeholder="月" style="width: 60px" />
                <span>/</span>
                <el-input v-model="form.step2.xiangying_dijiao_jiezhi_day" placeholder="日" style="width: 60px" />
              </span>
            </el-form-item>
            <el-form-item label="合同签订时间">
              <span class="date-inputs">
                <el-input v-model="form.step2.qianding_year" placeholder="年" style="width: 80px" />
                <span>/</span>
                <el-input v-model="form.step2.qianding_month" placeholder="月" style="width: 60px" />
                <span>/</span>
                <el-input v-model="form.step2.qianding_day" placeholder="日" style="width: 60px" />
              </span>
            </el-form-item>
            </template>
          </el-form>
        </div>
        <div v-show="currentStep === 2">
          <div v-if="form.step1.procurement_method === '补充协议'" class="supplement-note">
            以下为与主合同中标供应商一致的信息（名称、联系人、联系方式可改）。<strong>含税报价（元）</strong>即第 1 步填写的<strong>新增金额</strong>，与主合同含税报价无关，不可在此修改。经营范围、税率与主合同一致，不可改。
          </div>
          <el-button v-if="form.step1.procurement_method !== '补充协议'" type="primary" size="small" :disabled="!canAddSupplier" @click="addSupplier">添加供应商</el-button>
          <el-table :data="form.suppliers" style="margin-top: 12px">
            <el-table-column type="index" label="序号" width="60" />
            <el-table-column label="供应商" width="140">
              <template #default="{ row }">
                <el-input v-model="row.supplier_name" placeholder="供应商名称" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="联系人" width="100">
              <template #default="{ row }">
                <el-input v-model="row.contact_person" placeholder="联系人" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="联系方式" width="120">
              <template #default="{ row }">
                <el-input v-model="row.contact_phone" placeholder="联系方式" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="经营范围" min-width="120">
              <template #default="{ row }">
                <el-input
                  v-if="form.step1.procurement_method !== '补充协议'"
                  v-model="row.business_scope"
                  placeholder="经营范围"
                  size="small"
                />
                <span v-else class="cell-readonly">{{ row.business_scope || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="税率" width="80">
              <template #default="{ row }">
                <el-input
                  v-if="form.step1.procurement_method !== '补充协议'"
                  v-model="row.tax_rate"
                  placeholder="如13%"
                  size="small"
                />
                <span v-else class="cell-readonly">{{ row.tax_rate || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="含税报价（元）" width="140">
              <template #default="{ row }">
                <NumericInput
                  v-if="form.step1.procurement_method !== '补充协议'"
                  v-model="row.quoted_price"
                  size="small"
                  style="width: 100%"
                />
                <span v-else class="cell-readonly">{{ formatSupplementQuotedDisplay(row.quoted_price) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80" fixed="right">
              <template #default="{ $index }">
                <el-button link type="danger" :disabled="!canRemoveSupplier" @click="removeSupplier($index)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div v-if="form.step1.procurement_method !== '补充协议' && form.suppliers.length" class="deal-amount-area">
            <template v-if="form.step1.procurement_method === '五选二'">
              <div class="deal-amount-row">
                <span>一标段中选人：</span>
                <span>{{ sortedSuppliers[0]?.supplier_name || '-' }} {{ sortedSuppliers[0]?.quoted_price != null ? `（${sortedSuppliers[0].quoted_price?.toLocaleString()} 元）` : '' }}</span>
              </div>
              <div class="deal-amount-row">
                <span>二标段中选人：</span>
                <span>{{ sortedSuppliers[1]?.supplier_name || '-' }} {{ sortedSuppliers[1]?.quoted_price != null ? `（${sortedSuppliers[1].quoted_price?.toLocaleString()} 元）` : '' }}</span>
              </div>
              <div class="deal-amount-row">
                <span>成交金额1（元）</span>
                <NumericInput v-model="form.step2.chengjiao_jine1" style="width: 160px" />
                <span class="ml">成交金额1（大写）：</span>
                <span>{{ numToCn(form.step2.chengjiao_jine1 ?? 0) }}</span>
              </div>
              <div class="deal-amount-row">
                <span>成交金额2（元）</span>
                <NumericInput v-model="form.step2.chengjiao_jine2" style="width: 160px" />
                <span class="ml">成交金额2（大写）：</span>
                <span>{{ numToCn(form.step2.chengjiao_jine2 ?? 0) }}</span>
              </div>
            </template>
            <template v-else>
              <div class="deal-amount-row">
                <span>成交金额：</span>
                <span>{{ sortedSuppliers[0]?.quoted_price?.toLocaleString() ?? '-' }} 元</span>
                <span class="ml">成交金额（大写）：</span>
                <span>{{ numToCn(sortedSuppliers[0]?.quoted_price ?? 0) }}</span>
              </div>
            </template>
          </div>
        </div>
        <div v-show="currentStep === 3">
          <div v-if="processTimeTableTitle" class="process-time-title" style="margin-bottom: 12px; font-weight: 600">
            {{ processTimeTableTitle }}
          </div>
          <el-table :data="form.time_records" style="margin-top: 12px">
            <el-table-column type="index" label="序号" width="60" />
            <el-table-column prop="flow_name" label="流程" min-width="200" />
            <el-table-column label="日期" width="180">
              <template #default="{ row, $index }">
                <el-input v-model="form.time_records[$index].date_val" placeholder="如 2026.3.15" style="width: 100%" />
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
      <template #footer>
        <el-button v-if="currentStep > 0" @click="currentStep--">上一步</el-button>
        <el-button v-if="currentStep < 3" type="primary" @click="currentStep++">下一步</el-button>
        <el-button v-else type="primary" :loading="saving" @click="submitProcurement">完成</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="overviewVisible" title="采购项目总览" width="910" :close-on-click-modal="false">
      <div v-if="overviewData" class="overview-content">
        <h4 style="margin: 0 0 8px">工程项目信息</h4>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="工程名称">{{ overviewData.project_name }}</el-descriptions-item>
          <el-descriptions-item label="工程编号">{{ overviewData.project_number }}</el-descriptions-item>
          <el-descriptions-item label="工程ID">{{ overviewData.project_id_display }}</el-descriptions-item>
          <el-descriptions-item label="发包单位">{{ overviewData.construction_unit }}</el-descriptions-item>
          <el-descriptions-item label="发包方联系人">{{ overviewData.construction_contact_person || '-' }}</el-descriptions-item>
          <el-descriptions-item label="发包方联系方式">{{ overviewData.construction_contact_phone || '-' }}</el-descriptions-item>
          <el-descriptions-item label="合同总价">{{ overviewData.total_contract_price?.toLocaleString() }} 元</el-descriptions-item>
          <el-descriptions-item label="工程地址">{{ overviewData.project_address }}</el-descriptions-item>
          <el-descriptions-item label="项目部">{{ overviewData.department }}</el-descriptions-item>
          <el-descriptions-item label="现场管理人">{{ overviewData.site_manager }}</el-descriptions-item>
          <el-descriptions-item label="现场管理人电话">{{ overviewData.site_manager_phone }}</el-descriptions-item>
        </el-descriptions>
        <h4 style="margin: 16px 0 8px">采购信息</h4>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="采购类型">{{ overviewData.procurement_type }}</el-descriptions-item>
          <el-descriptions-item label="采购方式">{{ overviewData.procurement_method }}</el-descriptions-item>
          <el-descriptions-item label="合同编号">{{ overviewData.contract_number }}</el-descriptions-item>
          <el-descriptions-item label="标段">{{ overviewData.contract_section || '-' }}</el-descriptions-item>
          <el-descriptions-item label="采购项目名称">{{ overviewData.procurement_project_name }}</el-descriptions-item>
          <el-descriptions-item label="签订日期">{{ formatDateYMD(overviewData.sign_date) }}</el-descriptions-item>
          <el-descriptions-item label="采购内容" :span="2">{{ overviewData.content }}</el-descriptions-item>
          <el-descriptions-item label="控制价">{{ overviewControlPriceLabel }}</el-descriptions-item>
          <template v-if="overviewData.procurement_method === '五选二' && overviewData.step2">
            <el-descriptions-item label="一标段名称">{{ overviewData.step2.biaoduanming1 || '-' }}</el-descriptions-item>
            <el-descriptions-item label="二标段名称">{{ overviewData.step2.biaoduanming2 || '-' }}</el-descriptions-item>
            <el-descriptions-item label="控制价（一标段）">{{ overviewData.step2.kongzhijia_biao1 != null ? overviewData.step2.kongzhijia_biao1?.toLocaleString() : '-' }} 元</el-descriptions-item>
            <el-descriptions-item label="控制价（二标段）">{{ overviewData.step2.kongzhijia_biao2 != null ? overviewData.step2.kongzhijia_biao2?.toLocaleString() : '-' }} 元</el-descriptions-item>
            <el-descriptions-item label="成交金额1">{{ overviewData.step2.chengjiao_jine1 != null ? overviewData.step2.chengjiao_jine1?.toLocaleString() : '-' }} 元</el-descriptions-item>
            <el-descriptions-item label="成交金额2">{{ overviewData.step2.chengjiao_jine2 != null ? overviewData.step2.chengjiao_jine2?.toLocaleString() : '-' }} 元</el-descriptions-item>
          </template>
        </el-descriptions>
        <h4 style="margin: 16px 0 8px">供应商</h4>
        <el-table :data="overviewSuppliers" size="small">
          <el-table-column prop="supplier_name" label="供应商" min-width="120" />
          <el-table-column prop="contact_person" label="联系人" width="80" />
          <el-table-column prop="contact_phone" label="联系方式" width="110" />
          <el-table-column prop="quoted_price" label="含税报价" width="110">
            <template #default="{ row }">
              {{ row.quoted_price == null || row.quoted_price === '' ? '-' : `${formatContractPrice(row.quoted_price)} 元` }}
            </template>
          </el-table-column>
          <el-table-column prop="contract_section" label="标段" width="70" />
          <el-table-column prop="is_winner" label="中标" width="55">
            <template #default="{ row }">{{ row.is_winner ? '是' : '' }}</template>
          </el-table-column>
        </el-table>
        <h4 v-if="overviewData.time_records?.length" style="margin: 16px 0 8px">流程时间</h4>
        <el-table v-if="overviewData.time_records?.length" :data="overviewData.time_records" size="small">
          <el-table-column prop="flow_name" label="流程" min-width="180" />
          <el-table-column prop="date_val" label="日期" width="120">
            <template #default="{ row }">{{ formatDateYMD(row.date_val) }}</template>
          </el-table-column>
        </el-table>
      </div>
    </el-dialog>

    <el-dialog v-model="docxPreviewVisible" :title="docxPreviewTitle" width="90%" top="5vh" destroy-on-close>
      <div ref="docxPreviewContainer" class="docx-preview-container" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { useBreadcrumbStore } from '@/store/breadcrumb'
import { listProjects, getProject } from '@/api/projects'
import { listProcurements, createProcurement, getProcurement, updateProcurement, updateProcurementRemark, deleteProcurement, getParentContractOptions } from '@/api/procurements'
import request from '@/api/request'
import { formatDateYMD, formatNumericLocale, formatContractPrice } from '@/utils/format'
import nzhcn from 'nzh/cn'
import NumericInput from '@/components/NumericInput.vue'
import { renderAsync } from 'docx-preview'
import { useRealtimeSync, EventType } from '@/composables/useRealtimeSync'

const route = useRoute()
const router = useRouter()
const bc = useBreadcrumbStore()
const projects = ref<any[]>([])
const projectsLoading = ref(false)
const projectsLoadedOnce = ref(false)
const selectedProjectId = ref<number | null>(null)
const project = computed(() => (selectedProjectId.value ? projects.value.find((p) => p.id === selectedProjectId.value) : null))
const projectSelectPlaceholder = '请选择或搜索工程项目（点击输入关键词）'
const procurements = ref<any[]>([])
const remarkSavingMap = ref<Record<number, boolean>>({})

const { updateContext } = useRealtimeSync({
  context: { project_id: selectedProjectId.value ?? undefined, scope: 'procurement_list' },
  onEvent: (e) => {
    const procEvents = [EventType.PROCUREMENT_CREATED, EventType.PROCUREMENT_UPDATED, EventType.PROCUREMENT_DELETED]
    if (procEvents.includes(e.type as string) && selectedProjectId.value) {
      const payload = e.payload as { project_id?: number }
      if (!payload?.project_id || payload.project_id === selectedProjectId.value) {
        loadProcurements()
      }
    }
    if ([EventType.FILE_UPLOADED, EventType.FILE_DELETED,
         EventType.PROCESS_FILE_SYNC_STATUS_CHANGED,
         EventType.LEDGER_CREATED, EventType.LEDGER_UPDATED].includes(e.type as string)) {
      const payload = e.payload as { project_id?: number; procurement_id?: number }
      if (payload?.project_id === selectedProjectId.value) {
        if (selectedProcurementForFiles.value && payload?.procurement_id === selectedProcurementForFiles.value.id) {
          loadFilesForProcurement(selectedProcurementForFiles.value.id)
        }
      }
    }
  },
})
const tableRef = ref()
const searchKeyword = ref('')
const upperHeight = ref(280)
const upperAreaRef = ref<HTMLElement>()
const activeFileTab = ref<'process' | 'archive'>('process')
const selectedIds = ref<number[]>([])
const selectedProcurementForEdit = ref<any>(null)
const selectedProcurementForFiles = ref<any>(null)
const editingProcurementId = ref<number | null>(null)
const editingProcurementDetail = ref<any>(null)

const filteredProcurements = computed(() => {
  const kw = (searchKeyword.value || '').trim().toLowerCase()
  if (!kw) return procurements.value
  return procurements.value.filter(
    (p: any) =>
      (p.contract_number || '').toLowerCase().includes(kw) ||
      (p.supplier || '').toLowerCase().includes(kw) ||
      (p.project_name || '').toLowerCase().includes(kw) ||
      (project.value?.project_name || '').toLowerCase().includes(kw)
  )
})

const upperTotal = computed(() => filteredProcurements.value.length)

const processFiles = ref<any[]>([])
const archiveFiles = ref<any[]>([])
const processFilePrintModes = ref<Record<string, string>>({})
const processFileSelections = ref<any[]>([])

const processFileTableMaxHeight = 350
const archiveFileSelections = ref<any[]>([])

const sortedSuppliers = computed(() => {
  const list = form.suppliers.filter((s) => s && (s.quoted_price ?? 0) >= 0)
  return [...list].sort((a, b) => (a.quoted_price ?? 0) - (b.quoted_price ?? 0))
})

const processTimeTableTitle = computed(() => {
  const p = form.step2
  const method = form.step1.procurement_method
  const projectId = p.project_id || ''
  const projectName = p.project_name || ''
  const content = p.content || ''
  if (method === '补充协议') {
    let seq: number | undefined
    if (editingProcurementId.value && editingProcurementDetail.value) {
      const cn = editingProcurementDetail.value.contract_number || ''
      const m = cn.match(/-补(\d+)$/)
      seq = m ? parseInt(m[1], 10) : undefined
    }
    if (seq == null) seq = parentContractInfo.value?.next_supplement_seq ?? 1
    return `${projectId}${projectName}${content}补充协议${seq}`
  }
  return `${projectId}${projectName}${content}`
})

function numToCn(num: number): string {
  if (num == null || num <= 0) return '零元整'
  const n = Math.round(num * 100) / 100
  return nzhcn.toMoney(String(n), { outSymbol: false })
}

async function loadProcurements() {
  if (!selectedProjectId.value) {
    procurements.value = []
    return
  }
  const list = await listProcurements(selectedProjectId.value, true)
  procurements.value = (list || []).map((p: any) => ({
    ...p,
    remark: p.remark || '',
    _remarkOriginal: p.remark || '',
  }))
}

async function saveRemarkInline(row: any) {
  if (!row?.id) return
  const nextRemark = String(row.remark || '').trim()
  const prevRemark = String(row._remarkOriginal || '')
  if (nextRemark === prevRemark) return
  try {
    remarkSavingMap.value[row.id] = true
    await updateProcurementRemark(row.id, nextRemark)
    row._remarkOriginal = nextRemark
    row.remark = nextRemark
    ElMessage.success('备注已保存')
  } catch (e: any) {
    row.remark = prevRemark
    ElMessage.error(e?.response?.data?.detail || '备注保存失败')
  } finally {
    remarkSavingMap.value[row.id] = false
  }
}

async function loadProjectsForSelect(keyword: string) {
  projectsLoading.value = true
  try {
    const list = await listProjects({ keyword: (keyword || '').trim(), page: 1, page_size: 0 })
    let merged = list
    if (selectedProjectId.value && !list.find((p: any) => p.id === selectedProjectId.value)) {
      try {
        const p = await getProject(selectedProjectId.value)
        merged = [p, ...list]
      } catch {
        // 当前选中的工程可能已删除，忽略
      }
    }
    projects.value = merged
    projectsLoadedOnce.value = true
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载工程项目列表失败')
    if (!projects.value.length) projects.value = []
  } finally {
    projectsLoading.value = false
  }
}

function onProjectSelectFocus() {
  if (!projectsLoadedOnce.value && !projectsLoading.value) {
    loadProjectsForSelect('')
  }
}

function updateBreadcrumb() {
  const p = project.value
  bc.setProcurementContext({
    projectId: p?.id ?? null,
    projectNumber: p?.project_id ?? '',
    projectName: p?.project_name ?? '',
    procurementId: null,
    procurementName: '',
  })
}

watch(selectedProjectId, (id) => {
  updateContext({ project_id: id ?? undefined, scope: 'procurement_list' })
})

function onProjectChange() {
  procurements.value = []
  selectedProcurementForFiles.value = null
  processFiles.value = []
  archiveFiles.value = []
  if (selectedProjectId.value) {
    loadProcurements()
    updateBreadcrumb()
  } else {
    bc.setProcurementContext({ projectId: null, projectNumber: '', projectName: '', procurementId: null, procurementName: '' })
  }
}

function startDrag(e: MouseEvent) {
  const startY = e.clientY
  const startH = upperHeight.value
  const onMove = (ev: MouseEvent) => {
    const dy = ev.clientY - startY
    const newH = Math.max(120, Math.min(500, startH + dy))
    upperHeight.value = newH
  }
  const onUp = () => {
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
  }
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}

function onRowClick(row: any) {
  selectedProcurementForFiles.value = row
  loadFilesForProcurement(row.id)
}

function handleSelectionChange(rows: any[]) {
  selectedIds.value = rows.map((r) => r.id)
  selectedProcurementForEdit.value = rows.length === 1 ? rows[0] : null
}

async function loadFilesForProcurement(procId: number) {
  try {
    const [processRes, archiveRes] = await Promise.all([
      request.get('/files/process-list', { params: { procurement_id: procId } }),
      request.get('/files', { params: { procurement_id: procId } }),
    ])
    processFiles.value = Array.isArray(processRes) ? processRes : []
    archiveFiles.value = Array.isArray(archiveRes) ? archiveRes : []
    processFilePrintModes.value = {}
  } catch {
    processFiles.value = []
    archiveFiles.value = []
  }
}

function showUploadArchive() {
  if (selectedProcurementForFiles.value && project.value) {
    router.push({
      path: '/archive',
      query: { project_id: String(project.value.id), procurement_id: String(selectedProcurementForFiles.value.id) },
    })
  }
}

async function deleteArchiveFile(row: any) {
  try {
    await ElMessageBox.confirm('确定删除该文件？', '提示', { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' })
    await request.delete(`/files/${row.id}`)
    ElMessage.success('已删除')
    if (selectedProcurementForFiles.value) loadFilesForProcurement(selectedProcurementForFiles.value.id)
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

function handleProcessFileSelectionChange(rows: any[]) {
  processFileSelections.value = rows
}
function handleArchiveFileSelectionChange(rows: any[]) {
  archiveFileSelections.value = rows
}

const docxPreviewVisible = ref(false)
const docxPreviewContainer = ref<HTMLElement>()
const docxPreviewTitle = ref('')

async function downloadProcessFile(row: { name: string }) {
  const token = localStorage.getItem('token')
  const url = `/api/files/process-content?procurement_id=${selectedProcurementForFiles.value!.id}&filename=${encodeURIComponent(row.name)}`
  const res = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
  if (!res.ok) throw new Error('下载失败')
  const blob = await res.blob()
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = row.name
  a.click()
  URL.revokeObjectURL(a.href)
  ElMessage.success('已下载，请用本地应用打开编辑')
}

async function openProcessFileForEdit(row: { name: string }) {
  if (!selectedProcurementForFiles.value) return
  try {
    const res = await request.post('/files/process-file-open', null, {
      params: { procurement_id: selectedProcurementForFiles.value.id, filename: row.name },
    })
    const data = res as any
    if (data?.message === 'ok') {
      ElMessage.success('已打开文件')
      return
    }
    await downloadProcessFile(row)
  } catch {
    try {
      await downloadProcessFile(row)
    } catch (e: any) {
      ElMessage.error(e.response?.data?.detail || e.message || '打开失败')
    }
  }
}

async function previewProcessFile(row: { name: string }) {
  if (!selectedProcurementForFiles.value) return
  try {
    const token = localStorage.getItem('token')
    const url = `/api/files/process-content?procurement_id=${selectedProcurementForFiles.value.id}&filename=${encodeURIComponent(row.name)}`
    const res = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
    if (!res.ok) throw new Error('打开失败')
    const blob = await res.blob()
    const ext = (row.name || '').toLowerCase().split('.').pop()
    if (ext === 'docx' || ext === 'doc') {
      docxPreviewTitle.value = row.name
      docxPreviewVisible.value = true
      await nextTick()
      const container = docxPreviewContainer.value
      if (container) {
        container.innerHTML = ''
        const arrayBuffer = await blob.arrayBuffer()
        await renderAsync(arrayBuffer, container)
      }
    } else {
      const blobUrl = URL.createObjectURL(blob)
      window.open(blobUrl, '_blank')
    }
  } catch (e: any) {
    ElMessage.error(e.message || '打开失败')
  }
}

async function openProcessFolder() {
  if (!selectedProcurementForFiles.value) return
  try {
    const res = await request.post('/files/process-folder-open', null, {
      params: { procurement_id: selectedProcurementForFiles.value.id },
    })
    const data = res as any
    if (data?.message === 'ok') {
      ElMessage.success('已打开文件夹')
    } else if (data?.path) {
      await navigator.clipboard.writeText(data.path)
      ElMessage.success('路径已复制到剪贴板，可在资源管理器中粘贴打开')
    } else {
      ElMessage.warning('无法打开文件夹')
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '打开失败')
  }
}

async function openArchiveFolder() {
  if (!selectedProcurementForFiles.value) return
  try {
    const res = await request.post('/files/archive-folder-open', null, {
      params: { procurement_id: selectedProcurementForFiles.value.id },
    })
    const data = res as any
    if (data?.message === 'ok') {
      ElMessage.success('已打开文件夹')
    } else if (data?.path) {
      await navigator.clipboard.writeText(data.path)
      ElMessage.success('路径已复制到剪贴板，可在资源管理器中粘贴打开')
    } else {
      ElMessage.warning('无法打开文件夹')
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '打开失败')
  }
}
async function markProcessFileModified(row: { name: string }) {
  if (!selectedProcurementForFiles.value) return
  try {
    await ElMessageBox.confirm('确认标记该文件为「我已手动修改」？后续表单保存时将备份旧版本并生成新文件，需您手动合并。', '提示', { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' })
    await request.post('/files/process-file-mark-modified', null, { params: { procurement_id: selectedProcurementForFiles.value.id, filename: row.name } })
    ElMessage.success('已标记')
    await loadFilesForProcurement(selectedProcurementForFiles.value.id)
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error((e as any).response?.data?.detail || '操作失败')
  }
}

async function confirmProcessFileMerge(row: { name: string }) {
  if (!selectedProcurementForFiles.value) return
  try {
    await ElMessageBox.confirm('确认已完成手动合并？系统将保留最近2个备份版本。', '提示', { confirmButtonText: '确定', cancelButtonText: '取消', type: 'info' })
    await request.post('/files/process-file-confirm-merge', null, { params: { procurement_id: selectedProcurementForFiles.value.id, filename: row.name } })
    ElMessage.success('已确认')
    await loadFilesForProcurement(selectedProcurementForFiles.value.id)
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error((e as any).response?.data?.detail || '操作失败')
  }
}

async function deleteProcessFile(row: { name: string }) {
  if (!selectedProcurementForFiles.value) return
  try {
    await ElMessageBox.confirm('确定删除该流程文件？', '提示', { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' })
    await request.delete('/files/process-file', { params: { procurement_id: selectedProcurementForFiles.value.id, filename: row.name } })
    ElMessage.success('已删除')
    loadFilesForProcurement(selectedProcurementForFiles.value.id)
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error((e as any).response?.data?.detail || '删除失败')
  }
}
async function previewArchiveFile(row: { id: number }) {
  try {
    const token = localStorage.getItem('token')
    const res = await fetch(`/api/files/${row.id}/content`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
    if (!res.ok) throw new Error('下载失败')
    const blob = await res.blob()
    const blobUrl = URL.createObjectURL(blob)
    window.open(blobUrl, '_blank')
  } catch (e: any) {
    ElMessage.error(e.message || '打开失败')
  }
}
function formatUploadTime(t: string | undefined) {
  if (!t) return '-'
  const d = new Date(t)
  return isNaN(d.getTime()) ? '-' : `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
function formatFileSize(bytes: number | undefined) {
  if (bytes == null) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function editProcurement() {
  if (selectedProcurementForEdit.value) editProcurementRow(selectedProcurementForEdit.value)
}

async function editProcurementRow(row: any) {
  try {
    const detail = await getProcurement(row.id)
    editingProcurementId.value = row.id
    editingProcurementDetail.value = detail
    form.step1 = {
      procurement_type: detail.procurement_type || '材料采购',
      procurement_method: detail.procurement_method || '邀请询比',
    }
    const s2 = detail.step2 || {}
    // 以 s2 为底，保留后端 form_data 全部字段，避免编辑时丢失未显式列出的字段
    form.step2 = {
      ...s2,
      procurement_type: detail.procurement_type,
      procurement_method: detail.procurement_method,
      project_name: detail.project_name ?? '',
      project_number: detail.project_number ?? '',
      project_id: detail.project_id_display ?? detail.project_id ?? '',
      construction_unit: detail.construction_unit ?? '',
      construction_contact_person: detail.construction_contact_person ?? '',
      construction_contact_phone: detail.construction_contact_phone ?? '',
      total_contract_price: detail.total_contract_price ?? 0,
      project_address: detail.project_address ?? '',
      department: detail.department ?? '',
      site_manager: detail.site_manager ?? '',
      site_manager_phone: detail.site_manager_phone ?? '',
      procurement_project_name: detail.procurement_project_name ?? detail.project_name ?? '',
      content: detail.content ?? '',
      control_price: detail.control_price || 0,
      sign_date: detail.sign_date || '',
      leibie: s2.leibie || '材料物资类',
      tax_method: s2.tax_method || '一般计税方法计算',
      contract_format: s2.contract_format || '采用非公司印发的合同标准文本编制',
      use_standard_contract: s2.use_standard_contract || '是',
      passed_procurement: s2.passed_procurement || '是',
      reviewed: s2.reviewed || '是',
      gonggao_year: s2.gonggao_year || '',
      gonggao_month: s2.gonggao_month || '',
      gonggao_day: s2.gonggao_day || '',
      yixiang_baoming_jiezhi_year: s2.yixiang_baoming_jiezhi_year || '',
      yixiang_baoming_jiezhi_month: s2.yixiang_baoming_jiezhi_month || '',
      yixiang_baoming_jiezhi_day: s2.yixiang_baoming_jiezhi_day || '',
      jiaoyi_fengmian_year: s2.jiaoyi_fengmian_year || '',
      jiaoyi_fengmian_month: s2.jiaoyi_fengmian_month || '',
      jiaoyi_wenjian_year: s2.jiaoyi_wenjian_year || '',
      jiaoyi_wenjian_month: s2.jiaoyi_wenjian_month || '',
      jiaoyi_wenjian_day: s2.jiaoyi_wenjian_day || '',
      jiaoyi_wenjian_huoqv_jiezhi_year: s2.jiaoyi_wenjian_huoqv_jiezhi_year || '',
      jiaoyi_wenjian_huoqv_jiezhi_month: s2.jiaoyi_wenjian_huoqv_jiezhi_month || '',
      jiaoyi_wenjian_huoqv_jiezhi_day: s2.jiaoyi_wenjian_huoqv_jiezhi_day || '',
      xiangying_dijiao_jiezhi_year: s2.xiangying_dijiao_jiezhi_year || '',
      xiangying_dijiao_jiezhi_month: s2.xiangying_dijiao_jiezhi_month || '',
      xiangying_dijiao_jiezhi_day: s2.xiangying_dijiao_jiezhi_day || '',
      qianding_year: s2.qianding_year || '',
      qianding_month: s2.qianding_month || '',
      qianding_day: s2.qianding_day || '',
      biaoduanming1: s2.biaoduanming1 || '',
      biaoduanming2: s2.biaoduanming2 || '',
      kongzhijia_biao1: s2.kongzhijia_biao1,
      kongzhijia_biao2: s2.kongzhijia_biao2,
      chengjiao_jine1: s2.chengjiao_jine1,
      chengjiao_jine2: s2.chengjiao_jine2,
    }
    form.suppliers = (detail.suppliers || []).map((s: any) => ({
      supplier_name: s.supplier_name || '',
      contact_person: s.contact_person || '',
      contact_phone: s.contact_phone || '',
      business_scope: s.business_scope || '',
      tax_rate: s.tax_rate || '',
      quoted_price: s.quoted_price || 0,
    }))
    if (detail.procurement_method === '补充协议') {
      form.parent_contract_id = detail.parent_contract_id ?? null
      form.supplement_amount = Number((detail as any).supplement_amount) || 0
      form.supplement_content = detail.content ?? ''
      form.supplement_control_price = detail.step2?.supplement_control_price ?? 0
      form.supplement_procurement_project_name =
        detail.step2?.procurement_project_name ?? detail.procurement_project_name ?? ''
      if (project.value) {
        form.step2.project_name = project.value.project_name
      }
      if (form.parent_contract_id) {
        const parentDetail = await getProcurement(form.parent_contract_id)
        form.supplement_is_dual = parentDetail?.procurement_method === '五选二'
        form.contract_section = parentDetail?.contract_section || ''
        await loadParentContractOptions()
        const pid = form.parent_contract_id
        const inOptions = parentContractOptions.value.some((p: any) => p.id === pid)
        if (!inOptions && parentDetail) {
          parentContractOptions.value = [
            {
              id: parentDetail.id,
              contract_number: parentDetail.contract_number || parentDetail.procurement_project_name || String(pid),
              project_name: parentDetail.project_name || parentDetail.procurement_project_name || '',
              content: parentDetail.content || '',
              contract_section: parentDetail.contract_section || '',
            },
            ...parentContractOptions.value,
          ]
        }
        const opt = parentContractOptions.value.find((p: any) => p.id === pid)
        const nextSuppSeq = (opt?.supplement_count ?? 0) + 1
        const w = pickParentWinnerSupplier(parentDetail)
        const orig = w ? Number(w.quoted_price) || 0 : 0
        parentContractInfo.value = {
          contract_number: parentDetail.contract_number,
          original_price: orig,
          supplier_name: w?.supplier_name,
          sign_date: parentDetail.sign_date || '',
          next_supplement_seq: nextSuppSeq,
        }
        if (w && form.suppliers.length) {
          form.suppliers[0].business_scope = w.business_scope || ''
          form.suppliers[0].tax_rate = w.tax_rate || ''
          form.suppliers[0].quoted_price = Number(form.supplement_amount) || 0
        }
      }
    }
    {
      const existing = new Map(
        (detail.time_records || []).map((r: any) => [r.flow_name, r.date_val || '']),
      )
      const hetongSaved = String(
        detail.step2?.hetong_jiaodi ?? existing.get('合同交底') ?? '',
      ).trim()
      const names = getFlowNamesForMethod(form.step1.procurement_method)
      form.time_records = names.map((name) => ({
        flow_name: name,
        date_val: name === '合同交底' ? hetongSaved : existing.get(name) || '',
      }))
    }
    currentStep.value = 0
    dialogVisible.value = true
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '加载失败')
  }
}

async function handleBatchDelete() {
  if (!selectedIds.value.length) return
  try {
    await ElMessageBox.confirm('确定删除选中的采购项目？将同步删除相关文件夹、文件和台账。', '提示', { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' })
    const allWarnings: string[] = []
    for (const id of selectedIds.value) {
      const res = await deleteProcurement(id)
      if (res?.warnings?.length) allWarnings.push(...res.warnings)
    }
    ElMessage.success('已删除')
    if (allWarnings.length) ElMessage.warning(allWarnings.join('；'))
    await loadProcurements()
    selectedIds.value = []
    selectedProcurementForEdit.value = null
    selectedProcurementForFiles.value = null
    tableRef.value?.clearSelection?.()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

async function handleExport() {
  try {
    const list = filteredProcurements.value
    if (!list.length) {
      ElMessage.warning('无数据可导出')
      return
    }
    const fmt2 = (v: number | null | undefined) => (v != null && v !== '' && !Number.isNaN(Number(v)) ? Number(v).toFixed(2) : (v ?? ''))
    const rows = [
      ['工程编号', '采购类型', '采购方式', '采购项目名称', '采购内容', '供应商', '合同价', '签订日期', '控制价', '备注'],
      ...list.map((p: any) => [
        project.value?.project_id || '',
        p.procurement_type || '',
        p.procurement_method || '',
        p.project_name || '',
        p.content || '',
        p.supplier || '',
        fmt2(p.contract_price),
        p.sign_date || '',
        fmt2(p.control_price),
        p.remark || '',
      ]),
    ]
    const csv = rows.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n')
    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `采购项目清单_${project.value?.project_id || 'export'}.csv`
    a.click()
    URL.revokeObjectURL(a.href)
    ElMessage.success('导出成功')
  } catch (e: any) {
    ElMessage.error('导出失败')
  }
}
const dialogVisible = ref(false)
const overviewVisible = ref(false)
const overviewData = ref<any>(null)
const overviewSuppliers = computed(() => overviewData.value?.suppliers ?? [])
const overviewControlPriceLabel = computed(() => {
  const o = overviewData.value
  if (!o) return '-'
  const p = formatContractPrice(o.control_price)
  return p === '/' ? '/' : `${p} 元`
})

function formatSupplementQuotedDisplay(v: number | null | undefined) {
  return formatContractPrice(v)
}
const currentStep = ref(0)
const saving = ref(false)

const FLOW_NAMES_FULL = [
  '采购意向公告', '采购意向公告上网审批表', '意向报名截止日期', '交易文件', '交易文件审核表',
  '响应文件接收函', '响应文件递交截止日期', '供应商推荐表', '询比/单源采购会议通知', '供应商资格审查表',
  '询比/单源/直接采购记录及结果呈批表', '中选通知书', '合同文件呈批表', '用章申请表', '合同签订', '阳光采购平台公布结果',
  '合同交底',
]
const FLOW_NAMES_DIRECT = [
  '供应商推荐表', '询比\\单源\\直接采购记录及结果呈批表', '合同文件呈批表', '用章申请表', '合同签订', '阳光采购平台公布结果',
  '合同交底',
]
const FLOW_NAMES_SUPPLEMENT = [
  '合同文件呈批表', '用章申请表', '合同签订', '阳光采购平台公布结果',
  '合同交底',
]

const parentContractOptions = ref<any[]>([])
const parentContractInfo = ref<{ contract_number?: string; original_price?: number; supplier_name?: string; sign_date?: string; next_supplement_seq?: number } | null>(null)

function createDefaultStep1() {
  return {
    procurement_type: '材料采购',
    procurement_method: '邀请询比',
  }
}

function createDefaultStep2() {
  return {
    procurement_type: '材料采购',
    procurement_method: '邀请询比',
    project_name: '',
    project_number: '',
    project_id: '',
    construction_unit: '',
    construction_contact_person: '',
    construction_contact_phone: '',
    total_contract_price: 0,
    project_address: '',
    department: '',
    site_manager: '',
    site_manager_phone: '',
    procurement_project_name: '',
    content: '',
    control_price: 0,
    sign_date: '',
    gonggao_year: '',
    gonggao_month: '',
    gonggao_day: '',
    yixiang_baoming_jiezhi_year: '',
    yixiang_baoming_jiezhi_month: '',
    yixiang_baoming_jiezhi_day: '',
    jiaoyi_fengmian_year: '',
    jiaoyi_fengmian_month: '',
    jiaoyi_wenjian_year: '',
    jiaoyi_wenjian_month: '',
    jiaoyi_wenjian_day: '',
    jiaoyi_wenjian_huoqv_jiezhi_year: '',
    jiaoyi_wenjian_huoqv_jiezhi_month: '',
    jiaoyi_wenjian_huoqv_jiezhi_day: '',
    xiangying_dijiao_jiezhi_year: '',
    xiangying_dijiao_jiezhi_month: '',
    xiangying_dijiao_jiezhi_day: '',
    qianding_year: '',
    qianding_month: '',
    qianding_day: '',
    biaoduanming1: '',
    biaoduanming2: '',
    kongzhijia_biao1: undefined as number | undefined,
    kongzhijia_biao2: undefined as number | undefined,
    chengjiao_jine1: undefined as number | undefined,
    chengjiao_jine2: undefined as number | undefined,
    leibie: '材料物资类',
    tax_method: '一般计税方法计算',
    contract_format: '采用非公司印发的合同标准文本编制',
    use_standard_contract: '是',
    passed_procurement: '是',
    reviewed: '是',
  }
}

const form = reactive({
  parent_contract_id: null as number | null,
  supplement_amount: 0,
  supplement_content: '',
  supplement_control_price: 0,
  supplement_procurement_project_name: '',
  supplement_is_dual: false,
  contract_section: '' as string,
  step1: createDefaultStep1(),
  step2: createDefaultStep2(),
  suppliers: [] as any[],
  time_records: [] as { flow_name: string; date_val: string }[],
})

function getFlowNamesForMethod(method: string): string[] {
  if (method === '直接采购') return FLOW_NAMES_DIRECT
  if (method === '补充协议') return FLOW_NAMES_SUPPLEMENT
  return FLOW_NAMES_FULL
}
function initTimeRecords() {
  const method = form.step1.procurement_method
  form.time_records = getFlowNamesForMethod(method).map((name) => ({ flow_name: name, date_val: '' }))
}

function copyToClipboard(text: string) {
  if (!text) return
  navigator.clipboard.writeText(text).then(() => ElMessage.success('已复制'))
}

watch(() => form.step1.procurement_type, (v) => {
  form.step2.procurement_type = v
  if (form.step1.procurement_method === '补充协议' && project.value) loadParentContractOptions()
})
watch(() => form.step1.procurement_method, (v) => {
  form.step2.procurement_method = v
  // 编辑载入时勿覆盖 time_records，否则流程时间会丢失（watch 异步执行在 loadForEdit 赋值之后）
  if (editingProcurementId.value) return
  initTimeRecords()
  // 编辑模式下勿重置 parent_contract_id，否则会触发「请选择主合同」弹框
  if (v === '补充协议' && project.value && !editingProcurementId.value) {
    form.parent_contract_id = null
    parentContractInfo.value = null
    form.supplement_procurement_project_name = ''
    loadParentContractOptions()
  }
})

watch(project, (p) => {
  bc.setProcurementContext({
    projectId: p?.id ?? null,
    projectNumber: p?.project_id ?? '',
    projectName: p?.project_name ?? '',
    procurementId: null,
    procurementName: '',
    isAddProcurementOpen: false,
  })
}, { immediate: true })
watch(dialogVisible, (v) => {
  bc.setProcurementContext({ isAddProcurementOpen: v })
})
watch(selectedProcurementForFiles, (row) => {
  bc.setProcurementContext({
    procurementId: row?.id ?? null,
    procurementName: row?.project_name ?? '',
  })
})
watch(
  () => [form.supplement_amount, form.step1.procurement_method],
  () => {
    if (form.step1.procurement_method !== '补充协议' || !form.suppliers.length) return
    if (form.suppliers.length === 1) {
      form.suppliers[0].quoted_price = Number(form.supplement_amount) || 0
    }
  },
)

watch(activeFileTab, (tab) => {
  bc.setProcurementContext({ activeFileTab: tab })
})
function onMethodChange() {
  form.parent_contract_id = null
  form.supplement_amount = 0
  form.supplement_content = ''
  form.supplement_is_dual = false
  form.contract_section = ''
  parentContractInfo.value = null
  if (form.step1.procurement_method === '五选二') {
    for (const k of DATE_FIELDS) form.step2[k] = ''
  }
  initSuppliersByMethod()
  if (form.step1.procurement_method === '补充协议' && project.value) {
    loadParentContractOptions()
  }
}

function onSupplementIsDualChange() {
  form.parent_contract_id = null
  form.contract_section = ''
  parentContractInfo.value = null
  if (project.value) loadParentContractOptions()
}

function onContractSectionChange() {
  form.parent_contract_id = null
  parentContractInfo.value = null
}

const filteredParentContractOptions = computed(() => {
  if (!form.supplement_is_dual || !form.contract_section) return parentContractOptions.value
  return parentContractOptions.value.filter((p: any) => p.contract_section === form.contract_section)
})

async function loadParentContractOptions() {
  if (!project.value) return
  const list = await getParentContractOptions(
    project.value.id,
    form.step1.procurement_type,
    form.supplement_is_dual
  )
  parentContractOptions.value = list
}

/** 补充协议：主合同中标供应商（五选二按主合同标段取排序第 1/2 名） */
function pickParentWinnerSupplier(parentDetail: any) {
  const list = (parentDetail?.suppliers || []).slice()
  const sorted = [...list].sort(
    (a: any, b: any) => (Number(a.quoted_price) || 0) - (Number(b.quoted_price) || 0),
  )
  if (parentDetail?.procurement_method === '五选二') {
    const sect = parentDetail?.contract_section || ''
    const idx = sect === '二标段' ? 1 : 0
    return sorted[idx] || sorted[0] || null
  }
  return sorted[0] || null
}

function applySupplementSupplierFromParent(parentDetail: any, nextSuppSeq: number) {
  const w = pickParentWinnerSupplier(parentDetail)
  const orig = w ? Number(w.quoted_price) || 0 : 0
  parentContractInfo.value = {
    contract_number: parentDetail.contract_number,
    original_price: orig,
    supplier_name: w?.supplier_name,
    sign_date: parentDetail.sign_date || '',
    next_supplement_seq: nextSuppSeq,
  }
  if (!w) {
    form.suppliers = []
    return
  }
  form.suppliers = [
    {
      supplier_name: w.supplier_name || '',
      contact_person: w.contact_person || '',
      contact_phone: w.contact_phone || '',
      business_scope: w.business_scope || '',
      tax_rate: w.tax_rate || '',
      quoted_price: Number(form.supplement_amount) || 0,
    },
  ]
}

async function onParentContractSelect(id: number) {
  if (!id) {
    parentContractInfo.value = null
    form.suppliers = []
    return
  }
  try {
    const detail = await getProcurement(id)
    const opt = parentContractOptions.value.find((p: any) => p.id === id)
    const nextSuppSeq = (opt?.supplement_count ?? 0) + 1
    applySupplementSupplierFromParent(detail, nextSuppSeq)
    if (!form.supplement_procurement_project_name?.trim()) {
      form.supplement_procurement_project_name = detail.procurement_project_name || ''
    }
    form.step2.project_id = project.value?.project_id || ''
    form.step2.project_number = project.value?.project_number || ''
  } catch {
    parentContractInfo.value = null
  }
}

function onVisibilityChange() {
  if (document.visibilityState === 'visible' && activeFileTab.value === 'process' && selectedProcurementForFiles.value) {
    loadFilesForProcurement(selectedProcurementForFiles.value.id)
  }
}

onMounted(async () => {
  document.addEventListener('visibilitychange', onVisibilityChange)
  initTimeRecords()
  const qProjectId = route.query.project_id
  const qProcurementId = route.query.procurement_id

  if (qProjectId) {
    const pid = Number(qProjectId)
    try {
      const p = await getProject(pid)
      projects.value = [p]
      selectedProjectId.value = pid
      projectsLoadedOnce.value = true
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail || '加载指定工程项目失败')
    }
  }

  await loadProjectsForSelect('')

  if (selectedProjectId.value) {
    try {
      await loadProcurements()
      if (project.value) {
        Object.assign(form.step2, {
          project_name: project.value.project_name,
          project_number: project.value.project_number,
          project_id: project.value.project_id,
          construction_unit: project.value.construction_unit,
          construction_contact_person: project.value.construction_contact_person || '',
          construction_contact_phone: project.value.construction_contact_phone || '',
          total_contract_price: project.value.total_contract_price,
          project_address: project.value.project_address,
          department: project.value.department,
          site_manager: project.value.site_manager,
          site_manager_phone: project.value.site_manager_phone,
        })
      }
      if (qProcurementId) await highlightProcurementFromQuery()
      updateBreadcrumb()
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail || '加载采购项目失败')
    }
  }
})

onUnmounted(() => {
  document.removeEventListener('visibilitychange', onVisibilityChange)
})

function getMinSuppliers(method: string): number {
  if (method === '五选二') return 5
  if (method === '邀请询比') return 3
  return 1
}

function initSuppliersByMethod() {
  const method = form.step1.procurement_method
  const empty = () => ({
    supplier_name: '',
    contact_person: '',
    contact_phone: '',
    business_scope: '',
    tax_rate: '',
    quoted_price: 0,
  })
  if (method === '补充协议') {
    form.suppliers = [empty()]
    return
  }
  const min = getMinSuppliers(method)
  form.suppliers = Array.from({ length: min }, empty)
}

function addSupplier() {
  const method = form.step1.procurement_method
  if (method === '单一来源' || method === '直接采购') return
  form.suppliers.push({
    supplier_name: '',
    contact_person: '',
    contact_phone: '',
    business_scope: '',
    tax_rate: '',
    quoted_price: 0,
  })
}

function removeSupplier(index: number) {
  const method = form.step1.procurement_method
  const min = getMinSuppliers(method)
  if (method === '单一来源' || method === '直接采购') return
  if (form.suppliers.length <= min) return
  form.suppliers.splice(index, 1)
}

const canAddSupplier = computed(() => {
  const m = form.step1.procurement_method
  return m !== '补充协议' && m !== '单一来源' && m !== '直接采购'
})

const canRemoveSupplier = computed(() => {
  const m = form.step1.procurement_method
  if (m === '补充协议' || m === '单一来源' || m === '直接采购') return false
  const min = getMinSuppliers(m)
  return form.suppliers.length > min
})

async function highlightProcurementFromQuery() {
  const pid = route.query.procurement_id
  if (pid && procurements.value.length) {
    const row = procurements.value.find((p: any) => String(p.id) === String(pid))
    if (row) {
      await nextTick()
      tableRef.value?.setCurrentRow?.(row)
      selectedProcurementForFiles.value = row
    }
  }
}

async function showOverview(row: any) {
  try {
    overviewData.value = await getProcurement(row.id)
    overviewVisible.value = true
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '加载失败')
  }
}

async function handleDeleteProcurement(row: any) {
  try {
    await ElMessageBox.confirm('确定删除该采购项目？将同步删除相关文件夹、文件和台账。', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    const res = await deleteProcurement(row.id)
    ElMessage.success('已删除')
    if (res?.warnings?.length) {
      ElMessage.warning(res.warnings.join('；'))
    }
    await loadProcurements()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.detail || '删除失败')
    }
  }
}

const DATE_FIELDS = [
  'gonggao_year', 'gonggao_month', 'gonggao_day',
  'yixiang_baoming_jiezhi_year', 'yixiang_baoming_jiezhi_month', 'yixiang_baoming_jiezhi_day',
  'jiaoyi_fengmian_year', 'jiaoyi_fengmian_month',
  'jiaoyi_wenjian_year', 'jiaoyi_wenjian_month', 'jiaoyi_wenjian_day',
  'jiaoyi_wenjian_huoqv_jiezhi_year', 'jiaoyi_wenjian_huoqv_jiezhi_month', 'jiaoyi_wenjian_huoqv_jiezhi_day',
  'xiangying_dijiao_jiezhi_year', 'xiangying_dijiao_jiezhi_month', 'xiangying_dijiao_jiezhi_day',
  'qianding_year', 'qianding_month', 'qianding_day',
]
function showAddProcurement() {
  editingProcurementId.value = null
  editingProcurementDetail.value = null
  form.step1 = createDefaultStep1()
  form.parent_contract_id = null
  form.supplement_amount = 0
  form.supplement_content = ''
  form.supplement_control_price = 0
  form.supplement_procurement_project_name = ''
  form.supplement_is_dual = false
  form.contract_section = ''
  parentContractInfo.value = null
  form.step2 = createDefaultStep2()
  initSuppliersByMethod()
  initTimeRecords()
  currentStep.value = 0
  if (project.value) {
    Object.assign(form.step2, {
      project_name: project.value.project_name,
      project_number: project.value.project_number,
      project_id: project.value.project_id,
      construction_unit: project.value.construction_unit,
      construction_contact_person: project.value.construction_contact_person || '',
      construction_contact_phone: project.value.construction_contact_phone || '',
      total_contract_price: project.value.total_contract_price,
      project_address: project.value.project_address,
      department: project.value.department,
      site_manager: project.value.site_manager,
      site_manager_phone: project.value.site_manager_phone,
    })
  }
  if (form.step1.procurement_method === '补充协议') loadParentContractOptions()
  dialogVisible.value = true
}

function mergedProcurementProjectName(): string {
  if (form.step1.procurement_method === '补充协议') {
    return (form.supplement_procurement_project_name || form.step2.procurement_project_name || '').trim()
  }
  return (form.step2.procurement_project_name || '').trim()
}

/** 流程表行名 → 第二步年月日字段（与表单控件一致） */
const FLOW_NAME_TO_STEP2_DATE_KEYS: Record<string, string[]> = {
  采购意向公告: ['gonggao_year', 'gonggao_month', 'gonggao_day'],
  意向报名截止日期: ['yixiang_baoming_jiezhi_year', 'yixiang_baoming_jiezhi_month', 'yixiang_baoming_jiezhi_day'],
  交易文件: ['jiaoyi_fengmian_year', 'jiaoyi_fengmian_month'],
  交易文件审核表: ['jiaoyi_wenjian_year', 'jiaoyi_wenjian_month', 'jiaoyi_wenjian_day'],
  交易文件获取截止日期: [
    'jiaoyi_wenjian_huoqv_jiezhi_year',
    'jiaoyi_wenjian_huoqv_jiezhi_month',
    'jiaoyi_wenjian_huoqv_jiezhi_day',
  ],
  响应文件递交截止日期: [
    'xiangying_dijiao_jiezhi_year',
    'xiangying_dijiao_jiezhi_month',
    'xiangying_dijiao_jiezhi_day',
  ],
  合同签订: ['qianding_year', 'qianding_month', 'qianding_day'],
}

function parseFlowDateValToYmd(s: string): { y: string; m: string; d: string } {
  let t = (s || '').trim().replace(/年/g, '.').replace(/月/g, '.').replace(/日/g, '')
  for (const sep of ['/', '-', ' ']) {
    t = t.split(sep).join('.')
  }
  const parts = t
    .split('.')
    .map((p) => p.trim())
    .filter((p) => p !== '')
  return { y: parts[0] || '', m: parts[1] || '', d: parts[2] || '' }
}

function step2DateKeysAllBlank(target: Record<string, any>, keys: string[]): boolean {
  return keys.every((k) => {
    const v = target[k]
    return v == null || String(v).trim() === ''
  })
}

/** 仅把流程表日期写入仍为空的第二步年月日，使 form_data 与 Word 占位符一致，且后端能识别「非仅 _time_records」变更 */
function applyTimeRecordsDatesIntoBlankStep2Fields(target: Record<string, any>) {
  for (const r of form.time_records) {
    const keys = FLOW_NAME_TO_STEP2_DATE_KEYS[r.flow_name]
    if (!keys?.length) continue
    const dv = (r.date_val || '').trim()
    if (!dv) continue
    if (!step2DateKeysAllBlank(target, keys)) continue
    const { y, m, d } = parseFlowDateValToYmd(dv)
    if (!y) continue
    if (keys.length === 2) {
      target[keys[0]] = y
      target[keys[1]] = m || ''
    } else {
      target[keys[0]] = y
      target[keys[1]] = m || ''
      target[keys[2]] = d || ''
    }
  }
}

/** 与创建时 buildPayload 写入库的 sign_date 格式一致；可传入已合并流程表日期的对象 */
function signDateForStep2(step2: Record<string, any> = form.step2): string {
  const y = step2.qianding_year
  const mo = step2.qianding_month
  const d = step2.qianding_day
  if (y && mo && d) {
    return `${y}-${String(mo).padStart(2, '0')}-${String(d).padStart(2, '0')}`
  }
  return step2.sign_date ?? ''
}

function buildPayload() {
  const procName = mergedProcurementProjectName()
  const step2: Record<string, any> = {
    ...form.step2,
    procurement_project_name: procName,
    control_price: form.step2.control_price ?? 0,
    procurement_type: form.step1.procurement_type,
    procurement_method: form.step1.procurement_method,
    ...(form.step1.procurement_method === '补充协议' && { supplement_control_price: form.supplement_control_price ?? 0 }),
  }
  applyTimeRecordsDatesIntoBlankStep2Fields(step2)
  step2.sign_date = signDateForStep2(step2)
  return {
    project_id: project.value.id,
    step1: { ...form.step1 },
    step2,
    parent_contract_id: form.parent_contract_id || undefined,
    supplement_amount: form.supplement_amount ?? 0,
    supplement_content: form.supplement_content,
    supplement_control_price: form.supplement_control_price,
    suppliers: form.suppliers.map((s) => ({
      supplier_name: s.supplier_name,
      contact_person: s.contact_person,
      contact_phone: s.contact_phone,
      business_scope: s.business_scope || '',
      tax_rate: s.tax_rate || '',
      quoted_price: s.quoted_price || 0,
    })),
    time_records: form.time_records.map((r) => ({ flow_name: r.flow_name, date_val: r.date_val || '' })),
  }
}

function hetongJiaodiFromForm(): string {
  const row = form.time_records.find((r) => r.flow_name === '合同交底')
  return (row?.date_val || '').trim()
}

function buildFormDataStr() {
  const fullTime = form.time_records.map((r) => ({ flow_name: r.flow_name, date_val: r.date_val || '' }))
  const _time_records = fullTime.filter((r) => r.flow_name !== '合同交底')
  const base: Record<string, any> = {
    ...form.step2,
    procurement_project_name: mergedProcurementProjectName() || form.step2.procurement_project_name,
    _time_records,
    hetong_jiaodi: hetongJiaodiFromForm(),
  }
  applyTimeRecordsDatesIntoBlankStep2Fields(base)
  base.sign_date = signDateForStep2(base)
  if (form.step1.procurement_method === '补充协议') {
    base.content = form.supplement_content
    base.supplement_control_price = form.supplement_control_price
  }
  // 将 undefined 转为 null，避免 JSON.stringify 丢弃字段导致编辑后数据丢失
  const sanitized = Object.fromEntries(
    Object.entries(base).map(([k, v]) => [k, v === undefined ? null : v])
  )
  return JSON.stringify(sanitized)
}

function parseDateToMs(s: string): number | null {
  if (!s || typeof s !== 'string') return null
  const normalized = s.trim().replace(/\./g, '-').replace(/\//g, '-')
  const m = normalized.match(/^(\d{4})-?(\d{1,2})-?(\d{1,2})$/)
  if (!m) return null
  const [, y, mo, d] = m
  const d2 = new Date(parseInt(y, 10), parseInt(mo, 10) - 1, parseInt(d, 10))
  return isNaN(d2.getTime()) ? null : d2.getTime()
}

async function submitProcurement() {
  const method = form.step1.procurement_method
  if (method === '补充协议') {
    if (!form.parent_contract_id) {
      ElMessage.error('请选择主合同')
      return
    }
    if (!form.supplement_content) {
      ElMessage.error('请填写补充内容')
      return
    }
    if (!mergedProcurementProjectName()) {
      ElMessage.error('请填写采购项目名称')
      return
    }
    const suppSignDate =
      form.step2.qianding_year && form.step2.qianding_month && form.step2.qianding_day
        ? `${form.step2.qianding_year}.${Number(form.step2.qianding_month)}.${Number(form.step2.qianding_day)}`
        : (form.step2.sign_date || '')
    const parentSignDate = parentContractInfo.value?.sign_date || ''
    if (suppSignDate && parentSignDate) {
      const suppMs = parseDateToMs(suppSignDate)
      const parentMs = parseDateToMs(parentSignDate)
      if (suppMs != null && parentMs != null && suppMs < parentMs) {
        try {
          await ElMessageBox.confirm(
            '补充协议签订日期早于主合同签订日期，是否仍要保存？',
            '提示',
            { confirmButtonText: '仍要保存', cancelButtonText: '取消', type: 'warning' }
          )
        } catch {
          return
        }
      }
    }
    if (form.suppliers.length !== 1) {
      ElMessage.error('补充协议须且仅能填写一家供应商，请先选择主合同以带出中标供应商')
      return
    }
  } else {
    const minSuppliers = method === '五选二' ? 5 : method === '邀请询比' ? 3 : 1
    if (form.suppliers.length < minSuppliers) {
      ElMessage.error(`${method}需至少${minSuppliers}家供应商`)
      return
    }
    if (!form.step2.procurement_project_name || !form.step2.content) {
      ElMessage.error('请填写采购项目名称和采购内容')
      return
    }
    // 含税报价 ≤ 控制价（五选二：所有供应商都≤控制价）
    const ctrl = form.step2.control_price ?? null
    for (let i = 0; i < form.suppliers.length; i++) {
      const qp = form.suppliers[i]?.quoted_price ?? 0
      const limit = ctrl
      if (limit != null && limit !== '' && Number(limit) > 0 && qp > Number(limit)) {
        ElMessage.error(`供应商「${form.suppliers[i]?.supplier_name || `第${i + 1}家`}」含税报价（${qp?.toLocaleString()} 元）大于控制价（${Number(limit).toLocaleString()} 元），请调整。`)
        return
      }
    }
  }
  if (method === '补充协议') {
    const limit = form.supplement_control_price ?? null
    const limitVal = limit === '/' || limit === '' || limit == null ? null : Number(limit)
    if (limitVal != null && !Number.isNaN(limitVal) && limitVal > 0 && form.supplement_amount > limitVal) {
      ElMessage.error(`补充协议新增金额（${form.supplement_amount?.toLocaleString()} 元）大于控制价（${limitVal.toLocaleString()} 元），请调整。`)
      return
    }
  }
  saving.value = true
  try {
    if (editingProcurementId.value) {
      const updatePayload: Record<string, any> = {
        project_name: mergedProcurementProjectName() || form.step2.procurement_project_name,
        content: method === '补充协议' ? form.supplement_content : form.step2.content,
        form_data: buildFormDataStr(),
        suppliers: form.suppliers,
      }
      if (method === '补充协议') {
        updatePayload.supplement_amount = form.supplement_amount
        updatePayload.supplement_content = form.supplement_content
      } else {
        updatePayload.control_price = form.step2.control_price ?? null
      }
      const updatedId = editingProcurementId.value
      await updateProcurement(updatedId, updatePayload)
      ElMessage.success('更新成功')
      dialogVisible.value = false
      editingProcurementId.value = null
      editingProcurementDetail.value = null
      await loadProcurements()
      if (selectedProcurementForFiles.value?.id === updatedId) {
        loadFilesForProcurement(updatedId)
      }
      return
    }
    await createProcurement(buildPayload())
    ElMessage.success('创建成功')
    dialogVisible.value = false
    await loadProcurements()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped lang="scss">
.procurement-list-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 16px;
    gap: 12px;
    .project-select-item { margin-bottom: 0; }
    .procurement-project-select { width: 400px !important; }
    .header-search-col {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 6px;
    }
    .search-input { width: 280px; }
    .table-total-above-grid {
      font-size: 14px;
      color: var(--el-text-color-regular);
      line-height: 1.4;
    }
    h2 { font-size: 18px; }
  }
  .action-bar { margin-bottom: 16px; }
  .split-upper {
    flex-shrink: 0;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    .table-scroll-wrapper { overflow-x: auto; flex: 1; }
    .pagination {
      padding: 8px 0;
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      .ml { margin-left: 4px; }
      .pagination-controls { margin-left: 8px; }
      .page-jump-input { width: 60px; margin: 0 4px; }
    }
  }
  .split-handle {
    flex-shrink: 0;
    height: 8px;
    cursor: ns-resize;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--color-bg);
    &:hover .split-handle-bar { opacity: 1; }
    .split-handle-bar { font-size: 10px; opacity: 0.5; }
  }
  .split-lower {
    flex: 1;
    min-height: 120px;
    overflow: auto;
    .file-toolbar { margin-bottom: 8px; display: flex; align-items: center; gap: 8px; }
    .tip-text { color: var(--el-text-color-secondary); font-size: 13px; }
    .file-pagination {
      padding: 8px 0;
      display: flex;
      align-items: center;
      gap: 8px;
      .ml { margin-left: 4px; }
    }
  }
  .table-scroll-wrapper { overflow-x: auto; width: 100%; }
  .step-content { margin-top: 24px; min-height: 200px; }
  .supplement-note { color: var(--el-text-color-secondary); margin-bottom: 12px; }
  .cell-readonly { color: var(--el-text-color-regular); font-size: 13px; }
  .overview-content { max-height: 70vh; overflow-y: auto; }
  .file-name-link { color: var(--el-color-primary); cursor: pointer; }
  .file-name-link:hover { text-decoration: underline; }
  .docx-preview-container { max-height: 75vh; overflow: auto; padding: 12px; }
  .date-inputs { display: flex; align-items: center; gap: 8px; }
  .deal-amount-area {
    margin-top: 16px;
    padding: 12px;
    background: var(--color-bg);
    border-radius: 4px;
    font-size: 14px;
    .deal-amount-row { margin-bottom: 8px; }
    .deal-amount-row:last-child { margin-bottom: 0; }
    .ml { margin-left: 24px; }
  }
  :deep(.remark-input .el-textarea__inner) {
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    word-break: break-word;
    line-height: 1.4;
    resize: none;
  }
}
</style>

<template>
  <div class="settings-view">
    <h2>系统设置</h2>
    <el-tabs v-model="activeTab">
      <el-tab-pane label="用户管理" name="users">
        <div v-if="userStore.user?.role !== '系统管理员'" class="section">
          <el-alert type="warning" :closable="false">仅系统管理员可访问</el-alert>
        </div>
        <div v-else class="section">
          <el-button type="primary" @click="showAddUser">新增用户</el-button>
          <el-table :data="users" style="margin-top: 16px">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="username" label="用户名" width="120" />
            <el-table-column prop="real_name" label="姓名" width="100" />
            <el-table-column prop="role" label="角色" width="120" />
            <el-table-column prop="computer_ip" label="电脑IP" width="120" />
            <el-table-column prop="is_active" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'danger'">
                  {{ row.is_active ? '启用' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button link type="primary" @click="editUser(row)">编辑</el-button>
                <el-button
                  link
                  type="danger"
                  :disabled="row.id === userStore.user?.id"
                  @click="deleteUser(row)"
                >
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>
      <el-tab-pane label="Word模板" name="templates">
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
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="userDialogVisible" :title="editingUser ? '编辑用户' : '新增用户'" width="660" :close-on-click-modal="false">
      <el-form ref="userFormRef" :model="userForm" :rules="userRules" label-width="100px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="userForm.username" :disabled="!!editingUser" />
        </el-form-item>
        <el-form-item v-if="!editingUser" label="密码" prop="password">
          <el-input v-model="userForm.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="姓名" prop="real_name">
          <el-input v-model="userForm.real_name" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="userForm.role" style="width: 100%">
            <el-option label="采购管理员" value="采购管理员" />
            <el-option label="系统管理员" value="系统管理员" />
          </el-select>
        </el-form-item>
        <el-form-item label="电脑IP" prop="computer_ip">
          <el-input v-model="userForm.computer_ip" placeholder="分布式存储时填写" />
        </el-form-item>
        <el-form-item label="文件路径" prop="file_share_path">
          <el-input v-model="userForm.file_share_path" placeholder="如 D:/shanhai_files" />
        </el-form-item>
        <el-form-item v-if="editingUser" label="状态" prop="is_active">
          <el-switch v-model="userForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="userDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveUser">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { useUserStore } from '@/store/user'
import { useRealtimeSync, EventType } from '@/composables/useRealtimeSync'
import {
  listUsers,
  createUser,
  updateUser,
  deleteUser as apiDeleteUser,
} from '@/api/users'
import { getTemplateStructure, getTemplateConfig, updateTemplateConfig } from '@/api/templates'
import type { User } from '@/api/types'
import type { UserCreate, UserUpdate } from '@/api/users'

const userStore = useUserStore()
const activeTab = ref('users')
const users = ref<User[]>([])
const templateStructure = ref<{ path: string; files: string[] }[]>([])
const templatePath = ref('')
const templatePathSaving = ref(false)
const userDialogVisible = ref(false)
const editingUser = ref<User | null>(null)
const userFormRef = ref<FormInstance>()
const userForm = ref({
  username: '',
  password: '',
  real_name: '',
  role: '采购管理员',
  computer_ip: '',
  file_share_path: '',
  is_active: true,
})
const userRules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [
    {
      required: true,
      message: '请输入密码',
      trigger: 'blur',
      validator: (_: any, v: string, cb: (e?: Error) => void) => {
        if (editingUser.value) return cb()
        if (!v) return cb(new Error('请输入密码'))
        cb()
      },
    },
  ],
}

useRealtimeSync({
  context: { scope: 'admin' },
  onEvent: (e) => {
    const adminEvents = [
      EventType.USER_CREATED, EventType.USER_UPDATED, EventType.USER_DELETED,
      EventType.TEMPLATE_UPDATED, EventType.CONFIG_CHANGED,
    ]
    if (adminEvents.includes(e.type as string) && userStore.user?.role === '系统管理员') {
      loadUsers()
      loadTemplates()
    }
  },
})

onMounted(async () => {
  if (userStore.user?.role !== '系统管理员') {
    return
  }
  await loadUsers()
  await loadTemplates()
})

async function loadUsers() {
  try {
    users.value = await listUsers()
  } catch {
    ElMessage.error('加载用户列表失败')
  }
}

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
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    templatePathSaving.value = false
  }
}

function showAddUser() {
  editingUser.value = null
  userForm.value = {
    username: '',
    password: '',
    real_name: '',
    role: '采购管理员',
    computer_ip: '',
    file_share_path: '',
    is_active: true,
  }
  userDialogVisible.value = true
}

function editUser(user: User) {
  editingUser.value = user
  userForm.value = {
    username: user.username,
    password: '',
    real_name: user.real_name || '',
    role: user.role,
    computer_ip: user.computer_ip || '',
    file_share_path: user.file_share_path || '',
    is_active: user.is_active,
  }
  userDialogVisible.value = true
}

async function saveUser() {
  if (!userFormRef.value) return
  await userFormRef.value.validate(async (valid) => {
    if (!valid) return
    try {
      if (editingUser.value) {
        const data: UserUpdate = {
          real_name: userForm.value.real_name,
          role: userForm.value.role,
          computer_ip: userForm.value.computer_ip || undefined,
          file_share_path: userForm.value.file_share_path || undefined,
          is_active: userForm.value.is_active,
        }
        await updateUser(editingUser.value.id, data)
        ElMessage.success('更新成功')
      } else {
        const data: UserCreate = {
          username: userForm.value.username,
          password: userForm.value.password,
          real_name: userForm.value.real_name,
          role: userForm.value.role,
          computer_ip: userForm.value.computer_ip || undefined,
          file_share_path: userForm.value.file_share_path || undefined,
        }
        await createUser(data)
        ElMessage.success('创建成功')
      }
      userDialogVisible.value = false
      await loadUsers()
    } catch (e: any) {
      ElMessage.error(e.response?.data?.detail || '操作失败')
    }
  })
}

async function deleteUser(user: User) {
  await ElMessageBox.confirm(`确定删除用户 ${user.username}？`, '确认', {
    type: 'warning',
  })
  try {
    await apiDeleteUser(user.id)
    ElMessage.success('删除成功')
    await loadUsers()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
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

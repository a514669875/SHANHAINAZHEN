<template>
  <div class="main-layout">
    <header class="top-nav">
      <div class="nav-left">
        <span class="logo">山海纳珍录</span>
        <span class="subtitle">山海纳万珍，一键录千文</span>
      </div>
    </header>
    <div class="breadcrumb-bar">
      <el-breadcrumb separator="/">
        <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
        <el-breadcrumb-item
          v-for="(item, idx) in breadcrumbs"
          :key="item.path"
          :to="idx < breadcrumbs.length - 1 ? { path: item.path } : undefined"
        >
          {{ item.title }}
        </el-breadcrumb-item>
      </el-breadcrumb>
    </div>
    <div class="content-area">
      <aside class="sidebar">
        <el-menu
          :default-active="activeMenu"
          router
          background-color="#fff"
          text-color="#1F2937"
        >
          <el-menu-item index="/">
            <el-icon><HomeFilled /></el-icon>
            <span>首页</span>
          </el-menu-item>
          <el-menu-item index="/projects">
            <el-icon><Folder /></el-icon>
            <span>工程项目管理</span>
          </el-menu-item>
          <el-menu-item index="/procurements">
            <el-icon><Folder /></el-icon>
            <span>材料（设备）业务</span>
          </el-menu-item>
          <el-menu-item index="/archive">
            <el-icon><Folder /></el-icon>
            <span>归档管理</span>
          </el-menu-item>
          <el-menu-item index="/ledger">
            <el-icon><DataAnalysis /></el-icon>
            <span>智能台账</span>
          </el-menu-item>
          <el-menu-item index="/settings">
            <el-icon><Setting /></el-icon>
            <span>系统配置</span>
          </el-menu-item>
        </el-menu>
      </aside>
      <main class="main-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useUserStore } from '@/store/user'
import { useBreadcrumbStore } from '@/store/breadcrumb'

const route = useRoute()
const userStore = useUserStore()
const bc = useBreadcrumbStore()

const activeMenu = computed(() => route.path)

watch(
  () => route.path,
  () => {
    if (!route.path.startsWith('/projects') && !route.path.startsWith('/procurements') && !route.path.startsWith('/archive')) {
      bc.clear()
    }
  },
  { immediate: true }
)

const breadcrumbs = computed(() => {
  const items: { path: string; title: string }[] = []
  if (route.path === '/') return items
  if (route.path === '/projects') {
    items.push({ path: '/projects', title: '工程项目管理' })
    items.push({ path: '/projects', title: '工程项目清单' })
  } else if (route.path === '/procurements') {
    items.push({ path: '/procurements', title: '材料（设备）业务' })
    if (bc.projectNumber && bc.projectName) {
      items.push({ path: '/procurements', title: bc.projectNumber + ' ' + bc.projectName })
      if (bc.isAddProcurementOpen) {
        items.push({ path: '/procurements', title: '新增采购项目' })
      } else if (bc.procurementName && bc.procurementId) {
        items.push({ path: '/procurements', title: bc.procurementName })
        items.push({
          path: '/procurements',
          title: bc.activeFileTab === 'process' ? '流程文件' : '归档文件',
        })
      } else {
        items.push({ path: '/procurements', title: '采购项目清单' })
      }
    }
  } else if (route.path.startsWith('/projects')) {
    items.push({ path: '/projects', title: '工程项目管理' })
  } else if (route.path === '/archive') {
    items.push({ path: '/archive', title: '归档管理' })
    if (bc.projectNumber && bc.procurementName && bc.procurementId) {
      items.push({ path: '/archive', title: bc.projectNumber })
      items.push({ path: '/archive', title: bc.procurementName })
      items.push({ path: '/archive', title: '上传合同文件' })
    }
  } else if (route.path === '/ledger') {
    items.push({ path: '/ledger', title: '智能台账' })
    if (bc.ledgerContractNumber) {
      items.push({ path: '/ledger', title: '合同详情' })
      items.push({ path: '/ledger', title: bc.ledgerContractNumber })
    }
  } else if (route.path === '/settings') {
    items.push({ path: '/settings', title: '系统设置' })
  } else if (route.path === '/login') {
    items.push({ path: '/login', title: '登录' })
  }
  return items
})

onMounted(async () => {
  await userStore.fetchUser()
})
</script>

<style scoped lang="scss">
.main-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
}
.top-nav {
  height: 80px;
  padding: 0 24px;
  background:rgb(67, 99, 185);
  color: white;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.nav-left {
  display: flex;
  flex-direction: column;
  .logo {
    font-size: 30px;
    font-weight: bold;
  }
  .subtitle {
    font-size: 18px;
    opacity: 0.9;
  }
}
.breadcrumb-bar {
  padding: 12px 24px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
}
.content-area {
  flex: 1;
  display: flex;
  overflow: hidden;
}
.sidebar {
  width: 200px;
  background: #fff;
  border-right: 1px solid #e5e7eb;
  overflow-y: auto;
}
.main-content {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
  background: #F3F4F6;
}
</style>

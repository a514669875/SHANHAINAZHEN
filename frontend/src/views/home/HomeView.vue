<template>
  <div class="home-view">
    <h2>首页</h2>
    <el-row :gutter="16">
      <el-col :span="6">
        <el-card shadow="hover">
          <template #header>工程项目</template>
          <div class="stat-value">{{ stats.projects }}</div>
          <div class="stat-label">个</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <template #header>采购项目</template>
          <div class="stat-value">{{ stats.procurements }}</div>
          <div class="stat-label">个</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <template #header>台账记录</template>
          <div class="stat-value">{{ stats.ledgers }}</div>
          <div class="stat-label">条</div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import request from '@/api/request'

const stats = ref({ projects: 0, procurements: 0, ledgers: 0 })

onMounted(async () => {
  try {
    const res = await request.get('/stats')
    stats.value = {
      projects: (res as any).projects || 0,
      procurements: (res as any).procurements || 0,
      ledgers: (res as any).ledgers || 0,
    }
  } catch {
    // ignore
  }
})
</script>

<style scoped lang="scss">
.home-view {
  h2 { margin-bottom: 24px; font-size: 18px; }
  .stat-value { font-size: 32px; font-weight: bold; color: #1E3A8A; }
  .stat-label { font-size: 14px; color: #6B7280; }
}
</style>

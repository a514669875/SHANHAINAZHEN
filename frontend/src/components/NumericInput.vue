<template>
  <el-input
    v-model="localVal"
    :placeholder="placeholder"
    :size="size"
    :style="style"
    @blur="onBlur"
  />
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue?: number | null
    placeholder?: string
    size?: 'default' | 'small'
    style?: string
  }>(),
  { modelValue: undefined, placeholder: '', size: 'default', style: 'width: 100%' }
)

const emit = defineEmits<{ (e: 'update:modelValue', v: number | null): void }>()

function toDisplay(v: number | null | undefined): string {
  if (v == null || v === '') return '/'
  return String(v)
}

const localVal = ref(toDisplay(props.modelValue))

watch(
  () => props.modelValue,
  (v) => {
    const d = toDisplay(v)
    if (localVal.value !== d) localVal.value = d
  },
  { immediate: true }
)

function onBlur() {
  const s = (localVal.value || '').trim()
  if (s === '' || s === '/') {
    emit('update:modelValue', null)
    localVal.value = '/'
    return
  }
  const n = parseFloat(s)
  if (!isNaN(n)) {
    emit('update:modelValue', n)
    localVal.value = String(n)
  } else {
    emit('update:modelValue', null)
    localVal.value = '/'
  }
}
</script>

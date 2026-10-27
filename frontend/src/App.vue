<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { logout, readUser } from './api/auth'

const route = useRoute()
const router = useRouter()
const user = computed(() => readUser())
const showBar = computed(() => route.path !== '/login')

async function signOut() {
  await logout()
  router.push('/login')
}
</script>

<template>
  <div v-if="showBar" class="desk">
    <header class="mast">
      <div>
        <p class="kicker">材料编制</p>
        <strong>招投标材料工作台</strong>
      </div>
      <div class="mast-user">
        <span>{{ user?.display_name }} · {{ user?.role }}</span>
        <el-button @click="signOut">退出</el-button>
      </div>
    </header>
    <router-view />
  </div>
  <router-view v-else />
</template>

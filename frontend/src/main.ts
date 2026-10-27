import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './styles.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', meta: { guestOnly: true }, component: () => import('./views/LoginView.vue') },
    { path: '/', redirect: '/workbench' },
    { path: '/workbench', meta: { requiresAuth: true }, component: () => import('./views/WorkbenchView.vue') },
  ],
})

router.beforeEach((to) => {
  const token = localStorage.getItem('access_token')
  if (to.meta.guestOnly && token) return '/workbench'
  if (to.meta.requiresAuth && !token) return { path: '/login', query: { redirect: to.fullPath } }
  return true
})

createApp(App).use(router).mount('#app')

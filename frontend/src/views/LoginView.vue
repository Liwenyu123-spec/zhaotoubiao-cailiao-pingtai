<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login } from '../api/auth'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const form = reactive({ username: 'admin', password: 'Admin#2026' })

async function submit() {
  loading.value = true
  try {
    await login(form.username.trim(), form.password)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/workbench'
    router.push(redirect)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="login-split">
    <section class="login-intro">
      <div class="intro-copy">
        <p class="kicker">招投标材料</p>
        <h1>把招标要求变成可执行的材料任务。</h1>
        <p class="login-lead">导入招标文件，核对要求出处，再按部门和责任人收集证明材料。</p>
        <ul>
          <li><strong>要求可回溯</strong><span>每条条款保留文件和页码</span></li>
          <li><strong>人工来确认</strong><span>抽取结果不是审查结论</span></li>
          <li><strong>材料分开管</strong><span>报价和财务按角色隔离</span></li>
        </ul>
      </div>
    </section>
    <section class="login-pane">
      <div class="login-card">
        <p class="kicker">登录</p>
        <h2>进入工作台</h2>
        <p class="login-lead">测试账号见《测试账号速查》。</p>
        <el-form label-position="top">
          <el-form-item label="账号">
            <el-input v-model="form.username" size="large" autocomplete="username" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="form.password" size="large" type="password" show-password autocomplete="current-password" @keyup.enter="submit" />
          </el-form-item>
          <el-button class="submit" type="primary" size="large" :loading="loading" @click="submit">登录</el-button>
        </el-form>
      </div>
    </section>
  </main>
</template>

<style scoped>
.login-split {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(340px, 1.2fr) minmax(380px, 0.8fr);
  background:
    radial-gradient(ellipse at 0% 100%, rgba(196, 168, 122, .18), transparent 42%),
    linear-gradient(180deg, #f7f4ee 0%, #efe8dc 100%);
  color: #2a312c;
}
.login-intro {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding: 64px 72px 64px 48px;
}
.intro-copy { width: min(520px, 100%); }
.kicker { margin: 0; color: #8a5a2b; letter-spacing: .16em; font-size: 12px; }
.intro-copy h1 { margin: 14px 0 0; font-size: 42px; line-height: 1.28; font-weight: 650; }
.login-lead { margin: 16px 0 0; color: #5e675f; line-height: 1.7; }
.intro-copy ul { display: grid; gap: 14px; margin: 40px 0 0; padding: 0; list-style: none; }
.intro-copy li { padding-left: 14px; border-left: 2px solid #d7c4a2; }
.intro-copy strong, .intro-copy span { display: block; }
.intro-copy span { margin-top: 4px; color: #6d756e; font-size: 13px; }
.login-pane { display: grid; place-items: center; padding: 40px; }
.login-card {
  width: min(400px, 100%);
  padding: 36px 32px 28px;
  background: rgba(255, 253, 248, .92);
  border: 1px solid rgba(226, 216, 198, .9);
  border-radius: 20px;
  box-shadow: 0 20px 50px rgba(72, 54, 28, .08);
}
.login-card h2 { margin: 8px 0 0; font-size: 28px; font-weight: 650; }
.login-card .login-lead { margin-bottom: 8px; font-size: 14px; }
.submit { width: 100%; margin-top: 6px; }
.login-card :deep(.el-form-item__label) { color: #3c463f; }
.login-card :deep(.el-input__wrapper) {
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 0 0 1px #e4dccb inset;
}
.login-card :deep(.el-button--primary) {
  height: 44px;
  border: 0;
  border-radius: 10px;
  background: #2c3330;
}
.login-card :deep(.el-button--primary:hover) { background: #3a433f; }
@media (max-width: 900px) {
  .login-split { grid-template-columns: 1fr; }
  .login-intro { justify-content: flex-start; padding: 40px 24px 8px; }
  .intro-copy h1 { font-size: 32px; }
}
</style>

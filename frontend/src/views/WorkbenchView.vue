<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  addRequirement,
  createProject,
  getProject,
  listProjects,
  patchRequirement,
  uploadDocument,
  type Project,
  type ProjectDetail,
  type Requirement,
} from '../api/projects'

const projects = ref<Project[]>([])
const currentId = ref<number | null>(null)
const detail = ref<ProjectDetail | null>(null)
const loading = ref(false)
const form = reactive({ name: '', code: '', bidder: '', deadline: '' })
const extra = reactive({ category: '资格', content: '' })
const categories = ['资格', '评分', '格式', '签章', '时间', '商务', '技术', '其他']

const statusText: Record<Requirement['status'], string> = {
  pending: '待确认',
  confirmed: '已确认',
  not_applicable: '不适用',
}

async function refreshProjects() {
  projects.value = await listProjects()
}

async function openProject(id: number) {
  currentId.value = id
  detail.value = await getProject(id)
}

async function onCreate() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写项目名称')
    return
  }
  const created = await createProject({ ...form })
  form.name = ''
  form.code = ''
  form.bidder = ''
  form.deadline = ''
  await refreshProjects()
  await openProject(created.id)
}

async function onUpload(file: File) {
  if (!currentId.value) {
    ElMessage.warning('请先选择项目')
    return false
  }
  loading.value = true
  try {
    const result = await uploadDocument(currentId.value, file)
    ElMessage.success(`抽出 ${result.extracted} 条。${result.parse_note}`)
    await refreshProjects()
    await openProject(currentId.value)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '导入失败')
  } finally {
    loading.value = false
  }
  return false
}

async function onAdd() {
  if (!currentId.value || !extra.content.trim()) return
  await addRequirement(currentId.value, { category: extra.category, content: extra.content.trim() })
  extra.content = ''
  await refreshProjects()
  await openProject(currentId.value)
}

async function setStatus(row: Requirement, status: Requirement['status']) {
  await patchRequirement(row.id, { status })
  await refreshProjects()
  if (currentId.value) await openProject(currentId.value)
}

onMounted(async () => {
  await refreshProjects()
  if (projects.value[0]) await openProject(projects.value[0].id)
})
</script>

<template>
  <div class="grid grid-2 workbench">
    <div class="panel">
      <div class="panel-head"><h3>投标项目</h3><span>创建后导入招标文件</span></div>
      <div class="form-pad">
        <el-form label-position="top">
          <el-form-item label="项目名称"><el-input v-model="form.name" placeholder="例如：某泵站设备采购" /></el-form-item>
          <el-form-item label="项目编号"><el-input v-model="form.code" /></el-form-item>
          <el-form-item label="投标主体"><el-input v-model="form.bidder" /></el-form-item>
          <el-form-item label="截止时间"><el-input v-model="form.deadline" placeholder="2026-11-30 09:30" /></el-form-item>
          <el-button type="primary" @click="onCreate">创建项目</el-button>
        </el-form>
        <button
          v-for="item in projects"
          :key="item.id"
          class="project-card"
          :class="{ active: item.id === currentId }"
          @click="openProject(item.id)"
        >
          <strong>{{ item.name }}</strong>
          <span>{{ item.code || '无编号' }} · 待确认 {{ item.pending_count }}/{{ item.requirement_count }}</span>
        </button>
      </div>
    </div>
    <div class="panel">
      <div class="panel-head">
        <h3>要求矩阵{{ detail ? ` · ${detail.project.name}` : '' }}</h3>
        <span>检查提示，不是审查结论</span>
      </div>
      <div class="form-pad">
        <el-alert
          title="关键条款、低置信项和空白扫描页都要人工确认。读不出的内容不会被补全。"
          type="warning"
          :closable="false"
          show-icon
        />
        <div v-if="detail" class="doc-list">
          <p v-if="!detail.documents.length" class="muted">还没有导入文件。</p>
          <p v-for="doc in detail.documents" :key="doc.id">{{ doc.filename }} · {{ doc.parse_note }}</p>
        </div>
        <el-upload :show-file-list="false" accept=".txt,.md,.pdf,.docx" :before-upload="onUpload" :disabled="!currentId">
          <el-button :loading="loading" :disabled="!currentId">导入文件</el-button>
        </el-upload>
        <div class="extra-row">
          <el-select v-model="extra.category" style="width: 120px">
            <el-option v-for="item in categories" :key="item" :label="item" :value="item" />
          </el-select>
          <el-input v-model="extra.content" placeholder="人工补录一条要求" />
          <el-button :disabled="!currentId" @click="onAdd">加入矩阵</el-button>
        </div>
        <el-table :data="detail?.requirements || []" empty-text="选择项目后显示要求">
          <el-table-column prop="category" label="类别" width="90" />
          <el-table-column prop="content" label="要求" min-width="240" />
          <el-table-column label="出处" width="140">
            <template #default="{ row }">
              <div>{{ row.source_file }}</div>
              <div class="muted">{{ row.source_location }}</div>
            </template>
          </el-table-column>
          <el-table-column label="置信" width="90">
            <template #default="{ row }">
              <el-tag :type="row.confidence === 'low' ? 'warning' : 'success'" effect="plain">{{ row.confidence }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">{{ statusText[row.status as Requirement['status']] }}</template>
          </el-table-column>
          <el-table-column label="操作" width="170">
            <template #default="{ row }">
              <el-button size="small" @click="setStatus(row, 'confirmed')">确认</el-button>
              <el-button size="small" @click="setStatus(row, 'not_applicable')">不适用</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { createArchiveAsset, listArchiveAssets, type ArchiveAsset } from '../api/archive'
import {
  addRequirement,
  createProject,
  createTask,
  generateTaskPlan,
  getProject,
  listProjects,
  patchRequirement,
  patchTask,
  uploadDocument,
  type Project,
  type ProjectDetail,
  type Requirement,
  type MaterialTask,
  type TaskSuggestion,
} from '../api/projects'

const projects = ref<Project[]>([])
const currentId = ref<number | null>(null)
const detail = ref<ProjectDetail | null>(null)
const loading = ref(false)
const form = reactive({ name: '', code: '', bidder: '', deadline: '' })
const extra = reactive({ category: '资格', content: '' })
const taskForm = reactive({ requirement_id: 0, department: '商务', due_at: '' })
const categories = ['资格', '评分', '格式', '签章', '时间', '商务', '技术', '其他']
const departments = ['投标负责人', '商务', '技术', '法务合规', '财务', '采购', '项目管理']
const assetTypes = ['证照', '业绩', '人员', '财务', '信用', '模板']
const archiveAssets = ref<ArchiveAsset[]>([])
const suggestions = ref<TaskSuggestion[]>([])
const suggestionTrace = ref<string[]>([])
const archiveForm = reactive({ asset_type: '证照', title: '', holder_name: '', valid_until: '', confidentiality: 'internal', scope_note: '', source_project: '' })

const statusText: Record<Requirement['status'], string> = {
  pending: '待确认',
  confirmed: '已确认',
  not_applicable: '不适用',
}

async function refreshProjects() {
  projects.value = await listProjects()
}

async function refreshArchive() {
  archiveAssets.value = await listArchiveAssets()
}

async function onAddArchive() {
  if (!archiveForm.title.trim()) return ElMessage.warning('请填写档案名称')
  await createArchiveAsset({ ...archiveForm })
  archiveForm.title = ''
  archiveForm.holder_name = ''
  archiveForm.valid_until = ''
  archiveForm.scope_note = ''
  archiveForm.source_project = ''
  ElMessage.success('企业档案已登记')
  await refreshArchive()
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

async function setStatus(row: { id: number }, status: Requirement['status']) {
  await patchRequirement(row.id, { status })
  await refreshProjects()
  if (currentId.value) await openProject(currentId.value)
}

async function onCreateTask() {
  if (!currentId.value || !taskForm.requirement_id) return ElMessage.warning('请选择要分派的要求')
  await createTask(currentId.value, { ...taskForm })
  taskForm.requirement_id = 0
  taskForm.due_at = ''
  ElMessage.success('任务已创建')
  await openProject(currentId.value)
}

async function onGeneratePlan() {
  if (!currentId.value) return
  const result = await generateTaskPlan(currentId.value)
  suggestions.value = result.suggestions
  suggestionTrace.value = result.trace
  ElMessage.success(`已生成 ${result.suggestions.length} 条任务建议，请人工确认`)
}

async function onAcceptSuggestion(item: TaskSuggestion) {
  if (!currentId.value) return
  await createTask(currentId.value, { requirement_id: item.requirement_id, department: item.department, due_at: '' })
  suggestions.value = suggestions.value.filter((row) => row.requirement_id !== item.requirement_id)
  await openProject(currentId.value)
  ElMessage.success('已采用建议并创建任务')
}

async function onTaskStatusChange(task: { id: number }, status: 'open' | 'submitted' | 'done' | 'recheck') {
  await patchTask(task.id, { task_status: status })
  if (currentId.value) await openProject(currentId.value)
  ElMessage.success('任务状态已更新')
}

onMounted(async () => {
  await refreshProjects()
  await refreshArchive()
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
        <div class="archive-box">
          <div class="subhead"><strong>企业档案</strong><span>可复用材料登记</span></div>
          <div class="archive-form">
            <el-select v-model="archiveForm.asset_type" style="width: 100px"><el-option v-for="item in assetTypes" :key="item" :label="item" :value="item" /></el-select>
            <el-input v-model="archiveForm.title" placeholder="档案名称" />
            <el-input v-model="archiveForm.holder_name" placeholder="持有主体/人员" />
            <el-input v-model="archiveForm.valid_until" placeholder="有效期，如 2027-12-31" />
            <el-input v-model="archiveForm.scope_note" placeholder="适用范围" />
            <el-button @click="onAddArchive">登记档案</el-button>
          </div>
          <div v-if="archiveAssets.length" class="archive-list">
            <div v-for="item in archiveAssets.slice(0, 5)" :key="item.id" class="archive-item">
              <strong>{{ item.title }}</strong><span>{{ item.asset_type }} · {{ item.valid_until || '未登记有效期' }}</span>
            </div>
          </div>
          <p v-else class="muted">还没有企业档案。</p>
        </div>
      </div>
    </div>
    <div class="panel">
      <div class="panel-head">
        <h3>要求矩阵{{ detail ? ` · ${detail.project.name}` : '' }}</h3>
        <span>检查提示，不是审查结论</span>
      </div>
      <div class="form-pad">
        <div v-if="detail" class="task-box task-box-prominent">
          <div class="subhead"><strong>材料任务</strong><span>当前项目的任务分派与完成情况</span></div>
          <el-button size="small" type="success" plain @click="onGeneratePlan">生成任务建议</el-button>
          <div class="extra-row">
            <el-select v-model="taskForm.requirement_id" placeholder="选择要求" style="min-width: 260px">
              <el-option v-for="item in detail.requirements" :key="item.id" :label="`${item.category}：${item.content.slice(0, 30)}`" :value="item.id" />
            </el-select>
            <el-select v-model="taskForm.department" placeholder="责任部门" style="width: 150px">
              <el-option v-for="item in departments" :key="item" :label="item" :value="item" />
            </el-select>
            <el-input v-model="taskForm.due_at" placeholder="截止日期" style="width: 150px" />
            <el-button type="primary" @click="onCreateTask">分派任务</el-button>
          </div>
          <el-table :data="detail.tasks || []" empty-text="还没有材料任务">
            <el-table-column prop="department" label="部门" width="100" />
            <el-table-column prop="requirement_content" label="对应要求" min-width="260" />
            <el-table-column prop="due_at" label="截止" width="130" />
            <el-table-column label="状态" width="150">
              <template #default="{ row }">
                <el-select :model-value="row.task_status" size="small" @change="(value: 'open' | 'submitted' | 'done' | 'recheck') => onTaskStatusChange(row as MaterialTask, value)">
                  <el-option label="待处理" value="open" />
                  <el-option label="已提交" value="submitted" />
                  <el-option label="已完成" value="done" />
                  <el-option label="需重新检查" value="recheck" />
                </el-select>
              </template>
            </el-table-column>
          </el-table>
          <div v-if="suggestions.length" class="suggestion-list">
            <div class="suggestion-head">Agent 建议（需人工确认）<span>{{ suggestionTrace.join(' → ') }}</span></div>
            <div v-for="item in suggestions" :key="item.requirement_id" class="suggestion-item">
              <span>要求 #{{ item.requirement_id }} · 建议分派给 <strong>{{ item.department }}</strong></span>
              <el-button size="small" @click="onAcceptSuggestion(item)">采用</el-button>
            </div>
          </div>
        </div>
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
              <el-button size="small" @click="setStatus(row as Requirement, 'confirmed')">确认</el-button>
              <el-button size="small" @click="setStatus(row as Requirement, 'not_applicable')">不适用</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>
  </div>
</template>

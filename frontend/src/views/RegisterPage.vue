<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth.js'

const router = useRouter()
const { register } = useAuth()

const form = ref({ username: '', password: '', confirm: '' })
const error = ref('')
const loading = ref(false)

async function handleSubmit() {
  error.value = ''
  if (form.value.password !== form.value.confirm) {
    error.value = '两次密码不一致'
    return
  }
  if (form.value.password.length < 4) {
    error.value = '密码至少4位'
    return
  }
  loading.value = true
  try {
    await register(form.value.username, form.value.password)
    router.push('/skills')
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-card card">
      <h1>注册新账号</h1>
      <div v-if="error" class="error-msg">{{ error }}</div>
      <form @submit.prevent="handleSubmit">
        <div class="form-group">
          <label>用户名</label>
          <input v-model="form.username" class="form-input" placeholder="请输入用户名" required />
        </div>
        <div class="form-group">
          <label>密码</label>
          <input v-model="form.password" class="form-input" type="password" placeholder="至少4位密码" required />
        </div>
        <div class="form-group">
          <label>确认密码</label>
          <input v-model="form.confirm" class="form-input" type="password" placeholder="再次输入密码" required />
        </div>
        <div class="form-actions">
          <button class="btn btn-primary" :disabled="loading">
            {{ loading ? '注册中...' : '注册' }}
          </button>
        </div>
      </form>
      <div class="auth-link">
        已有账号？<router-link to="/login">去登录</router-link>
      </div>
    </div>
  </div>
</template>

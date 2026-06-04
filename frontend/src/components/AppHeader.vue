<script setup>
import { useAuth } from '../composables/useAuth.js'
import { useRouter } from 'vue-router'

const { isLoggedIn, username, logout } = useAuth()
const router = useRouter()
</script>

<template>
  <nav class="navbar">
    <router-link to="/skills" class="navbar-brand">AI Agent 工作空间</router-link>
    <div class="navbar-links" v-if="isLoggedIn">
      <router-link to="/skills">Skills</router-link>
      <router-link to="/conversations">会话</router-link>
      <router-link to="/mcp">MCP</router-link>
    </div>
    <div class="navbar-right" v-if="isLoggedIn">
      <span>{{ username }}</span>
      <button class="btn btn-outline btn-sm" @click="logout">退出</button>
    </div>
  </nav>
</template>

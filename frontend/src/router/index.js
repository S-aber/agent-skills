import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/LoginPage.vue'),
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('../views/RegisterPage.vue'),
  },
  {
    path: '/skills',
    name: 'Skills',
    component: () => import('../views/SkillsPage.vue'),
  },
  {
    path: '/conversations',
    name: 'Conversations',
    component: () => import('../views/ConversationsPage.vue'),
  },
  {
    path: '/mcp',
    name: 'McpServers',
    component: () => import('../views/McpServersPage.vue'),
  },
  {
    path: '/chat/:id',
    name: 'Chat',
    component: () => import('../views/ChatPage.vue'),
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/skills',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Auth guard
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('access_token')
  const publicRoutes = ['/login', '/register']
  if (!token && !publicRoutes.includes(to.path)) {
    next('/login')
  } else if (token && publicRoutes.includes(to.path)) {
    next('/skills')
  } else {
    next()
  }
})

export default router

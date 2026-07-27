<template>
  <router-view />
</template>

<script setup>
</script>

<style>
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --color-primary: #4f46e5;
  --color-primary-light: #818cf8;
  --color-danger: #ef4444;
  --color-success: #22c55e;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  -webkit-font-smoothing: antialiased;
}
</style>

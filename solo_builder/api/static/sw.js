/**
 * Solo Builder — Service Worker for offline dashboard (TASK-418).
 * Caches dashboard shell (HTML, CSS, JS) for offline access.
 * API calls always go to network first, fall back to cache.
 */
const CACHE_NAME = "sb-dashboard-v1";
const SHELL_ASSETS = [
  "/",
  "/static/dashboard.css",
  "/static/dashboard.js",
  "/static/dashboard_state.js",
  "/static/dashboard_utils.js",
  "/static/dashboard_tasks.js",
  "/static/dashboard_panels.js",
  "/static/dashboard_branches.js",
  "/static/dashboard_cache.js",
  "/static/dashboard_journal.js",
  "/static/dashboard_health.js",
  "/static/dashboard_settings.js",
  "/static/dashboard_stalled.js",
  "/static/dashboard_subtasks.js",
  "/static/dashboard_history.js",
  "/static/dashboard_analytics.js",
  "/static/dashboard_keyboard.js",
  "/static/dashboard_graph.js",
  "/static/dashboard_svg.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  // API calls: network-first, cache-fallback
  if (url.pathname.startsWith("/status") || url.pathname.startsWith("/tasks") ||
      url.pathname.startsWith("/health") || url.pathname.startsWith("/heartbeat") ||
      url.pathname.startsWith("/changes")) {
    event.respondWith(
      fetch(event.request)
        .then((resp) => {
          const clone = resp.clone();
          caches.open(CACHE_NAME).then((c) => c.put(event.request, clone));
          return resp;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }
  // Shell assets: cache-first
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});

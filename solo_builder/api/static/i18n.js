/**
 * Solo Builder — i18n string externalization (groundwork).
 * Default locale: en. Future: load from /static/locales/{lang}.json
 */
const _STRINGS = {
  // Header
  "hdr.title": "Solo Builder",
  "hdr.step": "Step",
  "hdr.paused": "Polling paused",
  "hdr.resumed": "Polling resumed",
  // Tasks
  "task.verified": "verified",
  "task.running": "running",
  "task.pending": "pending",
  "task.review": "review",
  "task.complete": "Pipeline already complete.",
  "task.reset": "Reset",
  "task.copy_id": "Copy ID",
  // Subtasks
  "st.verify": "Verify",
  "st.retry": "Retry",
  "st.copy": "Copy output",
  "st.no_output": "No output to copy",
  // Actions
  "action.refreshing": "Refreshing…",
  "action.copied": "Copied",
  "action.failed": "Failed",
  "action.no_task": "No task selected",
  // Keyboard
  "kb.shortcuts": "Keyboard Shortcuts",
};

export function t(key, fallback) {
  return _STRINGS[key] || fallback || key;
}

export default _STRINGS;

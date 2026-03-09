// Shared mutable state — imported by all dashboard modules.
// Object properties are mutable across ES module boundaries.
export const state = {
  base: "",
  pollMs: parseInt(localStorage.getItem("sb-poll-ms") || "2000", 10),
  pollIntervalId: null,
  selectedTask: null,
  tasksCache: {},
  taskIds: [],
  rateEma: null,
  prevVerified: 0,
  prevStep: 0,
  lastSeenStep: parseInt(localStorage.getItem("sb-last-seen-step") || "0", 10),
  tabFocused: true,
  allTasks: [],
  pollPaused: false,
  viewMode: "grid",
  lastStatusOk: Date.now(),
  notifHistory: [],
};

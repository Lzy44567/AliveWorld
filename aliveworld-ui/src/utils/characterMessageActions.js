// UI projection only: all mutations still use the existing group controller.
export function messageActions(row, ctx) {
  if (row.temporary || ctx.busy || ctx.commandPending || ctx.settingsBusy || ctx.needsReload) return {};
  const failed = ctx.failure;
  if (failed?.input_ids?.at(-1) === row.message.message_id && failed.operation !== 'proactive') {
    return { failed: true, retry: Boolean(failed.retryable), edit: failed.operation === 'send' };
  }
  if (ctx.queuedCount) return {};
  const latest = ctx.session.groups.at(-1);
  if (latest?.input_ids?.at(-1) === row.message.message_id) return { undo: true, regenerate: latest.origin !== 'proactive' };
  return {};
}

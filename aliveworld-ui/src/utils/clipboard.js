export async function copyText(value) {
  const text = typeof value === 'string' ? value : JSON.stringify(value ?? '', null, 2);
  if (!text) return false;
  try {
    if (globalThis.navigator?.clipboard?.writeText) {
      await globalThis.navigator.clipboard.writeText(text);
      return true;
    }
  } catch (_) {
    // WebView permissions vary; fall through to the local selection fallback.
  }
  if (!globalThis.document?.body) return false;
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.setAttribute('readonly', '');
  textarea.style.position = 'fixed';
  textarea.style.opacity = '0';
  document.body.appendChild(textarea);
  textarea.select();
  let copied = false;
  try { copied = document.execCommand('copy'); } catch (_) { copied = false; }
  textarea.remove();
  return copied;
}

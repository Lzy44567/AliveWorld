const safeFilePart = value => String(value || 'export')
  .replace(/[<>:"/\\|?*\u0000-\u001f]/g, '_')
  .replace(/[. ]+$/g, '')
  .slice(0, 80) || 'export';

export const downloadJson = (filename, value) => {
  const blob = new Blob([JSON.stringify(value, null, 2)], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `${safeFilePart(filename)}.json`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
};

export { safeFilePart };

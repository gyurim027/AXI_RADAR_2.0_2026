// 어드민 표 내려받기. 엑셀이 한글을 바로 읽도록 UTF-8 BOM, 줄바꿈은 CRLF로 만든다 (CSV 파일 규칙).
const BOM = String.fromCharCode(0xfeff);
const cell = (v) => {
  const s = String(v ?? '');
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

export function downloadCsv(filename, rows) {
  const text = `${BOM}${rows.map((r) => r.map(cell).join(',')).join('\r\n')}\r\n`;
  const url = URL.createObjectURL(new Blob([text], { type: 'text/csv;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

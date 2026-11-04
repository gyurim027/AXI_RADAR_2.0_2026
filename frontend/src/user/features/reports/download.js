// 보고서 내려받기. 실제 PDF·엑셀 파일은 백엔드가 만든다.
// 가안은 미리 보기 내용을 파일로 옮긴다. 엑셀은 UTF-8 BOM, CRLF 형식의 CSV, PDF는 인쇄 창(PDF로 저장)이다.
import { COMMON } from '../../../shared/copy/common.js';
import { reportFileName } from '../../../shared/utils/format.js';

const BOM = String.fromCharCode(0xfeff); // 엑셀이 UTF-8로 읽도록 맨 앞에 붙인다
const csvCell = (v) => {
  const s = String(v ?? '');
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

/** lines: 맨 위에 적는 줄(자료 기준일·산정 기준 버전 등), table: [머리 줄, ...행] */
function buildRows({ header, table, withComplaintSource }) {
  const rows = [...header.map((h) => [h]), [], ...table, [], [COMMON.sourceMap]];
  if (withComplaintSource) rows.push([COMMON.sourceComplaint]);
  return rows;
}

function save(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export function makeFile({ format, runName, guLabel, reportName, header, table, withComplaintSource }) {
  const rows = buildRows({ header, table, withComplaintSource });
  if (format === 'excel') {
    const text = `${BOM}${rows.map((r) => r.map(csvCell).join(',')).join('\r\n')}\r\n`;
    save(new Blob([text], { type: 'text/csv;charset=utf-8' }), reportFileName(runName, guLabel, reportName, 'csv'));
    return;
  }
  // PDF: 보고서만 담은 문서를 인쇄 창으로 열어 'PDF로 저장'하게 한다
  const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[c]);
  const html = `<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>${esc(
    reportFileName(runName, guLabel, reportName, 'pdf'),
  )}</title><style>body{font-family:sans-serif;padding:24px;font-size:12px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #999;padding:4px 8px;text-align:left}p{margin:2px 0}.src{margin-top:16px;color:#555}</style></head><body><h1 style="font-size:18px">${esc(reportName)}</h1>${header
    .map((h) => `<p>${esc(h)}</p>`)
    .join('')}<table>${table.map((r, i) => `<tr>${r.map((c) => (i === 0 ? `<th>${esc(c)}</th>` : `<td>${esc(c)}</td>`)).join('')}</tr>`).join('')}</table><div class="src"><p>${esc(
    COMMON.sourceMap,
  )}</p>${withComplaintSource ? `<p>${esc(COMMON.sourceComplaint)}</p>` : ''}</div></body></html>`;
  const frame = document.createElement('iframe');
  frame.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0';
  document.body.append(frame);
  frame.contentDocument.open();
  frame.contentDocument.write(html);
  frame.contentDocument.close();
  setTimeout(() => {
    frame.contentWindow.focus();
    frame.contentWindow.print();
    setTimeout(() => frame.remove(), 1000);
  }, 200);
}

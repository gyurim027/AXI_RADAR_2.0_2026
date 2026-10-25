// US-10~US-14 기준정보 문구. 키 앞의 번호는 10_2_화면명세_사용자의 화면 번호다.

export const APPROVAL = {
  // US-10
  title: '승인 대기',
  subtitle: 'RADAR 운영팀이 올린 산정 기준·담당 부서 표 변경 제안입니다. 승인한 설정은 다음 산정부터 사용할 수 있습니다.',
  head: ['제안', '내용', '제안일'],
  proposalName: (kind, version) => (version ? `${kind} ${version}` : kind),
  empty: '승인할 제안이 없습니다. 새 제안이 오면 알림으로 알려 드립니다.', // E-3
  compareTitle: (kind, version) => (kind === '산정 기준' ? `산정 기준 ${version} 변경 제안` : `${kind} 수정 제안`),
  changeRow: (field, from, to, type) => (type === 'weight' ? `${field} 분야 반영 비율 ${from} → ${to}` : `${field} ${from} → ${to}`),
  impact: (top, changed) => `상위 ${top}곳 중 ${changed}곳이 바뀝니다.`,
  reject: '돌려보내기',
  approve: '승인하기',
  approveLabel: (kind, version) => (kind === '산정 기준' ? `산정 기준 ${version} 제안 승인하기` : `${kind} 수정 제안 승인하기`),
  rejectReasonLabel: '돌려보내는 사유',
  rejectReasonError: '돌려보내는 사유를 적어 주세요. RADAR 운영팀이 사유를 보고 다시 고칩니다.',
  rejectSend: '돌려보내기', // 흐름 U-66의 선 이름 (K-19)
  closeLabel: '돌려보내는 사유 입력 닫기', // 명세에 없는 닫기 버튼 (확인 필요)
};

export const DATA = {
  // US-12
  title: '데이터 목록',
  subtitle: 'RADAR가 순위를 낼 때 쓰는 자료와 기준일입니다.',
  head: ['자료', '제공기관', '기준일', '최신 여부', '공유 조건'],
};

export const REGS = {
  // US-13
  title: '법령 및 규정',
  subtitle: '근거로 쓰는 법령과 업무분장이 바뀐 내역입니다.',
  head: ['규정 제목', '변경 대상', '시행일'],
  empty: '바뀐 법령이나 업무분장이 없습니다.',
};

export const ACTIONS = {
  // US-14
  title: '조치 제안',
  subtitle: '자료로 찾은 문제마다 현장에서 확인할 것, 요청할 조치, 받는 부서를 정리한 표입니다.',
  head: ['자료로 찾은 문제', '확인할 것', '조치', '조치 제안 문장', '받는 부서', '근거 조문'],
  deptCheck: '받는 부서 확인 필요',
  articlePending: '근거 조문 확인 전',
};

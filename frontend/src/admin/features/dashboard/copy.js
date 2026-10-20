// AD-01 대시보드 문구 (10_3_화면명세_어드민 AD-01)
import { withEuro } from '../../../shared/utils/format.js';

export const DASH = {
  title: '대시보드',
  subtitle: '지금 회차가 어디까지 왔는지와 다음에 할 일을 봅니다.',
  runTitle: (name) => `${name} 회차`,
  next: (task) => `다음에 할 일: ${task}`,
  goto: (screen) => `${withEuro(screen)} 가기`,
  dataTitle: '자료 최신 여부',
  runsTitle: '최근 수집·산정 실행',
  approvalsTitle: '승인 현황',
  regTitle: '규정 변경',
  failed: '대시보드를 불러오지 못했습니다.',
};

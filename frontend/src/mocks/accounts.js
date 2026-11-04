// 가짜 계정. 비밀번호는 모두 radar1234 (가안). 실제 인증은 백엔드가 맡는다.
import { ROLE } from '../shared/constants.js';

export const MOCK_PASSWORD = 'radar1234';
export const CONTACT_PHONE = '031-000-0000'; // CM-01 3 계정 도움 %연락처% (예시)

export const ACCOUNTS = [
  {
    id: 'suj',
    role: ROLE.DISTRICT,
    gu: '수정구',
    org: '수정구 건설과 도로관리팀', // US-00 0-2 %소속%
  },
  {
    id: 'jungwon',
    role: ROLE.DISTRICT,
    gu: '중원구',
    org: '중원구 건설과 도로관리팀',
  },
  {
    id: 'bundang',
    role: ROLE.DISTRICT,
    gu: '분당구',
    org: '분당구 건설과 도로관리팀',
  },
  {
    // 분당구는 도로관리팀과 보도관리팀이 함께 쓴다 (0_안내 용어). 화면은 같은 방식으로 보인다 (US-00 0-2).
    id: 'bundang-sidewalk',
    role: ROLE.DISTRICT,
    gu: '분당구',
    org: '분당구 건설과 보도관리팀',
  },
  {
    id: 'city',
    role: ROLE.CITY,
    gu: null,
    org: '성남시 도로과 도로관리팀',
  },
  {
    id: 'operator',
    role: ROLE.OPERATOR,
    gu: null,
    org: 'RADAR 운영팀',
  },
];

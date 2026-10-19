// CM-01 로그인 문구. 키 앞의 번호는 10_2_화면명세_사용자의 블록 번호다.
import { CONTACT_PHONE } from '../../../mocks/accounts.js';

export const LOGIN_COPY = {
  title: 'RADAR 보도 점검 우선순위', // 1-1
  subtitle: '성남시 보도 정기 점검 대상을 고르는 도구입니다. 받은 계정으로 로그인해 주세요.', // 1-2
  idLabel: '아이디', // 2-1
  pwLabel: '비밀번호', // 2-3
  submit: '로그인', // 2-5
  wrong: (remaining, lockMinutes) =>
    `아이디 또는 비밀번호가 맞지 않습니다. ${remaining}번 더 틀리면 ${lockMinutes}분 동안 로그인할 수 없습니다.`, // 2-6
  // 5번 틀려 잠긴 뒤의 문구는 명세에 없다. 2-6 문구의 뒷부분만 쓴다. (확인 필요)
  locked: (lockMinutes) => `아이디 또는 비밀번호가 맞지 않습니다. ${lockMinutes}분 동안 로그인할 수 없습니다.`,
  help: `계정이 필요하거나 비밀번호를 잊었다면 RADAR 운영팀에 연락해 주세요. ${CONTACT_PHONE}`, // 3-1
};

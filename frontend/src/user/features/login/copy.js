// CM-01 로그인 문구. 키 앞의 번호는 10_2_화면명세_사용자의 블록 번호다.
import { CONTACT_PHONE } from '../../../mocks/accounts.js';

export const LOGIN_COPY = {
  title: 'RADAR 보도 점검 우선순위', // 1-1
  subtitle: '성남시 보도 정기 점검의 우선순위를 제안하는 도구입니다. 받은 계정으로 로그인해 주세요.', // 1-2 (K-18)
  idLabel: '아이디', // 2-1
  pwLabel: '비밀번호', // 2-3
  submit: '로그인', // 2-5
  wrong: (remaining, lockMinutes) =>
    `아이디 또는 비밀번호가 맞지 않습니다. ${remaining}번 더 틀리면 ${lockMinutes}분 동안 로그인할 수 없습니다.`, // 2-6
  // 2-7 잠김. 서버가 남은 시간을 주지 않으므로 쓰지 않는다. 없는 아이디도 횟수에 들어가므로 '아이디 또는 비밀번호'로 쓴다 (POL-022).
  locked: (maxFails, lockMinutes) =>
    `아이디 또는 비밀번호를 ${maxFails}번 잘못 입력해 ${lockMinutes}분 동안 로그인할 수 없습니다. 잠시 뒤에 다시 시도해 주세요.`,
  inactive: '사용이 중지된 계정입니다. 다시 사용하려면 RADAR 운영팀에 문의해 주세요.', // 2-8
  noRole: '계정의 권한이 아직 정해지지 않았습니다. RADAR 운영팀에 문의해 주세요.', // 2-9
  network: '서버에 연결하지 못했습니다. 잠시 뒤에 다시 시도해 주세요.', // 2-10
  other: '로그인하지 못했습니다. 잠시 뒤에 다시 시도해 주세요.', // 2-11
  noStorage: '로그인 상태를 저장하지 못했습니다. 브라우저 설정에서 사이트 데이터 저장을 허용해 주세요.', // 2-12
  expired: '로그인 시간이 지났습니다. 다시 로그인해 주세요.', // 2-13
  roleChanged: '계정의 권한이 바뀌었습니다. 다시 로그인해 주세요.', // 서버 401 role_changed. 정의서에 없는 문구라 제안
  help: `계정이 필요하거나 비밀번호를 잊었다면 RADAR 운영팀에 연락해 주세요. ${CONTACT_PHONE}`, // 3-1
};

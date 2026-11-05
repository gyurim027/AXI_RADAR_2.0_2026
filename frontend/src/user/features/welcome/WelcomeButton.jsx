import { useWelcome } from './useWelcome.js';
import { WELCOME } from './copy.js';

// 메뉴 항목 모양은 받은 className이 정하고, 버튼 기본 모양(바탕·테두리)만 지운다.
const RESET = { cursor: 'pointer', fontFamily: 'inherit', background: 'none', borderTop: 0, borderLeft: 0, borderRight: 0 };

/** 상단 메뉴의 `소개`. 누르면 소개 모달이 다시 열린다. */
export default function WelcomeButton({ className = '', plain = false }) {
  const { open } = useWelcome();
  const style = plain ? { ...RESET, borderBottom: 0, color: 'inherit', font: 'inherit', padding: 0 } : RESET;
  return <button type="button" className={className} style={style} onClick={open}>{WELCOME.menuLabel}</button>;
}

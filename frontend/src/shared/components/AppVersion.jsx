import { APP_VERSION } from '../version.js';
import styles from './AppVersion.module.css';

/** 화면 맨 아래에 작고 연한 회색으로 버전을 보인다. 사용자·어드민·로그인 화면이 함께 쓴다. */
export default function AppVersion() {
  return <p className={styles.version}>{`v${APP_VERSION}`}</p>;
}

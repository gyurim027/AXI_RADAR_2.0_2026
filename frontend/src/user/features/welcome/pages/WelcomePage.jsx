import { useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../../../app/providers/AuthProvider.jsx';
import { ROLE } from '../../../../shared/constants.js';
import AppVersion from '../../../../shared/components/AppVersion.jsx';
import Button from '../../../components/Button.jsx';
import Callout from '../../../components/Callout.jsx';
import Card from '../../../components/Card.jsx';
import Tag from '../../../components/Tag.jsx';
import { InfoHelp } from '../../../components/FormControls.jsx';
import { homePath, startPath } from '../landing.js';
import { WELCOME as C } from '../copy.js';
import styles from './WelcomePage.module.css';

/** 로그인 직후 보이는 소개 화면. 서비스 소개, 사용 흐름, 만든 과정을 한 장에 담는다. */
export default function WelcomePage() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const { state } = useLocation();
  const operator = user.role === ROLE.OPERATOR;

  useEffect(() => { document.title = `${C.menuLabel} · ${C.title}`; }, []);

  const start = () => navigate(startPath(user.role, state?.next), { replace: true });
  const logout = async () => { await signOut(); navigate('/login', { replace: true }); };

  return (
    <div className={styles.page}>
      <a href="#welcome-main" className={styles.skip}>본문 바로가기</a>
      <header className={styles.bar}>
        <Link to={homePath(user.role)} className={styles.brand}>RADAR<span className={styles.brandRest}> 보도 점검 우선순위</span></Link>
        <div className={styles.account}>
          <span>{user.org}</span>
          <button type="button" className={styles.logout} onClick={logout}>로그아웃</button>
        </div>
      </header>

      <main id="welcome-main" className={styles.main} tabIndex={-1}>
        <section className={styles.hero} aria-labelledby="welcome-title">
          <p className={styles.eyebrow}>{C.eyebrow}</p>
          <h1 id="welcome-title" className={styles.title}>{C.title}</h1>
          <p className={styles.lead}>{C.lead}</p>
          <Button onClick={start}>{operator ? C.startOperator : C.startDistrict}</Button>
        </section>

        <section className={styles.section} aria-labelledby="intro-title">
          <h2 id="intro-title" className={styles.h2}>{C.introTitle}</h2>
          <div className={styles.cards}>
            {C.cards.map((c) => (
              <Card key={c.key} title={c.title} variant={c.key === 'effect' ? 'soft' : 'plain'}>
                <p className={styles.body}>{c.body}</p>
              </Card>
            ))}
          </div>
          <Callout>{C.pocNote}</Callout>
        </section>

        <section className={styles.section} aria-labelledby="flow-title">
          <h2 id="flow-title" className={styles.h2}>{C.flowTitle}</h2>
          <ol className={styles.flow}>
            {C.flow.map((f, i) => (
              <li key={f.key} className={styles.step}>
                <span className={styles.num} aria-hidden="true">{i + 1}</span>
                <div className={styles.stepText}>
                  <p className={styles.stepLabel}>
                    {f.label}
                    {f.help ? <InfoHelp label={`${f.label} 도움말 보기`}>{f.help}</InfoHelp> : null}
                  </p>
                  <p className={styles.muted}>{f.text}</p>
                </div>
              </li>
            ))}
          </ol>
          <ul className={styles.roles}>
            {C.roles.map((r) => (
              <li key={r.key} className={styles.role}>
                <Tag tone={r.key === user.role ? 'info' : 'neutral'}>{r.label}</Tag>
                <span className={styles.muted}>{r.text}</span>
              </li>
            ))}
          </ul>
          <ul className={styles.terms} aria-label={C.termsTitle}>
            {C.terms.map((t) => (
              <li key={t.key} className={styles.term}>
                <span>{t.label}</span>
                <InfoHelp label={`${t.label} 도움말 보기`}>{t.help}</InfoHelp>
              </li>
            ))}
          </ul>
        </section>

        <section className={styles.section} aria-labelledby="history-title">
          <h2 id="history-title" className={styles.h2}>{C.historyTitle}</h2>
          <ol className={styles.history}>
            {C.history.map((h) => (
              <li key={h.key} className={styles.phase}>
                <p className={styles.phaseHead}><Tag tone="info">{h.step}</Tag><span className={styles.muted}>{h.period}</span></p>
                <p className={styles.stepLabel}>{h.title}</p>
                <p className={styles.muted}>{h.people}</p>
              </li>
            ))}
          </ol>
        </section>

        <AppVersion />
      </main>
    </div>
  );
}

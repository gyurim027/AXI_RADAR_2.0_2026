import { useState } from 'react';
import Tag from '../../../../components/Tag.jsx';
import { DRAWER } from '../../copy.js';
import styles from './Tabs.module.css';

/** ② 조문 (US-03 2-1). 조문 이름을 누르면 원문 문단이 펼쳐진다. 시행 전 조문은 '시행 전' 꼬리표로 따로 둔다. */
export default function ArticlesTab({ detail }) {
  const [openId, setOpenId] = useState(null);
  return (
    <section>
      <p className={styles.sub}>{DRAWER.articleSub}</p>
      <div className={styles.content}>
        {detail.articles.length === 0 ? (
          <p className={styles.muted}>{DRAWER.articleEmpty}</p>
        ) : (
          <ul className={styles.list}>
            {detail.articles.map((a) => (
              <li key={a.id}>
                <div className={styles.articleRow}>
                  <button type="button" className={styles.linkBtn} aria-expanded={openId === a.id} onClick={() => setOpenId(openId === a.id ? null : a.id)}>
                    {a.name}
                  </button>
                  <Tag tone="gray" small>
                    {DRAWER.articleEffective(a.effective)}
                  </Tag>
                  {a.pending ? (
                    <Tag tone="mid" small>
                      {DRAWER.articlePending}
                    </Tag>
                  ) : null}
                </div>
                {openId === a.id ? <p className={styles.articleBody}>{a.body}</p> : null}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

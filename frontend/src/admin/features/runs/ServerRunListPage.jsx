import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { getAdminRun, listAdminRuns } from '../../../api/admin.js';

const L = {
  title: '회차 목록',
  intro: 'DB77에 저장된 실행회차입니다. 1차 배포에서는 기존 회차 2의 조회 화면만 엽니다.',
  failed: '회차 목록 조회에 실패했습니다.',
  loading: '회차 목록을 불러오는 중입니다.',
  empty: '등록된 회차가 없습니다.',
  headers: ['회차', '생성일', '자료 기간', '빌드', '규칙 버전', '운영 상태', '동작'],
  unknown: '정보 없음',
};

const tdStyle = { padding: 12, borderBottom: '1px solid #ddd' };

export default function ServerRunListPage() {
  const [rows, setRows] = useState(null);
  const [listError, setListError] = useState('');
  const [detail, setDetail] = useState(null);
  const [detailError, setDetailError] = useState('');
  const [detailLoading, setDetailLoading] = useState(false);
  const [params, setParams] = useSearchParams();
  const selectedId = params.get('runId');

  useEffect(() => {
    let active = true;
    listAdminRuns()
      .then((data) => {
        if (active) setRows(data);
      })
      .catch((err) => {
        if (active) setListError(err.message || L.failed);
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (selectedId !== '2') {
      setDetail(null);
      setDetailError(selectedId ? '1차 배포에서는 회차 2만 열 수 있습니다.' : '');
      setDetailLoading(false);
      return;
    }
    let active = true;
    setDetail(null);
    setDetailError('');
    setDetailLoading(true);
    getAdminRun(2)
      .then((data) => {
        if (active) setDetail(data);
      })
      .catch((err) => {
        if (active) setDetailError(err.message || '회차 상세 조회에 실패했습니다.');
      })
      .finally(() => {
        if (active) setDetailLoading(false);
      });
    return () => { active = false; };
  }, [selectedId]);

  function openRunTwo() {
    const next = new URLSearchParams(params);
    next.set('runId', '2');
    setParams(next);
  }

  function closeDetail() {
    const next = new URLSearchParams(params);
    next.delete('runId');
    setParams(next);
  }

  const opened = detail?.run;
  const period = opened?.periodStart && opened?.periodEnd
    ? `${opened.periodStart} ~ ${opened.periodEnd}`
    : '기간 정보 없음';

  return (
    <section>
      <h1>{L.title}</h1>
      <p>{L.intro}</p>

      {listError && <p role="alert">{listError}</p>}
      {!listError && rows === null && <p role="status">{L.loading}</p>}
      {!listError && rows?.length === 0 && <p>{L.empty}</p>}

      {!listError && rows?.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {L.headers.map((head) => (
                  <th key={head} scope="col" style={{ ...tdStyle, textAlign: 'left' }}>
                    {head}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((run) => (
                <tr key={run.id}>
                  <td style={tdStyle}>{run.name}</td>
                  <td style={tdStyle}>{run.created}</td>
                  <td style={tdStyle}>{run.period}</td>
                  <td style={tdStyle}>{run.buildId ?? '-'}</td>
                  <td style={tdStyle}>{run.ruleVersion ?? '-'}</td>
                  <td style={tdStyle}>{L.unknown}</td>
                  <td style={tdStyle}>
                    <button
                      type="button"
                      disabled={String(run.runId) !== '2' || (selectedId === '2' && detailLoading)}
                      onClick={openRunTwo}
                      aria-label={`${run.name} 열기`}
                    >
                      {String(run.runId) === '2' ? '열기' : '보존 대상'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedId && (
        <section aria-label="선택한 회차" style={{ marginTop: 24, padding: 16, border: '1px solid #bbb' }}>
          <button type="button" onClick={closeDetail}>닫기</button>
          {detailLoading && <p role="status">회차 2 상세 정보를 불러오는 중입니다.</p>}
          {detailError && <p role="alert">{detailError}</p>}
          {opened && !detailLoading && (
            <>
              <h2>실행회차 {opened.runId}</h2>
              <p>자료 기간: {period}</p>
              <p>빌드: {opened.buildId ?? '-'}</p>
              <p>규칙 버전: {opened.ruleVersion ?? '-'}</p>
              <p>운영 상태: 확인할 수 없음 (DB77에 상태 컬럼 없음)</p>
              <p>후보 선정값은 운영자의 최종 결정이 아닙니다.</p>
              <p>회차 선택 정보는 현재 페이지 주소의 runId=2에 유지됩니다.</p>
            </>
          )}
        </section>
      )}
    </section>
  );
}

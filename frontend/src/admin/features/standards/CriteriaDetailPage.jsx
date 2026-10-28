import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { getVersion, previewChange, requestVersionApproval, saveVersionDraft } from '../../../api/admin.js';
import { useAsync } from '../../../shared/hooks/useAsync.js';
import Badge from '../../components/Badge.jsx';
import Button from '../../components/Button.jsx';
import DataTable from '../../components/DataTable.jsx';
import { NumberCell, TextArea, TextInput } from '../../components/Field.jsx';
import Loadable from '../../components/Loadable.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import Panel, { Banner } from '../../components/Panel.jsx';
import Tabs from '../../components/Tabs.jsx';
import { VERSION_TONE } from './CriteriaListPage.jsx';
import { DETAIL } from './copy.js';
import styles from './Standards.module.css';
import { reportActionError } from '../../utils/actionError.js';
import {settingsBackendEnabled} from '../../../api/backend.js';
import {StoredSettingDetail} from './StoredSettings.jsx';

const TAB_KEYS = ['weights', 'thresholds', 'conditions'];

/** 바뀐 칸은 주황 바탕과 500 굵기로 보인다. 색만으로 알리지 않도록 굵기도 함께 쓴다 (디자인 시스템 유형 D) */
function Changed({ on, children }) {
  return on ? <span className={styles.changedCell}>{children}</span> : <span className={styles.readonly}>{children}</span>;
}

/** AD-10 산정 기준 상세 (유형 D): 이전 값과 현재 값을 나란히 놓고, 아래에 바꾸는 이유와 고정 작업 줄이 있다. 게시 버튼은 없다. */
export default function CriteriaDetailPage() {
  return settingsBackendEnabled?<StoredSettingDetail/>:<MockCriteriaDetailPage/>;
}

function MockCriteriaDetailPage() {
  const { version } = useParams();
  const state = useAsync(() => getVersion({ version }), [version]);
  return (
    <div>
      <Loadable state={state} areaName={DETAIL.failedArea} rows={6}>{(d) => <Detail key={d.meta.version} data={d} reload={state.reload} />}</Loadable>
    </div>
  );
}

function Detail({ data, reload }) {
  const { meta } = data;
  const editable = meta.editable;
  const [tab, setTab] = useState('weights');
  const [values, setValues] = useState(() => ({
    weights: Object.fromEntries(data.indicators.map((i) => [i.id, i.current])),
    thresholds: Object.fromEntries(data.thresholds.map((t) => [t.id, t.current])),
    conditions: data.conditions.map((c) => ({ id: c.id, name: c.name, value: c.value, ratio: c.ratio, use: c.use })),
  }));
  const [preview, setPreview] = useState(null);
  const [calcBusy, setCalcBusy] = useState(false);
  const [reason, setReason] = useState('');
  const [reasonError, setReasonError] = useState('');
  const [busy, setBusy] = useState(false);
  const [requested, setRequested] = useState(false);

  // 처음 열 때 지금 값으로 변화를 계산해 둔다
  useEffect(() => {
    let alive = true;
    previewChange({ version: meta.version, values }).then((p) => alive && setPreview(p));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const sum = useMemo(() => Object.values(values.weights).reduce((a, b) => a + (Number(b) || 0), 0), [values.weights]);

  const setWeight = (id, v) => setValues((s) => ({ ...s, weights: { ...s.weights, [id]: v } }));
  const setThreshold = (id, v) => setValues((s) => ({ ...s, thresholds: { ...s.thresholds, [id]: v } }));
  const setCondition = (id, patch) => setValues((s) => ({ ...s, conditions: s.conditions.map((c) => (c.id === id ? { ...c, ...patch } : c)) }));
  const addCondition = () => setValues((s) => ({ ...s, conditions: [...s.conditions, { id: `kn${Date.now()}`, name: '', value: '', ratio: 0, use: true }] }));

  const recalc = async () => {
    setCalcBusy(true);
    try {
      await saveVersionDraft({ version: meta.version, values });
      setPreview(await previewChange({ version: meta.version, values }));
    } catch {
      reportActionError();
    } finally {
      setCalcBusy(false);
    }
  };

  const request = async () => {
    if (!reason.trim()) {
      setReasonError(DETAIL.reasonError);
      return;
    }
    setBusy(true);
    try {
      const r = await requestVersionApproval({ version: meta.version, values, reason });
      if (r.ok) {
        setRequested(true);
        reload();
      } else setReasonError(DETAIL.reasonError);
    } catch {
      reportActionError();
    } finally {
      setBusy(false);
    }
  };

  const weightColumns = [
    { key: 'field', header: DETAIL.weightsHead[0], first: true, width: 140 },
    { key: 'name', header: DETAIL.weightsHead[1], width: 320 },
    {
      key: 'current',
      header: DETAIL.weightsHead[2],
      align: 'right',
      width: 200,
      render: (i) =>
        editable ? (
          <NumberCell value={values.weights[i.id]} onChange={(v) => setWeight(i.id, v)} label={`${i.name} 현재 가중치`} suffix="%" width={88} changed={values.weights[i.id] !== i.previous} />
        ) : (
          <Changed on={i.current !== i.previous}>{`${i.current}%`}</Changed>
        ),
    },
    {
      key: 'previous',
      header: DETAIL.weightsHead[3],
      align: 'right',
      width: 160,
      render: (i) => `${i.previous}%`,
    },
  ];
  const thresholdColumns = [
    { key: 'name', header: DETAIL.thresholdsHead[0], first: true, width: 280 },
    {
      key: 'current',
      header: DETAIL.thresholdsHead[1],
      align: 'right',
      width: 200,
      render: (t) =>
        editable ? (
          <NumberCell value={values.thresholds[t.id]} onChange={(v) => setThreshold(t.id, v)} label={`${t.name} 현재 값`} width={96} changed={values.thresholds[t.id] !== t.previous} />
        ) : (
          <Changed on={t.current !== t.previous}>{t.current}</Changed>
        ),
    },
    { key: 'previous', header: DETAIL.thresholdsHead[2], align: 'right', width: 160 },
    { key: 'unit', header: DETAIL.thresholdsHead[3], width: 100 },
  ];
  const conditionColumns = [
    {
      key: 'name',
      header: DETAIL.conditionsHead[0],
      first: true,
      width: 280,
      render: (c) =>
        editable && c.id.startsWith('kn') ? (
          <TextInput inline label={DETAIL.conditionName} hideLabel value={c.name} onChange={(v) => setCondition(c.id, { name: v })} />
        ) : (
          c.name
        ),
    },
    {
      key: 'value',
      header: DETAIL.conditionsHead[1],
      width: 220,
      render: (c) =>
        editable ? <TextInput inline label={`${c.name || DETAIL.conditionName} 기준값`} value={c.value} onChange={(v) => setCondition(c.id, { value: v })} width={150} /> : c.value,
    },
    {
      key: 'ratio',
      header: DETAIL.conditionsHead[2],
      align: 'right',
      width: 200,
      render: (c) =>
        editable ? <NumberCell value={c.ratio} onChange={(v) => setCondition(c.id, { ratio: v })} label={`${c.name || DETAIL.conditionName} 반영 비율`} suffix="%" width={88} /> : `${c.ratio}%`,
    },
    {
      key: 'use',
      header: DETAIL.conditionsHead[3],
      width: 140,
      render: (c) =>
        editable ? (
          <label className={styles.inlineEdit}>
            <input type="checkbox" checked={c.use} onChange={(e) => setCondition(c.id, { use: e.target.checked })} />
            <span>{DETAIL.use}</span>
          </label>
        ) : c.use ? (
          DETAIL.use
        ) : (
          DETAIL.useOff
        ),
    },
  ];

  const weightRows = data.indicators.map((i) => ({ ...i, current: editable ? values.weights[i.id] : i.current }));

  return (
    <>
      <Link to="/admin/standards/criteria" className={styles.back}>
        {DETAIL.back}
      </Link>
      <PageHeader title={DETAIL.title(meta.version)} subtitle={DETAIL.subtitle} meta={<Badge tone={VERSION_TONE[meta.status]}>{meta.status}</Badge>} />
      <p className={styles.meta}>{DETAIL.run(meta.run)}</p>
      {meta.status === '반려' && meta.returnedReason ? (
        <div style={{ marginTop: 16 }}>
          <Banner tone="warning">{DETAIL.returned(meta.returnedReason)}</Banner>
        </div>
      ) : null}

      <div className={styles.stack} style={{ marginTop: 24 }}>
        <section aria-label={DETAIL.usedTitle}>
          <h2 className={styles.usedTitle}>{DETAIL.usedTitle}</h2>
          <DataTable
            caption={DETAIL.usedTitle}
            compact
            columns={[
              { key: 'field', header: DETAIL.usedHead[0], first: true, nowrap: true },
              { key: 'name', header: DETAIL.usedHead[1] },
              { key: 'source', header: DETAIL.usedHead[2] },
              { key: 'valueState', header: DETAIL.usedHead[3], nowrap: true },
            ]}
            rows={data.indicators}
            getRowKey={(i) => i.id}
          />
        </section>
        <Tabs label={DETAIL.title(meta.version)} idPrefix="detail" value={tab} onChange={setTab} tabs={TAB_KEYS.map((k) => ({ key: k, label: DETAIL.tabs[k] }))} />
        <div id="detail-panel" role="tabpanel" aria-labelledby={`detail-${tab}`}>
          {tab === 'weights' ? (
            <div>
              <DataTable caption={DETAIL.tabs.weights} columns={weightColumns} rows={weightRows} getRowKey={(i) => i.id} />
              <p className={styles.sum}>{DETAIL.weightsSum(sum)}</p>
            </div>
          ) : null}
          {tab === 'thresholds' ? <DataTable caption={DETAIL.tabs.thresholds} columns={thresholdColumns} rows={data.thresholds} getRowKey={(t) => t.id} /> : null}
          {tab === 'conditions' ? (
            <div className={styles.stack}>
              <DataTable caption={DETAIL.tabs.conditions} columns={conditionColumns} rows={values.conditions} getRowKey={(c) => c.id} />
              {editable ? (
                <div>
                  <Button variant="secondary" onClick={addCondition}>
                    {DETAIL.addCondition}
                  </Button>
                </div>
              ) : null}
            </div>
          ) : null}
        </div>

        <Panel title={DETAIL.previewTitle}>
          <div className={styles.previewLine}>
            <p className={styles.previewText}>{preview ? DETAIL.previewBody(preview.top, preview.changed) : ' '}</p>
            {editable ? (
              <Button variant="secondary" loading={calcBusy} onClick={recalc}>
                {DETAIL.recalc}
              </Button>
            ) : null}
          </div>
        </Panel>

        {editable ? (
          <Panel>
            <TextArea label={DETAIL.reasonLabel} value={reason} onChange={(v) => { setReason(v); setReasonError(''); }} placeholder={DETAIL.reasonPlaceholder} error={reasonError} required />
          </Panel>
        ) : null}
        {requested ? (
          <Banner tone="success">
            {DETAIL.requested}{' '}
            <Link to="/admin/standards/approvals" className={styles.jurLink}>
              {DETAIL.toApprovals}
            </Link>
          </Banner>
        ) : null}
      </div>

      {editable ? (
        <div className={styles.actionBar}>
          <span className={styles.barText}>{preview ? DETAIL.recalcedAt(preview.at.slice(0, 16).replace('T', ' ').replaceAll('-', '.')) : ''}</span>
          <Button variant="primary" loading={busy} onClick={request}>
            {DETAIL.request}
          </Button>
        </div>
      ) : null}
    </>
  );
}

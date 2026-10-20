import { useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { listUploadTargets, listUploads, uploadFile } from '../../../api/admin.js';
import { useAsync } from '../../../shared/hooks/useAsync.js';
import Button from '../../components/Button.jsx';
import DataTable from '../../components/DataTable.jsx';
import { FileInput, SelectInput, TextInput } from '../../components/Field.jsx';
import Loadable from '../../components/Loadable.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import Panel, { Banner } from '../../components/Panel.jsx';
import { UPLOAD } from './copy.js';
import styles from './Data.module.css';

const FORMATS = ['CSV', 'XLSX', 'SHP', 'DXF'];
const FORMAT_TEXT = FORMATS.join(', ');
const RECEIVED = ['파일', '시 내부 자료'];
const OFFICIAL = ['공식 원본', '가공본', '미확인'];

/** AD-03 자료 올리기 (유형 C): 폼 아래에 올린 기록 표. 출처와 기준일은 필수이고, 올리면 검사가 바로 돈다. */
export default function UploadPage() {
  const [params] = useSearchParams();
  const targets = useAsync(() => listUploadTargets(), []);
  const records = useAsync(() => listUploads(), []);

  return (
    <div>
      <PageHeader title={UPLOAD.title} subtitle={UPLOAD.subtitle} />
      <div className={styles.stackPanels}>
        <Loadable state={targets} areaName={UPLOAD.title} rows={4}>
          {(list) => <UploadForm targets={list} preset={params.get('data')} onUploaded={records.reload} />}
        </Loadable>
        <Panel title={UPLOAD.recordsTitle} padded={false}>
          <Loadable state={records} areaName={UPLOAD.failedArea} rows={4}>
            {(rows) => (
              <DataTable
                caption={UPLOAD.recordsTitle}
                columns={[
                  { key: 'atLabel', header: UPLOAD.recordsHead[0], nowrap: true },
                  { key: 'by', header: UPLOAD.recordsHead[1], nowrap: true },
                  { key: 'dataName', header: UPLOAD.recordsHead[2], first: true },
                  { key: 'basis', header: UPLOAD.recordsHead[3], nowrap: true },
                  { key: 'source', header: UPLOAD.recordsHead[4] },
                  {
                    key: 'errors',
                    header: UPLOAD.recordsHead[5],
                    nowrap: true,
                    render: (u) => (
                      <Link to="/admin/data/checks" className={styles.link}>
                        {UPLOAD.errorsCount(u.errors)}
                      </Link>
                    ),
                  },
                ]}
                rows={rows}
                getRowKey={(u) => u.id}
                footer={<span>{UPLOAD.recordsNote}</span>}
              />
            )}
          </Loadable>
        </Panel>
      </div>
    </div>
  );
}

function UploadForm({ targets, preset, onUploaded }) {
  const initial = targets.find((t) => t.id === preset) || targets[0];
  const [dataId, setDataId] = useState(initial.id);
  const item = targets.find((t) => t.id === dataId);
  const [file, setFile] = useState(null);
  const [source, setSource] = useState('');
  const [basis, setBasis] = useState('');
  const [received, setReceived] = useState(initial.source);
  const [official, setOfficial] = useState(initial.official === '미확인' ? '가공본' : initial.official);
  const [period, setPeriod] = useState('');
  const [errors, setErrors] = useState({});
  const [done, setDone] = useState(null);
  const [busy, setBusy] = useState(false);

  const pick = (id) => {
    const t = targets.find((x) => x.id === id);
    setDataId(id);
    setReceived(t.source);
    setOfficial(t.official === '미확인' ? '가공본' : t.official); // 공식 배포판인지 모르면 '가공본'으로 둔다
    setDone(null);
  };

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setDone(null);
    try {
      const r = await uploadFile({ dataId, fileName: file?.name || '', source, basis, received, official, period });
      if (!r.ok) {
        setErrors(r.errors);
        return;
      }
      setErrors({});
      setDone(item.name);
      setFile(null);
      onUploaded();
    } finally {
      setBusy(false);
    }
  };

  const options = useMemo(() => targets.map((t) => ({ value: t.id, label: t.name })), [targets]);

  return (
    <Panel className={styles.formPanel}>
      <form className={styles.formGrid} onSubmit={submit} noValidate>
        <SelectInput label={UPLOAD.data} value={dataId} onChange={pick} options={options} required />
        <FileInput key={done ? 'done' : 'form'} label={UPLOAD.file} fileName={file?.name} onChange={setFile} help={UPLOAD.fileHelp(FORMAT_TEXT)} error={errors.format ? UPLOAD.errorFormat(FORMAT_TEXT) : null} required />
        <TextInput label={UPLOAD.source} value={source} onChange={setSource} placeholder={UPLOAD.sourcePlaceholder} error={errors.sourceBasis && !source.trim() ? UPLOAD.errorSourceBasis : null} required />
        <TextInput label={UPLOAD.basis} type="date" value={basis} onChange={setBasis} help={UPLOAD.basisHelp} error={errors.sourceBasis && !basis.trim() ? UPLOAD.errorSourceBasis : null} required />
        <SelectInput label={UPLOAD.received} value={received} onChange={setReceived} options={RECEIVED} />
        <SelectInput label={UPLOAD.official} value={official} onChange={setOfficial} options={OFFICIAL} />
        {item.complaint ? <TextInput label={UPLOAD.period} value={period} onChange={setPeriod} /> : null}
        {done ? (
          <Banner tone="success">
            {UPLOAD.done(done)}{' '}
            <Link to="/admin/data/checks" className={styles.link}>
              {UPLOAD.goChecks}
            </Link>
          </Banner>
        ) : null}
        <div className={styles.formActions}>
          <Button type="submit" variant="primary" loading={busy}>
            {UPLOAD.submit}
          </Button>
        </div>
      </form>
    </Panel>
  );
}

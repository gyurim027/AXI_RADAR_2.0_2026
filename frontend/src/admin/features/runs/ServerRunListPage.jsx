import { useEffect, useState } from 'react';
import { listAdminRuns } from '../../../api/admin.js';

const L = {
  title: '\uD68C\uCC28 \uBAA9\uB85D',
  intro: 'DB77\uC5D0 \uC800\uC7A5\uB41C \uC2E4\uD589\uD68C\uCC28 \uC815\uBCF4\uC785\uB2C8\uB2E4. \uD604\uC7AC\uB294 \uC77D\uAE30 \uC804\uC6A9\uC785\uB2C8\uB2E4.',
  failed: '\uD68C\uCC28 \uBAA9\uB85D \uC870\uD68C\uC5D0 \uC2E4\uD328\uD588\uC2B5\uB2C8\uB2E4.',
  loading: '\uD68C\uCC28 \uBAA9\uB85D\uC744 \uBD88\uB7EC\uC624\uB294 \uC911\uC785\uB2C8\uB2E4.',
  empty: '\uB4F1\uB85D\uB41C \uD68C\uCC28\uAC00 \uC5C6\uC2B5\uB2C8\uB2E4.',
  headers: [
    '\uD68C\uCC28', '\uC0DD\uC131\uC77C', '\uC790\uB8CC \uAE30\uAC04',
    '\uBE4C\uB4DC', '\uADDC\uCE59 \uBC84\uC804', '\uC6B4\uC601 \uC0C1\uD0DC',
  ],
  unknown: '\uC815\uBCF4 \uC5C6\uC74C',
};

export default function ServerRunListPage() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    listAdminRuns()
      .then((data) => {
        if (active) setRows(data);
      })
      .catch((err) => {
        if (active) setError(err.message || L.failed);
      });
    return () => { active = false; };
  }, []);

  return (
    <section>
      <h1>{L.title}</h1>
      <p>{L.intro}</p>

      {error && <p role="alert">{error}</p>}
      {!error && rows === null && <p role="status">{L.loading}</p>}
      {!error && rows?.length === 0 && <p>{L.empty}</p>}

      {!error && rows?.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {L.headers.map((head) => (
                  <th key={head} scope="col"
                    style={{ padding: 12, textAlign: 'left', borderBottom: '1px solid #aaa' }}>
                    {head}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((run) => (
                <tr key={run.id}>
                  <td style={{ padding: 12 }}>{run.name}</td>
                  <td style={{ padding: 12 }}>{run.created}</td>
                  <td style={{ padding: 12 }}>{run.period}</td>
                  <td style={{ padding: 12 }}>{run.buildId ?? '-'}</td>
                  <td style={{ padding: 12 }}>{run.ruleVersion ?? '-'}</td>
                  <td style={{ padding: 12 }}>{L.unknown}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

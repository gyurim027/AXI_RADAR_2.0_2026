import { mockCall } from './client.js';
import * as server from '../mocks/server.js';
import { backendAuthEnabled, priorityBackendEnabled } from './backend.js';
import { listCandidates } from './candidates.js';
import { toConditionRecord } from './priority.js';

export const getAnnualReport = mockCall('annualReport', (arg) => server.getAnnualReport(arg));
export const getBasisTable = mockCall('basisTable', (arg) => server.getBasisTable(arg));
const mockConditionRecord = mockCall('conditionRecord', (arg) => server.getConditionRecord(arg));
/** 우선순위 점수 근거. 서버 연결 모드에서는 점수 모델 결과로 요약을 만든다. */
export async function getConditionRecord(arg) {
  if (!(backendAuthEnabled && priorityBackendEnabled)) return mockConditionRecord(arg);
  return toConditionRecord(await listCandidates({ runId: arg.runId, gu: null }));
}
export const getProtectionCompare = mockCall('protectionCompare', (arg) => server.getProtectionCompare(arg));
export const getHalfYearSummary = mockCall('halfYearSummary', (arg) => server.getHalfYearSummary(arg));
export const recordDownload = mockCall('download', (arg) => server.recordDownload(arg));

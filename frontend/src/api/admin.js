// 어드민 화면이 데이터를 받는 길. 지금은 src/mocks/adminServer.js(가짜 서버)를 부른다. 백엔드가 붙으면 각 함수 안쪽만 fetch로 바꾼다.
import { mockCall } from './client.js';
import * as server from '../mocks/adminServer.js';
import { COMPLAINT_DATA_ID } from '../mocks/adminData.js';
import { backendRequest, backendAuthEnabled, opsBackendEnabled } from './backend.js';
import { createOpsApi } from './ops.js';
import { createChecksApi } from './checks.js';

const ops = createOpsApi(backendRequest);
const checks = createChecksApi(backendRequest);
/** 서버 모드에서만 쓴다: 검사 결과 화면의 위치 미확인 현황과 낮음 민원 */
export const getUnlocated = checks.getUnlocated;
export const listLowComplaints = checks.listLowComplaints;
export const listIssues = checks.listIssues;

export const getViewAsLabel = () => server.viewAsLabel();
const listMockAdminRuns = mockCall('admin.listAdminRuns', (arg) => server.listAdminRuns(arg));

export const listAdminRuns = backendAuthEnabled
  ? async () => {
      const response = await backendRequest('/api/d10/runs');

      if (!Array.isArray(response?.runs)) {
        throw new Error('D-10 회차 목록 응답 형식이 올바르지 않습니다.');
      }

      return response.runs.map((run) => {
        const start = run.periodStart ?? null;
        const end = run.periodEnd ?? null;

        return {
          id: String(run.runId),
          runId: run.runId,
          name: `실행회차 ${run.runId}`,
          kind: null,
          kindLabel: '유형 정보 없음',
          status: '상태 정보 없음',
          version: '-',
          period: start && end ? `${start} ~ ${end}` : '기간 정보 없음',
          created: run.createdAt ? String(run.createdAt).slice(0, 10) : '-',
          review: '-',
          complaintPeriod: {
            start: start ?? '',
            end: end ?? '',
          },
          calcDone: null,
          ran: null,
          readOnly: true,
          buildId: run.buildId,
          ruleVersion: run.ruleVersion,
        };
      });
    }
  : listMockAdminRuns;
/** D-10: ?? ?? 2 ?? ?? (DB ?? ??) */
export const getAdminRun = async (runId) => {
  if (!backendAuthEnabled) {
    throw new Error('?? ?? ????? ??? ? ? ????.');
  }
  if (String(runId) !== '2') {
    throw new Error('1? ????? ?? 2? ? ? ????.');
  }
  const response = await backendRequest('/api/d10/runs/2');
  if (String(response?.run?.runId) !== '2') {
    throw new Error('D-10 ?? ?? ??? ???? ????.');
  }
  return response;
};

export const listAdminNotifications = opsBackendEnabled ? ops.listNotifications : mockCall('admin.listAdminNotifications', (arg) => server.listAdminNotifications(arg));
export const markAdminNotificationRead = opsBackendEnabled ? ops.markNotificationRead : mockCall('admin.markAdminNotificationRead', (arg) => server.markAdminNotificationRead(arg));
export const listViewAsOptions = mockCall('admin.listViewAsOptions', (arg) => server.listViewAsOptions(arg));
export const startViewAs = mockCall('admin.startViewAs', (arg) => server.startViewAs(arg));
export const stopViewAs = mockCall('admin.stopViewAs', (arg) => server.stopViewAs(arg));
export const getDashboard = opsBackendEnabled ? ops.getDashboard : mockCall('admin.getDashboard', (arg) => server.getDashboard(arg));
export const listData = mockCall('admin.listData', (arg) => server.listData(arg));
export const listUploadTargets = mockCall('admin.listUploadTargets', (arg) => server.listUploadTargets(arg));
export const listUploads = mockCall('admin.listUploads', (arg) => server.listUploads(arg));
const uploadCall = mockCall('admin.uploadFile', (arg) => server.uploadFile(arg));
/** 민원 파일은 개인정보를 가리고 분류하느라 처리 시간이 길다 (목업에서도 조금 기다리게 한다) */
/**
 * 파일 올리기 요청. 서버가 파일 내용을 검사하고 저장하려면 실제 File 객체가 함께 가야 한다.
 * arg: { dataId, file(File), fileName, source, basis(기준일 YYYY-MM-DD), received, official, month(민원 파일 대상 월 YYYY-MM) }
 * 실제 서버 연결 때는 multipart/form-data로 보낸다(file을 그대로 붙인다).
 */
export const uploadFile = async (arg) => {
  if (arg?.dataId === COMPLAINT_DATA_ID) await new Promise((resolve) => setTimeout(resolve, 1500));
  return uploadCall(arg);
};
export const getChecks = mockCall('admin.getChecks', (arg) => server.getChecks(arg));
export const listLowLocation = mockCall('admin.listLowLocation', (arg) => server.listLowLocation(arg));
export const listClassify = mockCall('admin.listClassify', (arg) => server.listClassify(arg));
export const markClassifyAdmin = mockCall('admin.markClassifyAdmin', (arg) => server.markClassifyAdmin(arg));
export const createRun = mockCall('admin.createRun', (arg) => server.createRun(arg));
export const getOpenCheck = mockCall('admin.getOpenCheck', (arg) => server.getOpenCheck(arg));
export const openRun = mockCall('admin.openRun', (arg) => server.openRun(arg));
export const startCalc = mockCall('admin.startCalc', (arg) => server.startCalc(arg));
export const listExecutions = opsBackendEnabled ? ops.listExecutions : mockCall('admin.listExecutions', (arg) => server.listExecutions(arg));
/** 서버 줄에는 로그가 없어 펼칠 때 한 건을 따로 받는다. 연습용 서버는 줄에 로그가 이미 있다. */
export const getExecution = opsBackendEnabled ? ops.getExecution : mockCall('admin.getExecution', ({ id }) => server.listExecutions({ days: 3650 }).find((e) => e.id === id));
export const rerunExecution = opsBackendEnabled ? ops.rerunExecution : mockCall('admin.rerunExecution', (arg) => server.rerunExecution(arg));
export const listSchedule = mockCall('admin.listSchedule', (arg) => server.listSchedule(arg));
export const listVersions = mockCall('admin.listVersions', (arg) => server.listVersions(arg));
export const createVersion = mockCall('admin.createVersion', (arg) => server.createVersion(arg));
export const getVersion = mockCall('admin.getVersion', (arg) => server.getVersion(arg));
export const saveVersionDraft = mockCall('admin.saveVersionDraft', (arg) => server.saveVersionDraft(arg));
export const previewChange = mockCall('admin.previewChange', (arg) => server.previewChange(arg));
export const requestVersionApproval = mockCall('admin.requestVersionApproval', (arg) => server.requestVersionApproval(arg));
export const getDept = opsBackendEnabled ? ops.getDept : mockCall('admin.getDept', (arg) => server.getDept(arg));
/** 서버 모드에서만 쓴다: 수정안 근거 원문 찾기 */
export const searchLawText = opsBackendEnabled ? ops.searchLaw : () => Promise.resolve({ result: '보유 원문에서 못 찾음', items: [] });
export const getArticle = mockCall('admin.getArticle', (arg) => server.getArticle(arg));
export const requestDeptApproval = mockCall('admin.requestDeptApproval', (arg) => server.requestDeptApproval(arg));
export const listRegulationChanges = opsBackendEnabled ? ops.listRegulationChanges : mockCall('admin.listRegulationChanges', (arg) => server.listRegulationChanges(arg));
export const markRegulationSeen = opsBackendEnabled ? ops.markRegulationSeen : mockCall('admin.markRegulationSeen', (arg) => server.markRegulationSeen(arg));
export const getActionTable = mockCall('admin.getActionTable', (arg) => server.getActionTable(arg));
export const saveActionRow = mockCall('admin.saveActionRow', (arg) => server.saveActionRow(arg));
export const getDraftArticle = mockCall('admin.getDraftArticle', (arg) => server.getDraftArticle(arg));
export const saveActionDraft = mockCall('admin.saveActionDraft', (arg) => server.saveActionDraft(arg));
export const recordAdminDownload = mockCall('admin.recordAdminDownload', (arg) => server.recordAdminDownload(arg));
export const listApprovals = mockCall('admin.listApprovals', (arg) => server.listApprovals(arg));
export const listAccounts = opsBackendEnabled ? ops.listAccounts : mockCall('admin.listAccounts', (arg) => server.listAccounts(arg));
export const createAccount = opsBackendEnabled ? ops.createAccount : mockCall('admin.createAccount', (arg) => server.createAccount(arg));
export const setAccountStatus = opsBackendEnabled ? ops.setAccountStatus : mockCall('admin.setAccountStatus', (arg) => server.setAccountStatus(arg));
export const listAccess = opsBackendEnabled ? ops.listAccess : mockCall('admin.listAccess', (arg) => server.listAccess(arg));
export const getAlertEmail = opsBackendEnabled ? ops.getAlertEmail : mockCall('admin.getAlertEmail', (arg) => server.getAlertEmail(arg));
export const saveAlertEmail = opsBackendEnabled ? ops.saveAlertEmail : mockCall('admin.saveAlertEmail', (arg) => server.saveAlertEmail(arg));
export const getNewRunDefaults = mockCall('admin.getNewRunDefaults', (arg) => server.getNewRunDefaults(arg));
export const getPeriodGaps = mockCall('admin.periodGaps', (arg) => server.getPeriodGaps(arg));
export const setRunPeriod = mockCall('admin.setRunPeriod', (arg) => server.setRunPeriod(arg));

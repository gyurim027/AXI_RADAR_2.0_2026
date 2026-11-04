import { mockCall } from './client.js';
import { backendRequest, i07BackendEnabled } from './backend.js';
import { createApprovalApi } from './approvals.js';
import * as server from '../mocks/server.js';

const approvals = createApprovalApi(backendRequest);
export const listProposals = i07BackendEnabled ? approvals.list : mockCall('proposals', () => server.listProposals());
export const decideProposal = i07BackendEnabled ? approvals.decide : mockCall('decideProposal', (arg) => server.decideProposal(arg));
export const previewProposal = (row) => i07BackendEnabled ? approvals.preview(row) : Promise.resolve({ proposalId: row.id, changes: row.changes, impact: row.impact });
export const applyProposal = (arg) => approvals.apply(arg);
export const listDataList = mockCall('dataList', () => server.listDataList());
export const listRegulations = mockCall('regulations', () => server.listRegulations());
export const listActionTable = mockCall('actionTable', () => server.listActionTable());

import { mockCall } from './client.js';
import * as server from '../mocks/server.js';

export const listProposals = mockCall('proposals', () => server.listProposals());
export const decideProposal = mockCall('decideProposal', (arg) => server.decideProposal(arg));
export const listClassifySamples = mockCall('classify', (arg) => server.listClassifySamples(arg));
export const markClassify = mockCall('markClassify', (arg) => server.markClassify(arg));
export const listDataList = mockCall('dataList', () => server.listDataList());
export const listRegulations = mockCall('regulations', () => server.listRegulations());
export const listActionTable = mockCall('actionTable', () => server.listActionTable());

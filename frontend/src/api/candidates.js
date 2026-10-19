import { mockCall } from './client.js';
import * as server from '../mocks/server.js';

export const listCandidates = mockCall('candidates', (arg) => server.listCandidates(arg));
export const getCandidateDetail = mockCall('candidateDetail', (arg) => server.getCandidateDetail(arg));
export const saveDecision = mockCall('saveDecision', (arg) => server.saveDecision(arg));
export const setDept = mockCall('setDept', (arg) => server.setDept(arg));
export const getConfirmSummary = mockCall('confirmSummary', (arg) => server.getConfirmSummary(arg));
export const confirmGu = mockCall('confirmGu', (arg) => server.confirmGu(arg));
export const getGuCompare = mockCall('guCompare', (arg) => server.getGuCompare(arg));

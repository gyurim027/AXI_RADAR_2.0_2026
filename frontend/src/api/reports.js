import { mockCall } from './client.js';
import * as server from '../mocks/server.js';

export const getAnnualReport = mockCall('annualReport', (arg) => server.getAnnualReport(arg));
export const getBasisTable = mockCall('basisTable', (arg) => server.getBasisTable(arg));
export const getConditionRecord = mockCall('conditionRecord', (arg) => server.getConditionRecord(arg));
export const getProtectionCompare = mockCall('protectionCompare', (arg) => server.getProtectionCompare(arg));
export const getHalfYearSummary = mockCall('halfYearSummary', (arg) => server.getHalfYearSummary(arg));
export const recordDownload = mockCall('download', (arg) => server.recordDownload(arg));

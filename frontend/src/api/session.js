import { mockCall } from './client.js';
import * as server from '../mocks/server.js';

export const getCurrentUser = () => {
  const u = server.currentUser();
  return u ? server.publicUser(u) : null;
};
export const login = mockCall('login', ({ loginId, password }) => server.login(loginId, password));
export const logout = mockCall('logout', () => server.logout());
export const listRuns = mockCall('runs', () => server.listRuns());
export const listNotifications = mockCall('notifications', () => server.listNotifications());
export const markNotificationRead = mockCall('notifications', (arg) => server.markNotificationRead(arg));

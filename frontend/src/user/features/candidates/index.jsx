import CandidateListRoute from './pages/CandidateListPage.jsx';

// handle.edgeToEdge: 표와 지도가 화면 높이를 채운다(디자인 시스템 9-1)
export const candidateRoutes = [
  { path: 'candidates', element: <CandidateListRoute />, handle: { edgeToEdge: true, title: '점검 후보' } },
];

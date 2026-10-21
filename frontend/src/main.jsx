import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import 'pretendard/dist/web/variable/pretendardvariable-dynamic-subset.css';
import 'leaflet/dist/leaflet.css';
import './styles/user-tokens.css';
import './styles/admin-tokens.css';
import './styles/alias.css';
import './styles/admin-alias.css';
import './styles/base.css';
import App from './app/App.jsx';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

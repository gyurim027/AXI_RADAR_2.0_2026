import { RouterProvider } from 'react-router-dom';
import { AuthProvider } from './providers/AuthProvider.jsx';
import { router } from './routes.jsx';

export default function App() {
  return (
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
  );
}

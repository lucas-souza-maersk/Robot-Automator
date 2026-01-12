import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { LanguageProvider } from './contexts/LanguageContext';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Configuration from './pages/Configuration';
import System from './pages/System'; // Nova página

const PrivateRoute = ({ children }) => {
  const token = localStorage.getItem('edi_token');
  return token ? children : <Navigate to="/login" />;
};

function App() {
  return (
    <LanguageProvider> {/* Envolve tudo */}
      <Router>
        <Routes>
          <Route path="/login" element={<Login />} />
          
          <Route path="/dashboard" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
          <Route path="/profiles" element={<PrivateRoute><Configuration /></PrivateRoute>} />
          <Route path="/system" element={<PrivateRoute><System /></PrivateRoute>} />

          <Route path="*" element={<Navigate to="/dashboard" />} />
        </Routes>
      </Router>
    </LanguageProvider>
  );
}

export default App;
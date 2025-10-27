// src/App.js
import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Container, CssBaseline, CircularProgress, Box } from '@mui/material';

import { auth } from './firebase';
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard'; // 👈 Dashboard 페이지를 임포트
import LoginPage from './pages/LoginPage';

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = auth.onAuthStateChanged(currentUser => {
      setUser(currentUser);
      setLoading(false);
    });
    return () => unsubscribe();
  }, []);

  if (loading) {
    return <Box sx={{ display: 'flex', justifyContent: 'center', mt: 5 }}><CircularProgress /></Box>;
  }

  return (
    <Router>
      <CssBaseline />
      <Navbar user={user} />
      <Container sx={{ mt: 4, mb: 4 }}>
        {user ? (
          // 🙋‍♂️ 로그인 시 항상 Dashboard 페이지만 보여줍니다.
          <Dashboard user={user} />
        ) : (
          <LoginPage />
        )}
      </Container>
    </Router>
  );
}

export default App;
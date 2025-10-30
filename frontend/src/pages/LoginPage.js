// src/pages/LoginPage.js
import React from 'react';
import { Button, Typography, Paper } from '@mui/material';
import GoogleIcon from '@mui/icons-material/Google';
import { loginWithGoogle } from '../firebase';
import '../App.css';

function LoginPage() {
  const handleLogin = async () => {
    try {
      await loginWithGoogle();
    } catch (error) {
      console.error("구글 로그인 실패:", error);
    }
  };

  return (
    <Paper sx={{ p: 4, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <Typography variant="h5" sx={{ mb: 2 }}>Laions Fan App</Typography>
      <Typography sx={{ mb: 3 }}>로그인하고 모든 기능을 이용해보세요!</Typography>
      <Button
        variant="contained"
        startIcon={<GoogleIcon />}
        onClick={handleLogin}
      >
        Google 계정으로 로그인
      </Button>
    </Paper>
  );
}

export default LoginPage;
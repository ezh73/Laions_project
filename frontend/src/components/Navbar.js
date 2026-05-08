// src/components/Navbar.js
import React from 'react';
import { AppBar, Toolbar, Typography, Button, Box } from '@mui/material';
import { logout } from '../firebase';

export default function Navbar({ user }) {
  return (
    <AppBar position="static">
      <Toolbar>
        <Typography variant="h6" sx={{ flexGrow: 1 }}>
          Laions
        </Typography>
        {user && (
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <Typography sx={{ mx: 2 }}>
              {(user.displayName || user.user_metadata?.full_name || user.user_metadata?.name || user.email || '사용자')}님
            </Typography>
            <Button color="inherit" variant="outlined" onClick={logout}>로그아웃</Button>
          </Box>
        )}
      </Toolbar>
    </AppBar>
  );
}
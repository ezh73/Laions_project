// src/firebase.js
// Firebase → Supabase Auth 마이그레이션
// Firebase Auth를 Supabase Auth로 대체합니다.

import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = process.env.REACT_APP_SUPABASE_URL;
const SUPABASE_ANON_KEY = process.env.REACT_APP_SUPABASE_ANON_KEY;

const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

export const auth = supabase.auth;

// Google login with Supabase
export const loginWithGoogle = async () => {
  try {
    // 현재 접속 중인 origin을 redirectTo로 사용
    // Tailscale IP, localhost 등 어떤 환경에서도 동작
    const currentOrigin = window.location.origin;
    console.log("🔐 Google login redirectTo:", currentOrigin);
    
    // signInWithOAuth 호출
    const { data, error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: currentOrigin,
        queryParams: {
          access_type: 'offline',
          prompt: 'consent',
        },
      },
    });
    if (error) throw error;
    
    // data.url이 있으면 직접 window.location으로 리디렉션
    // (Supabase SDK가 자동으로 리디렉션하지 않는 환경 대비)
    if (data && data.url) {
      console.log("🔐 Redirecting to OAuth URL:", data.url);
      window.location.href = data.url;
    }
    
    return data;
  } catch (error) {
    console.error("구글 로그인 실패:", error);
    throw error;
  }
};

// Supabase auth state observer (App.js에서 사용)
export const onAuthStateChangedListener = (callback) => {
  const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
    callback(session?.user || null);
  });
  return subscription.unsubscribe.bind(subscription);
};

// Logout function
export const logout = async () => {
  const { error } = await supabase.auth.signOut();
  if (error) {
    console.error("로그아웃 실패:", error);
    throw error;
  }
};

export default supabase;

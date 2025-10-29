// src/firebase.js

import { initializeApp } from "firebase/app";
// 💡 [핵심 수정] 필요한 함수들을 firebase/auth에서 모두 가져옵니다.
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  signOut,
  setPersistence,              // <-- 1. setPersistence 추가
  browserSessionPersistence    // <-- 2. browserSessionPersistence 추가
} from "firebase/auth";

// Environment variables are automatically loaded from the .env file
const firebaseConfig = {
  apiKey: process.env.REACT_APP_FIREBASE_API_KEY,
  authDomain: process.env.REACT_APP_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.REACT_APP_FIREBASE_PROJECT_ID,
  storageBucket: process.env.REACT_APP_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.REACT_APP_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.REACT_APP_FIREBASE_APP_ID
};

// Firebase app initialization
const app = initializeApp(firebaseConfig);

// Firebase auth object and Google provider
export const auth = getAuth(app);
const provider = new GoogleAuthProvider();

// 💡 [핵심 수정] Google login popup 함수를 async/await 구조로 변경합니다.
export const loginWithGoogle = async () => {
  try {
    // ▼▼▼ 로그인 실행 직전에 이 코드를 추가합니다. ▼▼▼
    // 로그인 정보 저장 방식을 'session'으로 설정합니다.
    // 이렇게 하면 브라우저를 닫을 때 로그인 정보가 자동으로 사라집니다.
    await setPersistence(auth, browserSessionPersistence);

    // 이제 구글 로그인을 실행합니다.
    const result = await signInWithPopup(auth, provider);
    console.log("구글 로그인 성공 (세션 유지 모드):", result.user);
    return result; // 전체 result 객체를 반환하거나 result.user를 반환할 수 있습니다.

  } catch (error) {
    console.error("구글 로그인 실패:", error);
    throw error;
  }
};

// Logout function (기존 함수와 동일, 두 개 중 하나만 남기셔도 됩니다)
export const logout = () => {
  return signOut(auth);
};

export const logoutUser = async () => {
    const auth = getAuth();
    try {
        await signOut(auth);
        console.log("로그아웃 성공");
    } catch (error) {
        console.error("로그아웃 실패:", error);
        throw error;
    }
};
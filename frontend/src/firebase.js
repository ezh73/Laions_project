// src/firebase.js

import { initializeApp } from "firebase/app";
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  signOut,
  setPersistence,
  browserLocalPersistence,
  onAuthStateChanged
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

// 앱 초기화 시점에 persistence 설정 (login 호출보다 먼저 적용)
setPersistence(auth, browserLocalPersistence);

// Google login with popup (redirect 대신 popup 사용)
export const loginWithGoogle = async () => {
  try {
    const result = await signInWithPopup(auth, provider);
    return result.user;
  } catch (error) {
    console.error("구글 로그인 실패:", error);
    throw error;
  }
};

// Firebase auth state observer (App.js에서 사용)
export const onAuthStateChangedListener = (callback) => {
  return onAuthStateChanged(auth, callback);
};

// Logout function (통일)
export const logout = () => {
  return signOut(auth);
};

// src/hooks/useSystemMode.js
// 백엔드 config.py의 ADMIN_MODE, SEASON_MODE 중앙 관리와 대응
// health API를 호출하여 seasonMode와 isAdminMode를 한 곳에서 관리

import { useState, useEffect } from 'react';
import { getHealth } from '../api/systemApi';

export default function useSystemMode() {
  const [seasonMode, setSeasonMode] = useState(null);
  const [isAdminMode, setIsAdminMode] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchSystemMode = async () => {
      try {
        const healthRes = await getHealth();
        setSeasonMode(healthRes.data.season_mode);
        setIsAdminMode(healthRes.data.admin_mode || false);
      } catch (err) {
        console.error("useSystemMode - health check failed:", err);
        setError(err.response?.data?.detail || "서버 상태를 확인할 수 없습니다.");
      } finally {
        setLoading(false);
      }
    };

    fetchSystemMode();
  }, []);

  return { seasonMode, isAdminMode, loading, error };
}

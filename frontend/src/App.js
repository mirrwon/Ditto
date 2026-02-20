import "./styles/tokens.css";
import "./styles/components.css"
import "./styles/layout.css"
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useState } from 'react';
import { ROUTES } from './constants/routes';
import {
  clearSession,
  readStoredUser,
  SESSION_EXPIRED_EVENT,
  touchActivity,
  isSessionExpired,
} from './services/session';
import api from './services/api';

//이미지 배경으로 설정
import { useEffect } from "react";

// pages (라우트에 직접 연결되는 페이지)\
import Home from './pages/Home';
import Login from './pages/auth/Login';
import Register from './pages/auth/Register';
import Myinfo from './pages/Myinfo';
import MyinfoEdit from './pages/MyinfoEdit';
import ChatPage from "./pages/ChatPage";
import PlantData from './pages/PlantData';
import Map from './pages/Map';

//게시판
import PlantBoard from "./pages/plantboard/PlantBoard";

import DiaryMainPage from "./pages/plantboard/DiaryMainPage";
import DiaryNewPage from "./pages/plantboard/DiaryNewPage";
import DiaryDetailPage from "./pages/plantboard/DiaryDetailPage";
import DiaryEditPage from "./pages/plantboard/DiaryEditPage";

import TimeLogPage from "./pages/plantboard/TimeLogPage";

// 챗봇 2,3,4Page
import UploadPage from "./components/chat/UploadPage";
import Survey from "./components/chat/Survey";
import PlantSelectPage from "./components/chat/PlantSelectPage";
import AnalyzePage from "./components/chat/AnalyzePage";
import RenderPage from "./components/chat/RenderPage";

// layout (공통 레이아웃)
import Layout from './components/layout/Layout';

import "./styles/PageTransition.css";

const SessionTracker = ({ user, onLogout }) => {
  const location = useLocation();

  useEffect(() => {
    if (!user) return;
    if (isSessionExpired()) {
      onLogout();
      return;
    }
    touchActivity();
  }, [location.key, user, onLogout]);

  return null;
};

const PageLoader = ({ isLoading }) => {
  if (!isLoading) return null;

  return (
    <div className="page-loading-overlay">
      <div className="page-loading-content">
        <div className="page-loading-logo">Ditto</div>
        <div className="page-loading-bar-wrap">
          <div className="page-loading-bar" />
        </div>
      </div>
    </div>
  );
};

const AppContent = ({ user, setUser, handleLogout }) => {
  const location = useLocation();
  const [isPageLoading, setIsPageLoading] = useState(false);
  const [prevKey, setPrevKey] = useState(location.key);

  // 라우트 변경 감지시 즉시 로딩 상태 활성화 (렌더링 단계에서 처리하여 깜빡임 방지)
  if (location.key !== prevKey) {
    setIsPageLoading(true);
    setPrevKey(location.key);
  }

  useEffect(() => {
    if (isPageLoading) {
      const timer = setTimeout(() => {
        setIsPageLoading(false);
      }, 1000); // 1초로 약간 단축하여 체감 속도 개선
      return () => clearTimeout(timer);
    }
  }, [isPageLoading]);

  return (
    <div className="App">
      <SessionTracker user={user} onLogout={handleLogout} />
      <PageLoader isLoading={isPageLoading} />

      {/* 로딩 중에는 내부 컨텐츠를 보이지 않게 처리 */}
      <div style={{ visibility: isPageLoading ? "hidden" : "visible", height: "100%" }}>
        <Layout user={user} onLogout={handleLogout}>
          <Routes>
            <Route path={ROUTES.HOME} element={<Home />} />
            <Route path={ROUTES.LOGIN} element={<Login setUser={setUser} />} />
            <Route path={ROUTES.REGISTER} element={<Register />} />
            <Route path={ROUTES.MYINFO} element={user ? <Myinfo /> : <Navigate to={ROUTES.LOGIN} />} />
            <Route path={ROUTES.MYINFO_EDIT} element={user ? <MyinfoEdit /> : <Navigate to={ROUTES.LOGIN} />} />
            <Route path={ROUTES.CHAT} element={user ? <ChatPage /> : <Navigate to={ROUTES.LOGIN} />} />
            <Route path={ROUTES.PLANTBOARD} element={user ? <PlantBoard /> : <Navigate to={ROUTES.LOGIN} />} />
            <Route path={ROUTES.DIARY} element={user ? <DiaryMainPage /> : <Navigate to={ROUTES.LOGIN} />} />
            <Route path={ROUTES.DIARY_NEW} element={user ? <DiaryNewPage /> : <Navigate to={ROUTES.LOGIN} />} />
            <Route path={ROUTES.DIARY_DETAIL} element={user ? <DiaryDetailPage /> : <Navigate to={ROUTES.LOGIN} />} />
            <Route path={ROUTES.DIARY_EDIT} element={user ? <DiaryEditPage /> : <Navigate to={ROUTES.LOGIN} />} />
            <Route path={ROUTES.TIMELOG} element={user ? <TimeLogPage /> : <Navigate to={ROUTES.LOGIN} />} />
            <Route path={ROUTES.PLANT_DATA} element={<PlantData />} />
          </Routes>
        </Layout>
      </div>
    </div>
  );
};

function App() {
  // localStorage에서 user 정보 불러와 초기 상태 설정
  const [user, setUser] = useState(readStoredUser());

  // 로그아웃: localStorage 비우고 user 상태도 null로
  const handleLogout = () => {
    api.post('/api/auth/logout').catch(() => {});
    clearSession();
    setUser(null);
  };

  //이미지 배경으로 설정
  // cover background removed

  useEffect(() => {
    const handleSessionExpired = () => {
      setUser(null);
    };

    window.addEventListener(SESSION_EXPIRED_EVENT, handleSessionExpired);
    return () => {
      window.removeEventListener(SESSION_EXPIRED_EVENT, handleSessionExpired);
    };
  }, []);



  return (

    <div className="App">
      <BrowserRouter>
        <SessionTracker user={user} onLogout={handleLogout} />
        {/* Layout: Header/Footer 등 공통 UI (로그아웃 핸들러도 내려줌) */}
        <Layout user={user} onLogout={handleLogout}>
          <Routes>

            {/* 메인(Home): 로그인한 사용자만 접근 */}
             <Route path={ROUTES.HOME} element={<Home />} />

            {/* 로그인: 비로그인 사용자 접근 */}
            <Route
              path={ROUTES.LOGIN}
              element={<Login setUser={setUser} />}
            />

            {/* 회원가입: 비로그인 사용자 접근 */}
            <Route
              path={ROUTES.REGISTER}
              element={<Register />}
            />

            {/* 내 정보: 로그인한 사용자만 접근 */}
            <Route
              path={ROUTES.MYINFO}
              element={user ? <Myinfo /> : <Navigate to={ROUTES.LOGIN} />}
            />

            {/* 내 정보 수정: 로그인한 사용자만 접근 */}
            <Route
              path={ROUTES.MYINFO_EDIT}
              element={user ? <MyinfoEdit /> : <Navigate to={ROUTES.LOGIN} />}
            />

            {/* Chat: 로그인한 사용자만 접근 */}
            <Route
              path={ROUTES.CHAT}
              element={user ? <ChatPage /> : <Navigate to={ROUTES.LOGIN} />}
            />

            {/* PlantBoard: 로그인한 사용자만 접근 */}

            < Route
              path={ROUTES.PLANTBOARD}
              element={user ? <PlantBoard/> : <Navigate to={ROUTES.LOGIN} />}
            /> 

            {/* Map: 로그인한 사용자만 접근 */}
            <Route
              path={ROUTES.MAP}
              element={user ? <Map /> : <Navigate to={ROUTES.LOGIN} />}
            />


            <Route
              path={ROUTES.DIARY}
              element={user ? <DiaryMainPage /> : <Navigate to={ROUTES.LOGIN} />}
            />
            <Route
              path={ROUTES.DIARY_NEW}
              element={user ? <DiaryNewPage /> : <Navigate to={ROUTES.LOGIN} />}
            />
            <Route
              path={ROUTES.DIARY_DETAIL}
              element={user ? <DiaryDetailPage /> : <Navigate to={ROUTES.LOGIN} />}
            />
            <Route
              path={ROUTES.DIARY_EDIT}
              element={user ? <DiaryEditPage /> : <Navigate to={ROUTES.LOGIN} />}
            />

            <Route
              path={ROUTES.TIMELOG}  
              element={user ? <TimeLogPage /> : <Navigate to={ROUTES.LOGIN} />}
            />

            <Route
              path={ROUTES.PLANT_DATA}
              element={<PlantData />}
            />

            <Route 
              path={ROUTES.UPLOAD}
              element={<UploadPage />}
            />

            <Route 
              path={ROUTES.SURVEY}
              element={<Survey />}
            />

            <Route 
              path={ROUTES.PLANT_PICK}
              element={<PlantSelectPage />}
            />

            <Route 
              path={ROUTES.ANALYZE}
              element={<AnalyzePage />}
            />

            <Route path={ROUTES.RENDER} element={<RenderPage />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </div>
  );
}

export default App;

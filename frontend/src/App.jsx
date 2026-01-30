import { Routes, Route } from 'react-router-dom';
import { useState, useEffect } from 'react'; // 🌟 상태 관리 추가
import Home from './pages/Home';
import TreePage from './pages/TreePage';
import WritePage from './pages/WritePage';
import ExplorePage from './pages/ExplorePage';
import ReportPage from './pages/ReportPage';
import LoginPage from './pages/LoginPage';
import './App.css';
import ProtectedRoute from './components/ProtectedRoute';

function App() {
  // 🌟 화면 너비를 실시간으로 감지하는 상태
  const [zoomLevel, setZoomLevel] = useState(1);

  useEffect(() => {
    const handleResize = () => {
      const width = window.innerWidth;
      // 🌟 기준: FHD(1920px) 이상일 때 조나단의 노트북 느낌(125%)이 나도록 설정
      if (width >= 1900) {
        setZoomLevel(1.25);
      } else {
        setZoomLevel(1);
      }
    };

    // 처음 로드될 때 실행
    handleResize();

    // 화면 크기가 바뀔 때마다 실행
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    // 🌟 최상위 div에 zoom 스타일을 적용합니다.
    <div style={{ 
      zoom: zoomLevel, 
      minHeight: '100vh', 
      width: '100%',
      backgroundColor: '#f8fafc' // 배경색 단절 방지 (선택 사항)
    }}>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/tree" element={
          <ProtectedRoute>
            <TreePage />
          </ProtectedRoute>
        } />
        <Route path="/write" element={
          <ProtectedRoute>
            <WritePage />
          </ProtectedRoute>
        } />
        <Route path="/explore" element={
          <ProtectedRoute>
            <ExplorePage />
          </ProtectedRoute>
        } />
        <Route path="/report" element={
          <ProtectedRoute>
            <ReportPage />
          </ProtectedRoute>
        } />
      </Routes>
    </div>
  );
}

export default App;
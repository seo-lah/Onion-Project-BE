import TreeScene from '../4_reportpage/TreeScene';
import { Edit2, TreePine, Search, User, HomeIcon, X, LogOut, Music, Pause, Play } from "lucide-react"; // 🌟 LogOut 추가
import { useNavigate, useLocation } from 'react-router-dom';
import { useState } from 'react';
import Swal from 'sweetalert2';
import api from '../api/axios'; // axios 인스턴스 import
import { useRef, useEffect } from 'react';
import PropTypes from 'prop-types';

const menuItems = [
  { name: "Home", path: "/", icon: <HomeIcon size={20} /> },
  { name: "Personality Tree", path: "/tree", icon: <TreePine size={20} /> },
  { name: "Write Page", path: "/write", icon: <Edit2 size={20} /> },
  { name: "Explore Page", path: "/explore", icon: <Search size={20} /> },
  { name: "My Report Page", path: "/report", icon: <User size={20} /> },
];


// --- [MusicPlayer Component] ---
const MusicPlayer = ({ isPlaying, setIsPlaying }) => {
    const audioRef = useRef(null);
    // const [isPlaying, setIsPlaying] = useState(false); // 👈 삭제 (부모에서 관리)
    const [progress, setProgress] = useState(0);
    const [musicUrl, setMusicUrl] = useState(null);
    const [loading, setLoading] = useState(true);

    // 1. 음악 데이터 가져오기
    useEffect(() => {
        const fetchMusic = async () => {
            try {
                const response = await api.get('/user/music/list');
                const musicData = response.data;
                
                if (musicData.musics && musicData.musics.length > 0) {
                    // 가장 최근에 올린 음악 사용
                    const latestMusic = musicData.musics[musicData.musics.length - 1];
                    const url = latestMusic.music_url || latestMusic.url;
                    
                    // URL 가공 (http로 시작하지 않으면 baseURL 붙이기)
                    if (url && !url.startsWith('http')) {
                        const baseUrl = api.defaults.baseURL;
                        setMusicUrl(`${baseUrl}${url.startsWith('/') ? '' : '/'}${url}`);
                    } else {
                        setMusicUrl(url);
                    }
                }
            } catch (error) {
                console.error("Failed to load music:", error);
            } finally {
                setLoading(false);
            }
        };
        fetchMusic();
    }, []);

    // 2. 재생 시간 업데이트
    const handleTimeUpdate = () => {
        if (audioRef.current) {
            const current = audioRef.current.currentTime;
            const duration = audioRef.current.duration;
            if (duration > 0) {
                setProgress((current / duration) * 100);
            }
        }
    };

    const togglePlay = () => {
        if (!audioRef.current || !musicUrl) return;
        
        if (isPlaying) {
            audioRef.current.pause();
            setIsPlaying(false); // 🌟 부모 상태 업데이트
        } else {
            audioRef.current.play().catch(e => console.error("Play error:", e));
            setIsPlaying(true);  // 🌟 부모 상태 업데이트
        }
    };

    // 음악이 없거나 로딩 중이면 렌더링 안 함 (선택 사항)
    if (loading) return null;
    if (!musicUrl) return null; 

    return (
        <div className="fixed bottom-10 right-10 z-[100] w-[340px] h-24 bg-white/80 backdrop-blur-xl border border-white/40 rounded-[30px] flex items-center px-5 shadow-2xl animate-in slide-in-from-bottom-10 duration-500">
            
            {/* 1. 왼쪽: 앨범 아트 (회전 아이콘) */}
            <div className="relative shrink-0">
                <div className={`w-14 h-14 rounded-full flex items-center justify-center bg-zinc-800 shadow-lg ${isPlaying ? 'animate-spin-slow' : ''}`}>
                    <Music size={24} color="white" />
                </div>
                {/* 재생 중일 때 나타나는 작은 표시기 (디테일) */}
                {isPlaying && (
                    <div className="absolute -top-1 -right-1 w-4 h-4 bg-emerald-500 border-2 border-white rounded-full" />
                )}
            </div>

            {/* 2. 중간: 정보 및 진행 바 (중앙 집중 구조) */}
            <div className="flex-1 mx-4 flex flex-col justify-center min-w-0">
                <div className="flex flex-col mb-2">
                    <span className="text-zinc-900 font-bold text-sm truncate">My Diary Music</span>
                    <span className="text-zinc-500 text-[11px] font-medium leading-tight">Onion Background Player</span>
                </div>
                
                {/* 진행 바 커스텀 */}
                <div className="w-full h-1.5 bg-zinc-200 rounded-full relative overflow-hidden">
                    <div 
                        className="h-full bg-emerald-500 transition-all duration-300 ease-linear rounded-full"
                        style={{ width: `${progress}%` }}
                    />
                </div>
            </div>

            {/* 3. 오른쪽: 재생 컨트롤 버튼 */}
            <div className="shrink-0 flex items-center justify-center">
                <button 
                    onClick={togglePlay}
                    className="w-12 h-12 rounded-full bg-zinc-800 text-white flex items-center justify-center hover:bg-black hover:scale-105 active:scale-95 transition-all shadow-md group"
                >
                    {isPlaying ? (
                        <Pause size={20} fill="currentColor" />
                    ) : (
                        <Play size={20} fill="currentColor" className="ml-1" />
                    )}
                </button>
            </div>

            {/* 오디오 태그 및 스타일 (기존과 동일) */}
            <audio ref={audioRef} src={musicUrl} onTimeUpdate={handleTimeUpdate} onEnded={() => setIsPlaying(false)} loop />
            <style>{`
                @keyframes spin-slow {
                    from { transform: rotate(0deg); }
                    to { transform: rotate(360deg); }
                }
                .animate-spin-slow {
                    animation: spin-slow 12s linear infinite;
                }
            `}</style>
        </div>
    );
};

MusicPlayer.propTypes = {
    isPlaying: PropTypes.bool.isRequired,
    setIsPlaying: PropTypes.func.isRequired,
};

export default function FullPage() {
    const navigate = useNavigate();
    const location = useLocation();
    const [isNavOpen, setIsNavOpen] = useState(false);

    const [isMusicPlaying, setIsMusicPlaying] = useState(false);

    // 🌟 로그아웃 함수 (다른 페이지와 동일하게 추가)
    const handleLogout = async () => {
        const result = await Swal.fire({
            title: 'Log out?',
            text: "You can always come back and write your diary! 🌳",
            icon: 'question',              // 질문형 아이콘
            showCancelButton: true,
            confirmButtonColor: '#6D5B98', // ONION 메인 보라색
            cancelButtonColor: '#aaa',     // 취소는 무채색 계열
            confirmButtonText: 'Logout',
            cancelButtonText: 'Cancel',
            reverseButtons: true           // 버튼 위치 최적화
          });
        
          // 2. 사용자가 '로그아웃'을 눌렀을 때만 처리
          if (result.isConfirmed) {
            localStorage.removeItem('token');
            localStorage.removeItem('user_id');
            Swal.fire({
                title: 'Logged out.',
                text: 'Logged out successfully.',
                icon: 'success',
                confirmButtonText: 'OK',
                confirmButtonColor: '#6D5B98' // ONION 앱 메인 컬러로 맞추면 더 좋겠죠?
              });
            
            navigate('/login');
        }
    };

    return (
      <div className="relative w-full h-screen">
        {/* [사이드 배너 버튼] */}
        <div 
            onClick={() => setIsNavOpen(true)}
            className="fixed right-0 top-[5vh] w-14 h-16 flex items-center justify-center z-[60] cursor-pointer group"
        >
            <div className="w-14 h-16 bg-zinc-800 rounded-tl-[20px] rounded-bl-[20px] flex items-center justify-center shadow-lg group-hover:w-16 transition-all text-white">
                <TreePine size={30} />
            </div>
        </div>

        {/* [확장되는 메뉴 박스] */}
        {isNavOpen && (
            <>
                <div className="fixed inset-0 bg-black/20 backdrop-blur-sm z-[70]" onClick={() => setIsNavOpen(false)} />
                <div className={`fixed right-0 top-[5vh] h-auto min-h-[400px] w-72 bg-zinc-800 rounded-tl-[30px] rounded-bl-[30px] shadow-2xl z-[80] transition-transform duration-300 flex flex-col p-8`}>
                    <div className="flex justify-between items-center mb-10">
                        <span className="text-zinc-400 font-bold tracking-widest text-sm uppercase">Menu</span>
                        <button onClick={() => setIsNavOpen(false)} className="text-white hover:rotate-90 transition-transform">
                            <X size={24} />
                        </button>
                    </div>

                    <nav className="flex flex-col gap-4">
                        {menuItems.map((item) => {
                            const isCurrentPage = location.pathname === item.path;
                            return (
                                <div key={item.path} className="relative">
                                    {isCurrentPage ? (
                                        <div className="flex items-center gap-4 px-6 py-4 bg-zinc-700/50 rounded-2xl border border-zinc-600 opacity-100 cursor-default text-white">
                                            <span className="text-emerald-400">{item.icon}</span>
                                            <span className="font-bold text-lg">{item.name}</span>
                                            <div className="absolute right-4 w-2 h-2 bg-emerald-400 rounded-full" />
                                        </div>
                                    ) : (
                                        <button
                                            onClick={() => {
                                                navigate(item.path);
                                                setIsNavOpen(false);
                                            }}
                                            className="w-full flex items-center gap-4 px-6 py-4 text-zinc-400 hover:text-white hover:bg-zinc-700 rounded-2xl transition-all group"
                                        >
                                            <span className="group-hover:scale-110 transition-transform">{item.icon}</span>
                                            <span className="text-lg font-medium">{item.name}</span>
                                        </button>
                                    )}
                                </div>
                            );
                        })}
                    </nav>

                    {/* 🌟 로그아웃 영역 추가 (일관성 유지) */}
                    <div className="mt-6 pt-6 border-t border-zinc-700">
                        <button
                            onClick={handleLogout}
                            className="w-full flex items-center gap-4 px-6 py-4 text-rose-400 hover:text-rose-300 hover:bg-rose-500/10 rounded-2xl transition-all group"
                        >
                            <LogOut size={20} className="group-hover:-translate-x-1 transition-transform" />
                            <span className="text-lg font-bold">Logout</span>
                        </button>
                    </div>
                </div>
            </>
        )}

        {/* 🌟 [수정] TreeScene에 'isWindy'라는 이름으로 재생 상태를 전달합니다. */}
        <TreeScene className="w-full h-full" isWindy={isMusicPlaying} />

        {/* 🌟 [NEW] 음악 플레이어 추가 */}
        <MusicPlayer isPlaying={isMusicPlaying} setIsPlaying={setIsMusicPlaying} />
      </div>
    );
}
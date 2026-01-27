
// import React from "react";
import { Calendar } from "../components/ui/calendar"; // 경로 확인 필수!
import { useState, useRef,useEffect } from 'react';
import SimpleBar from 'simplebar-react';
import { useLocation, useNavigate } from 'react-router-dom';
import 'simplebar-react/dist/simplebar.min.css';
import { Edit2, TreePine, Search, User, HomeIcon, X, LogOut } from "lucide-react";
import api from '../api/axios';
import { 
    FontBoldIcon, 
    FontItalicIcon, 
    SlashIcon, 
    UnderlineIcon, 
    StrikethroughIcon, 
    ImageIcon, 
    GearIcon,
  } from "@radix-ui/react-icons";

  import { 
    Plus, 
    Play, 
    Pause, 
    PaintBucket, 
    Baseline, 
    Trash2, 
    AlignLeft, 
    AlignCenter, 
    AlignRight 
  } from "lucide-react";

const menuItems = [
    { name: "Home", path: "/", icon: <HomeIcon size={20} /> },
    { name: "Personality Tree", path: "/tree", icon: <TreePine size={20} /> },
    { name: "Write Page", path: "/write", icon: <Edit2 size={20} /> },
    { name: "Explore Page", path: "/explore", icon: <Search size={20} /> },
    { name: "My Report Page", path: "/report", icon: <User size={20} /> },
];

export default function WritePage() {

    const location = useLocation();
    const editState = location.state;

    // --- 1. 상태 관리 (선택 데이터들) ---
    const [title, setTitle] = useState("");
    // const [content, setContent] = useState("");
    const [date, setDate] = useState(new Date()); // 선택된 날짜
    const [selectedMood, setSelectedMood] = useState(""); // 선택된 기분
    const [selectedWeather, setSelectedWeather] = useState(""); // 선택된 날씨
    const [tagInput, setTagInput] = useState(""); // 태그 입력창 값
    // 초기 상태는 빈 배열로 두고 서버에서 받아옵니다.
    const [tags, setTags] = useState([]); 
    const [selectedTags, setSelectedTags] = useState([]);

    const [menu, setMenu] = useState({ visible: false, x: 0, y: 0, target: null });
    const editorRef = useRef(null); // 에디터 영역 참조
    const fileInputRef = useRef(null); // [이미지 업로드 추가] 파일 input 참조
    const audioRef = useRef(null);
    const [musicFile, setMusicFile] = useState(null);

    const navigate = useNavigate();
    const [isNavOpen, setIsNavOpen] = useState(false);

    const [isLoading, setIsLoading] = useState(false); // 로딩 상태
    const [progress, setProgress] = useState(0);       // 게이지 진행도


    const [isSettingsOpen, setIsSettingsOpen] = useState(false);
    const [userSettings, setUserSettings] = useState({
        bgImage: "/static/images/default_bg.jpg",
        songUrl: "/static/music/standard.mp3" // 기본 서버 경로로 설정 (예시)
    });

    const [bgImageBase64, setBgImageBase64] = useState(""); // 추가


    const [isModalOpen, setIsModalOpen] = useState(true); // 페이지 진입 시 바로 모달 띄우기
    const [isScanning, setIsScanning] = useState(false); // 분석 중 로딩 상태
    const [content, setContent] = useState(""); // 일기 내용
    const scanInputRef = useRef(null); // 🌟 사진 스캔용 (새로 추가)
    const videoRef = useRef(null);
    const canvasRef = useRef(null);
    const [isWebcamOpen, setIsWebcamOpen] = useState(false);

    const [capturedImage, setCapturedImage] = useState(null); // 찍은 사진 데이터(Base64)
    const [isPreviewOpen, setIsPreviewOpen] = useState(false); // 확인 창 오픈 여부



    // 이미지 압축을 위한 헬퍼 함수
    const compressImage = (file) => {
        return new Promise((resolve) => {
            const reader = new FileReader();
            reader.readAsDataURL(file);
            reader.onload = (event) => {
                const img = new Image();
                img.src = event.target.result;
                img.onload = () => {
                    const canvas = document.createElement('canvas');
                    const MAX_WIDTH = 1280; // 가로 크기를 최대 1280px로 제한 (용량 확보 핵심)
                    let width = img.width;
                    let height = img.height;
    
                    if (width > MAX_WIDTH) {
                        height *= MAX_WIDTH / width;
                        width = MAX_WIDTH;
                    }
    
                    canvas.width = width;
                    canvas.height = height;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0, width, height);
    
                    // JPEG 형식으로 변환하며 화질을 0.7(70%)로 설정 (용량 대폭 감소)
                    canvas.toBlob((blob) => {
                        resolve(new File([blob], file.name, { type: "image/jpeg" }));
                    }, 'image/jpeg', 0.7);
                };
            };
        });
    };
    // 1. 카메라 시작 함수
    const startWebcam = async () => {
        setIsWebcamOpen(true);
        setIsModalOpen(false); // 선택 모달은 닫음
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true });
            if (videoRef.current) {
                videoRef.current.srcObject = stream;
            }
        } catch (err) {
            alert("카메라를 켤 수 없습니다: " + err.message);
            setIsWebcamOpen(false);
        }
    }; 


    // 2. 사진 촬영 및 백엔드 전송
    // 1단계: 사진 찍고 미리보기 띄우기
    const handleCapture = () => {
        if (!videoRef.current || !canvasRef.current) return;
    
        const canvas = canvasRef.current;
        const video = videoRef.current;
        canvas.width = 1280;
        canvas.height = (video.videoHeight / video.videoWidth) * 1280;
        canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
    
        // 캔버스 내용을 이미지 데이터(Base64)로 추출
        const imageData = canvas.toDataURL('image/jpeg', 0.9);
        setCapturedImage(imageData);
        setIsPreviewOpen(true); // 확인 창 열기
    
        // 카메라 스트림 일시 중지 (자원 절약)
        const stream = video.srcObject;
        stream.getTracks().forEach(track => track.stop());
    };
    
    // 2단계: 사용자가 '진행' 눌렀을 때 실제로 서버 전송
    const confirmAndScan = async () => {
        if (!capturedImage) return;
        
    
        setIsPreviewOpen(false);
        setIsWebcamOpen(false);
        setIsScanning(true);
    
        try {
            // Base64를 Blob 파일로 변환
            const response_blob = await fetch(capturedImage);
            const blob = await response_blob.blob();
            const file = new File([blob], "webcam_snap.jpg", { type: "image/jpeg" });
    
            const formData = new FormData();
            formData.append('file', file);

    
            const response = await api.post('/scan-diary', formData);
            
            setProgress(100);
            setTimeout(() => {
                const extractedText = response.data.extracted_text;
                console.log(content);
                setContent(extractedText);
                if (editorRef.current) {
                    editorRef.current.innerHTML = extractedText.replace(/\n/g, '<br>');
                }
                setIsScanning(false);
                setCapturedImage(null); // 데이터 초기화
            }, 600);
    
        } catch (error) {
            console.error("분석 실패:", error);
            alert("이미지 분석에 실패했습니다.");
            setIsScanning(false);
        }
    };
    
    // 3단계: 다시 찍기
    const handleRetake = () => {
        setIsPreviewOpen(false);
        setCapturedImage(null);
        startWebcam(); // 카메라 다시 켜기
    };



    const handleImageScan = async (e) => {
  
        const file = e.target.files[0];
        if (!file) return;
      
        setIsScanning(true); 
        setIsModalOpen(false); 
      
        try {
            const compressedFile = await compressImage(file);
            const formData = new FormData();
            
            // 🌟 주소 수정 및 user_id 추가
            formData.append('file', compressedFile); 
         
    
            const response = await api.post('/scan-diary', formData);

            setProgress(100); 
            setTimeout(() => {
                const extractedText = response.data.extracted_text;
                setContent(extractedText);
                if (editorRef.current) {
                    editorRef.current.innerHTML = extractedText.replace(/\n/g, '<br>');
                }
                setIsScanning(false); // 100%를 보여준 뒤 오버레이 닫기
            }, 600);
            const extractedText = response.data.extracted_text;
    
            setContent(extractedText); 
            if (editorRef.current) {
                editorRef.current.innerHTML = extractedText.replace(/\n/g, '<br>');
            }
        } catch (error) {
            console.error("OCR Error:", error);
            alert("이미지 분석에 실패했습니다.");
        } finally {
            setIsScanning(false);
        }
    };


    // 🌟 로그아웃 함수 추가
    const handleLogout = () => {
        if (window.confirm("로그아웃 하시겠습니까?")) {
            localStorage.removeItem('token');
            localStorage.removeItem('user_id');
            alert("로그아웃 되었습니다.");
            navigate('/login');
        }
    };

    const getAudioSrc = (url) => {
        if (!url) return "";
        
        if (url.startsWith('blob:') || url.startsWith('data:') || url.startsWith('http')) {
            return url;
        }
        
        // axios 인스턴스에 설정된 baseURL을 그대로 활용
        const baseUrl = api.defaults.baseURL;
        return `${baseUrl}${url.startsWith('/') ? '' : '/'}${url}`;
    };

    // --- 로딩 애니메이션 로직 ---
    useEffect(() => {
        let interval;
        if (isLoading || isScanning) {
            setProgress(0); // 시작할 때 0으로 초기화
            // 30초를 기준으로 진행하지만, 90%에서 멈추어 서버 응답을 대기하는 방식
            interval = setInterval(() => {
                setProgress((prev) => {
                    if (prev < 60) return prev + 2;      // 0~60%는 빠르게
                    if (prev < 90) return prev + 0.5;    // 60~90%는 천천히
                    return prev;                         // 90%에서 대기
                });
            }, 500); // 0.5초마다 갱신
        } else {
            setProgress(0);
            clearInterval(interval);
        }
        return () => clearInterval(interval);
    }, [isLoading, isScanning]);

    // --- [추가] 수정 모드일 때 데이터 로드 ---
    useEffect(() => {
        if (editState?.isEdit && editState?.existingData) {
            const d = editState.existingData;
            setTitle(d.title);
            // 에디터 HTML 내용 주입
            if (editorRef.current) {
                editorRef.current.innerHTML = d.content;
            }
            // Standard 데이터 복구
            setSelectedMood(d.standard.mood);
            setSelectedWeather(d.standard.weather);
            setSelectedTags(d.standard.tags);
            setDate(new Date(d.standard.date));
        }
    }, [editState]);

    // --- [추가] 1. 서버에서 기존 태그 목록 가져오기 ---
    useEffect(() => {
        // 🌟 이제 토큰을 여기서 직접 꺼낼 필요가 없습니다. (api.js의 인터셉터가 처리)
        const currentToken = localStorage.getItem('token');
        
        const fetchUserTags = async () => {
            try {
                // 1. api 인스턴스 사용 (Base URL과 Authorization 헤더 자동 포함)
                const response = await api.get('/user/stats');
                
                // 2. Axios는 응답 데이터가 바로 response.data에 들어있습니다.
                const data = response.data;
                
                // 3. 데이터 가공 (기존 로직 유지)
                const tagNames = Object.keys(data.user_tag_counts || {});
                setTags(tagNames); 
    
            } catch (err) {
                // 4. 에러 처리 (401 권한 없음, 404 등은 모두 여기로 점프)
                console.error("태그 로드 실패:", err);
                
                // 만약 토큰이 만료되어 401 에러가 난다면 로그인 페이지로 보낼 수도 있습니다.
                if (err.response?.status === 401) {
                    navigate('/login');
                }
            }
        };
    
        const fetchSettings = async () => {
            try {
                // 🌟 1. Promise.all과 api.get을 결합합니다.
                // 헤더(Authorization)는 인터셉터가 자동으로 넣어주니 신경 쓸 필요 없어요!
                const [imageRes, musicRes] = await Promise.all([
                    api.get('/user/profile-image'),
                    api.get('/user/music/list')
                ]);
        
                let newSettings = { ...userSettings };
        
                // 🌟 2. Axios는 응답 데이터가 .data에 들어있습니다.
                // 성공 시 데이터 가공 로직
                const imageData = imageRes.data;
                const serverImg = imageData.image_url || imageData.bgImage || imageData.url;
                if (serverImg) newSettings.bgImage = serverImg;
        
                const musicData = musicRes.data;
                if (musicData.musics?.length > 0) {
                    const latestMusic = musicData.musics[musicData.musics.length - 1];
                    newSettings.songUrl = latestMusic.music_url || latestMusic.url;
                }
        
                setUserSettings(newSettings);
                
            } catch (err) {
                // 🌟 3. 둘 중 하나라도 실패하거나 네트워크 에러가 나면 여기로 점프합니다.
                console.error("설정 로드 실패:", err);
            }
        };
        
        if (currentToken) {
            fetchUserTags();
            fetchSettings();
        }
    }, [ ]); // 의존성 배열 유지

    const handleDeleteTag = async (tagName) => {
        // 1. 사용자 확인
        if (!window.confirm(`'${tagName}' 태그를 정말 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.`)) {
            return;
        }
    
        try {
            // 2. API 호출
            // 🌟 Axios의 DELETE 요청에서 Body를 보낼 때는 { data: { ... } } 형식을 사용합니다.
            await api.delete('/user/tags', {
                data: { tag_name: tagName }
            });
    
            // 3. UI 상태 업데이트
            // Axios는 성공(2xx) 시에만 이 줄로 내려옵니다.
            setTags(prev => prev.filter(t => t !== tagName));
            setSelectedTags(prev => prev.filter(t => t !== tagName));
            
            alert("태그가 삭제되었습니다.");
    
        } catch (err) {
            // 4. 에러 처리
            console.error("태그 삭제 에러:", err);
            
            const errorMessage = err.response?.data?.detail || "태그 삭제에 실패했습니다.";
            alert(errorMessage);
        }
    };

    // --- [수정] 서버 통신 없이 로컬에서 태그 추가 ---
    const handleAddTag = () => {
        const trimmedTag = tagInput.trim();
        
        if (!trimmedTag) return;
        
        // 1. 전체 태그 목록에 추가 (중복이 아닐 때만)
        if (!tags.includes(trimmedTag)) {
            setTags(prev => [...prev, trimmedTag]);
        }
    
        // 2. 추가와 동시에 선택 상태로 만들기 (중복 선택 방지)
        if (!selectedTags.includes(trimmedTag)) {
            setSelectedTags(prev => [...prev, trimmedTag]);
        }
    
        setTagInput(""); // 입력창 초기화
    };

    // 엔터키 입력 시 실행
    const handleTagKeyDown = (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            handleAddTag();
        }
    };

    const toggleTagSelection = (tag) => {
        setSelectedTags(prev => 
            prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]
        );
    };
    
    // 기존 getImageSrc를 아래와 같이 수정
    const getImageSrc = (url) => {
        // 1. 기본 이미지 처리
        if (!url) return "/static/images/default_bg.jpg";
    
        // 2. 로컬 미리보기나 데이터 주소는 그대로 반환
        if (url.startsWith('blob:') || url.startsWith('data:')) {
            return url;
        }
        
        // 3. 주소가 http로 시작하면 외부 이미지이므로 그대로 쓰고, 
        // 아니면 우리가 설정한 환경 변수 주소와 결합합니다.
        const baseUrl = url.startsWith('http') 
            ? url 
            : (import.meta.env.VITE_API_URL) + url;
    
        // 4. 캐시 무효화를 위한 타임스탬프 추가
        return `${baseUrl}${baseUrl.includes('?') ? '&' : '?'}t=${new Date().getTime()}`;
    };

    // --- 1. 이미지 클릭 핸들러 (슬라이더 버그 수정 버전) ---
    const handleImageClick = (e) => {
        if (e.target.tagName === 'IMG') {
            const img = e.target;
            const rect = img.getBoundingClientRect();
            
            // [중요] 슬라이더 초기값이 튀지 않도록 현재 이미지의 실제 백분율 너비 계산
            let currentWidthPct = 100;
            if (img.style.width && img.style.width.includes('%')) {
                currentWidthPct = parseInt(img.style.width);
            } else if (img.parentElement) {
                // 스타일이 지정 안 된 경우 실제 픽셀 비율로 계산
                currentWidthPct = Math.round((img.offsetWidth / img.parentElement.offsetWidth) * 100);
            }
            
            setMenu({
                visible: true,
                x: rect.left + (rect.width / 2) - 80,
                y: rect.top + window.scrollY - 70,
                target: img,
                width: currentWidthPct // 슬라이더 시작점을 현재 너비에 맞춤
            });
        } else {
            setMenu(prev => ({ ...prev, visible: false }));
        }
    };

    useEffect(() => {
        const handleClickOutside = (e) => {
            if (!e.target.closest('.image-control-menu') && e.target.tagName !== 'IMG') {
                setMenu(prev => ({ ...prev, visible: false }));
            }
        };
        window.addEventListener('mousedown', handleClickOutside);
        return () => window.removeEventListener('mousedown', handleClickOutside);
    }, []);

    //설정 저장 api
    const handleSettingsSave = async () => {
        // 🌟 1. 세션 체크 (인터셉터가 처리하지만, 버튼 클릭 시 직관적인 알림을 위해 유지)
        if (!localStorage.getItem('token')) {
            alert("로그인 세션이 만료되었습니다. 다시 로그인해주세요.");
            return;
        }
    
        try {
            let finalMusicUrl = userSettings.songUrl;
            let finalBgImageUrl = userSettings.bgImage;
    
            let musicSuccess = true;
            let imageSuccess = true;
    
            // 1. 음악 업로드 섹션 (FormData 사용)
            if (musicFile) {
                const musicFormData = new FormData();
                musicFormData.append("title", "My Diary Music");
                musicFormData.append("artist", "Song Chaewon");
                musicFormData.append("file", musicFile);
    
                try {
                    // Axios는 FormData를 넣으면 자동으로 Content-Type을 multipart/form-data로 설정합니다.
                    const musicRes = await api.post("/user/music/upload", musicFormData);
                    const musicData = musicRes.data;
                    finalMusicUrl = musicData.music_url || musicData.url;
                } catch (err) {
                    musicSuccess = false;
                    console.error("음악 업로드 실패:", err);
                }
            }
    
            // 2. 이미지 업로드 섹션 (PUT 요청 + JSON)
            if (bgImageBase64) {
                try {
                    // api.put을 사용하며, 주소와 데이터만 넘기면 끝!
                    await api.put("/user/profile-image", {
                        image_url: bgImageBase64
                    });
                    finalBgImageUrl = bgImageBase64;
                } catch (err) {
                    imageSuccess = false;
                    console.error("이미지 업로드 실패:", err);
                }
            }
    
            // 3. 최종 상태 업데이트
            if (musicSuccess && imageSuccess) {
                setUserSettings({
                    songUrl: finalMusicUrl,
                    bgImage: finalBgImageUrl
                });
    
                setMusicFile(null);
                setBgImageBase64("");
                setIsSettingsOpen(false);
                alert("설정이 성공적으로 저장되었습니다! ✨");
            } else {
                alert("일부 설정 저장에 실패했습니다. 다시 시도해 주세요.");
            }
        } catch (err) {
            console.error("시스템 에러:", err);
            alert("서버와 통신 중 오류가 발생했습니다.");
        }
    };
    
    // 파일 업로드 시 Base64 변환 함수 (이미지/오디오 공용)
    const handleFileChange = (e, type) => {
        const file = e.target.files[0];
        if (!file) return;
    
        if (type === 'songUrl') {
            // 음악 파일 처리
            setMusicFile(file);
            const localAudioUrl = URL.createObjectURL(file);
            setUserSettings(prev => ({ ...prev, songUrl: localAudioUrl }));
        } else {
            // 이미지 파일 처리
            
            const reader = new FileReader();
            reader.onloadend = () => {
                const base64String = reader.result;
                setUserSettings(prev => ({ ...prev, bgImage: base64String }));
                setBgImageBase64(base64String); // 🌟 여기에 Base64 문자열 저장!
            };
            reader.readAsDataURL(file);
        }
    };


    // --- 2. 실시간 크기 조절 (드래그 시 자연스럽게 변경) ---
    const handleResize = (e) => {
        const val = e.target.value;
        if (menu.target) {
            menu.target.style.width = `${val}%`;
            menu.target.style.height = 'auto'; // 비율 유지
            setMenu(prev => ({ ...prev, width: val }));
        }
    };

    // --- 3. 정렬 시 간격 유지 (Margin 버그 수정) ---
    const alignImage = (alignment) => {
        if (!menu.target) return;
        const img = menu.target;
        const vMargin = "20px"; // 상하 간격을 20px로 고정
        
        img.style.display = "block";
        if (alignment === 'left') {
            img.style.margin = `${vMargin} auto ${vMargin} 0`;
        } else if (alignment === 'center') {
            img.style.margin = `${vMargin} auto`;
        } else if (alignment === 'right') {
            img.style.margin = `${vMargin} 0 ${vMargin} auto`;
        }
    };

    const deleteImage = () => {
        if (menu.target) menu.target.remove();
        setMenu(prev => ({ ...prev, visible: false }));
    };

    // --- 1. 새로운 선 추가 함수 (두께감 있는 div 버전) ---
    const insertCustomLine = () => {
        // 선 주변에 위아래로 글을 쓸 수 있는 공간(<p>)과 함께 선 영역을 삽입합니다.
        // contenteditable="false"를 주어 선 자체가 글자로 인식되지 않게 합니다.
        const lineHtml = `
        <div class="diary-divider-wrapper" 
             contenteditable="false" 
             style="display: block; width: 100%; padding: 12px 0; margin: 0; cursor: pointer;"
             onmouseover="this.querySelector('line').setAttribute('stroke', '#3b82f6'); this.style.backgroundColor='#eff6ff';"
             onmouseout="this.querySelector('line').setAttribute('stroke', '#e5e5e5'); this.style.backgroundColor='transparent';"
             onclick="this.remove();">
            <svg width="100%" height="1" style="display: block; overflow: visible;">
                <line x1="0" y1="0.5" x2="100%" y2="0.5" 
                      stroke="#e5e5e5" 
                      stroke-width="1" 
                      shape-rendering="crispEdges" />
            </svg>
        </div>
        <p><br></p>
    `;
        document.execCommand('insertHTML', false, lineHtml);
    };

    // --- 4. 이미지 업로드 (초기 간격 설정) ---
    const handleImageUpload = (e) => {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (event) => {
                const base64String = event.target.result;
                // 처음에 삽입될 때 상하 마진 20px와 너비 100%를 명시적으로 부여함
                const imgHtml = `
                    
                    <img src="${base64String}" 
                         style="width: 50%; height: auto; display: block; margin: 20px auto; cursor: pointer; border-radius: 8px; transition: filter 0.3s;" />
                    `;
                document.execCommand('insertHTML', false, imgHtml);
            };
            reader.readAsDataURL(file);
        }
        e.target.value = '';
    };

    


    // 2. 스타일 적용 함수 (상태 업데이트를 제거하여 커서 튐 방지)
    const applyStyle = (command, value = null) => {
        document.execCommand(command, false, value);
        // 여기서 setContent를 호출하지 않아도 DOM은 이미 변해있습니다.
    };



    // --- [수정] 일기 저장/업데이트 함수 ---
    // --- [수정] 일기 저장/업데이트 함수 ---
    const handleSave = async (isDraft = false) => {
        // 에디터 내용 및 유효성 검사 (기존 로직 유지)
        const currentContent = editorRef.current ? editorRef.current.innerHTML : "";
        
        if (!isDraft) {
            const plainText = currentContent.replace(/<[^>]*>/g, "").trim();
            if (plainText.length < 10) {
                alert("AI 분석을 위해 일기 내용을 최소 10자 이상 작성해 주세요! ✍️");
                return;
            }
            if (!title.trim()) {
                alert("일기 제목을 입력해 주세요.");
                return;
            }
        }
    
        if (!localStorage.getItem('token')) {
            alert("로그인 세션이 만료되었습니다.");
            navigate('/login');
            return;
        }
    
        setIsLoading(!isDraft);
    
        // 날짜 및 시간 생성 (기존 로직 유지)
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const localDateString = `${year}-${month}-${day}`;
        const now = new Date();
        const savedTime = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;
    
        const diaryData = {
            title: title.trim(),
            content: currentContent,
            entry_date: localDateString,
            mood: selectedMood || "soso",
            weather: selectedWeather || "sun",
            tags: selectedTags,
            image_url: "",
            is_temporary: isDraft,
            entry_time: savedTime,
            diary_id: editState?.diaryId || null
        };
    
        try {
            // 🌟 1. 임시저장을 정식저장으로 전환할 때 이전 데이터 삭제
            if (!isDraft && editState?.isEdit) {
                await api.delete(`/diaries/${editState.diaryId}`);
                console.log("이전 임시저장 데이터 삭제 성공");
            }
    
            // 🌟 2. URL 및 메서드 설정
            const isUpdatingDraft = isDraft && editState?.isEdit;
            const url = isUpdatingDraft 
                ? `/diaries/${editState.diaryId}` 
                : `/analyze-and-save`;
            
            // 🌟 3. Axios 호출 (분석 요청 시 timeout 50초 부여)
            await api({
                method: isUpdatingDraft ? 'PATCH' : 'POST',
                url: url,
                data: diaryData,
                timeout: isDraft ? 10000 : 50000 // 분석 시에는 50초, 단순 저장 시에는 10초
            });
    
            // 🌟 4. 성공 처리 (Axios는 성공 시 바로 여기로 옴)
            setProgress(100);
            setTimeout(() => {
                setIsLoading(false);
                alert(isDraft ? "임시저장 완료!" : "일기가 성공적으로 분석되고 저장되었습니다! 🧅");
                navigate('/explore');
            }, 600);
    
        } catch (err) {
            setIsLoading(false);
            console.error("저장 실패:", err);
    
            // 🌟 5. 에러 대응
            const errorData = err.response?.data;
            if (errorData?.detail?.includes("AI Analysis Failed")) {
                alert("Gemini AI가 일기를 분석하는 데 실패했습니다. 내용을 조금 더 보강해 보세요.");
            } else if (err.code === 'ECONNABORTED') {
                alert("분석 시간이 너무 오래 걸려 중단되었습니다. 잠시 후 다시 시도해 주세요.");
            } else {
                alert(`저장 실패: ${errorData?.detail || "서버 연결 오류"}`);
            }
        }
    };


        
    
    

    // 1. 음악 재생을 위한 상태와 Ref 추가
    const [isPlaying, setIsPlaying] = useState(false);
    

    const toggleMusic = async () => {
        if (!audioRef.current) return;
    
        try {
            if (isPlaying) {
                audioRef.current.pause();
            } else {
                // 재생 promise가 해결될 때까지 기다림
                await audioRef.current.play();
            }
            setIsPlaying(!isPlaying);
        } catch (err) {
            console.error("재생 실패:", err);
            // 에러가 나면 상태를 정지로 초기화
            setIsPlaying(false);
        }
    };


    return (

        
        
        <div className="min-h-screen w-full bg-brand-bg m-0 p-0 overflow-x-hidden flex items-center justify-center relative">
            {/* --- 1. 진입 시 선택 모달 --- */}
            {isModalOpen && (
                <div className="fixed inset-0 z-[1100] flex items-center justify-center bg-black/60 backdrop-blur-md">
                    <div className="bg-white w-[400px] p-10 rounded-[40px] shadow-2xl text-center flex flex-col gap-6 animate-in fade-in zoom-in duration-300">
                        <div className="space-y-2">
                            <h2 className="text-2xl font-bold text-zinc-800">어떻게 작성할까요?</h2>
                            <p className="text-zinc-500 text-sm">기록 방식을 선택해주세요.</p>
                        </div>
                        
                        <div className="flex flex-col gap-3">
                            {/* 1. 직접 쓰기 */}
                            <button onClick={() => setIsModalOpen(false)} className="w-full py-4 bg-zinc-100 hover:bg-zinc-200 text-zinc-800 rounded-2xl font-bold transition-all flex items-center justify-center gap-2">
                                <Edit2 size={20} /> 직접 타이핑하기
                            </button>
            
                            {/* 2. 🌟 카메라로 바로 찍기 */}
                            <button 
                                onClick={startWebcam} 
                                className="w-full py-4 bg-blue-500 hover:bg-blue-600 text-white rounded-2xl font-bold transition-all flex items-center justify-center gap-2 shadow-lg shadow-blue-500/30"
                            >
                                <Search size={20} /> 실시간 사진 찍기
                            </button>
                            
                            {/* 3. 갤러리에서 가져오기 */}
                            <button 
                                onClick={() => scanInputRef.current.click()} 
                                className="w-full py-4 bg-emerald-500 hover:bg-emerald-600 text-white rounded-2xl font-bold transition-all flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/30"
                            >
                                <ImageIcon width={20} height={20} /> 갤러리에서 스캔
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* 🌟 스캔 전용 숨겨진 Input (새로 추가) */}
            <input type="file" accept="image/*" ref={scanInputRef} onChange={handleImageScan} className="hidden" />
            {/* 🌟 카메라 촬영 전용 (capture="environment"가 핵심) */}
            {/* --- 웹캠 오버레이 UI --- */}
            {isWebcamOpen && (
                <div className="fixed inset-0 z-[1300] bg-black flex flex-col items-center justify-center p-4">
                    <div className="relative w-full max-w-2xl rounded-3xl overflow-hidden shadow-2xl border-4 border-white/20">
                        <video ref={videoRef} autoPlay playsInline className="w-full h-full object-cover" />
                        <div className="absolute bottom-6 left-0 right-0 flex justify-center gap-4">
                            <button onClick={() => setIsWebcamOpen(false)} className="px-6 py-3 bg-white/20 text-white rounded-full backdrop-blur-md">취소</button>
                            <button onClick={handleCapture} className="px-8 py-3 bg-emerald-500 text-white rounded-full font-bold shadow-lg">📸 사진 찍기</button>
                        </div>
                    </div>
                    <p className="text-white/60 mt-4">일기장을 카메라 중앙에 맞춰주세요.</p>
                    <canvas ref={canvasRef} className="hidden" />
                </div>
            )}
            {/* --- 2.5 찍은 사진 미리보기 및 확인 창 --- */}
            {isPreviewOpen && (
                <div className="fixed inset-0 z-[1400] bg-black/90 flex flex-col items-center justify-center p-6 backdrop-blur-md">
                    <div className="w-full max-w-xl bg-white rounded-[40px] overflow-hidden shadow-2xl animate-in zoom-in duration-300">
                        <div className="p-8 text-center border-b border-gray-100">
                            <h3 className="text-2xl font-bold text-zinc-800">사진 확인</h3>
                            <p className="text-zinc-500 text-sm mt-1">글씨가 선명하게 잘 찍혔나요?</p>
                        </div>
                        
                        {/* 찍힌 사진 표시 */}
                        <div className="w-full h-80 bg-zinc-100 flex items-center justify-center overflow-hidden">
                            <img src={capturedImage} alt="Captured" className="max-w-full max-h-full object-contain" />
                        </div>
            
                        <div className="p-6 flex gap-4">
                            <button 
                                onClick={handleRetake}
                                className="flex-1 py-4 bg-zinc-100 hover:bg-zinc-200 text-zinc-700 rounded-2xl font-bold transition-all"
                            >
                                다시 찍기
                            </button>
                            <button 
                                onClick={confirmAndScan}
                                className="flex-1 py-4 bg-emerald-500 hover:bg-emerald-600 text-white rounded-2xl font-bold transition-all shadow-lg shadow-emerald-500/30"
                            >
                                이 사진으로 분석
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* 2. 스캔 중 로딩 */}
            {/* --- 2. 사진 분석 중 로딩 오버레이 (게이지 바 적용) --- */}
            {isScanning && (
                <div className="fixed inset-0 z-[1200] flex flex-col items-center justify-center bg-zinc-900/90 backdrop-blur-lg">
                    <div className="w-[400px] flex flex-col items-center gap-8">
                        {/* 상단 아이콘 애니메이션 */}
                        <div className="relative">
                            <div className="w-20 h-20 border-4 border-emerald-500/20 border-t-emerald-500 rounded-full animate-spin"></div>
                            <div className="absolute inset-0 flex items-center justify-center">
                                <ImageIcon width={32} height={32} className="text-emerald-400 animate-pulse" />
                            </div>
                        </div>
            
                        {/* 메시지 */}
                        <div className="text-center space-y-2">
                            <h3 className="text-white text-2xl font-bold font-['Archivo']">Reading your diary...</h3>
                            <p className="text-zinc-400 text-sm">Gemini가 정성스러운 손글씨를 텍스트로 바꾸고 있습니다.</p>
                        </div>
            
                        {/* 게이지 바 컨테이너 */}
                        <div className="w-full h-3 bg-zinc-800 rounded-full overflow-hidden border border-zinc-700 shadow-inner">
                            <div 
                                className="h-full bg-gradient-to-r from-emerald-500 via-teal-400 to-emerald-300 transition-all duration-500 ease-out"
                                style={{ width: `${progress}%` }}
                            />
                        </div>
            
                        {/* 퍼센트 표시 */}
                        <span className="text-emerald-400 font-mono text-lg">{Math.floor(progress)}%</span>
                    </div>
                </div>
            )}

            {/* --- 로딩 오버레이 (isLoading이 true일 때만 표시) --- */}
            {isLoading && (
                <div className="fixed inset-0 z-[1000] flex flex-col items-center justify-center bg-zinc-900/80 backdrop-blur-md">
                    <div className="w-[400px] flex flex-col items-center gap-8">
                        {/* 소울폼 로고 느낌의 아이콘 애니메이션 */}
                        <div className="relative">
                            <div className="w-20 h-20 border-4 border-emerald-500/20 border-t-emerald-500 rounded-full animate-spin"></div>
                            <div className="absolute inset-0 flex items-center justify-center">
                                <TreePine size={32} className="text-emerald-400 animate-pulse" />
                            </div>
                        </div>

                        {/* 진행 메시지 */}
                        <div className="text-center space-y-2">
                            <h3 className="text-white text-2xl font-bold font-['Archivo']">Analyzing your soul...</h3>
                            <p className="text-zinc-400 text-sm">소중한 당신의 기록을 AI가 깊게 읽어보고 있습니다.</p>
                        </div>

                        {/* 게이지 바 컨테이너 */}
                        <div className="w-full h-3 bg-zinc-800 rounded-full overflow-hidden border border-zinc-700 shadow-inner">
                            {/* 실제 움직이는 게이지 부분 */}
                            <div 
                                className="h-full bg-gradient-to-r from-emerald-500 via-teal-400 to-emerald-300 transition-all duration-500 ease-out"
                                style={{ width: `${progress}%` }}
                            />
                        </div>

                        {/* 퍼센트 표시 */}
                        <span className="text-emerald-400 font-mono text-lg">{Math.floor(progress)}%</span>
                    </div>
                </div>
            )}

            {/* 커스텀 우클릭 메뉴 UI */}
            {menu.visible && (
                <div 
                    className="image-control-menu fixed z-[100] bg-zinc-800 text-white shadow-2xl rounded-full px-4 py-2 flex items-center gap-3 transition-all animate-in fade-in zoom-in duration-200"
                    style={{ top: menu.y, left: menu.x }}
                    contentEditable={false}
                >
                    <button onClick={() => alignImage('left')} className="hover:text-blue-400 p-1"><AlignLeft size={18} /></button>
                    <button onClick={() => alignImage('center')} className="hover:text-blue-400 p-1"><AlignCenter size={18} /></button>
                    <button onClick={() => alignImage('right')} className="hover:text-blue-400 p-1"><AlignRight size={18} /></button>
                    
                    <div className="h-4 w-[1px] bg-white/20 mx-1" />
                    
                    {/* 크기 조절 슬라이더 (드래그하여 시각적으로 조절) */}
                    <div className="flex items-center gap-2">
                        <span className="text-[10px] text-white/50">Size</span>
                        <input 
                            type="range" 
                            min="10" max="100" 
                            value={menu.width} 
                            onChange={handleResize}
                            className="w-24 h-1 bg-white/20 rounded-lg appearance-none cursor-pointer accent-blue-500"
                        />
                    </div>

                    <div className="h-4 w-[1px] bg-white/20 mx-1" />
                    <button onClick={deleteImage} className="hover:text-red-400 p-1"><Trash2 size={18} /></button>
                </div>
            )}
            
            
            {/* [이미지 업로드 추가] 숨겨진 파일 입력 input */}
            {/* accept="image/*"는 이미지 파일만 선택 가능하게 제한합니다. */}
            <input 
                type="file" 
                accept="image/*" 
                ref={fileInputRef} 
                onChange={handleImageUpload}
                className="hidden" 
            />
            
            {/*사이드 배너*/}
            {/* [사이드 배너 버튼] */}
            <div 
                onClick={() => setIsNavOpen(true)}
                className="fixed right-0 top-[5vh] w-14 h-16 flex items-center justify-center z-[60] cursor-pointer group"
            >
                <div className="w-14 h-16 bg-zinc-800 rounded-tl-[20px] rounded-bl-[20px] flex items-center justify-center shadow-lg group-hover:w-16 transition-all">
                    <div className="w-9 h-9 flex items-center justify-center">
                        <Edit2 size={30} color="white" />
                    </div>
                </div>
            </div>

            {/* [확장되는 메뉴 박스] */}
            {isNavOpen && (
                <>
                    {/* 배경 오버레이 */}
                    <div 
                        className="fixed inset-0 bg-black/20 backdrop-blur-sm z-[70]" 
                        onClick={() => setIsNavOpen(false)} 
                    />
                    
                    {/* 실제 메뉴창 */}
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

                        {/* 🌟 로그아웃 영역 (경계선 포함) */}
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

            {/*메인*/}
            <div className="w-[95%] h-[680px] relative -translate-x-[27px] flex items-center justify-center
            bg-[linear-gradient(150deg,_rgba(242,224,220,0.37),_rgba(252,227,186,0.37),_rgba(241,219,128,0.37),_rgba(238,202,94,0.37))] 
            rounded-[40px] 
            shadow-[0px_1.1966018676757812px_29.91504669189453px_0px_rgba(251,165,99,0.10)] 
            outline outline-[3px] outline-offset-[-3px] 
            outline-white/50 backdrop-blur-2xl overflow-hidden">
                
                <div className="flex w-[calc(100%-80px)] h-[612px] gap-1 items-start justify-center">
                
                {/* 왼쪽 일기 작성 공간 */}
                <div className="flex-1 h-full bg-neutral-50 rounded-tl-[35px] rounded-bl-[35px] relative p-16">
                    {/* 제목 입력창 */}
                    <input 
                        className="bg-transparent w-full h-[50px] outline-none text-neutral-900 placeholder:text-neutral-900/30 text-3xl font-normal mb-4" 
                        placeholder="Title"
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                    />
                    <div className="w-full h-[2px] bg-neutral-900/10 mb-6" />

                    {/* 에디터 영역: 이전의 hr 관련 호버 스타일은 제거했습니다. */}
                    {/* --- 2. SimpleBar 적용 영역 --- */}
                    <SimpleBar 
                        style={{ height: 'calc(100% - 120px)' }} 
                        autoHide={true}
                        // 라이브러리 내부 스크롤 기능을 활성화하기 위해 필요
                        className="custom-simplebar" 
                    >
                        <div 
                            ref={editorRef}
                            contentEditable
                            suppressContentEditableWarning={true}
                            onInput={() => {}}
                            onClick={handleImageClick}
                            // [중요] 부모인 SimpleBar가 스크롤을 담당하므로 여기서는 overflow-y-auto를 뺍니다.
                            className="w-full h-full outline-none text-neutral-900 text-xl leading-relaxed
                                       empty:before:content-['Whatever_you’re_holding_inside,_you_can_let_it_out.'] 
                                       empty:before:text-neutral-900/30 
                                       empty:before:pointer-events-none
                                       [&_img]:transition-all [&_img]:duration-300
                                       [&_img:hover]:brightness-90 [&_img:hover]:grayscale-[0.5] [&_img:hover]:ring-2 [&_img:hover]:ring-blue-300"
                        />
                    </SimpleBar>
                </div>

                {/* 도구 팔레트 (기존과 동일하지만 이미지 클릭 로직 포함) */}
                <div className="w-[40px] h-full bg-neutral-50 flex flex-col items-center pt-10 gap-4 relative">
                    <button onClick={() => applyStyle('bold')} className="hover:bg-gray-200 p-2 rounded"><FontBoldIcon /></button>
                    <button onClick={() => applyStyle('italic')} className="hover:bg-gray-200 p-2 rounded"><FontItalicIcon /></button>
                    
                    <div className="relative group">
                        <button className="p-2 hover:bg-gray-200 rounded"><PaintBucket size={20} /></button>
                        <input type="color" className="absolute inset-0 opacity-0 cursor-pointer" onChange={(e) => applyStyle('hiliteColor', e.target.value)} />
                    </div>
                    <div className="relative group">
                        <button className="p-2 hover:bg-gray-200 rounded"><Baseline size={20} /></button>
                        <input type="color" className="absolute inset-0 opacity-0 cursor-pointer" onChange={(e) => applyStyle('foreColor', e.target.value)} />
                    </div>

                    <button onClick={insertCustomLine} className="hover:bg-gray-200 p-2 rounded"><SlashIcon /></button>
                    <button onClick={() => applyStyle('underline')} className="hover:bg-gray-200 p-2 rounded"><UnderlineIcon /></button>
                    <button onClick={() => applyStyle('strikeThrough')} className="hover:bg-gray-200 p-2 rounded"><StrikethroughIcon /></button>
                    
                    <button onClick={() => fileInputRef.current.click()} className="hover:bg-gray-200 p-2 rounded"><ImageIcon /></button>
                    
                    <button 
                        onClick={() => setIsSettingsOpen(true)} 
                        className="absolute bottom-5 hover:bg-gray-200 p-2 rounded transition-colors"
                    >
                        <GearIcon />
                    </button>
                </div>

                {/* 오른쪽 카테고리 선택 영역 */}
                <div className="scrollbar-hide w-64 h-[612px] relative z-20 overflow-y-auto overflow-x-hidden flex flex-col gap-1">
                    
                    {/* 1. Today Mood (이미지 버튼화) */}
                    <div className="w-full h-[90px] bg-neutral-50 rounded-tr-[35px] p-3">
                        <div className="text-xl mb-2">Today Mood</div>
                        <div className="flex justify-between gap-1">
                            {['delight', 'happy', 'soso', 'angry', 'sad'].map((m) => (
                                <button 
                                    key={m}
                                    onClick={() => setSelectedMood(m)}
                                    className={`p-1 rounded-md transition-all ${selectedMood === m ? 'bg-amber-200 scale-110 shadow-sm' : 'hover:bg-gray-100'}`}
                                >
                                    <img className="h-7 w-auto" src={`/emotion/${m}.png`} alt={m} />
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* 2. Weather (이미지 버튼화) */}
                    <div className="w-full h-[85px] bg-neutral-50 p-3">
                        <div className="text-xl mb-2">Weather</div>
                        <div className="flex justify-between gap-1">
                            {['sun', 'cloud', 'dark', 'rain', 'snow'].map((w) => (
                                <button 
                                    key={w}
                                    onClick={() => setSelectedWeather(w)}
                                    className={`p-1 rounded-md transition-all ${selectedWeather === w ? 'bg-blue-200 scale-110 shadow-sm' : 'hover:bg-gray-100'}`}
                                >
                                    <img className="h-7 w-auto" src={`/weather/${w}.png`} alt={w} />
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* 3. Calendar (날짜 기록) */}
                    <div className="w-full bg-white flex justify-center p-1">
                        <Calendar 
                            mode="single" 
                            selected={date} 
                            // 선택된 날짜가 있을 때만 상태를 업데이트하도록 방어 코드 추가
                            onSelect={(newDate) => {
                                if (newDate) setDate(newDate);
                            }} 
                            className="scale-90 origin-top" 
                        />
                    </div>

                    {/* 4. Tags 섹션 */}
                    <div className="w-full h-auto bg-neutral-50 p-3">
                        <div className="text-xl mb-2 font-['Archivo']">Tags</div>
                        
                        {/* 기존 태그 목록 (DB에서 가져온 값들) */}
                        <div className="flex flex-wrap gap-2 mb-3">
                            {tags
                            .filter(tag => tag !== 'unsorted') // 🌟 'unsorted' 태그 제외
                            .map((tag, index) => (
                                <button 
                                    key={`${tag}-${index}`}
                                    onClick={() => toggleTagSelection(tag)}
                                    className={`px-2 py-1 rounded-[5px] text-sm transition-colors font-['Archivo'] ${
                                        selectedTags.includes(tag) 
                                            ? 'bg-rose-500 text-white' 
                                            : 'bg-gray-200 text-neutral-600'
                                    }`}
                                >
                                    # {tag}
                                </button>
                            ))}
                        </div>
                        
                        {/* 새 태그 입력 및 추가 버튼 */}
                        <div className="flex items-center bg-gray-100 rounded-[3px] px-2 group">
                            <input 
                                className="bg-transparent text-sm w-full h-8 outline-none font-['Archivo']"
                                placeholder="Add new tag & Press Enter"
                                value={tagInput}
                                onChange={(e) => setTagInput(e.target.value)}
                                onKeyDown={handleTagKeyDown} // 엔터 키 연결
                            />
                            <button 
                                onClick={handleAddTag} // 로컬 추가 함수 연결
                                className="p-1 hover:bg-gray-200 rounded-full transition-colors"
                                title="Add tag"
                            >
                                <Plus size={16} className="text-gray-400 group-hover:text-black" />
                            </button>
                        </div>
                    </div>

                    {/* 5. Buttons */}
                    <div className="flex gap-1 w-full mt-2">
                        {/* 음악 및 이미지 박스 */}
                        {/* 음악 및 이미지 박스 (상태값 적용) */}
                        <div onClick={toggleMusic} className="group w-[50%] h-[65px] relative rounded-[10px] overflow-hidden cursor-pointer bg-black">
                            {/* 유저가 설정한 이미지로 변경 */}
                            {/* 배경 이미지 부분 */}
                            <img 
                                className="w-full h-full object-cover opacity-60" 
                                src={getImageSrc(userSettings.bgImage)} // 🟢 getImageSrc 적용
                                alt="bg" 
                                onError={(e) => { e.target.src = "/static/images/default_bg.jpg"; }} // 깨짐 방지용 기본 이미지
                            />
                            <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                                {isPlaying ? <Pause color="white" fill="white" className="opacity-50" /> : <Play className="opacity-50" color="white" fill="white" />}
                            </div>
                            {/* 유저가 설정한 노래로 변경 */}
                            <audio 
                                ref={audioRef} 
                                key={userSettings.songUrl} // 경로 바뀔 때마다 태그 재로드 강제
                                preload="auto"
                            >
                                <source src={getAudioSrc(userSettings.songUrl)} type="audio/webm" />
                                <source src={getAudioSrc(userSettings.songUrl)} type="audio/mpeg" />
                                Your browser does not support the audio element.
                            </audio>
                        </div>
                        <button 
                            onClick={() => handleSave(true)}
                            className="group flex-1 bg-neutral-400 rounded-[10px] text-white text-sm hover:bg-neutral-500"
                        >
                            Save as draft
                        </button>
                    </div>
                    <button 
                        onClick={() => handleSave(false)}
                        className="group w-full h-[50px] bg-black rounded-[10px] text-white text-xl mt-1 hover:bg-gray-800"
                    >
                        Save Diary
                    </button>
                </div>
            </div>
        </div>
        
        {/* 설정 모달 */}
        {isSettingsOpen && (
            <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/50 backdrop-blur-sm">
                <div className="bg-white w-[450px] p-8 rounded-[30px] shadow-2xl flex flex-col gap-6">
                    <h2 className="text-2xl font-bold flex items-center gap-2">
                        <GearIcon width={24} height={24} /> Settings
                    </h2>
                    
                    <div className="flex flex-col gap-5">
                        {/* 배경 이미지 설정 */}
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">Custom Image</label>
                            <input 
                                type="file" 
                                accept="image/*"
                                onChange={(e) => handleFileChange(e, 'bgImage')}
                                className="text-xs file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:bg-zinc-100 file:text-zinc-700 hover:file:bg-zinc-200 cursor-pointer w-full"
                            />
                        </div>
        
                        {/* 음악 파일 설정 */}
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">Background Music</label>
                            <input 
                                type="file" 
                                accept="audio/*"
                                onChange={(e) => handleFileChange(e, 'songUrl')}
                                className="text-xs file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:bg-zinc-100 file:text-zinc-700 hover:file:bg-zinc-200 cursor-pointer w-full"
                            />
                        </div>
        
                        {/* 🌟 [추가/수정] 태그 관리 섹션 */}
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">Manage All Tags (Click X to Delete from DB)</label>
                            <div className="w-full max-h-32 overflow-y-auto bg-gray-50 rounded-xl p-3 border border-gray-100 flex flex-wrap gap-2 custom-scroll">
                                {/* 🌟 filter 추가: 'unsorted'가 아닌 태그들만 추출 */}
                                {tags.filter(tag => tag !== 'unsorted').length > 0 ? (
                                    tags
                                        .filter(tag => tag !== 'unsorted')
                                        .map((tag) => (
                                            <div 
                                                key={tag} 
                                                className="flex items-center gap-1 bg-white border border-gray-200 px-2 py-1 rounded-md shadow-sm group"
                                            >
                                                <span className="text-xs text-gray-600"># {tag}</span>
                                                <button 
                                                    onClick={() => handleDeleteTag(tag)}
                                                    className="text-gray-400 hover:text-red-500 transition-colors"
                                                    title="Delete Tag"
                                                >
                                                    <X size={12} />
                                                </button>
                                            </div>
                                        ))
                                ) : (
                                    <span className="text-xs text-gray-400">등록된 태그가 없습니다.</span>
                                )}
                            </div>
                        </div>
                        </div>
            
                    <div className="flex gap-3 mt-4">
                        <button 
                            onClick={() => setIsSettingsOpen(false)}
                            className="flex-1 py-3 bg-gray-100 rounded-xl hover:bg-gray-200 transition-colors"
                        >
                            Cancel
                        </button>
                        <button 
                            onClick={() => handleSettingsSave(userSettings)}
                            className="flex-1 py-3 bg-black text-white rounded-xl hover:bg-zinc-800 transition-colors"
                        >
                            Save Changes
                        </button>
                    </div>
                </div>
            </div>
        )}
        </div>
    )
}


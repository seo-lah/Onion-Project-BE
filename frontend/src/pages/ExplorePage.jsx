/* eslint-disable react/prop-types */ // 파일 최상단에 추가
import { Edit2, TreePine, Search, User, HomeIcon, X, List, Bot } from "lucide-react";
import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom'; // 1. useNavigate 추가
import {  useLocation } from 'react-router-dom';
import { LogOut, Trash2 } from "lucide-react";
import api from '../api/axios'
import Swal from 'sweetalert2';


const menuItems = [
    { name: "Home", path: "/", icon: <HomeIcon size={20} /> },
    { name: "Personality Tree", path: "/tree", icon: <TreePine size={20} /> },
    { name: "Write Page", path: "/write", icon: <Edit2 size={20} /> },
    { name: "Explore Page", path: "/explore", icon: <Search size={20} /> },
    { name: "My Report Page", path: "/report", icon: <User size={20} /> },
];


// ----------------------------------------------------------------------
// [1] 일기 개별 카드 컴포넌트 (JournalEntry)
// * 기존 '일기 한장' 템플릿의 스타일과 비율을 완벽하게 유지하면서 재사용 가능하게 분리
// ----------------------------------------------------------------------
const JournalEntry = ({ data, onDeleteSuccess, isChatActive, onSelect, isSelected }) => {
    // 각 일기마다 탭 상태(Standard/Insight)를 독립적으로 가짐
    const [activeTab, setActiveTab] = useState('standard');

    const navigate = useNavigate(); // 이동을 위한 hook

    // 챗봇 활성화 시 클릭 핸들러
    const handleClick = () => {
        if (isChatActive) {
            onSelect(data.id, data.title);
        }
    };

    // 🌟 일기 삭제 함수
    
    const handleDeleteClick = async () => {
            // 1. 삭제 확인 모달 띄우기
            const result = await Swal.fire({
              title: 'Are you sure you want to delete this diary?',
              text: "Deleted diary cannot be recovered! 📋",
              icon: 'warning',
              showCancelButton: true,
              confirmButtonColor: '#d33',     // 삭제 버튼: 빨간색
              cancelButtonColor: '#6D5B98',  // 취소 버튼: 브랜드 컬러
              confirmButtonText: 'Delete',
              cancelButtonText: 'Cancel',
              reverseButtons: true           // 버튼 위치를 OS 표준에 맞게 조정
            });
          
            // 2. 사용자가 '삭제하기'를 클릭했을 때만 실행
            if (result.isConfirmed) {
            try {
                // 🌟 토큰 가져오기
                const response = await api.delete(`/diaries/${data.id}`);

                if (response.status === 200 || response.status === 204){
                    
                    Swal.fire({
                        title: 'Diary deleted.',
                        text: 'Diary deleted successfully.',
                        icon: 'success',
                        confirmButtonText: 'OK',
                        confirmButtonColor: '#6D5B98' // ONION 앱 메인 컬러로 맞추면 더 좋겠죠?
                      });
                    
                    onDeleteSuccess(data.id);
                } else {
                    
                    alert("Delete failed.");
                }
            } catch (error) {
                console.error("Delete Error:", error);
            }
        }
    };

    // 수정 버튼 클릭 시 실행
    const handleEditClick = () => {
        // /write 페이지로 이동하면서 현재 일기의 모든 데이터를 state로 넘깁니다.
        navigate('/write', { 
            state: { 
                isEdit: true, 
                diaryId: data.id,
                existingData: data 
            } 
        });
    };

    return (
        // 피드 내에서 세로로 쌓이기 위해 absolute -> relative로 변경, 간격 추가(mb-12)
        // 내부 요소들의 absolute 배치를 위해 w, h 고정
        <div 
            onClick={handleClick}
            className={`w-[1473px] h-[602px] relative gap-2 overflow-hidden shrink-0 mb-12 transition-all duration-300 rounded-xl
                ${isChatActive ? 'cursor-pointer hover:bg-blue-50/50 hover:shadow-xl' : 'bg-transparent'}
                ${isSelected ? 'ring-4 ring-blue-400 bg-blue-50/30' : ''}
            `}
        >
            
            {/* 왼쪽 글 공간 */}
            {/* 왼쪽 글 공간 */}
            <div className={`w-[1093px] h-[595px] left-[4px] top-[7px] absolute overflow-hidden shadow-sm rounded-sm transition-colors ${isSelected ? 'bg-blue-50' : 'bg-white'}`}>
                <div className="w-[calc(100%-128px)] ml-7 h-24 left-[32px] top-[12px] relative overflow-hidden">
                    <div className="top-[50px] absolute justify-start text-neutral-900 text-4xl font-normal font-['Archivo'] leading-5">
                        {data.title}
                    </div>
                    <div className="w-full h-[1px] top-[93px] absolute bg-neutral-900/30" />
                    
                    {/* 🌟 챗봇 활성화 시 버튼들 비활성화 */}
                    {!isChatActive && (
                        <div className="flex items-center absolute right-[20px] bottom-[28%] gap-2 z-40">
                            {data.is_temporary && (
                                <button onClick={handleEditClick} className="hover:bg-gray-100 p-2 rounded-full"><Edit2 size="20" color="black" /></button>
                            )}
                            <button onClick={handleDeleteClick} className="hover:bg-rose-50 p-2 rounded-full transition-colors group"><Trash2 size="20" className="text-gray-400 group-hover:text-rose-500" /></button>
                        </div>
                    )}
                </div>

                {/* 본문 영역 - 챗봇 활성화 시 클릭 이벤트 전파 방지 */}
                <div 
                    dangerouslySetInnerHTML={{ __html: data.content }} 
                    className={`custom-scroll break-all overflow-y-auto w-[calc(100%-128px)] h-[400px] bottom-[35px] left-[65px] top-[130px] absolute text-black text-xl font-normal font-['Archivo'] leading-7 ${isChatActive ? 'pointer-events-none' : ''}`}
                />
            </div>
            
            
            {/* 중간 경계 바 */}
            <div className="w-[532px] h-0 left-[1098px] z-30 top-[50px] absolute origin-top-left rotate-90 outline outline-1 outline-offset-[-0.50px] outline-black/5"></div>

            {/* 오른쪽 카테고리 공간 */}
            <div className="w-[381px] h-[597px] right-[0px] top-[5px] absolute overflow-hidden">
                {/* 탭 헤더 */}
                <div
                    onClick={() => setActiveTab('standard')}
                    className={`cursor-pointer flex justify-center w-[130px] h-7 items-center left-[2%] top-0 absolute rounded-tl-[10px] rounded-tr-[10px] transition-colors ${activeTab === 'standard' ? 'bg-white z-20' : 'bg-[#E2E1E1] text-[#7C7C7C]'}`}
                >
                    <div className={`text-xl font-normal font-['Archivo'] ${activeTab === 'standard' ? 'text-[#2F2E2C]' : 'text-[#7C7C7C]'}`}>Standard</div>
                </div>
    
                {/* [수정] is_temporary가 false일 때만 Insight 탭 헤더 표시 */}
                {!data.is_temporary && (
                    <div
                        onClick={() => setActiveTab('insight')}
                        className={`cursor-pointer flex justify-center w-[110px] h-7 items-center left-[38%] top-0 absolute rounded-tl-[10px] rounded-tr-[10px] transition-colors ${activeTab === 'insight' ? 'bg-white z-20' : 'bg-[#E2E1E1] text-[#7C7C7C]'}`}
                    >
                        <div className={`text-xl font-normal font-['Archivo'] ${activeTab === 'insight' ? 'text-[#2F2E2C]' : 'text-[#7C7C7C]'}`}>Insight</div>
                    </div>
                )}

                {/* 탭 내용 영역 */}
                {/* 탭 내용 영역 */}
                <div className="overflow-y-auto w-[380px] h-[calc(100%-25.67px)] left-[3.50px] top-[25.67px] absolute bg-white shadow-[-5px_0px_15px_rgba(0,0,0,0.02)]">
                    {activeTab === 'standard' ? (
                        <>
                            {/* --- Standard View --- */}
{/* Today Mood 섹션 */}
<div className="w-full h-[111px] left-[0px] top-[0px] absolute overflow-hidden">
    <div className="left-[15px] top-[25px] absolute text-center justify-start text-black text-2xl font-normal font-['Archivo'] leading-5">Today Mood</div>
    
    <div className="flex left-[17px] top-[55px] h-12 absolute justify-between w-full items-center pr-8">
        {['delight', 'happy', 'soso', 'angry', 'sad'].map(mood => (
            <img key={mood} className={`h-10 w-auto ${data.standard.mood === mood ? 'opacity-100 scale-110' : 'opacity-30'}`} src={`/emotion_new/${mood}.png`} alt={mood} onError={(e) => e.target.style.display='none'} />
        ))}
    </div>
    {/* 📏 가로 경계선: w-[92%] 부분을 수정하여 길이 조절 가능 */}
    <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[92%] h-[1px] bg-gray-300/50" />
</div>

{/* Weather 섹션 */}
<div className="w-full h-[118px] left-[0px] top-[110px] absolute overflow-hidden">
    <div className="left-[15px] top-[25px] absolute text-center justify-start text-black text-2xl font-normal font-['Archivo'] leading-5">Weather</div>
    
    <div className="flex left-[17px] right-[17px] top-[65px] h-12 absolute justify-between w-auto items-center">
        {['sun', 'cloud', 'dark', 'rain', 'snow'].map(weather => (
            <img key={weather} className={`h-10 w-auto ${data.standard.weather === weather ? 'opacity-100 scale-110' : 'opacity-30'}`} src={`/weather/${weather}.png`} alt={weather} onError={(e) => e.target.style.display='none'} />
        ))}
    </div>
    {/* 📏 가로 경계선 */}
    <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[92%] h-[1px] bg-gray-300/50" />
</div>

{/* Timestamp 섹션 */}
<div className="w-full h-[114px] left-[0px] top-[220px] absolute overflow-hidden">
    <div className="left-[15px] top-[25px] absolute text-center text-black text-2xl font-normal font-['Archivo'] leading-5">Timestamp</div>
   
    <div className="flex h-14 items-center justify-between top-[52px] absolute left-[15px] right-[15px]">
        <div className="w-[200px] h-[37px] bg-zinc-300/30 rounded-[10px] flex items-center justify-center">
            <span className="text-black text-2xl font-normal font-['Archivo'] leading-none">{data.standard.date}</span>
        </div>
        <div className="px-4 h-[37px] w-[140px] bg-zinc-300/30 rounded-[10px] flex items-center justify-center">
            <span className="text-black text-2xl font-normal font-['Archivo'] leading-none">{data.standard.time}</span>
        </div>
    </div>
    {/* 📏 가로 경계선 */}
    <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[92%] h-[1px] bg-gray-300/50" />
</div>

{/* Tags 섹션 */}
<div className="w-full h-[110px] left-[0px] top-[calc(220px+105px)] absolute overflow-hidden">
    <div className="left-[15px] top-[25px] absolute text-center text-black text-2xl font-normal font-['Archivo'] leading-5">Tags</div>

    <div className="w-[calc(100%-30px)] flex h-14 items-center left-[15px] right-[15px] top-[52px] relative">
        <div className="flex-1 max-w-[100%] h-11 bg-gray-300/30 rounded-[10px] flex items-center justify-start px-3 gap-2 overflow-x-auto scrollbar-hide">
            {data.standard.tags
                .filter(tag => tag !== 'unsorted') 
                .map((tag, index) => (
                    <div key={index} className="bg-[#BFB0EF] rounded-[5px] w-auto h-[25px] flex items-center justify-center px-2 gap-1 whitespace-nowrap">
                        <span className="text-neutral-600 text-sm font-normal font-['Archivo']">{tag}</span>
                    </div>
                ))
            }
        </div>
    </div>
    
</div>
                        </>
                    ) : (
                        /* --- Insight View (activeTab === 'insight'일 때 실행) --- */
                        <div className="w-full scrollbar-hide min-h-full flex flex-col items-center pt-[12px] relative">
                            <div className="w-80 h-auto flex flex-col items-center gap-6 pb-10">
                                {/* [1] Header */}
                                <div className="w-[340px] h-14 flex items-center justify-center relative shrink-0">
                                    <div className="w-[295px] h-8 left-[38px] top-[17px] absolute bg-gray-200 rounded-tr-[50px] rounded-br-[50px]" />
                                    <img className="w-14 h-12 left-[3px] top-[3px] absolute" src="/2_writepage/face.png" alt="face" />
                                    <div className="left-[57px] top-[24px] absolute text-center text-black text-xl font-normal font-['Archivo'] leading-5">What does this writing reveal?</div>
                                </div>
                                
                                {/* [2] Theme */}
                                <div className="w-80 flex flex-col items-center relative">
                                    <div className="w-full text-left text-black text-2xl font-normal font-['Archivo'] mb-[5px]">Theme</div>
                                    <div className="w-80 h-auto bg-gray-200 flex items-center justify-center rounded-[5px] p-4">
                                        <div className="text-center text-black text-xl font-normal font-['Archivo'] leading-tight break-keep">“{data.insight.theme}”</div>
                                    </div>
                                </div>
                                
                                {/* [3] Traits */}
                                <div className="w-full h-auto flex flex-col items-start">
                                    <div className="w-28 h-8 bg-amber-100 rounded-[5px] flex items-center justify-center relative z-10 mb-3">
                                        <span className="font-['Archivo'] text-orange-600 text-xl font-normal">Your Traits</span>
                                    </div>
                                    <div className="w-80 h-auto mt-[-5px] bg-amber-100 rounded-[5px] px-4 py-4 flex flex-col items-center gap-3">
                                        <div className="font-['Archivo'] break-words text-center font-bold text-xl">{data.insight.traits.title}</div>
                                        <div className="font-['Archivo'] break-words text-center text-base leading-5">{data.insight.traits.desc}</div>
                                        <div className="font-['Archivo'] break-words text-center text-base leading-5">{data.insight.traits.desc2}</div>
                                        <div className="font-['Archivo'] break-words text-center text-base leading-5">{data.insight.traits.desc3}</div>
                                    </div>
                                </div>
                
                                {/* [4] Solutions */}
                                <div className="w-full h-auto flex flex-col items-start">
                                    <div className="w-60 h-8 bg-blue-100 rounded-[5px] flex items-center justify-center relative z-10 mb-3">
                                        <span className="text-blue-500 text-xl font-normal font-['Archivo']">Recommended Solutions</span>
                                    </div>
                                    <div className="w-80 h-auto mt-[-5px] bg-blue-100 rounded-[5px] px-4 py-4 flex flex-col items-center gap-3">
                                        <div className="break-words text-center font-bold text-xl font-['Archivo']">{data.insight.solution.title}</div>
                                        <div className="font-['Archivo'] text-center text-base leading-5 text-black break-words">{data.insight.solution.desc}</div>
                                        <div className="w-full h-auto bg-blue-200/50 rounded-[5px] p-3">
                                            <div className="font-['Archivo'] text-center text-base leading-5 text-black break-words">{data.insight.solution.effect}</div>
                                        </div>
                                    </div>
                                </div>
                
                                {/* [5] Additional Comments */}
                                <div className="w-full h-auto flex flex-col items-start">
                                    <div className="w-[210px] h-8 bg-[#ffbdc8] rounded-[5px] flex items-center justify-center relative z-10 mb-3">
                                        <span className="text-[#ff3059] text-xl font-normal font-['Archivo']">Additional Comments</span>
                                    </div>
                                    <div className="w-80 h-auto mt-[-5px] bg-[#ffbdc8] rounded-[5px] px-4 py-4 flex flex-col items-center">
                                        <div className="font-['Archivo'] text-center text-base leading-5 text-black break-words">{data.insight.comment}</div>
                                    </div>
                                </div>
                
                                {/* [6] Keywords */}
                                <div className="w-full h-auto flex flex-col items-start">
                                    <div className="w-auto h-8 rounded-[5px] flex items-start justify-start relative z-10">
                                        <span className="text-black text-2xl font-normal font-['Archivo']">Keywords Discovery</span>
                                    </div>
                                    <div className="flex flex-wrap w-full gap-2 py-2">
                                        {data.insight.keywords.map((tag) => (
                                            <div key={tag} className="w-auto px-2 py-1 bg-[#FFEE99] rounded-[5px]">
                                                <span className="text-neutral-600 text-sm font-['Archivo'] ">{tag}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};


// ----------------------------------------------------------------------
// [3] 독립형 챗봇 컴포넌트 (성능 최적화를 위해 분리)
// ----------------------------------------------------------------------
const ChatBotWindow = ({ 
    selectedDiaries, toggleDiarySelection, userMessage, setUserMessage, 
    sendMessage, chatHistory, chatCount, isTyping, handleChatClose, scrollRef 
}) => {
    // 내부적으로만 위치 상태를 관리하여 ExplorePage 리렌더링을 방지합니다.
    const [pos, setPos] = useState({ x: window.innerWidth - 450, y: window.innerHeight - 620 });
    const dragging = useRef(false);
    const offset = useRef({ x: 0, y: 0 });

    const onMouseDown = (e) => {
        dragging.current = true;
        // 현재 마우스 위치와 창 위치의 차이 저장
        offset.current = {
            x: e.clientX - pos.x,
            y: e.clientY - pos.y
        };
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    };

    const onMouseMove = (e) => {
        if (!dragging.current) return;
        
        // requestAnimationFrame을 사용하여 브라우저 프레임에 맞춰 부드럽게 이동
        window.requestAnimationFrame(() => {
            setPos({
                x: e.clientX - offset.current.x,
                y: e.clientY - offset.current.y
            });
        });
    };

    const onMouseUp = () => {
        dragging.current = false;
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
    };

    return (
        <div 
            style={{ 
                transform: `translate(${pos.x}px, ${pos.y}px)`,
                left: 0, top: 0, // 기준점을 0,0으로 잡고 transform으로 이동 (성능 최적화)
                
            }}
            className="fixed w-[420px] h-[580px] bg-white/70 backdrop-blur-xl border border-white/40 shadow-2xl rounded-[30px] z-[2000] flex flex-col overflow-hidden animate-in fade-in zoom-in duration-300"
        >
            {/* 헤더 (드래그 핸들) */}
            <div onMouseDown={onMouseDown} className="p-5 bg-zinc-800 cursor-grab active:cursor-grabbing flex justify-between items-center text-white select-none">
                <div className="flex items-center gap-2">
                    <div className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
                    <span className="font-bold">Onion Assistant</span>
                </div>
                <button onClick={handleChatClose} className="hover:rotate-90 transition-transform"><X size={20} /></button>
            </div>

            {/* 채팅 내역 */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto p-5 space-y-4 custom-scroll bg-transparent">
                {chatHistory.length === 0 && (
                    <div className="text-center text-zinc-500 mt-10">
                        <p className="font-bold">Select a diary to analyze!</p>
                        <p className="text-sm mt-2 text-zinc-400">Answers are based on the selected diaries. (Up to 3)</p>
                    </div>
                )}
                {chatHistory.map((msg, i) => (
                    <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[80%] p-4 rounded-2xl text-sm leading-relaxed ${msg.role === 'user' ? 'bg-zinc-800 text-white rounded-tr-none' : 'bg-white/80 shadow-sm rounded-tl-none text-zinc-800'}`}>
                            {msg.content}
                        </div>
                    </div>
                ))}
                {isTyping && <div className="text-[11px] text-zinc-400 animate-pulse ml-1">Onion is reading your diary and thinking...</div>}
            </div>

            {/* 하단 입력창 영역 */}
            <div className="p-4 bg-white/50 border-t border-zinc-200/50">
                <div className="flex flex-wrap gap-2 mb-3">
                    {selectedDiaries.map(diary => (
                        <div key={diary.id} className="flex items-center gap-1 bg-white px-3 py-1 rounded-full border border-zinc-200 shadow-sm">
                            <span className="text-[11px] font-bold text-zinc-700 truncate max-w-[80px]">{diary.title}</span>
                            <button onClick={() => toggleDiarySelection(diary.id)} className="text-zinc-400 hover:text-rose-500"><X size={10} /></button>
                        </div>
                    ))}
                </div>

                <div className="relative flex items-center bg-white rounded-2xl shadow-sm border border-zinc-200 overflow-hidden">
                    <input 
                        type="text" maxLength={50} value={userMessage}
                        onChange={(e) => setUserMessage(e.target.value)}
                        onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                        placeholder={chatCount >= 5 ? "Limit exceeded" : "Ask about your diary (50 chars)"}
                        disabled={chatCount >= 5}
                        className="w-full p-4 outline-none text-sm pr-12"
                    />
                    <button onClick={sendMessage} className="absolute right-2 p-2 bg-zinc-800 text-white rounded-xl hover:bg-black transition-colors"><Edit2 size={16} /></button>
                </div>
                <div className="flex justify-between mt-2 px-1 text-[10px] text-zinc-400 font-mono">
                    <span>QUESTIONS: {chatCount}/5</span>
                    <span>{userMessage.length}/50</span>
                </div>
            </div>
        </div>
    );
};



// ----------------------------------------------------------------------
// [2] 메인 페이지 (ExplorePage)
// ----------------------------------------------------------------------
export default function ExplorePage() {

    const navigate = useNavigate();
    const location = useLocation();
    const [isNavOpen, setIsNavOpen] = useState(false);//*현재 하다만 부분

    const [isChatOpen, setIsChatOpen] = useState(false);
    const [selectedDiaries, setSelectedDiaries] = useState([]); // [{id, title}]
    const [userMessage, setUserMessage] = useState("");
    const [chatHistory, setChatHistory] = useState([]);
    const [chatCount, setChatCount] = useState(0);
    const [isTyping, setIsTyping] = useState(false);
    const token = localStorage.getItem('token');

    const handleEntryDelete = (deletedId) => {
        // 리스트에서 삭제된 ID를 제외한 나머지만 남김
        setJournalList(prevList => prevList.filter(item => item.id !== deletedId));
    };

    const scrollRef = useRef(null);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [chatHistory]);




    // 🌟 로그아웃 함수 추가
    // 🌟 함수 앞에 'async'를 추가하여 비동기 처리를 가능하게 합니다.
    const handleLogout = async () => {
        // 1. Swal을 이용한 세련된 로그아웃 확인창
        const result = await Swal.fire({
            title: 'Log out of your account?',
            text: "You can always come back and write your diary! 🌳",
            icon: 'question',
            showCancelButton: true,
            confirmButtonColor: '#6D5B98', // ONION 메인 컬러
            cancelButtonColor: '#aaa',
            confirmButtonText: 'Log out',
            cancelButtonText: 'Cancel',
            reverseButtons: true            // 버튼 위치를 OS 표준에 맞게 조정
        });
    
        // 2. 사용자가 'Log out'을 클릭한 경우에만 실행
        if (result.isConfirmed) {
            // 로컬 데이터 삭제
            localStorage.removeItem('token');
            localStorage.removeItem('user_id');
            
            // 3. 로그아웃 완료 메시지 (사용자가 확인을 누를 때까지 기다림)
            await Swal.fire({
                title: 'Logged out.',
                text: 'Logged out successfully. ✨',
                icon: 'success',
                confirmButtonText: 'OK',
                confirmButtonColor: '#6D5B98'
            });
            
            // 4. 로그인 페이지로 이동
            navigate('/login');
        }
    };
    // 1. 일기 리스트 데이터 상태
    const [journalList, setJournalList] = useState([]);
    
    // 2. 왼쪽 사이드바(리스트 목록) 활성화 상태
    const [isSidebarOpen, setIsSidebarOpen] = useState(false);

    // 3. 스크롤 이동을 위한 Refs 저장소
    const itemRefs = useRef({});

    // const [chatPos, setChatPos] = useState({ x: window.innerWidth - 450, y: window.innerHeight - 600 });
    // const dragRef = useRef({ startX: 0, startY: 0 });

    // 일기 선택 함수
    const toggleDiarySelection = (id, title) => {
        setSelectedDiaries(prev => {
            const isExist = prev.find(d => d.id === id);
            if (isExist) return prev.filter(d => d.id !== id);
            if (prev.length >= 3) {
                
                Swal.fire({
                    title: 'Warning',
                    text: 'You can select up to 3 diaries.',
                    icon: 'warning',
                    confirmButtonText: 'Cancel',
                    confirmButtonColor: '#6D5B98' // ONION 앱 메인 컬러로 맞추면 더 좋겠죠?
                  });
                return prev;
            }
            return [...prev, { id, title }];
        });
    };

    // 챗봇 닫기 (기록 초기화)
    const handleChatClose = () => {
        setIsChatOpen(false);
        setChatHistory([]);
        setChatCount(0);
        setSelectedDiaries([]);
    };

    // 메시지 전송
    // 메시지 전송 함수
    const sendMessage = async () => {
        if (chatCount >= 5 || selectedDiaries.length === 0 || !userMessage.trim()) {
            if (selectedDiaries.length === 0) {
                Swal.fire({
                    title: 'Warning',
                    text: 'Please select a diary to analyze first!',
                    icon: 'warning',
                    confirmButtonText: 'Cancel',
                    confirmButtonColor: '#6D5B98' // ONION 앱 메인 컬러로 맞추면 더 좋겠죠?
                  });
            };
            
            return;
        }
    
        const currentInput = userMessage;
        const userMsgObj = { role: 'user', content: currentInput };
        const cleanedHistory = chatHistory.map(msg => ({ role: msg.role, content: String(msg.content) }));
    
        setChatHistory(prev => [...prev, userMsgObj]);
        setChatCount(prev => prev + 1);
        setIsTyping(true);
        setUserMessage("");
    
        try {
            const payload = {
                diary_ids: selectedDiaries.map(d => String(d.id)),
                user_message: String(currentInput),
                chat_history: cleanedHistory 
            };
    
            const response = await api.post('/chat/diary', payload, {
                timeout: 50000 
            });
    
            if (response.data && response.data.status === "success") {
                const aiMessages = response.data.messages;
    
                // 🌟 [1. 기호 세척 함수: 문자열 앞뒤의 지저분한 JSON 기호를 제거]
                const cleanText = (str) => {
                    return str
                        .replace(/[[\]{}]/g, '')// 대괄호[배열], 중괄호{객체} 제거
                        .replace(/^[:\s,"]+/, '')        // 시작 부분의 콜론(:), 공백, 쉼표, 따옴표 제거
                        .replace(/["\s,\]}]+$/, '')      // 끝 부분의 따옴표, 공백, 쉼표, 괄호 제거
                        .replace(/\\n/g, '\n')           // 이스케이프된 줄바꿈 복구
                        .trim();
                };
    
                // 🌟 [2. 데이터 형태와 상관없이 문자열 리스트를 뽑아내는 로직]
                const extractTextSafe = (input) => {
                    let results = [];
                    if (typeof input === 'string') {
                        const trimmed = input.trim();
                        if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
                            try {
                                const sanitized = trimmed.replace(/\n/g, "\\n");
                                return extractTextSafe(JSON.parse(sanitized));
                            } catch (e) {
                                console.error("JSON Parsing Error:", e);
                                // 파싱 실패 시 기호 세척만 해서 반환
                                return [cleanText(trimmed)];
                            }
                        }
                        return [cleanText(trimmed)];
                    }
                    
                    if (Array.isArray(input)) {
                        input.forEach(item => {
                            results = [...results, ...extractTextSafe(item)];
                        });
                    } else if (typeof input === 'object' && input !== null) {
                        Object.values(input).forEach(val => {
                            results = [...results, ...extractTextSafe(val)];
                        });
                    }
                    return results;
                };
    
                const rawTexts = extractTextSafe(aiMessages);
                
                // 🌟 [3. 최종 빈 문자열 제거 및 말풍선 생성]
                const newBubbles = rawTexts
                    .filter(text => text.length > 0) // 알맹이가 있는 것만
                    .map(text => ({
                        role: 'assistant',
                        content: text
                    }));
                
                setChatHistory(prev => [...prev, ...newBubbles]);
            }
        } catch (error) {
            console.group("🚀 Chat API Error Detail");
            console.error("Error Code:", error.code);
            console.error("Error Message:", error.message);
            
            if (error.response) {
                console.error("Status:", error.response.status);
                console.error("Data:", error.response.data);
            }
            console.groupEnd();
        
            // 🌟 [핵심 수정] 타임아웃 또는 서버 과부하 에러 처리
            if (error.code === 'ECONNABORTED' || error.response?.status === 429) {
                // 타임아웃(50초 초과)이거나 서버에서 너무 많은 요청(429)을 받았을 때
                Swal.fire({
                    title: 'Notice',
                    text: 'Current AI analysis traffic is very high. Please try again in a few moments. 🌳',
                    icon: 'warning',
                    confirmButtonColor: '#6D5B98',
                    confirmButtonText: 'OK'
                });
            } else {
                // 그 외 일반적인 네트워크 에러 등
                const errorMsg = error.response?.data?.detail || error.message || "Unknown Error";
                Swal.fire({
                    title: 'Error',
                    text: `문제가 발생했습니다: ${errorMsg}`,
                    icon: 'error',
                    confirmButtonColor: '#6D5B98'
                });
            }
        
            // 에러가 발생했으므로 질문 횟수 차감을 취소(복구)합니다.
            setChatCount(prev => prev - 1);
        
        } finally {
            setIsTyping(false);
        }
    };

    const transformData = (backendData) => {
        return backendData.map(item => {
            // 날짜/시간 파싱 (DB에 저장된 포맷에 따라 조정 필요)
            // 예: "2024-01-01" 또는 ISO String 가정
            const dateObj = new Date(item.entry_date || item.created_at); 
            const dateStr = dateObj.toLocaleDateString();
            const timeStr = item.entry_time;
            const formatTime = (time) => {
                if (!time) return "";
                
                // 1. 시, 분, 초 분리
                let [hours, minutes] = time.split(':');
                let h = parseInt(hours, 10);
                
                // 2. AM/PM 결정 및 12시간제 변환
                const ampm = h >= 12 ? 'PM' : 'AM';
                h = h % 12 || 12; // 0시일 경우 12로 표시, 13시일 경우 1로 표시
                
                // 3. 최종 포맷 반환 (분은 그대로 사용)
                return `${ampm} ${h}:${minutes}`;
            };
            
            const formattedEntryTime = formatTime(timeStr);
            const originalContent = item.content || "";

            // AI 분석 데이터가 없는 경우(임시저장 등)를 대비한 기본값
            const analysis = item.analysis || {};
            const recommend = item.recommend || {};
            const method1 = recommend.method1 || {};
            

            return {
                id: item._id, // MongoDB의 _id
                title: item.title || "Untitled", // 제목이 없으므로 날짜로 대체
                content: originalContent,
                is_temporary: item.is_temporary,                
                // Standard 탭 데이터 매핑
                standard: {
                    date: dateStr,
                    time: formattedEntryTime,
                    mood: item.mood || '', // 기본값 설정
                    weather: item.weather || '',
                    tags: item.tags || []
                },

                // Insight 탭 데이터 매핑 (Backend 구조 -> Frontend 구조)
                insight: {
                    // analysis.theme1 (핵심 흐름) -> theme
                    theme: analysis.theme1 || "Analysis in progress or insufficient data.",
                    
                    // analysis.theme2 (핵심 신념) -> traits
                    traits: { 
                        title:  analysis.theme2_title ||"Core Beliefs", 
                        desc: analysis.theme2 || "No analysis information found." ,
                        desc2: analysis.theme3 || "No analysis information found." ,
                        desc3: analysis.theme4 || "No analysis information found." 
                    },

                    // recommend.method1 -> solution
                    solution: { 
                        title: method1.main || "Solution", 
                        desc: method1.content || "No recommended solutions found." ,
                        effect: method1.effect || ""
                    },

                    // one_liner -> comment
                    comment: item.one_liner || "You did a great job today!",
                    
                    // keywords_snapshot -> keywords
                    keywords: item.keywords_snapshot || []
                }
            };
        });
    };

    // 4. 데이터 가져오기 (API 연동)
    // 4. 데이터 가져오기 (API 연동)
    // 🌟 1. 로딩 상태를 명시적으로 관리합니다. (초기값 true)
    const [isLoading, setIsLoading] = useState(true);

    

    useEffect(() => {
        const fetchData = async () => {
            if (!token) {
                navigate('/login');
                return;
            }
            setIsLoading(true); 

            try {
                // 🌟 URL에서 user_id 제거 및 헤더 추가
                const response = await api.get('/diaries')
                

                
                const result = response.data;

                if (result && result.diaries) {
                    const sortedDiaries = [...result.diaries].sort((a, b) => {
                        const dateA = new Date(a.updated_at || `${a.entry_date}T${a.entry_time || '00:00:00'}`);
                        const dateB = new Date(b.updated_at || `${b.entry_date}T${b.entry_time || '00:00:00'}`);
                        return dateB - dateA;
                    });
                    setJournalList(transformData(sortedDiaries));
                }
            } catch (error) {
                console.error("로드 실패:", error);
            } finally {
                setIsLoading(false);
            }
        };
        fetchData();
    }, [token, navigate]);

    // --- 렌더링 조건문 수정 ---
    
    // 🌟 4. "데이터가 없을 때"가 아니라 "로딩 중일 때"만 로딩 화면을 보여줍니다.
    if (isLoading) {
        return <div className="min-h-screen flex items-center justify-center font-bold">Loading data...</div>;
    }

    // 🌟 5. 로딩은 끝났는데 데이터가 0개인 경우 처리
    if (journalList.length === 0) {
        return (
            <div className="w-full h-screen bg-gradient-to-b from-lime-200/40 via-emerald-200/40 to-emerald-300/40 flex flex-col items-center justify-center">
                {/* [사이드 배너 버튼] */}
                <div 
                    onClick={() => setIsNavOpen(true)}
                    className="fixed right-0 top-[5vh] w-14 h-16 flex items-center justify-center z-[60] cursor-pointer group"
                >
                    <div className="w-14 h-16 bg-zinc-800 rounded-tl-[20px] rounded-bl-[20px] flex items-center justify-center shadow-lg group-hover:w-16 transition-all">
                        <div className="w-9 h-9 flex items-center justify-center">
                            <HomeIcon size={30} color="white" />
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
                
                <p className="text-2xl text-neutral-600 font-bold mb-4">No diary entries yet. ✍️</p>
                <button 
                    onClick={() => navigate('/write')}
                    className="px-6 py-3 bg-zinc-800 text-white rounded-2xl hover:bg-black transition-all"
                >
                    Go to write your first diary
                </button>
            </div>
        );
    }

    // 특정 일기 위치로 스크롤 이동하는 함수
    const scrollToId = (id) => {
        const element = itemRefs.current[id];
        if (element) {
            element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    };

    if (journalList.length === 0) return <div className="min-h-screen flex items-center justify-center">Loading...</div>;

    return (
        // 전체 배경 및 레이아웃 컨테이너
        <div className="w-full h-screen bg-gradient-to-b from-lime-200/40 via-emerald-200/40 to-emerald-300/40 m-0 p-0 overflow-hidden relative flex">
            
            {/* [왼쪽 상태창 - 사이드바] */}
            {/* isSidebarOpen 상태에 따라 화면에 나타남 */}
            <div 
                className={`fixed left-0 top-0 h-full bg-white/95 backdrop-blur-md shadow-2xl z-[60] transition-transform duration-300 ease-in-out ${
                    isSidebarOpen ? 'translate-x-0' : '-translate-x-full'
                }`}
                style={{ width: '300px' }}
            >
                <div className="p-6 h-full flex flex-col">
                    <div className="flex justify-between items-center mb-8 border-b pb-4">
                        <h2 className="text-2xl font-bold font-['Archivo'] text-neutral-800">Journal Index</h2>
                        <button onClick={() => setIsSidebarOpen(false)} className="p-2 hover:bg-gray-100 rounded-full transition-colors">
                            <X size={24} color="#555" />
                        </button>
                    </div>
                    
                    {/* 일기 제목 목록 */}
                    <div className="flex-1 overflow-y-auto space-y-3 pr-2 custom-scroll">
                        {journalList.map((journal) => (
                            <div 
                                key={journal.id}
                                onClick={() => {
                                    scrollToId(journal.id); // 클릭 시 해당 위치로 스크롤
                                }}
                                className="cursor-pointer group p-4 rounded-xl hover:bg-emerald-50 transition-all border border-transparent hover:border-emerald-200 bg-white shadow-sm hover:shadow-md"
                            >
                                <div className="text-xs text-emerald-600 font-bold font-['Archivo'] mb-1">{journal.standard.date}</div>
                                <div className="text-base font-medium font-['Archivo'] text-gray-800 group-hover:text-emerald-800 truncate leading-tight">
                                    {journal.title}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* [메인 컨텐츠 영역 - 스크롤 가능] */}
            {/* flex-1로 남은 공간 차지, overflow-y-auto로 세로 스크롤 생성 */}
            <div className="flex-1 h-full overflow-y-auto overflow-x-hidden custom-scroll flex flex-col items-center pt-10 pb-20 relative">
                
                {/* [사이드 배너 버튼] */}
                <div 
                    onClick={() => setIsNavOpen(true)}
                    className="fixed right-0 top-[5vh] w-14 h-16 flex items-center justify-center z-[60] cursor-pointer group"
                >
                    <div className="w-14 h-16 bg-zinc-800 rounded-tl-[20px] rounded-bl-[20px] flex items-center justify-center shadow-lg group-hover:w-16 transition-all">
                        <div className="w-9 h-9 flex items-center justify-center">
                            <Search size={30} color="white" />
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

                {/* [리스트 배너 - List 버튼] */}
                {/* 클릭 시 왼쪽 사이드바(상태창) 오픈 */}
                <div 
                    onClick={() => setIsSidebarOpen(true)}
                    className="fixed right-0 top-[15vh] w-14 h-16 flex items-center justify-end z-50 cursor-pointer hover:w-16 transition-all"
                >
                    <div className="w-12 right-0 h-14 bg-zinc-500 rounded-tl-[20px] rounded-bl-[20px] flex items-center justify-center shadow-lg">
                        <div data-size="30" className="w-9 h-9 overflow-hidden">
                            <List size="35" color="white" />
                        </div>
                    </div>
                </div>

                {/* [일기 피드] */}
                {/* 데이터를 순회하며 JournalEntry 컴포넌트 렌더링 */}
                {journalList.map((journal) => (
                    <div 
                        key={journal.id} 
                        ref={(el) => (itemRefs.current[journal.id] = el)} // DOM 참조 저장 (스크롤 이동용)
                        className="flex justify-center w-full"
                    >
                        <JournalEntry 
                            data={journal} 
                            onDeleteSuccess={handleEntryDelete}
                            isChatActive={isChatOpen} // 🌟 챗봇 오픈 시 선택 모드 활성화
                            onSelect={toggleDiarySelection}
                            isSelected={selectedDiaries.some(d => d.id === journal.id)}
                        />
                    </div>
                ))}

                {/* 🌟 챗봇 오픈 버튼 (우측 하단) */}
                {!isChatOpen && (
                    <button 
                        onClick={() => setIsChatOpen(true)}
                        className="fixed bottom-10 right-10 w-20 h-20 bg-zinc-800 rounded-full flex items-center justify-center shadow-2xl hover:scale-110 transition-transform z-[100]"
                    >
                        <Bot color="white" size={30} />
                        <div className="absolute -top-2 -right-2 bg-emerald-500 text-white text-xs px-2 py-1 rounded-full animate-bounce">AI Chat</div>
                    </button>
                )}
    
                {/* 🌟 드래그 가능한 챗봇 창 */}
                {isChatOpen && (
                    <ChatBotWindow 
                        selectedDiaries={selectedDiaries}
                        toggleDiarySelection={toggleDiarySelection}
                        userMessage={userMessage}
                        setUserMessage={setUserMessage}
                        sendMessage={sendMessage}
                        chatHistory={chatHistory}
                        chatCount={chatCount}
                        isTyping={isTyping}
                        handleChatClose={handleChatClose}
                        scrollRef={scrollRef}
                    />
                )}

                {/* 하단 여백 */}
                <div className="h-20 w-full text-center text-gray-400 font-['Archivo']">Meeting the Inner Self</div>
            </div>
            <style dangerouslySetInnerHTML={{ __html: `
                .diary-divider-wrapper {
                    pointer-events: none !important; /* 클릭/호버 이벤트 완전 차단 */
                    cursor: default !important;     /* 마우스 커서 모양 고정 */
                    background-color: transparent !important; /* 호버 시 배경색 변하는 것 방지 */
                }
                .diary-divider-wrapper line {
                    stroke: #e5e5e5 !important;    /* 선 색상 고정 (파란색으로 변하는 것 방지) */
                }
            `}} />
        </div>
    );
}
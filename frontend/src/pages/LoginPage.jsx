import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { LogIn, UserPlus } from 'lucide-react';
import { useEffect } from 'react';
import api from '../api/axios';
import Swal from 'sweetalert2';

export default function LoginPage() {


    // 모드 전환 상태 (true: 로그인, false: 회원가입)
    const [isLogin, setIsLogin] = useState(true);
    
    // 폼 상태 관리

    const [user_id, setUserId] = useState('');       // 아이디(이메일)
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState(''); // 비번 재확인

    const [error, setError] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const navigate = useNavigate();

    useEffect(() => {
        if (localStorage.getItem('token')) {
            navigate('/'); // 이미 로그인 상태면 홈으로 튕겨내기
        }
    }, [navigate]);

    // const CURRENT_USER_ID = localStorage.getItem('user_id') || "string";

    // 입력값 초기화 함수
    const resetForm = () => {
    
        setUserId('');
        setPassword('');
        setConfirmPassword('');
        setError('');
    };

    // 1. 로그인 제출 핸들러
    const handleLogin = async (e) => {
        e.preventDefault();
        setError('');
        setIsLoading(true);
    
        try {
            // 1. 기존과 동일하게 폼 데이터 생성
            const formData = new URLSearchParams();
            formData.append('grant_type', 'password');
            formData.append('username', user_id);
            formData.append('password', password);
    
            // 2. api 인스턴스 사용
            // Axios는 body 자리에 URLSearchParams를 넣으면 
            // 자동으로 'Content-Type': 'application/x-www-form-urlencoded'를 설정해줍니다.
            const response = await api.post('/login', formData);
    
            // 3. Axios는 이미 JSON 파싱이 끝난 데이터를 response.data에 담고 있습니다.
            const data = response.data;
    
            // Axios는 성공(200~299) 시에만 이 줄로 내려옵니다.
            localStorage.setItem('user_id', data.user_id || user_id);
            if (data.access_token) {
                localStorage.setItem('token', data.access_token);
            }
            
            
            Swal.fire({
                title: 'Welcome back!',
                text: 'Welcome back!',
                icon: 'success',
                confirmButtonText: 'OK',
                confirmButtonColor: '#6D5B98' // ONION 앱 메인 컬러로 맞추면 더 좋겠죠?
              });
            navigate('/');
    
        } catch (err) {
            // 4. 에러 처리 (Axios는 4xx, 5xx 에러 시 바로 catch로 옵니다)
            console.error("Login failed", err);
            
            const errorMessage = err.response?.data?.detail || 'Login failed.';
            setError(errorMessage);
            
            Swal.fire({
                title: 'Error',
                text: errorMessage,
                icon: 'error',
                confirmButtonText: 'OK',
                confirmButtonColor: '#6D5B98' // ONION 앱 메인 컬러로 맞추면 더 좋겠죠?
              });
        } finally {
            setIsLoading(false);
        }
    };

    // 2. 회원가입 제출 핸들러 (DB 연동 코드 추가)
    const handleSignUp = async (e) => {
        e.preventDefault();
        setError('');
    
        if (password !== confirmPassword) {
            setError('Passwords do not match.');
            return;
        }
    
        setIsLoading(true);
    
        try {
            // 🌟 1. api 인스턴스 사용
            // Axios는 객체를 넣으면 자동으로 JSON으로 변환하고 Content-Type도 잡아줍니다.
            await api.post('/signup', { 
                user_id: user_id, 
                password: password 
            });
    
            // 🌟 2. Axios는 성공 시(2xx) 바로 다음 줄로 넘어옵니다.
            // response.ok 체크 없이 바로 성공 로직을 작성하세요.
            
            Swal.fire({
                title: 'Signup completed!',
                text: 'Signup completed! Please login.',
                icon: 'success',
                confirmButtonText: 'OK',
                confirmButtonColor: '#6D5B98' // ONION 앱 메인 컬러로 맞추면 더 좋겠죠?
              });

            setIsLogin(true);
            resetForm();
    
        } catch (err) {
            // 🌟 3. 에러 처리 (4xx, 5xx 에러는 모두 catch에서 잡힙니다)
            console.error("Signup failed", err);
            
            // 서버가 보내준 구체적인 에러 메시지(data.detail)를 화면에 표시
            const errorMessage = err.response?.data?.detail || 'This ID is already taken, or sign-up failed.';
            setError(errorMessage);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <section className="bg-gray-50 dark:bg-gray-900 font-['Archivo'] transition-all duration-500">
            <div className="flex flex-col items-center justify-center px-6 py-8 mx-auto md:h-screen lg:py-0">
                
                {/* 상단 로고 */}
                <Link to="/" className="flex items-center mb-6 text-2xl font-semibold text-gray-900 dark:text-white">
                    <div className="w-10 h-10 bg-black rounded-xl flex items-center justify-center mr-3">
                        {isLogin ? <LogIn size={24} color="white" /> : <UserPlus size={24} color="white" />}
                    </div>
                    Onion Diary
                </Link>

                <div className="w-full bg-white rounded-[40px] shadow-2xl dark:border md:mt-0 sm:max-w-md xl:p-0 dark:bg-gray-800 dark:border-gray-700 overflow-hidden">
                    <div className="p-8 space-y-6">
                        <h1 className="text-2xl font-bold leading-tight tracking-tight text-gray-900 md:text-3xl dark:text-white text-center">
                            {isLogin ? 'Sign in' : 'Create Account'}
                        </h1>
                        
                        <form className="space-y-4" onSubmit={isLogin ? handleLogin : handleSignUp}>
                            
                            

                            {/* 공통 아이디 필드 */}
                            <div>
                                <label className="block mb-2 text-sm font-medium text-gray-900 dark:text-white">User ID</label>
                                <input 
                                    type="text" 
                                    placeholder="your user id" 
                                    value={user_id}
                                    onChange={(e) => setUserId(e.target.value)}
                                    className="bg-gray-50 border border-gray-300 text-gray-900 rounded-xl focus:ring-black focus:border-black block w-full p-3 dark:bg-gray-700 dark:text-white" 
                                    required 
                                />
                            </div>

                            {/* 공통 비밀번호 필드 */}
                            <div>
                                <label className="block mb-2 text-sm font-medium text-gray-900 dark:text-white">Password</label>
                                <input
                                    type="password"
                                    placeholder="••••••••"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    className="bg-gray-50 border border-gray-300 text-gray-900 rounded-xl focus:ring-black focus:border-black block w-full p-3 dark:bg-gray-700 dark:text-white"
                                    required
                                />
                            </div>

                            {/* 회원가입 시에만 나타나는 비밀번호 재확인 필드 */}
                            {!isLogin && (
                                <div>
                                    <label className="block mb-2 text-sm font-medium text-gray-900 dark:text-white">Confirm Password</label>
                                    <input
                                        type="password"
                                        placeholder="••••••••"
                                        value={confirmPassword}
                                        onChange={(e) => setConfirmPassword(e.target.value)}
                                        className="bg-gray-50 border border-gray-300 text-gray-900 rounded-xl focus:ring-black focus:border-black block w-full p-3 dark:bg-gray-700 dark:text-white"
                                        required
                                    />
                                </div>
                            )}

                            {/* 제출 버튼 */}
                            <button 
                                type="submit" 
                                disabled={isLoading}
                                className={`w-full text-white bg-black hover:bg-zinc-800 font-bold rounded-2xl text-md px-5 py-4 text-center transition-all shadow-lg mt-4 ${
                                    isLoading ? 'opacity-50 cursor-not-allowed' : ''
                                }`}
                            >
                                {isLoading ? 'Processing...' : (isLogin ? 'Login' : 'Join Now')}
                            </button>

                            {/* 탭 전환 버튼 */}
                            <div className="text-center mt-4">
                                <button 
                                    type="button"
                                    onClick={() => { setIsLogin(!isLogin); resetForm(); }}
                                    className="text-sm font-medium text-gray-600 hover:text-black hover:underline dark:text-gray-400"
                                >
                                    {isLogin ? "Don't have an account? Sign up" : "Already have an account? Sign in"}
                                </button>
                            </div>
                        </form>

                        {/* 에러 메시지 */}
                        {error && (
                            <div className="p-3 text-sm text-center text-red-700 bg-red-100 rounded-xl animate-bounce" role="alert">
                                {error}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </section>
    );
}
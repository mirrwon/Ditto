import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { register, updateProfile } from "../../services/authService";
import JoinRegister from "../../components/auth/JoinRegister";
import "./Register.css";
import { storeUser } from "../../services/session";

const Register = () => {
  const nav = useNavigate();
  const location = useLocation();
  const params = new URLSearchParams(location.search);
  const isOauth = params.get("oauth") === "google";

  //서버 에러 메시지(회원가입 실패 등)
  const [error, setError] = useState("");

  const handleRegister = async (payload) => {
    try {
      setError("");

      // ⚠️ 아직 백엔드 확정 전이라면:
      // - profileImage 업로드 방식(FormData)이 필요할 수 있음.
      // - 일단은 payload 그대로 보내고,
      // - 백엔드가 파일 업로드를 받는 순간 FormData로 바꾸면 됨.     
      const response = isOauth ? await updateProfile(payload) : await register(payload);

      if (isOauth) {
        storeUser(response.data);
        window.location.replace("/");
        return;
      }

      //성공 → 로그인 이동
      nav("/login");
    } catch (err) {
      setError(err.response?.data?.message || "회원가입 실패(백엔드 미연결)");

       //실패해도 로그인으로 이동(프론트 테스트용)
      nav("/login", { replace: true });

    }
  };

  const goLogin = () => {
    nav("/login");
  };

  return (
    <div className="register-page">
      {/* 회원가입 폼 */}
      <JoinRegister onSubmit={handleRegister} />

      {/* 서버 에러 표시 */}
      {error && <p className="register-error">{error}</p>}

    </div>
  );
};

export default Register;

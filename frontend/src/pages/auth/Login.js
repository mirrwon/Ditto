import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login } from '../../services/authService';
import { storeUser } from '../../services/session';
import JoinLogin from '../../components/auth/JoinLogin';
import Button from '../../components/common/Button';
import './Login.css';

const Login = ({ setUser }) => {
  const nav = useNavigate();

  const goHome = () => nav('/');

  const [error, setError] = useState('');

  const handleLogin = async (formData) => {
    try {
      setError('');
      const res = await login(formData);
      storeUser(res.data);
      setUser(res.data);
      nav('/');
    } catch (err) {
      setError('아이디 또는 비밀번호가 올바르지 않습니다.');
    }
  };

  const goRegister = () => nav('/register');

  return (
    <div className="login-page">
      <div className="login-header">
        <div
          className="typo-title typo-xl login-brand"
          onClick={goHome}
          style={{ cursor: 'pointer' }}
        >
          Ditto
        </div>
        <div className="ui-line login-top-line" />
      </div>

      <div className="login-mid">
        <div className="login-mid-line" />
        <div className="login-mid-title">Login</div>
        <div className="login-mid-line" />
      </div>


      <div className="login-form-wrap">
        <JoinLogin onSubmit={handleLogin} />
        {error && <p className="login-error">{error}</p>}
      </div>

      <div className="login-actions">
        <Button text="회원가입" type="primary" onClick={goRegister} />
      </div>
    </div>
  );
};

export default Login;

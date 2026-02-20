import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Button from '../components/common/Button';
import { ROUTES } from '../constants/routes';
import { updateProfile } from '../services/authService';
import { readStoredUser, storeUser } from '../services/session';
import './MyinfoEdit.css';

const withCacheBust = (url, cacheBust) => {
  if (!url) return '';
  if (!cacheBust) return url;
  const sep = url.includes('?') ? '&' : '?';
  return `${url}${sep}v=${cacheBust}`;
};

const formatPhoneNumber = (value) => {
  const digits = value.replace(/\D/g, '').slice(0, 11);
  if (digits.length <= 3) return digits;
  if (digits.length <= 7) return `${digits.slice(0, 3)}-${digits.slice(3)}`;
  return `${digits.slice(0, 3)}-${digits.slice(3, 7)}-${digits.slice(7)}`;
};

const MyinfoEdit = ({ user, setUser }) => {
  const nav = useNavigate();

  const storedUser = useMemo(() => {
    return readStoredUser();
  }, []);

  const effectiveUser = storedUser || user;
  const isOauthUser = useMemo(() => {
    return effectiveUser?.provider === 'google' || Boolean(effectiveUser?.oauth_sub);
  }, [effectiveUser]);

  const initialMyinfo = useMemo(
    () => ({
      profileImageUrl: effectiveUser?.profileImageUrl || '',
      username: effectiveUser?.user_name || effectiveUser?.username || '',
      password: '',
      name: effectiveUser?.name || '혜원',
      gender: effectiveUser?.gender || 'female',
      birthDate: effectiveUser?.birthDate || '',
      phone: effectiveUser?.phone || '010-1234-5678',
      email: effectiveUser?.email || 'onlywon@gmail.com',
      zipcode: effectiveUser?.zipcode || '',
      address1: effectiveUser?.address1 || '',
      address2: effectiveUser?.address2 || '',
    }),
    [effectiveUser]
  );

  const [myinfo, setMyinfo] = useState(initialMyinfo);
  const [profileImageFile, setProfileImageFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    setMyinfo(initialMyinfo);
  }, [initialMyinfo]);

  useEffect(() => {
    if (!profileImageFile) {
      setPreviewUrl('');
      return;
    }
    const url = URL.createObjectURL(profileImageFile);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [profileImageFile]);

  const handleChangeMyinfo = (e) => {
    const { name, value } = e.target;
    const nextValue = name === 'phone' ? formatPhoneNumber(value) : value;
    setMyinfo((prev) => ({ ...prev, [name]: nextValue }));
  };

  const handleChangeProfileImage = (e) => {
    const file = e.target.files?.[0] ?? null;
    setProfileImageFile(file);
    setError('');
  };

  const handleAddressSearch = () => {
    if (!window.daum || !window.daum.Postcode) {
      setError('Address search is unavailable.');
      return;
    }

    new window.daum.Postcode({
      oncomplete: (data) => {
        const address =
          data.roadAddress || data.jibunAddress || data.address || '';
        setMyinfo((prev) => ({
          ...prev,
          zipcode: data.zonecode || '',
          address1: address,
        }));
        setError('');
      },
    }).open();
  };

  const goMyinfo = (e) => {
    if (e) e.preventDefault();
    nav(ROUTES.MYINFO);
  };

  const handleSubmitMyinfoEdit = async (e) => {
    e.preventDefault();
    setError('');

    try {
      const payload = {
        password: isOauthUser ? undefined : myinfo.password || undefined,
        name: myinfo.name,
        gender: myinfo.gender,
        birthDate: myinfo.birthDate,
        phone: myinfo.phone,
        email: myinfo.email,
        zipcode: myinfo.zipcode,
        address1: myinfo.address1,
        address2: myinfo.address2,
        profileImage: profileImageFile || undefined,
      };

      const res = await updateProfile(payload);
      const cacheBust = Date.now();
      const nextUser = {
        ...res.data,
        profileImageCacheBust: cacheBust,
      };

      storeUser(nextUser);
      if (setUser) setUser(nextUser);

      nav(ROUTES.MYINFO);
    } catch (err) {
      setError('프로필 수정에 실패했습니다.');
    }
  };

  const imageSrc =
    previewUrl ||
    withCacheBust(myinfo.profileImageUrl, effectiveUser?.profileImageCacheBust);

  return (
    <div className="l-cover">
      <div className="l-cover-center">
        <h1 className="myinfoedit-title">My Info Edit</h1>
        <div className="ui-line myinfoedit-divider" />

        {/* ✅ 핵심: form 래퍼 클래스 */}
        <form className="myinfoedit-form" onSubmit={handleSubmitMyinfoEdit}>
          {/* ================= 프로필 사진 ================= */}
          <section className="myinfoedit-section">
            <div className="myinfoedit-photoRow">
              <div className="myinfoedit-photoBox">
                {imageSrc ? (
                  <img
                    src={imageSrc}
                    alt="내 정보 사진"
                    className="myinfoedit-photoImg"
                  />
                ) : (
                  <div className="myinfoedit-photoEmpty">사진</div>
                )}
              </div>

              <input
                id="profileImage"
                type="file"
                accept="image/*"
                onChange={handleChangeProfileImage}
                className="myinfoedit-fileInput"
              />

              {/* ✅ ui-btn 사용 */}
              <label
                htmlFor="profileImage"
                className="ui-btn ui-btn-primary myinfoedit-fileBtn"
              >
                프로필 사진 수정
              </label>

              {profileImageFile && (
                <p className="myinfoedit-fileName">
                  선택된 파일: {profileImageFile.name}
                </p>
              )}
            </div>
          </section>

          {/* ================= 기본 정보 ================= */}
          <section className="myinfoedit-section">
            <label className="myinfoedit-label" htmlFor="myinfo-username">
              아이디
            </label>
            <input
              id="myinfo-username"
              name="username"
              type="text"
              value={myinfo.username}
              readOnly
              className="ui-input myinfoedit-readonly"
            />
            <p className="myinfoedit-help">아이디는 수정할 수 없어요.</p>

            <label className="myinfoedit-label" htmlFor="myinfo-password">
              비밀번호
            </label>
            <input
              id="myinfo-password"
              name="password"
              type="password"
              value={myinfo.password}
              onChange={handleChangeMyinfo}
              placeholder="비밀번호 변경 (원할 때만 입력)"
              autoComplete="new-password"
              className="ui-input"
              disabled={isOauthUser}
            />
            {isOauthUser && (
              <p className="myinfoedit-help">
                구글 회원은 비밀번호를 변경할 수 없어요.
              </p>
            )}

            <label className="myinfoedit-label" htmlFor="myinfo-name">
              이름
            </label>
            <input
              id="myinfo-name"
              name="name"
              type="text"
              value={myinfo.name}
              onChange={handleChangeMyinfo}
              placeholder="이름"
              className="ui-input"
            />

            <label className="myinfoedit-label" htmlFor="myinfo-gender">
              성별
            </label>
            <select
              id="myinfo-gender"
              name="gender"
              value={myinfo.gender}
              onChange={handleChangeMyinfo}
              className="ui-input"
            >
              <option value="male">남성</option>
              <option value="female">여성</option>
            </select>

            <label className="myinfoedit-label" htmlFor="myinfo-birthdate">
              생년월일
            </label>
            <input
              id="myinfo-birthdate"
              name="birthDate"
              type="date"
              value={myinfo.birthDate}
              onChange={handleChangeMyinfo}
              min="1900-01-01"
              max="2099-12-31"
              className="ui-input"
            />

            <label className="myinfoedit-label" htmlFor="myinfo-phone">
              전화번호
            </label>
            <input
              id="myinfo-phone"
              name="phone"
              type="tel"
              value={myinfo.phone}
              onChange={handleChangeMyinfo}
              placeholder="010-0000-0000"
              inputMode="numeric"
              maxLength={13}
              className="ui-input"
            />

            <label className="myinfoedit-label" htmlFor="myinfo-email">
              이메일
            </label>
            <input
              id="myinfo-email"
              name="email"
              type="email"
              value={myinfo.email}
              onChange={handleChangeMyinfo}
              placeholder="email@example.com"
              className="ui-input"
            />

            <label className="myinfoedit-label" htmlFor="myinfo-zipcode">
              우편번호
            </label>
            <div className="address-row">
              <input
                id="myinfo-zipcode"
                name="zipcode"
                type="text"
                value={myinfo.zipcode}
                onChange={handleChangeMyinfo}
                placeholder="우편번호"
                className="ui-input"
                readOnly
              />
              <button
                type="button"
                onClick={handleAddressSearch}
                className="ui-btn ui-btn-primary ui-btn--compact address-search"
              >
                주소 검색
              </button>
            </div>

            <label className="myinfoedit-label" htmlFor="myinfo-address1">
              주소
            </label>
            <input
              id="myinfo-address1"
              name="address1"
              type="text"
              value={myinfo.address1}
              onChange={handleChangeMyinfo}
              placeholder="기본 주소"
              className="ui-input"
            />

            <label className="myinfoedit-label" htmlFor="myinfo-address2">
              상세 주소
            </label>
            <input
              id="myinfo-address2"
              name="address2"
              type="text"
              value={myinfo.address2}
              onChange={handleChangeMyinfo}
              placeholder="상세 주소"
              className="ui-input"
            />
          </section>

          {/* ================= 버튼 ================= */}
          <div className="myinfoedit-actions">
            <Button text="취소" type="secondary" onClick={goMyinfo} />
            <button
              type="submit"
              className="ui-btn ui-btn-primary"
            >
              수정
            </button>
          </div>

          {error && <p className="error-message">{error}</p>}
        </form>
      </div>
    </div>
  );
};

export default MyinfoEdit;

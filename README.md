# Ditto (메타몽)

> AI 기반 반려식물 케어 서비스

내 방 사진 한 장으로 최적의 식물 배치를 추천받고, 식물을 다마고치 캐릭터로 키우는 플랫폼입니다.

---

## 서비스 소개

**Ditto**는 AI를 활용해 식물을 더 잘 키울 수 있도록 도와주는 반려식물 케어 플랫폼입니다.

- 실내 사진을 업로드하면 AI가 빛·공간·동선을 분석해 식물 배치 위치를 추천
- 물 주기, 비료, 분무 등 케어 활동을 타임로그로 기록
- 내 방이 레트로 픽셀 아트로 변환되고, 식물이 다마고치 캐릭터로 말을 걸어옴
- LoRA 파인튜닝된 Gemma-2-9B 모델이 식물 감정·대사·애니메이션을 실시간 생성

---

## 주요 기능

### 1. AI 식물 배치 추천 (챗봇)
- 실내 사진 업로드 → SAM + MiDaS + PnP 파이프라인으로 3D 공간 분석
- GPT-4o 기반 대화형 인터페이스로 식물 추천 및 케어 조언
- 채광, 동선, 가구 배치를 고려한 최적 위치 오버레이 시각화

### 2. 플랜트보드 (PlantBoard)
- **타임로그**: 물 주기, 비료, 자리 이동, 분무, 청소 등 케어 활동 기록
- **다이어리**: 식물과의 일상을 사진과 글로 기록
- **사진 꾸미기**: 식물 사진에 스티커·템플릿을 입혀 꾸미기

### 3. 다마고치 뷰 (Tamagotchi View)
- 내 방 사진을 **Gemini AI**로 1990년대 다마고치 스타일 픽셀 아트로 변환
- **Gemma-2-9B + LoRA** 파인튜닝 모델이 식물 캐릭터의 대사·감정·애니메이션 생성
- 물 부족, 비료 필요 등 케어 상태에 따라 캐릭터 반응이 달라짐

### 4. 식물 데이터 & 지도
- 식물 종류별 케어 정보 제공
- 주변 화원 카카오 지도 검색

---

## 기술 스택

### Backend
| 분류 | 기술 |
|------|------|
| API 서버 | FastAPI, Python 3.11 |
| AI - 이미지 생성 | Gemini 3 Pro Image (픽셀 아트 변환) |
| AI - 식물 추천 | GPT-4o |
| AI - 식물 대화 | Gemma-2-9B + LoRA (PEFT) |
| AI - 공간 분석 | SAM (Segment Anything), MiDaS, OpenCV |
| DB | MySQL (AWS RDS), Redis (RedisLabs) |
| 파일 스토리지 | AWS S3 |

### Frontend
| 분류 | 기술 |
|------|------|
| 프레임워크 | React 18 |
| 상태 관리 | React Hooks (useState, useEffect, custom hooks) |
| 스타일 | CSS Modules |
| 지도 | Kakao Maps API |

### Infra
| 분류 | 기술 |
|------|------|
| API 서버 | AWS EC2 |
| GPU 서버 (LoRA) | AWS EC2 (GPU 인스턴스) |
| 컨테이너 | Docker |

---

## 브랜치 구조

```
develop         ← 기준 브랜치
├── feature/app     ← 백엔드(FastAPI) + 프론트엔드(React) 전체 코드
└── feature/lora    ← Gemma-2-9B LoRA 학습/추론 서버 코드
```

---

## 실행 방법

### 1. Backend (API 서버)

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # 아래 환경변수 항목 참고하여 API 키 입력
uvicorn api_server:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm start
```

### 3. LoRA 추론 서버 (GPU 서버)

```bash
cd backend
pip install -r requirements-lora.txt
python serve_lora.py --adapter_dir ./lora_adapter --port 8001
```

> LoRA 어댑터 파일(`lora_adapter/`)은 별도로 학습하거나 공유된 파일을 사용하세요.

---

## 환경변수 (.env)

`.env` 파일을 `backend/` 디렉토리에 생성하여 아래 값을 입력하세요.

```env
# Gemini AI (픽셀 아트 생성)
GEMINI_API_KEY=

# OpenAI (식물 추천 챗봇)
OPENAI_API_KEY=

# AWS S3 (이미지 저장)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=
S3_BUCKET=

# MySQL (AWS RDS)
MYSQL_HOST=
MYSQL_PORT=3306
MYSQL_USER=
MYSQL_PASSWORD=
MYSQL_DB=

# Redis
REDIS_HOST=
REDIS_PORT=
REDIS_PASSWORD=

# LoRA 서버 주소 (GPU EC2 IP)
LORA_SERVER_URL=http://localhost:8001
LORA_TIMEOUT_SEC=15

# Google OAuth (소셜 로그인)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback
FRONTEND_OAUTH_REDIRECT=http://localhost:3000/login

# Kakao 지도
REST_API_KEY=

# JWT 시크릿
SECRET_KEY=
```

---

## 프로젝트 구조

```
ditto/
├── backend/
│   ├── api_server.py           # 메인 FastAPI 서버
│   ├── serve_lora.py           # LoRA 추론 서버 (GPU 서버용)
│   ├── train_lora.py           # LoRA 학습 스크립트
│   ├── requirements.txt        # API 서버 의존성
│   ├── requirements-lora.txt   # LoRA 서버 의존성
│   └── app/
│       ├── api/                # API 라우터 (채팅, 플랜트보드, 타마고치 등)
│       ├── cv/                 # 컴퓨터 비전 파이프라인 (SAM, MiDaS, PnP)
│       ├── llm/                # AI 모델 연동 (Gemini, GPT)
│       ├── services/           # 비즈니스 로직
│       └── db/                 # DB 클라이언트 (MySQL, Redis, S3)
└── frontend/
    └── src/
        ├── pages/              # 페이지 컴포넌트
        ├── components/         # 공통 컴포넌트 (채팅, 타임로그, 다이어리 등)
        ├── hooks/              # 커스텀 훅
        └── services/           # API 호출 모듈
```

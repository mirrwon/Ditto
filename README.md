# 메타몽 (Metamong)

AI 기반 반려식물 케어 서비스

---

## 서비스 소개

메타몽은 AI를 활용해 식물을 더 잘 키울 수 있도록 도와주는 반려식물 케어 플랫폼입니다.
식물 배치 추천부터 일상 기록, 다마고치 스타일의 식물 캐릭터까지 하나의 서비스에서 제공합니다.

---

## 주요 기능

### 1. AI 식물 배치 추천 (챗봇)
- 실내 사진을 업로드하면 AI가 최적의 식물 배치 위치를 분석
- GPT-4o 기반 대화형 인터페이스로 식물 추천 및 케어 조언 제공
- CV 파이프라인(SAM, MiDaS, PnP)으로 실내 공간을 3D 분석

### 2. 플랜트보드 (PlantBoard)
- **타임로그**: 물 주기, 비료, 자리 이동, 분무, 청소 등 식물 케어 활동 기록
- **다이어리**: 식물과의 일상을 사진과 글로 기록
- **사진 꾸미기**: 식물 사진에 스티커/템플릿을 입혀 꾸미기

### 3. 다마고치 뷰 (Tamagotchi View)
- 내 방 사진을 **Gemini AI**로 1990년대 다마고치 스타일 픽셀 아트로 변환
- LoRA 파인튜닝된 Gemma-2-9B 모델이 식물 캐릭터의 대사/감정/애니메이션 생성
- 식물이 살아있는 캐릭터처럼 말을 걸고 반응

### 4. 식물 데이터
- 식물 종류별 케어 정보 제공
- 주변 화원 지도 검색

---

## 기술 스택

### Backend
| 분류 | 기술 |
|------|------|
| API 서버 | FastAPI, Python 3.11 |
| AI - 이미지 분석 | GPT-4o, Gemini 3 Pro Image |
| AI - 식물 대화 | Gemma-2-9B + LoRA (PEFT) |
| AI - 공간 분석 | SAM (Segment Anything), MiDaS, OpenCV |
| DB | MySQL (AWS RDS), Redis (RedisLabs) |
| 파일 스토리지 | AWS S3 |

### Frontend
| 분류 | 기술 |
|------|------|
| 프레임워크 | React |
| 상태 관리 | React Hooks |
| 스타일 | CSS Modules |

### Infra
- AWS EC2 (API 서버, GPU 서버)
- Docker

---

## 실행 방법

### Backend
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env  # API 키 설정
uvicorn api_server:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm start
```

### LoRA 서버 (GPU 서버)
```bash
cd backend
python serve_lora.py --adapter_dir ./lora_adapter --port 8000
```

---

## 환경변수 (.env)

```
# Gemini AI
GEMINI_API_KEY=

# OpenAI
OPENAI_API_KEY=

# AWS S3
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=
S3_BUCKET=

# MySQL
MYSQL_HOST=
MYSQL_USER=
MYSQL_PASSWORD=
MYSQL_DB=

# Redis
REDIS_HOST=
REDIS_PORT=
REDIS_PASSWORD=

# LoRA 서버
LORA_SERVER_URL=http://localhost:8001
LORA_TIMEOUT_SEC=15

# Google OAuth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
```

---

## 프로젝트 구조

```
metamong/
├── backend/
│   ├── api_server.py          # 메인 FastAPI 서버
│   ├── serve_lora.py          # LoRA 추론 서버
│   ├── app/
│   │   ├── api/               # API 라우터
│   │   ├── services/          # 비즈니스 로직
│   │   ├── cv/                # 컴퓨터 비전 파이프라인
│   │   ├── llm/               # AI 모델 연동
│   │   └── db/                # DB 클라이언트
│   ├── plantboard_store/      # 플랜트보드 로컬 데이터
│   └── plants/                # 식물 이미지 저장소
└── frontend/
    └── src/
        ├── pages/             # 페이지 컴포넌트
        ├── components/        # 공통 컴포넌트
        ├── hooks/             # 커스텀 훅
        └── services/          # API 호출
```

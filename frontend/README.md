# final_project_metamong

---

## 0) 딱 2가지만 기억하기
- **main** = 최종본(완성된 것만 있음) ✅  
- **develop** = 작업 모으는 곳(여기로 PR 올림) ✅

---

## 1) 절대 규칙 3가지 
1) **main에는 직접 올리지 않기** (직접 push 금지)
2) **작업은 feature/(개인 branch명)에서 하기**
3) **PR(풀리퀘스트)은 develop로 올리기**

---

## 2) 작업 흐름 
1) 내가 할 일을 정한다 (가능하면 Issues에 적기)
2) **feature branch**를 만든다  
   - 예: `feature/login`, `feature/signup-ui`
3) feature 브랜치에서 작업하고 커밋한다
4) GitHub에서 **PR을 develop로** 올린다
5) 팀원이 확인하고 OK하면 develop에 합친다(merge)
6) develop이 안정적이면 **develop → main**으로 PR해서 최종 반영한다(관리자/합의 후)

---

## 3) 브랜치 이름 예시
- `feature/dowon_kg`
- `feature/dowon_db`

---

## 4) 커밋 메시지 예시
- `기능: 로그인 화면 추가`
- `버그: 버튼 오류 수정`
- `설명: README 수정`
- `설정: 설정 파일 정리`

---

## 5) PR(풀리퀘스트) 올릴 때 체크
PR 올릴 때 아래 2개만 지켜줘요:
- "내가 한 일" 한 줄로 적기
- 최소 1번은 실행해보기(에러 안 나는지)
- 화면 바뀌면 스크린샷 있으면 좋아요(가능하면)

---

## 6) GitHub 웹에서 PR 올리는 방법(클릭 순서)
### (A) 먼저 feature 브랜치 만들기
1) 레포 들어가기
2) 왼쪽 위에 브랜치 표시(`main` 또는 `develop`) 눌러서 드롭다운 열기
3) 브랜치 이름에 `feature/내작업이름` 입력
4) 아래에 **Create branch** 버튼 뜨면 클릭

### (B) 파일 올리기/수정하기(웹에서 할 때)
1) 파일 수정: 파일 클릭 → 연필 아이콘(Edit)
2) 새 파일: **Add file → Create new file**
3) 아래쪽 **Commit changes** 누르기  
   - (가능하면) 커밋 메시지 간단히 쓰기: `feat: ...`

### (C) PR 만들기 (가장 중요!)
1) 레포 상단 메뉴에서 **Pull requests** 클릭
2) **New pull request** 클릭
3) 여기서 꼭 확인:
   - **base** = `develop`  ✅ (합쳐질 곳)
   - **compare** = `feature/내브랜치` ✅ (내가 작업한 것)
4) 제목/설명 간단히 적기
5) **Create pull request** 클릭

### (D) PR이 올라가면
- 팀원이 댓글/리뷰로 확인해줌
- OK 받으면 **Merge** (보통 관리자가 누르거나, 규칙에 따라 진행)

---

## 7) 진짜 중요한 보안 규칙
- **.env / 비밀번호 / API KEY / 개인 토큰** 이런 건 절대 GitHub에 올리면 안 됩니다.
- 올릴 것 같으면 꼭 먼저 물어보기!

---


# QuantPilot — Prototype v13 · GitHub Pages

주식 자동매매·분석 플랫폼 **QuantPilot**의 정적 프로토타입(v13)을 GitHub Pages로 배포하는 리포지토리입니다.

## 🚀 5분 배포 절차

### 1) 리포지토리 생성 + 파일 업로드
```bash
gh repo create quantpilot-pages --public --clone
cd quantpilot-pages
# 이 zip의 파일을 여기에 풀어넣기
git add .
git commit -m "init: QuantPilot prototype v13"
git push -u origin main
```

### 2) GitHub Pages 활성화 (한 번만)
- **GitHub CLI 사용**:
  ```bash
  gh api -X POST /repos/:owner/quantpilot-pages/pages \
    -f "source[branch]=main" -f "source[path]=/"
  ```
- **또는 웹 UI**: Settings → Pages → Source = **GitHub Actions** 선택

### 3) 자동 배포 확인
- main 브랜치에 push하면 `.github/workflows/pages.yml`이 자동 실행됩니다.
- Actions 탭에서 초록 체크가 뜨면 완료.
- URL: `https://<your-username>.github.io/quantpilot-pages/`

## 📁 파일 구조

```
.
├── index.html              # 홈 (사이트맵, 14개 화면 카드)
├── prototype.html          # 단일 파일 통합 프로토타입 (권장)
├── s01.html ~ s14.html     # 개별 화면 (S01 로그인 ~ S14 Google & AI)
├── README.md               # 이 문서
└── .github/workflows/
    └── pages.yml           # 자동 배포 워크플로
```

## 🎯 주요 화면 (14개)

| 화면 | 설명 |
|---|---|
| S01 | 로그인 / 2FA |
| S02 | 대시보드 (라이브 위젯 · 30일 SLO 배지) |
| S03 | 시세 · 차트 |
| S04 | AI 스크리너 (자연어 → 필터 JSON) |
| S05 | AI 전략 빌더 (자연어 → 규칙 JSON) |
| S06 | 백테스트 |
| S07 | 페이퍼 → 실전 전환 |
| S08 | 주문 · 체결 |
| S09 | 리스크 관리 |
| S10 | 알림 · 리포트 |
| S11 | 관리자 (감사 로그 · SLO 정책 편집) |
| S12 | 가이드 (소개 · 전체 시스템 인포그래픽) |
| S13 | 버전관리 (Git 기반 rollback/diff · 전체 시스템 안내) |
| S14 | Google API 연동 & AI 활용 방안 |

## 🌐 커스텀 도메인 (선택)

1. 도메인 등록업체(Cloudflare/가비아/AWS Route 53 등)에서 CNAME 레코드 추가:
   ```
   quantpilot.example.com  →  <your-username>.github.io
   ```
2. 리포지토리 루트에 `CNAME` 파일 추가:
   ```bash
   echo "quantpilot.example.com" > CNAME
   git add CNAME && git commit -m "add custom domain" && git push
   ```
3. Settings → Pages → **Enforce HTTPS** 체크

## 🔗 백엔드 프록시 연동 (선택)

Pages는 정적 SPA만 서빙합니다. 실 API를 사용하려면:

1. 별도로 `quantpilot_backend`(FastAPI)를 배포 — Render, Fly.io, Cloud Run 등
2. HTTPS 도메인 확보 (예: `https://api.quantpilot.example.com`)
3. Pages 사이트에서 상단 툴바에 이 URL 입력 → `localStorage.QP_API_BASE`에 저장

백엔드가 없어도 프로토타입은 **로컬 폴백 모드**로 정상 동작합니다 (스크리너 정규식 파서, 버전관리 로컬 시뮬 등).

## ⚙️ 로컬 미리보기

```bash
python3 -m http.server 8090
# → http://localhost:8090/
```

## 📊 검증 완료

- ✅ 14개 화면 렌더 (screen-s01 ~ screen-s14)
- ✅ JS 문법 (`node --check`) 통과
- ✅ `getElementById` DOM 참조 누락 0건
- ✅ 백엔드 연결/폴백 양쪽 경로 지원
- ✅ 모바일 반응형 (뷰포트 320px+ 대응)

## 📄 라이선스

내부 시연용 프로토타입. 외부 재배포 전 요구사항 검토 필요.

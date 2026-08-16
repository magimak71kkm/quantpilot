# 🚀 GitHub Pages 배포 — Step-by-Step

**소요 시간**: 약 5분 · **사전 요구**: GitHub 계정, `gh` CLI 또는 브라우저

---

## 방법 1: GitHub CLI (권장 — 가장 빠름)

### 1단계. GitHub CLI 설치 확인
```bash
gh --version
# 없다면: brew install gh  (macOS)  또는  https://cli.github.com/
gh auth login
```

### 2단계. 이 zip을 풀고 리포지토리 생성
```bash
unzip quantpilot-pages.zip
cd quantpilot-pages

gh repo create quantpilot-pages --public --source=. --push
# → 자동으로 remote 설정 + main 브랜치 push
```

### 3단계. Pages 활성화 (한 번만)
```bash
# Actions 기반 배포 활성화
gh api -X POST "repos/{owner}/quantpilot-pages/pages" \
  -f "build_type=workflow"

# 또는 branch 기반:
# gh api -X POST "repos/{owner}/quantpilot-pages/pages" \
#   -f "source[branch]=main" -f "source[path]=/"
```

### 4단계. 배포 확인
```bash
gh run watch
# 초록 체크 뜨면 성공
gh browse
# → https://<username>.github.io/quantpilot-pages/ 접속
```

---

## 방법 2: 웹 UI (CLI 없을 때)

### 1단계. 리포지토리 생성
- https://github.com/new
- Name: `quantpilot-pages`, Visibility: **Public**, "Create repository"

### 2단계. 파일 업로드
- "uploading an existing file" 링크 → zip 내용을 드래그
- Commit message: `init: QuantPilot prototype v13` → Commit

### 3단계. Pages 활성화
- Repository → **Settings** → **Pages**
- **Source**: `GitHub Actions` 선택 → Save

### 4단계. 자동 배포 확인
- **Actions** 탭 → "Deploy to GitHub Pages" 워크플로 실행 중
- 완료 후 상단 배너에 URL 표시:
  `https://<username>.github.io/quantpilot-pages/`

---

## 🧪 배포 검증 체크리스트

```bash
# 홈 페이지
curl -sI https://<username>.github.io/quantpilot-pages/ | head -1
# → HTTP/2 200

# 단일 파일 프로토타입
curl -sI https://<username>.github.io/quantpilot-pages/prototype.html | head -1
# → HTTP/2 200

# 14개 화면 모두 확인
for i in $(seq -w 1 14); do
  curl -sI https://<username>.github.io/quantpilot-pages/s${i}.html | head -1
done
```

---

## 🔄 이후 업데이트

새 버전(v14+)을 배포할 때는 파일만 교체 후 push:
```bash
# 새 prototype.html 등을 덮어쓰기
git add . && git commit -m "update: v14"
git push
# → GitHub Actions가 자동으로 재배포 (약 1분)
```

---

## 🌐 커스텀 도메인 (선택)

### DNS 설정
Cloudflare/Route 53 등에서:
```
Type: CNAME
Name: quantpilot     (또는 원하는 서브도메인)
Value: <username>.github.io
```

### 리포지토리에 CNAME 추가
```bash
echo "quantpilot.yourdomain.com" > CNAME
git add CNAME && git commit -m "add custom domain" && git push
```

### HTTPS 강제
- Settings → Pages → **Enforce HTTPS** 체크 (24시간 이내 자동 적용)

---

## ❓ 트러블슈팅

| 증상 | 원인/조치 |
|---|---|
| Actions에서 "Pages not enabled" | Settings → Pages → Source에서 `GitHub Actions` 선택 |
| 404 응답 | 리포지토리가 **Public**인지 확인. Private은 Pro 요금제 필요 |
| CSS/JS 미로드 | `.nojekyll` 파일이 루트에 있는지 확인 (이미 포함됨) |
| 배포 후 반영 안 됨 | 브라우저 강력 새로고침(Ctrl+Shift+R), CDN 캐시 최대 10분 |
| Actions 권한 오류 | Settings → Actions → General → Workflow permissions → **Read and write** |

---

## 📌 예상 최종 URL

```
https://<your-github-username>.github.io/quantpilot-pages/
├── /                    → 홈 (index.html, 14개 화면 사이트맵)
├── /prototype.html      → 단일 파일 통합 프로토타입 (권장)
├── /s01.html            → 로그인
├── /s02.html            → 대시보드 (라이브 위젯 + SLO 배지)
├── ...
└── /s14.html            → Google & AI
```

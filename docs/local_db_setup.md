# 로컬 DB 띄우기 (SQL v2.2) — 은경, 10/26

강의실 공용 DB(진규님 PC)가 꺼져 있거나 집에서 작업할 때, 내 PC에 같은 DB를 띄우는 방법이다. Windows PowerShell 기준.

## 0. 먼저 알아 둘 것
- **SQL·CSV는 저장소(GitHub)에 없다. 공유 드라이브의 `v2.2_SQL_MySQL_PK_FK` 압축 파일을 받는다.**
  저장소에 올리지 않는 이유:
  - 79 `src_complaint`는 민원에서 나온 자료다 (가린 요약만 있어도 민원 자료, ISS-032).
  - 05·06 등에 수치지형도 가공 값이 들어 있다 (「공간정보의 구축 및 관리 등에 관한 법률」 제16조·제21조, 국토지리정보원 출처 표시 조건). 해외 클라우드(GitHub 포함)에 두지 않는다.
- 받은 SQL·CSV, `.env`는 **저장소 폴더 밖**에 둔다 (예: `C:\radar_sql`). 실수로 `git add` 하지 않게.
- 이미 v2.1을 띄운 DB가 있고 그 안의 값(시험 계정 등)을 지키고 싶으면 2번 대신 **3번(올림)** 을 쓴다.

## 1. MySQL 8 설치 (한 번만)
1. MySQL 공식 누리집(dev.mysql.com)의 **MySQL Installer for Windows**로 **MySQL Server 8**과 **MySQL Workbench**를 설치한다.
2. 설치 중 정하는 root 비밀번호는 본인만 알고, 채팅·저장소·문서에 적지 않는다.
3. 확인:
```powershell
mysql --version                                   # 'mysql  Ver 8.x' 가 나오면 OK. 안 나오면 아래처럼 전체 경로로
& "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" --version   # 폴더 이름(8.0/8.4)은 설치한 판에 맞게
```

## 2. 새로 만들기 (처음 띄울 때)
압축을 `C:\radar_sql`에 풀고, 실행 파일을 **영문 이름**으로 복사한다 (한글 경로는 `source`에서 깨질 수 있음).
```powershell
New-Item -ItemType Directory -Force C:\radar_sql | Out-Null                                   # 작업 폴더
Expand-Archive "<받은 압축 파일 경로>" -DestinationPath C:\radar_sql -Force                  # 압축 풀기
Copy-Item "C:\radar_sql\v2.2_SQL_MySQL_PK_FK\전체\00_전체_한번에_실행.txt" C:\radar_sql\full22.sql   # 영문 이름으로 복사

mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS mysqlteam02db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"   # DB 만들기 (비밀번호 물어봄)
mysql -u root -p --default-character-set=utf8mb4 mysqlteam02db -e "source C:/radar_sql/full22.sql"                    # 표 90개 만들고 채우기 (몇 분 걸림)
```
- DB 이름은 공용 DB와 같은 `mysqlteam02db`로 한다 (`.env` 기본값). 다른 이름이면 `.env`의 `RADAR_DB_NAME`도 바꾼다.
- `00_전체_한번에_실행` 파일은 **표를 지우고 다시 만든다.** 이미 쓰던 DB에 다시 돌리면 그 안의 계정·기록이 지워진다.

## 3. 올리기 (v2.1 DB를 그대로 두고 v2.2로)
```powershell
mysqldump -u root -p --default-character-set=utf8mb4 mysqlteam02db > C:\radar_sql\backup_v21.sql   # 먼저 백업
mysql -u root -p --default-character-set=utf8mb4 mysqlteam02db -e "source C:/radar_sql/v2.2_SQL_MySQL_PK_FK/upgrade_v2.1_to_v2.2.sql"   # 한 번만 실행
```
- 기존 값은 그대로 두고 77에 4칸, 79에 3칸, 90 `complaint_review`(빈 표)를 더한다. 두 번 실행하면 "이미 있는 칸" 오류가 난다.

## 4. 잘 됐는지 확인 (Workbench나 mysql 창에서)
```sql
USE mysqlteam02db;
SELECT COUNT(*) AS 표_수 FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE';  -- 90
SELECT COUNT(*) AS FK_수 FROM information_schema.REFERENTIAL_CONSTRAINTS WHERE CONSTRAINT_SCHEMA = DATABASE();           -- 95 (00_읽어보기에는 96으로 적혀 있지만 실제로 만들어지는 FK는 95개, 10/26 은경 확인)
SELECT (SELECT COUNT(*) FROM grid_feature) AS 격자, (SELECT COUNT(*) FROM src_complaint) AS 민원,
       (SELECT COUNT(*) FROM jurisdiction) AS 담당부서표, (SELECT COUNT(*) FROM complaint_review) AS 검수;            -- 2406 · 281153 · 23 · 0
SELECT COUNT(*) AS 설명_있는_칸 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND COLUMN_COMMENT <> '';   -- 1578
```

## 5. 서버가 쓸 DB 계정 (권장)
root로 서버를 돌리지 말고, 읽기·쓰기만 되는 계정을 하나 만든다. 비밀번호는 직접 정해서 이 창에만 입력한다.
```sql
CREATE USER 'radar_app'@'localhost' IDENTIFIED BY '<직접 정한 비밀번호>';
GRANT SELECT, INSERT, UPDATE, DELETE ON mysqlteam02db.* TO 'radar_app'@'localhost';
```

## 6. `.env` (저장소 폴더 안, 저장소에는 안 올라감)
```powershell
Copy-Item .env.example .env        # 처음 한 번
notepad .env                        # 아래 칸 채우기
```
```
RADAR_DB_HOST=127.0.0.1
RADAR_DB_PORT=3306
RADAR_DB_USER=radar_app
RADAR_DB_PASSWORD=<5번에서 정한 비밀번호>
RADAR_DB_NAME=mysqlteam02db
```
강의실 공용 DB로 돌아갈 때는 `RADAR_DB_HOST`·계정만 공용 DB 값으로 바꾼다.

## 7. 시험 계정 6개 (로그인이 필요한 API를 쓰려면)
```powershell
$env:RADAR_SEED_PASSWORD = Read-Host "시험 계정 비밀번호(8자 이상)"   # 이 창에서만 쓰임
uv run python -m scripts.auth_create_test_users              # 미리 보기 (DB 안 바뀜)
uv run python -m scripts.auth_create_test_users --apply      # 넣기 → "6개 넣었습니다."
Remove-Item Env:RADAR_SEED_PASSWORD                         # 다 쓰면 지우기
```
아이디: `suj` · `jungwon` · `bundang` · `bundang-sidewalk`(구 도로관리팀) · `city`(시 도로과) · `operator`(RADAR 운영자)

## 8. 서버 켜고 확인
```powershell
uv sync --group dev                                          # 패키지
uv run uvicorn app.main:app --port 8000                     # 서버 (창 켜 둠)
Invoke-RestMethod http://127.0.0.1:8000/health/db            # 새 창에서: status : ok 면 끝
```
| `/health/db` | 뜻 |
|---|---|
| `ok` | 붙음 |
| `not_configured` | `.env`의 HOST·USER가 빔 |
| `unreachable` | MySQL이 꺼짐, 비밀번호·DB 이름이 틀림 |

## 9. 아직 비어 있는 것
- 77·78·82 시험 회차 → 진규님이 넣기로 함. 그 전까지 `/api/priority/runs`는 빈 목록이 정상.
- 90 `complaint_review`는 빈 표로 시작 (C-08 검수 표본을 만들면 채워짐).

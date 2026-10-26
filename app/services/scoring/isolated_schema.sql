CREATE TABLE IF NOT EXISTS grid_cell(gid TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS grid_feature(ID_gid TEXT PRIMARY KEY REFERENCES grid_cell(gid), id_gu TEXT);
CREATE TABLE IF NOT EXISTS setting_version(setting_version_id INTEGER PRIMARY KEY AUTOINCREMENT,setting_kind TEXT,version_label TEXT,content_ref TEXT,proposed_by INTEGER,proposed_at TEXT,approval_status TEXT,approved_by INTEGER,approved_at TEXT,review_comment TEXT);
CREATE TABLE IF NOT EXISTS priority_run(run_id INTEGER PRIMARY KEY CHECK(typeof(run_id)='integer'),build_id TEXT,rule_version TEXT,created_at TEXT,note TEXT CHECK(length(note)<=300));
CREATE TABLE IF NOT EXISTS priority_candidate(run_id INTEGER REFERENCES priority_run(run_id),gid TEXT REFERENCES grid_cell(gid),selected_yn TEXT,score NUMERIC CHECK(score IS NULL OR(score>=0 AND score<=100)),rank_no INTEGER,complaint_cnt INTEGER,complaint_cnt_excl_low INTEGER,cond_result_yn TEXT,cond_hazard_yn TEXT,cond_exposure_yn TEXT,cond_vulnerable_yn TEXT,matched_roles TEXT,note TEXT CHECK(length(note)<=300),PRIMARY KEY(run_id,gid));
CREATE TABLE IF NOT EXISTS setting_snapshot(setting_version_id INTEGER PRIMARY KEY,payload TEXT NOT NULL,sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evidence(run_id INTEGER NOT NULL,gid TEXT NOT NULL,gu TEXT,payload TEXT NOT NULL,sha256 TEXT NOT NULL,PRIMARY KEY(run_id,gid));

use crate::model::Project;
use rusqlite::{params, Connection};
use std::path::{Path, PathBuf};
#[derive(Clone)]
pub struct Store {
    pub root: PathBuf,
}
impl Store {
    pub fn new(root: PathBuf) -> Result<Self, String> {
        std::fs::create_dir_all(root.join("projects")).map_err(|e| e.to_string())?;
        let s = Self { root };
        s.db()?.execute_batch("PRAGMA journal_mode=WAL; CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, created_at TEXT NOT NULL, document TEXT NOT NULL);").map_err(|e|e.to_string())?;
        Ok(s)
    }
    fn db(&self) -> Result<Connection, String> {
        let c = Connection::open(self.root.join("studio.sqlite3")).map_err(|e| e.to_string())?;
        c.busy_timeout(std::time::Duration::from_secs(5))
            .map_err(|e| e.to_string())?;
        Ok(c)
    }
    pub fn dir(&self, id: &str) -> Result<PathBuf, String> {
        let parsed = uuid::Uuid::parse_str(id).map_err(|_| "Invalid project identifier.")?;
        if parsed.to_string() != id {
            return Err("Invalid project identifier format.".into());
        }
        Ok(self.root.join("projects").join(id))
    }
    pub fn save(&self, p: &Project) -> Result<(), String> {
        let doc = serde_json::to_string(p).map_err(|e| e.to_string())?;
        self.db()?.execute("INSERT INTO projects(id,created_at,document) VALUES(?1,?2,?3) ON CONFLICT(id) DO UPDATE SET document=excluded.document",params![p.id,p.created_at,doc]).map_err(|e|e.to_string())?;
        Ok(())
    }
    pub fn get(&self, id: &str) -> Result<Project, String> {
        self.dir(id)?;
        let doc: String = self
            .db()?
            .query_row("SELECT document FROM projects WHERE id=?1", [id], |r| {
                r.get(0)
            })
            .map_err(|_| "Project not found.".to_string())?;
        let p: Project = serde_json::from_str(&doc).map_err(|e| e.to_string())?;
        if p.id != id {
            return Err("Project identifier does not match its stored record.".into());
        }
        self.validate_paths(&p)?;
        Ok(p)
    }
    pub fn modify(
        &self,
        id: &str,
        change: impl FnOnce(&mut Project) -> Result<(), String>,
    ) -> Result<Project, String> {
        self.dir(id)?;
        let mut connection = self.db()?;
        let tx = connection
            .transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)
            .map_err(|e| e.to_string())?;
        let doc: String = tx
            .query_row("SELECT document FROM projects WHERE id=?1", [id], |r| {
                r.get(0)
            })
            .map_err(|_| "Project not found.".to_string())?;
        let mut p: Project = serde_json::from_str(&doc).map_err(|e| e.to_string())?;
        if p.id != id {
            return Err("Project identifier does not match its stored record.".into());
        }
        self.validate_paths(&p)?;
        change(&mut p)?;
        self.validate_paths(&p)?;
        tx.execute(
            "UPDATE projects SET document=?2 WHERE id=?1",
            params![id, serde_json::to_string(&p).map_err(|e| e.to_string())?],
        )
        .map_err(|e| e.to_string())?;
        tx.commit().map_err(|e| e.to_string())?;
        Ok(p)
    }
    pub fn list(&self) -> Result<Vec<Project>, String> {
        let c = self.db()?;
        let mut s = c
            .prepare("SELECT id,document FROM projects ORDER BY created_at DESC")
            .map_err(|e| e.to_string())?;
        let rows = s
            .query_map([], |r| Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?)))
            .map_err(|e| e.to_string())?;
        rows.map(|r| {
            let (id, doc) = r.map_err(|e| e.to_string())?;
            let mut p: Project = serde_json::from_str(&doc).map_err(|e| e.to_string())?;
            if p.id != id {
                return Err("Project identifier does not match its stored record.".into());
            }
            self.validate_paths(&p)?;
            if p.poster_path
                .as_ref()
                .is_some_and(|path| !Path::new(path).is_file())
            {
                p.poster_path = None;
            }
            Ok(p)
        })
        .collect()
    }
    pub fn trusted_source(&self, p: &Project) -> Result<PathBuf, String> {
        self.validate_paths(p)?;
        let expected = self.dir(&p.id)?.join("source.mkv");
        let mac = self.dir(&p.id)?.join("source.mp4");
        let actual = Path::new(&p.source_path);
        if actual != expected && actual != mac {
            return Err("Source is outside its project.".into());
        }
        if !actual.is_file() {
            return Err("Source file is missing. Restore it in the project folder.".into());
        }
        let canonical = actual.canonicalize().map_err(|e| e.to_string())?;
        let project_dir = self.dir(&p.id)?.canonicalize().map_err(|e| e.to_string())?;
        if !canonical.starts_with(project_dir) {
            return Err("Source resolves outside its project.".into());
        }
        Ok(actual.into())
    }
    pub fn validate_paths(&self, p: &Project) -> Result<(), String> {
        let dir = self.dir(&p.id)?;
        let source = Path::new(&p.source_path);
        if source != dir.join("source.mp4") && source != dir.join("source.mkv") {
            return Err("Source is outside its project.".into());
        }
        let check = |path: &Path| -> Result<(), String> {
            if !path.starts_with(&dir)
                || path
                    .components()
                    .any(|c| matches!(c, std::path::Component::ParentDir))
            {
                return Err("Media path is outside its project.".into());
            }
            if path.exists() {
                let real = path.canonicalize().map_err(|e| e.to_string())?;
                let root = dir.canonicalize().map_err(|e| e.to_string())?;
                if !real.starts_with(root) {
                    return Err("Media path resolves outside its project.".into());
                }
            }
            Ok(())
        };
        check(source)?;
        if let Some(poster) = &p.poster_path {
            let path = Path::new(poster);
            if path != dir.join("poster.jpg") {
                return Err("Poster path is outside its expected project location.".into());
            }
            check(path)?;
        }
        for a in &p.exports {
            let video = Path::new(&a.path);
            let folder = video.parent().ok_or("Invalid export path")?;
            let export_id = folder
                .file_name()
                .and_then(|s| s.to_str())
                .ok_or("Invalid export identifier")?;
            uuid::Uuid::parse_str(export_id).map_err(|_| "Invalid export identifier")?;
            if folder.parent() != Some(dir.join("exports").as_path()) {
                return Err("Export is outside its project.".into());
            }
            let filename = match a.preset.as_str() {
                "h264" => "video.mp4",
                "webm" => "video.webm",
                _ => return Err("Unknown stored export preset.".into()),
            };
            if video != folder.join(filename)
                || Path::new(&a.poster_path) != folder.join("poster.jpg")
                || Path::new(&a.summary_path) != folder.join("summary.md")
                || Path::new(&a.transcript_path) != folder.join("transcript.txt")
            {
                return Err("Stored export paths are not valid for this project.".into());
            }
            for path in [&a.path, &a.poster_path, &a.summary_path, &a.transcript_path] {
                check(Path::new(path))?;
            }
        }
        Ok(())
    }
}
pub fn path_string(p: &Path) -> String {
    p.to_string_lossy().into_owned()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::EditPlan;
    fn project() -> Project {
        Project {
            id: uuid::Uuid::new_v4().to_string(),
            title: "project".into(),
            created_at: String::new(),
            duration: 2.0,
            width: 640,
            height: 360,
            has_audio: false,
            source_path: String::new(),
            poster_path: None,
            edits: EditPlan::initial(2.0),
            exports: vec![],
        }
    }
    #[test]
    fn missing_and_untrusted_sources_fail_closed() {
        let t = tempfile::tempdir().unwrap();
        let s = Store::new(t.path().into()).unwrap();
        let mut p = project();
        p.source_path = path_string(&s.dir(&p.id).unwrap().join("source.mp4"));
        assert!(s.trusted_source(&p).unwrap_err().contains("missing"));
        p.source_path = path_string(&t.path().join("outside.mp4"));
        std::fs::write(&p.source_path, b"fixture").unwrap();
        assert!(s.trusted_source(&p).unwrap_err().contains("outside"));
        assert!(s.get(&p.id).is_err());
        assert!(s.dir(&format!("urn:uuid:{}", p.id)).is_err());
    }
    #[test]
    fn corrupt_database_is_reported() {
        let t = tempfile::tempdir().unwrap();
        std::fs::write(t.path().join("studio.sqlite3"), b"This is not SQLite").unwrap();
        assert!(Store::new(t.path().into()).is_err());
    }
    #[test]
    fn corrupt_project_is_reported() {
        let t = tempfile::tempdir().unwrap();
        let s = Store::new(t.path().into()).unwrap();
        s.db()
            .unwrap()
            .execute(
                "INSERT INTO projects VALUES(?1,'','broken json')",
                [uuid::Uuid::new_v4().to_string()],
            )
            .unwrap();
        assert!(s.list().is_err());
    }
    #[test]
    fn preview_paths_are_scoped_and_missing_media_does_not_block_library() {
        let t = tempfile::tempdir().unwrap();
        let s = Store::new(t.path().into()).unwrap();
        let mut p = project();
        let dir = s.dir(&p.id).unwrap();
        p.source_path = path_string(&dir.join("source.mp4"));
        p.poster_path = Some(path_string(&dir.join("poster.jpg")));
        let folder = dir.join("exports").join(uuid::Uuid::new_v4().to_string());
        p.exports.push(crate::model::ExportArtifact {
            path: path_string(&folder.join("video.mp4")),
            poster_path: path_string(&folder.join("poster.jpg")),
            summary_path: path_string(&folder.join("summary.md")),
            transcript_path: path_string(&folder.join("transcript.txt")),
            preset: "h264".into(),
        });
        s.save(&p).unwrap();
        let cards = s.list().unwrap();
        assert_eq!(cards.len(), 1);
        assert!(cards[0].poster_path.is_none());
        assert!(s.get(&p.id).is_ok());
        p.poster_path = Some(path_string(&t.path().join("private.jpg")));
        s.save(&p).unwrap();
        assert!(s.get(&p.id).is_err());
        assert!(s.list().is_err());
        p.poster_path = None;
        p.exports[0].path = path_string(&t.path().join("private.mp4"));
        assert!(s.validate_paths(&p).is_err());
    }
    #[test]
    fn parent_components_and_mismatched_project_ids_are_rejected() {
        let t = tempfile::tempdir().unwrap();
        let s = Store::new(t.path().into()).unwrap();
        let mut p = project();
        p.source_path = path_string(&s.dir(&p.id).unwrap().join("..\\source.mp4"));
        assert!(s.validate_paths(&p).is_err());
        p.source_path = path_string(&s.dir(&p.id).unwrap().join("source.mp4"));
        s.save(&p).unwrap();
        let wrong_id = uuid::Uuid::new_v4().to_string();
        s.db()
            .unwrap()
            .execute(
                "UPDATE projects SET id=?1 WHERE id=?2",
                params![wrong_id, p.id],
            )
            .unwrap();
        assert!(s.get(&wrong_id).is_err());
        assert!(s.list().is_err());
    }
    #[test]
    fn transaction_preserves_parallel_changes_and_rolls_back_errors() {
        let t = tempfile::tempdir().unwrap();
        let s = Store::new(t.path().into()).unwrap();
        let mut p = project();
        p.source_path = path_string(&s.dir(&p.id).unwrap().join("source.mp4"));
        s.save(&p).unwrap();
        let mut workers = Vec::new();
        for _ in 0..2 {
            let s = s.clone();
            let id = p.id.clone();
            workers.push(std::thread::spawn(move || {
                for _ in 0..12 {
                    s.modify(&id, |p| {
                        p.edits.transcript.push('x');
                        Ok(())
                    })
                    .unwrap();
                }
            }));
        }
        for w in workers {
            w.join().unwrap()
        }
        assert_eq!(s.get(&p.id).unwrap().edits.transcript.len(), 24);
        assert!(s
            .modify(&p.id, |p| {
                p.title = "bad".into();
                Err("validation failed".into())
            })
            .is_err());
        assert_eq!(s.get(&p.id).unwrap().title, "project");
    }
}

# Reviewed release and backup

Set SHILU_PROFILE_PATH identically to the human workbench. Use a private output directory outside the public repository. Export only an already reviewed revision:

    python3 -m shilu.release --data-dir /private/workspace --project-id ID --revision N --output /private/releases/ID-N

Output must not exist. Store.export verifies human approval and current sources/rules, records export and advances revision. article.json is public; release-manifest.json is private and records reviewed/export revisions, source versions, rules hash and article SHA256. Never publish the entire bundle. Deployment status starts not_started; this command does not publish. If filesystem writing fails after Store.export, the database may record an export attempt without a bundle; re-read revision and retry to a fresh directory.

    python3 -m shilu.backup backup --source /private/workspace/shilu.sqlite3 --target /private/backups/date.sqlite
    python3 -m shilu.backup restore --source /private/backups/date.sqlite --target /private/restored/shilu.sqlite3

SQLite backup API provides a consistent database copy and integrity check. Both commands refuse existing targets. Parent directories must exist. Restore to a new private directory, inspect projects and source counts, then explicitly switch service configuration. These commands back up database data only; retain private profiles and original media separately.

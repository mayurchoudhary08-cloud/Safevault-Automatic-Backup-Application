# SafeVault — Automatic Backup & Restore Desktop Application

A reliable, practical Operating Systems laboratory and viva project built with Python 3, CustomTkinter, and SQLite. SafeVault performs real local file management, multithreaded chunked streaming backups, cryptographic SHA-256 integrity verification, safe isolated file restorations, and cooperative schedule automation.

---

## 1. Problem Statement

Computer users frequently encounter accidental data loss:
- Accidentally deleting a file or directory branch.
- Overwriting an assignment or thesis document with incorrect edits.
- Introducing a breaking bug into source code without version control.
- File corruption caused by faulty media or interrupted file transfer.

Without an intuitive backup system, users either lose work permanently or risk overwriting their remaining good files while attempting manual recovery. 

SafeVault solves this problem by maintaining separate, dated snapshots of protected folders, verifying every file with SHA-256 checksums, and restoring files into brand-new isolated directories so original documents are never destroyed.

---

## 2. Project Objectives

- **Practical OS Demonstration:** Implement core OS concepts (file I/O, tree traversal, threads, queues, scheduling, integrity) in real code rather than mock simulations.
- **Data Safety First:** Enforce defensive safeguards against recursive directory loops, directory traversal attacks, and silent file overwriting.
- **Viva-Ready Clarity:** Provide clean, readable, modular code that a college student can trace and explain during a viva exam.
- **Desktop Utility UX:** Present a clean, native desktop graphical interface using CustomTkinter with real-time progress indicators.

---

## 3. Features

1. **Interactive Dashboard:** Live metrics including successful backups count, storage utilized, latest backup status, upcoming schedule, and quick-action shortcuts.
2. **Defensive Path Setup:** Folder pickers for source and destination directories with real-time path validation (detects recursive nesting, overlapping roots, missing directories).
3. **Chunked Streaming Backups:** Non-blocking 64 KB chunked copy streams with live progress bars, processing speed tracking, and clean cancellation.
4. **Immutable JSON Manifests:** Each snapshot records relative paths, sizes, modification timestamps, and SHA-256 hashes.
5. **SHA-256 Integrity Verification:** On-demand and post-backup cryptographic verification to detect tampered, corrupted, or missing snapshot files.
6. **Safe Non-Destructive Restore:** Restores snapshots into newly created, timestamped directories (e.g. `SafeVault_Restored_<backup_id>_<timestamp>`), preventing overwrite of current files.
7. **Path Traversal Security:** Blocks `..` traversal attacks and absolute path escapes during manifest parsing and restore operations.
8. **Cooperative Scheduler:** Daily and weekly background scheduling while the app is running, with an automatic single startup catch-up run for missed intervals.
9. **Persistent Audit Trail:** Chronological activity logging backed by SQLite and a local `safevault.log` file, with event filtering.
10. **Built-in Demo Workspace Generator:** Generates a sample folder with documents and code for testing and viva presentations without risking personal user files.

---

## 4. Technologies Used

- **Python 3.11+ (Compatible with Python 3.13):** Core programming language.
- **CustomTkinter:** Modern light desktop user interface.
- **Tkinter (`filedialog`, `messagebox`):** Native Windows dialogs.
- **SQLite 3 (`sqlite3`):** Parameterized persistent storage for history, logs, and settings.
- **Standard Library:**
  - `pathlib` & `os`: Path resolution, directory scanning, and permissions checking.
  - `shutil`: Chunked copying and timestamp/metadata preservation (`copystat`).
  - `hashlib`: Chunked SHA-256 cryptographic digestion.
  - `threading` & `queue`: Background worker threads and thread-safe UI communication.
  - `json`: Versioned snapshot manifest serialization.
  - `datetime` & `time`: Timing and schedule computation.
  - `unittest`: Automated test framework.

---

## 5. Application Architecture

```
SafeVault/
│
├── main.py                     # Application entry point & dependency validation
├── requirements.txt            # Minimal third-party dependencies (customtkinter)
├── run.bat                     # Windows launch script
├── .gitignore                  # Ignore caches, database, and temporary test directories
├── README.md                   # Complete documentation & OS viva review
│
├── safevault/                  # Core application package
│   ├── __init__.py             # Package version and metadata
│   ├── app.py                  # Main GUI coordinator, sidebar navigation & queue listener
│   ├── database.py             # SQLite database manager (settings, runs, activity logs)
│   ├── paths.py                # Path validation & traversal prevention utilities
│   ├── backup_manager.py       # Background worker, chunked copier, manifest generator
│   ├── restore_manager.py      # Isolated restore engine with verification
│   ├── integrity.py            # SHA-256 file digestion & snapshot verification
│   ├── scheduler.py            # Daily/weekly cooperative scheduler & catch-up logic
│   ├── demo_workspace.py       # Harmless sample files generator for demonstration
│   ├── logger.py               # Synchronized file & database activity logging
│   └── ui/                     # Presentation layer
│       ├── __init__.py
│       ├── theme.py            # Restrained professional color palette & fonts
│       ├── common.py           # Reusable CardFrame, MetricCard, StatusBadge, ConfirmDialog
│       ├── dashboard.py        # System overview & live metrics
│       ├── backup_page.py      # Folder selection & path safety validation
│       ├── history_page.py     # Backup history table & manifest inspector
│       ├── restore_page.py     # Restore Center with directory selection
│       ├── activity_page.py    # Searchable audit trail & event filter
│       ├── settings_page.py    # Schedule configuration & next run preview
│       └── about_page.py       # OS concepts review & viva preparation notes
│
└── tests/                      # Automated unit & integration tests
    ├── test_paths.py           # Path validation & traversal security tests
    ├── test_database.py        # SQLite CRUD & statistics tests
    ├── test_backup.py          # Backup engine, empty folders & cancellation tests
    ├── test_integrity.py       # SHA-256 hash checks & corruption detection tests
    ├── test_restore.py         # Isolated restore & security rejection tests
    ├── test_app_smoke.py       # GUI initialization & navigation smoke test
    └── test_end_to_end.py      # Full student viva walkthrough test
```

---

## 6. Installation & Prerequisites

### Prerequisites
- Windows 10 or 11.
- Python 3.10, 3.11, 3.12, or 3.13 installed and added to PATH.

### Installation Steps
1. Clone the repository and navigate into the project directory:
   ```powershell
   git clone https://github.com/mayurchoudhary08-cloud/Safevault-Automatic-Backup-Application.git
   cd Safevault-Automatic-Backup-Application
   ```
2. Install the required dependencies:
   ```powershell
   py -m pip install -r requirements.txt
   ```
   *(or `python -m pip install -r requirements.txt`)*

---

## 7. How to Run

### Option A: Using the Windows batch script
Double-click `run.bat` or run:
```cmd
run.bat
```

### Option B: Using Python directly
```powershell
py main.py
```
*(or `python main.py`)*

---

## 8. Step-by-Step User Guides

### How to Create a Backup
1. Launch SafeVault.
2. If this is your first time or you want to demo safely, click **🧪 Create Demo Workspace** at the bottom of the sidebar. Choose any folder, and when prompted, click **Yes** to set it as your source.
3. Open **📁 Backup Setup** in the sidebar.
4. Verify your **Source Folder** and choose a separate **Backup Destination** (e.g. `D:/SafeVault_Backups` or `C:/MyBackups`).
5. Click **Save Folder Settings**.
6. Switch to **📊 Dashboard** and click the primary **🛡️ BACK UP NOW** button.
7. Watch the live progress bar, file processing counter, and status updates.

### How to Restore a Previous Version
1. Open **🔄 Restore Center** in the sidebar.
2. Choose the desired snapshot from the dropdown (newest backups appear first).
3. Review the snapshot metadata and included file list.
4. SafeVault automatically suggests a safe, new destination folder (e.g. `SafeVault_Restored_<backup_id>_<timestamp>`). You can change the base directory if desired.
5. Click **🚀 RESTORE THIS BACKUP**.
6. Review the confirmation dialog summarizing the operation and click **Restore Files Now**.
7. Once finished, click **Yes** to open the restored directory in Windows Explorer.

### How Scheduled Backups Work
1. Open **⚙️ Schedule & Settings**.
2. Toggle **Enable Schedule** to ON.
3. Select frequency (**Daily** or **Weekly**).
4. Enter the preferred time (e.g., `14:30`) and day (for weekly).
5. Click **Save Schedule & Settings**.
6. The scheduler runs cooperatively in the background while SafeVault is open.
7. **Startup Catch-Up Logic:** If the computer was shut down or SafeVault was closed when a scheduled backup was due, SafeVault detects this during application startup and triggers **at most one** catch-up backup.

### How SHA-256 Verification Works
1. During backup creation, SafeVault streams each file in 64 KB chunks through Python's `hashlib.sha256()`.
2. The hexadecimal hash digest is recorded alongside the relative path and size in `manifest.json`.
3. To re-verify any snapshot:
   - Go to **📜 Backup History**.
   - Find the snapshot row and click **Verify**.
   - SafeVault re-reads every file from the snapshot's `data/` folder, recalculates the SHA-256 hash, and compares it to the manifest.
   - If any byte has been altered, corrupted, or deleted, SafeVault identifies the exact file and displays an alert.

---

## 9. Database Structure

SafeVault persists operational data in `safevault.db` using SQLite:

### Table: `settings`
| Column | Type | Description |
|---|---|---|
| `key` | TEXT PRIMARY KEY | Setting name (`source_folder`, `schedule_time`, etc.) |
| `value` | TEXT NOT NULL | Setting value |

### Table: `backup_runs`
| Column | Type | Description |
|---|---|---|
| `backup_id` | TEXT PRIMARY KEY | Timestamp ID (`2026-10-09_223000`) |
| `source_path` | TEXT NOT NULL | Original source folder path |
| `snapshot_path`| TEXT NOT NULL | Full path to snapshot folder on disk |
| `start_time` | TEXT NOT NULL | ISO 8601 start timestamp |
| `completion_time` | TEXT | ISO 8601 finish timestamp |
| `status` | TEXT NOT NULL | `SUCCESS`, `FAILED`, or `CANCELLED` |
| `file_count` | INTEGER | Total files included |
| `total_size_bytes` | INTEGER | Sum of file sizes in bytes |
| `verification_status` | TEXT | `VERIFIED`, `UNVERIFIED`, or `FAILED` |
| `error_message` | TEXT | Error details if failed |

### Table: `activity_logs`
| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PRIMARY KEY | Autoincrement log event ID |
| `timestamp` | TEXT NOT NULL | ISO 8601 timestamp |
| `event_type` | TEXT NOT NULL | `BACKUP_STARTED`, `RESTORE_COMPLETED`, etc. |
| `message` | TEXT NOT NULL | Human-readable event description |
| `backup_id` | TEXT | Associated backup ID if applicable |

---

## 10. Data Structures & Algorithms

- **Directory Tree Traversal:** Depth-first search (DFS) traversal via `os.walk` to enumerate files and empty directories while preserving hierarchical parent-child relationships.
- **Streaming Buffer Algorithm:** Chunked 64 KB block streaming with constant $O(1)$ memory overhead, allowing multi-gigabyte files to be processed without memory exhaustion.
- **Relative Path Translation:** Normalization and prefix extraction transforming absolute paths into relative tree coordinates for independent restoration.
- **Hashing Algorithm:** SHA-256 cryptographic hashing ($O(N)$ linear byte processing) providing bit-level tamper and corruption detection.
- **FIFO Queue Message Passing:** Thread-safe `queue.Queue` providing producer-consumer inter-thread communication between worker threads and the Tkinter GUI event loop.

---

## 11. Operating Systems Concepts Demonstrated

| Concept | Implementation in SafeVault |
|---|---|
| **File System Management** | Traversal of directory inodes, path resolution (`Path.resolve()`), creation of nested subdirectories, and omission of symlink traversal. |
| **File Input/Output (I/O)** | Binary byte stream reading and writing (`open(..., 'rb')`, `open(..., 'wb')`), 64 KB chunk buffers, metadata cloning (`copystat`). |
| **Directory Structures** | Preserving relative path hierarchies and tracking empty directory nodes so complete directory trees can be restored. |
| **Multithreading & Concurrency** | Long-running I/O jobs execute on worker threads (`threading.Thread`) while the GUI runs on the main thread, avoiding UI freezing. |
| **Inter-Thread Communication** | Non-blocking thread-safe message queues (`queue.Queue`) and cancellation synchronization tokens (`threading.Event`). |
| **Job Scheduling** | Periodic background evaluation of time conditions, calculation of next run targets, and startup catch-up policy. |
| **Defensive Security** | Preventing path traversal escapes (`..`), blocking recursive folder loops, and validating read/write access permissions. |
| **Atomic Operations** | Staging snapshot files in `.partial_<id>` temporary directories and renaming atomically upon successful completion. |

---

## 12. Running Automated Tests

All tests run using Python's built-in `unittest` runner on isolated temporary directories. Real user files are never touched.

To run the entire test suite (24 tests):
```powershell
py -m unittest discover -s tests -p "test_*.py" -v
```

### Test Breakdown
- `test_paths.py` (7 tests): Nonexistent sources, file-as-source, recursive loops, overlapping directories, traversal attacks.
- `test_database.py` (4 tests): Settings CRUD, backup run lifecycle, activity logs, dashboard statistics queries.
- `test_backup.py` (3 tests): Nested directories, empty directory preservation, empty source handling, concurrent run prevention.
- `test_integrity.py` (4 tests): Intact snapshot check, missing file detection, tampered file hash detection, missing manifest check.
- `test_restore.py` (2 tests): Clean restore into a new directory, manifest path traversal rejection.
- `test_app_smoke.py` (1 test): GUI initialization, appearance settings, sidebar navigation, view refreshes.
- `test_end_to_end.py` (1 test): Full college viva walkthrough (demo creation $\to$ Backup 1 $\to$ file modification $\to$ Backup 2 $\to$ restore of Backup 1 $\to$ content verification $\to$ snapshot tampering detection).

---

## 13. Known Limitations

As designed for this version:
1. **Full Snapshots (No Deduplication):** Each backup is an independent, complete copy. While this maximizes simplicity and reliability, it consumes more storage than incremental deduplication.
2. **Cooperative Scheduling:** Automatic backups trigger while SafeVault is open. It does not install a hidden background Windows service. If the app was closed when a backup was due, it runs at most one catch-up backup on the next launch.
3. **Local Storage:** Backups are stored on local or attached drives. A local backup does not substitute for an off-site copy on a separate physical machine.
4. **Active/Locked Files:** Files locked exclusively by other running software (e.g., active database files) may fail to read during copy and will be logged with warnings.
5. **No Built-in Encryption:** Backups are standard local files with plain-text manifests, not encrypted archives.

---

## 14. Future Enhancements

- Content-addressable block deduplication to save disk space across similar snapshots.
- AES-256-GCM encryption for password-protected backup archives.
- Windows Task Scheduler integration for headless system background execution.
- Configurable retention policies with user-confirmed deletion of snapshots older than $N$ days.
- Cloud storage backend connectors (e.g., Google Drive, AWS S3).

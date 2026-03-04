# AI Coding Agent Instructions for Natura IT Monorepo

**Last Updated:** March 2, 2026  
**Target Audience:** GitHub Copilot, Claude, and other AI coding agents  
**Scope:** Hybrid RPA monorepo (Desktop Windows + Headless Linux + Data Pipelines)

---

## 🏗️ Architecture Overview

### Monorepo Structure
The repository is a **hybrid monorepo** with three independent execution environments:
- **`rpa_desktop_win/`** → Windows Server (GUI automation: SAP, Excel, macro-based)
- **`rpa_headless_linux/`** → Linux Docker (Web automation: Playwright headless, APIs)
- **`data_pipelines_linux/`** → Linux Docker (ETL: Pandas, Databricks, SQL connectors)
- **`core_shared/`** → Shared library (Vault, security, logging, utilities)

### Key Design Pattern: Domain-Driven Design (DDD)
All RPA bots use strict **3-layer architecture**:
```
main.py (entry point) 
  ↓
use_cases/ (business logic orchestration)
  ↓
adapters/ (technical implementations: SAPDriver, WebDriver, etc.)
  ↓ uses
domain/ (pure dataclasses: no logic)
```
**Why:** Separation allows unit testing adapters independently from SAP/Web dependencies.

Example: `rpa_desktop_win/Bot_sap_zmm0164/src/{domain,adapters,use_cases}`

---

## 📏 Naming Convention (Mandatory)

**Format:** `[DOMAIN]_[AREA]_[VERBO]_[OBJETO]_[SISTEMA].py`

### Reserved Domains
- `ops` = Operaciones | `fin` = Finanzas | `grw` = Growth | `mkt` = Marketing | `tec` = Tecnología

### Areas (by domain)
- OPS: `ped`, `tpt`, `pln`, `com`, `cal`, `cmp`, `fac`
- FIN: `pln`, `acc`, `tax`, `cyc`, `ret`
- TEC: `dat`, `inf`, `sec`

### Verbs (English, infinitive)
- `get` = simple read | `download` = fetch file | `process` = complex logic
- `ingest` = ETL/bulk load | `send` = communicate | `validate` = quality checks

### Systems
- `sap` = SAP GUI/ECC | `sql` = SQL Server | `dbr` = Databricks | `web` = REST/portal
- `mail` = email | `excel` = Excel files

**Examples:**
- `fin_acc_release_invoices_sap.py` → Finance/Accounting bot
- `ops_ped_ingest_cartoning_sftp.py` → Logistics/Sourcing pipeline
- `tec_dat_ingest_sales_dbr.py` → Data engineering pipeline

**Non-compliance Impact:** CI/CD routing and discovery fails; prioritize correctness over brevity.

---

## 🔐 Security & Configuration

### Secret Management (Vault Pattern)
- **Never hardcode** credentials or API keys
- Use `core_shared.security.vault.Vault.get_secret(key, default=None)`
- Variable naming: `BOT_[NAME]_[FIELD]` (e.g., `BOT_ZMM0164_SAP_PASSWORD`)
- Windows SMB credentials: `BOT_ZMM0164_OUTPUT_NET_USER`, `BOT_ZMM0164_OUTPUT_NET_PASSWORD`

### Environment-Based Configuration
```python
from core_shared.security.vault import Vault

client = Vault.get_secret("BOT_ZMM0164_SAP_CLIENT", "210")  # Fallback to "210"
password = Vault.get_secret("BOT_ZMM0164_SAP_PASSWORD")     # No fallback = required
```

### Multi-Environment Support
- Bots read `RPA_ENV` env var: `development`, `testing`, `production`
- Config layer (config.py) maps environment → settings (SAP connection, timeouts, logging levels)
- GitHub Secrets populated into GitHub Actions workflows

---

## 🤝 Integration Points

### Core Shared Library
Located in `core_shared/`:
- **`security/vault.py`** → Secret retrieval, SMB mounting (`mount_smb_windows()`)
- **`email/gmail_sender.py`** → Notification system
- **`email/html_templates.py`** → Email template library

### RPA Bot Template Structure
```
MyBot/
├── main.py                 # Entry point ONLY - no logic
├── config.py              # Multi-env configuration
├── requirements.txt       # Dependencies (pin versions!)
├── security/             # Local vault_helper wrapping core_shared
├── src/
│   ├── domain/            # Dataclasses (ExportConfig, Credentials, etc.)
│   ├── adapters/          # SAPDriver, WebDriver, etc. (testable)
│   └── use_cases/         # Orchestration logic (business workflows)
└── README.md + ARQUITECTURA.md
```

### SAP GUI Automation (Windows)
- **Library:** `pywin32==305` (pinned version critical)
- **Adapter:** `src/adapters/sap_driver.py` wraps `win32com.client`
- **Pattern:** Use field IDs (e.g., `wnd[0]/usr/ctxtSP$00006-LOW`), not pixel positions
- **Critical:** Always call `disconnect()` in finally block + force `taskkill /F /IM saplogon.exe`
  ```python
  finally:
      driver.disconnect()  # Sends /nex + waits + taskkill
  ```
  Reason: SAP COM port (6890) blocks next execution if not cleaned up.

### Network File Access (Windows)
- **Priority 1:** Try SMB mount via `net use Z: \\[path] /persistent:yes`
- **Priority 2:** Fallback to UNC path directly (`\\[server]\[path]`)
- **Pattern:** Used in `main.py` for shared output folders
  ```python
  if mount_smb_windows(NET_UNC_PATH, "Z", NET_USER, NET_PASSWORD, NET_DOMAIN):
      OUTPUT_FOLDER = r"Z:\..."
  else:
      OUTPUT_FOLDER = NET_UNC_PATH  # Fallback
  ```

---

## 🧪 Testing Pattern

### Framework: unittest + unittest.mock
- **Location:** `examples_test_example.py` OR `tests/` directory
- **No external dependencies** (pytest not used yet)
- **Mock SAP:** Use `unittest.mock.MagicMock` for `win32com.client`

### Test Structure
```python
from unittest.mock import Mock, patch, MagicMock

class TestExportData(unittest.TestCase):
    def test_domain_model_filename(self):
        config = ExportConfig(material_code="4100", output_folder="Z:\\", file_format="XLS")
        self.assertIn("zmm0164-", config.filename)
    
    @patch('adapters.sap_driver.win32com.client.GetObject')
    def test_sap_connect(self, mock_get_object):
        mock_get_object.return_value = MagicMock()
        # Test logic...
```

### TDD Approach (Red → Green → Refactor)
1. Write failing test for domain model
2. Implement dataclass to pass test
3. Write failing test for adapter (mock dependencies)
4. Implement adapter method
5. Write use_case test orchestrating adapters
6. Run full workflow test (integration)

---

## 📋 Development Workflow

### Setup New SAP Bot
1. **Name it correctly:** Follow `[DOMAIN]_[AREA]_[VERBO]_[OBJETO]_sap.py` convention
2. **Create structure:**
   ```bash
   mkdir -p src/{domain,adapters,use_cases}
   cp ARQUITECTURA.md README.md QUICK_START.md  # From template
   ```
3. **Define domain models:** `src/domain/export_data.py` (pure dataclasses)
4. **Implement adapter:** `src/adapters/sap_driver.py` (wraps pywin32)
5. **Write use case:** `src/use_cases/release_process.py` (orchestration)
6. **Configure:** `config.py` (environments), `main.py` (entry point only)
7. **Secure:** Use Vault for all credentials, no hardcoding

### Git Commit Conventions
- Reference REQUISITO/SDD in commit messages
- Tag architectural changes: `[ARCH]`, `[FEAT]`, `[DOCS]`, `[FIX]`
- Example: `[FEAT] Add SMB fallback logic to output folder handling`

### Debugging SAP Bot (Locally)
1. Set `RPA_ENV=development` (different SAP connection)
2. Enable debug logging in config.py: `LOG_LEVEL = "DEBUG"`
3. Use `test_smb_mount.py` to diagnose network issues
4. Verify field IDs match transactioncode (run SAP Debug → script → inspect)

---

## ⚙️ CI/CD & GitHub Actions

### Execution Model
- **Desktop bots:** Run on self-hosted Windows Server runner (`runs-on: [self-hosted, windows]`)
- **Headless bots:** Run on Docker Linux (`runs-on: ubuntu-latest` with Docker)
- **Schedules:** Configured via cron in workflow YAML (default: daily, outside business hours)

### Secrets in GitHub
Stored in **Settings > Secrets and variables > Actions**:
```
BOT_ZMM0164_SAP_CLIENT
BOT_ZMM0164_SAP_USER
BOT_ZMM0164_SAP_PASSWORD
BOT_ZMM0164_OUTPUT_NET_DOMAIN
BOT_ZMM0164_OUTPUT_NET_USER
BOT_ZMM0164_OUTPUT_NET_PASSWORD
```

### Workflow Template (Windows bot)
```yaml
name: Bot ZMM0164
on:
  schedule:
    - cron: '0 6 * * MON-FRI'
  workflow_dispatch:
jobs:
  run:
    runs-on: [self-hosted, windows]
    steps:
      - uses: actions/checkout@v2
      - name: Install dependencies
        run: |
          pip install -r rpa_desktop_win/Bot_sap_zmm0164/requirements.txt
          python -m pywin32_postinstall -install
      - name: Run bot
        env:
          RPA_ENV: production
          BOT_ZMM0164_SAP_CLIENT: ${{ secrets.BOT_ZMM0164_SAP_CLIENT }}
        run: python rpa_desktop_win/Bot_sap_zmm0164/main.py
```

---

## 📖 Key Files Reference

| Path | Purpose | Type |
|------|---------|------|
| `README.md` | Monorepo architecture, naming conventions | Reference |
| `rpa_desktop_win/Bot_sap_zmm0164/ARQUITECTURA.md` | 3-layer DDD pattern diagram | Reference |
| `rpa_desktop_win/Bot_sap_zmm0164/REQUISITO_NUEVO.md` | Business requirements + technical specs | Reference |
| `core_shared/security/vault.py` | Secret retrieval (all bots depend on this) | Implementation |
| `rpa_desktop_win/Bot_sap_zmm0164/config.py` | Environment-based configuration template | Template |
| `rpa_desktop_win/Bot_sap_zmm0164/examples_test_example.py` | TDD pattern examples | Template |

---

## ⚠️ Common Pitfalls

| Pitfall | Fix |
|---------|-----|
| Hardcoded credentials in code | Use Vault.get_secret("BOT_*_*") |
| Missing `finally: driver.disconnect()` | SAP hangs on next execution (port stuck) |
| Forgetting `python -m pywin32_postinstall` | COM objects won't register; SAP connection fails |
| Incorrect field IDs (copy-paste from old scripts) | Verify via SAP ABAP/4 debugger → Inspect Object → note exact ID |
| Bot name doesn't follow convention | CI/CD routing breaks; discovery fails |
| SMB mount hardcoded without UNC fallback | Bot fails if network has issues; use fallback strategy |
| Logging SAP passwords/Vault responses | Audit violation; always sanitize secrets in logs |
| Testing adapters without mocking pywin32 | Test environment must have SAP GUI installed (breaks in CI) |

---

## 🚀 Quick Ref: TDD Cycle for SAP Bot

**Phase 1: DOMAIN (Red)**
```python
# test_export_data.py
config = ExportConfig(material_code="4100", output_folder="Z:\\", file_format="XLS")
assert "zmm0164-" in config.filename  # FAILS - class doesn't exist yet
```

**Phase 2: DOMAIN (Green)**
```python
from dataclasses import dataclass
from datetime import date

@dataclass
class ExportConfig:
    material_code: str
    output_folder: str
    file_format: str
    
    @property
    def filename(self):
        return f"zmm0164-{date.today().isoformat()}.xls"
```

**Phase 3: ADAPTER (Red → Green)**
Mock SAP, test driver methods independently.

**Phase 4: USE_CASE (Red → Green)**
Orchestrate adapters; verify workflow sequencing.

**Phase 5: INTEGRATION**
E2E test with real SAP (TEST environment only).

---

## 📝 Documentation Standard

Every new bot should include:
- **REQUISITO.md** → Business requirements (MUST reference domain/area/system)
- **ARQUITECTURA.md** → Diagram of domain → adapters → use_cases
- **README.md** → Quick start (3 steps) + environment variables table
- **QUICK_START.md** → Copy-paste commands to run locally
- **EXTENSIBILIDAD.md** → How to add new transactions (e.g., ZMM0165 from ZMM0164 template)

---

## 🎯 Decision-Making Guide

**Q: Should I create a new bot or extend an existing one?**  
A: Extend if same transaction (ZMM0164 with more materials). Create new if different system/area.

**Q: Where do I put shared logic between bots?**  
A: Extract to `core_shared/` if used by 2+ bots. Keep bot-specific logic in `src/`.

**Q: What if SAP field ID changes in production?**  
A: (1) Update REQUISITO.md with version bump, (2) Add to DETALLES TÉCNICOS table, (3) Test in TEST env first, (4) Deploy with versioned tag.

**Q: How do I test locally without SAP GUI?**  
A: Use `unittest.mock.MagicMock` to simulate SAP GUI COM objects (see `examples_test_example.py`).

---

*For questions or updates, consult REQUISITO_NUEVO.md or ARQUITECTURA.md in the specific bot directory.*

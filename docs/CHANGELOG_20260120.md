# Changelog - 2026-01-20

## 🔧 Refactoring: Soul vs Body Configuration Structure

### 1. Configuration Consolidation
- **Goal**: Clear separation between Persona Identity ("Soul") and Platform Behavior ("Body").
- **Changes**:
    - **Deleted**: `personas/chef_choi/behavior.yaml` (Legacy file).
    - **Merged**: Core behavior settings (modifiers, probability model basics) moved into `personas/chef_choi/identity.yaml` under `behavior` key.
    - **Separated**: Platform-specific settings (Action Ratios, Follow Behavior) verified in `personas/chef_choi/platforms/twitter/behavior.yaml`.

### 2. Engine Logic Updates
- **`PersonaLoader`**:
    - Updated to load `behavior` from `identity.yaml` as the core fallback.
    - Correctly loads platform-specific `behavior.yaml` into `platform_configs`.
- **`BehaviorEngine`**:
    - **Removed**: File I/O operations (`open(...)`) in `__init__`.
    - **Added**: In-memory configuration loading from `active_persona`.
    - **Logic**: Merges Core Config + Platform Config (Platform overrides Core).
- **`FollowEngine`**:
    - **Removed**: File I/O.
    - **Added**: Direct access to `active_persona.platform_configs['twitter']['behavior']`.

## ✨ New Features

### 1. Relevance Cut-off Logic
- **Context**: Previously, the agent selected the best candidate from 8 posts even if the score was very low (e.g., 0.1), leading to low-quality interactions.
- **Implementation**:
    - Location: `agent/bot.py` -> `scout_and_respond`
    - Logic: Added a **Score Threshold (0.4)** check after selecting the best candidate.
    - Behavior:
        - `Score < 0.4`: **SKIP** interaction (Log: `✂️ Cut-off REJECTED`).
        - `Score >= 0.4`: **PROCEED** to decision (Log: `✅ Cut-off PASSED`).

### 2. Enhanced Logging
- Added explicit visual logs for the cut-off decision process to aid debugging and monitoring.

## 🧹 Maintenance
- Cleaned up root directory test scripts (`test_*.py`, `debug_*.py`) -> moved to `_archive/legacy_tests`.

---

## 🚀 Phase 24: Home PC Deployment

### 1. Cookie Management Script
- **New**: `scripts/manage_cookies.py`
- Commands: `show`, `import`, `export`
- Usage: `python scripts/manage_cookies.py import cookies.json`

### 2. Multi-Persona Support
- **Updated**: `agent/persona/persona_loader.py`
- `PERSONA_NAME` 환경변수로 페르소나 선택 (config 파일 우선순위 오버라이드)
- Usage: `PERSONA_NAME=chef_choi python main.py`

### 3. Deployment Decision
- **결정**: Proxy/Docker/VPN 제외, 집 PC에서 screen으로 3개 봇 운영
- **이유**: 3개 스케일에서는 오버엔지니어링, 같은 IP에서 독립 활동은 리스크 낮음


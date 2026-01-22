"""
Persona Loader
폴더 기반 페르소나 로딩 / Folder-based persona loading
"""
import yaml
import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional

PERSONAS_DIR = "personas"


@dataclass
class DomainConfig:
    name: str                      # 전문 분야명 (예: "요리")
    keywords: List[str]            # 관련 키워드
    perspective: str               # LLM 프롬프트용 관점 (예: "요리사 관점에서")
    relevance_desc: str            # 분석 결과 설명 (예: "요리/음식 관련도")
    fallback_topics: List[str]     # 트렌드 실패 시 fallback


@dataclass
class PersonaConfig:
    id: str
    name: str
    identity: str
    occupation: str
    core_keywords: List[str]
    time_keywords: Dict[str, List[str]] = field(default_factory=dict)
    system_prompt: str = ""
    engagement_rules: str = ""
    agent_goal: str = ""
    agent_description: str = ""
    domain: DomainConfig = None
    speech_style: Dict = field(default_factory=dict)
    behavior: Dict = field(default_factory=dict)
    relationships: Dict = field(default_factory=dict)
    core_relationships: Dict = field(default_factory=dict)
    mood: Dict = field(default_factory=dict)
    platform_configs: Dict = field(default_factory=dict)
    signature_series: Dict = field(default_factory=dict)
    raw_data: Dict = field(default_factory=dict)


class PersonaLoader:

    @staticmethod
    def get_persona_dir(persona_name: str) -> str:
        """페르소나 폴더 경로"""
        return os.path.join(PERSONAS_DIR, persona_name)

    @staticmethod
    def load_active_persona() -> PersonaConfig:
        """활성 페르소나 로드 (환경변수 또는 config 기반)"""
        persona_name = get_active_persona_name()
        return PersonaLoader.load_persona(persona_name)

    @staticmethod
    def _read_yaml(path: str) -> Dict:
        """YAML 파일 안전하게 읽기"""
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                print(f"[PersonaLoader] Failed to read {path}: {e}")
        return {}

    @staticmethod
    def load_persona(persona_name: str) -> PersonaConfig:
        """특정 페르소나 로드 (신구 구조 모두 지원)"""
        persona_dir = PersonaLoader.get_persona_dir(persona_name)
        if not os.path.exists(persona_dir):
            raise FileNotFoundError(f"Persona directory not found: {persona_dir}")

        # 1. Core Meta Data (identity.yaml 또는 persona.yaml)
        identity = PersonaLoader._read_yaml(os.path.join(persona_dir, "identity.yaml"))
        if not identity:
            # 레거시 호환: persona.yaml
            identity = PersonaLoader._read_yaml(os.path.join(persona_dir, "persona.yaml"))
        
        if not identity:
            raise ValueError(f"No identity.yaml or persona.yaml found in {persona_dir}")

        # 2. Speech Style (speech_style.yaml 또는 identity 내 포함)
        speech_style = PersonaLoader._read_yaml(os.path.join(persona_dir, "speech_style.yaml"))
        if not speech_style:
            speech_style = identity.get('speech_style', {})

        # 3. Mood & Schedule (mood.yaml 또는 behavior 내 포함)
        mood = PersonaLoader._read_yaml(os.path.join(persona_dir, "mood.yaml"))
        
        # 4. Relationships (core_relationships.yaml 또는 relationships.yaml)
        core_relationships = PersonaLoader._read_yaml(os.path.join(persona_dir, "core_relationships.yaml"))
        if not core_relationships:
            core_relationships = PersonaLoader._read_yaml(os.path.join(persona_dir, "relationships.yaml"))

        # 5. Prompts
        prompt_filename = identity.get('system_prompt_file', 'prompt.txt')
        prompt_path = os.path.join(persona_dir, prompt_filename)
        system_prompt = ""
        if os.path.exists(prompt_path):
            with open(prompt_path, 'r', encoding='utf-8') as f:
                system_prompt = f.read()

        rules_filename = identity.get('engagement_rules_file', 'rules.txt')
        rules_path = os.path.join(persona_dir, rules_filename)
        engagement_rules = ""
        if os.path.exists(rules_path):
            with open(rules_path, 'r', encoding='utf-8') as f:
                engagement_rules = f.read()

        # 6. Behavior (Core Engine Logic)
        behavior_path = os.path.join(persona_dir, "behavior.yaml")
        if os.path.exists(behavior_path):
             behavior = PersonaLoader._read_yaml(behavior_path)
        else:
             # Fallback to behavior defined in identity.yaml
             behavior = identity.get('behavior', {})

        # 7. Platform Specifics
        platform_configs = {}
        platforms_dir = os.path.join(persona_dir, "platforms")
        if os.path.exists(platforms_dir) and os.path.isdir(platforms_dir):
            for platform in os.listdir(platforms_dir):
                platform_path = os.path.join(platforms_dir, platform)
                if not os.path.isdir(platform_path): continue
                
                p_cfg = {'modes': {}}
                
                # platform.yaml (legacy) or config.yaml (new)
                p_cfg['config'] = PersonaLoader._read_yaml(os.path.join(platform_path, "config.yaml"))
                if not p_cfg['config']:
                    p_cfg['config'] = PersonaLoader._read_yaml(os.path.join(platform_path, "platform.yaml"))
                
                # activity.yaml (Social v2 통합 설정)
                p_cfg['activity'] = PersonaLoader._read_yaml(os.path.join(platform_path, "activity.yaml"))

                # behavior.yaml (platform specific override)
                p_cfg['behavior'] = PersonaLoader._read_yaml(os.path.join(platform_path, "behavior.yaml"))
                
                # modes/
                modes_dir = os.path.join(platform_path, "modes")
                if os.path.exists(modes_dir) and os.path.isdir(modes_dir):
                    for mode in os.listdir(modes_dir):
                        mode_path = os.path.join(modes_dir, mode)
                        if not os.path.isdir(mode_path): continue
                        
                        p_cfg['modes'][mode] = {}
                        for filename in [f for f in os.listdir(mode_path) if f.endswith('.yaml')]:
                            role = filename[:-5]
                            p_cfg['modes'][mode][role] = PersonaLoader._read_yaml(os.path.join(mode_path, filename))
                
                platform_configs[platform] = p_cfg

        # 8. Signature Series mapping
        signature_series = {}
        for platform, p_cfg in platform_configs.items():
            if 'series' in p_cfg['modes']:
                signature_series[platform] = p_cfg['modes']['series']

        # 9. Domain
        domain_data = identity.get('domain', {})
        domain = DomainConfig(
            name=domain_data.get('name', '일반'),
            keywords=domain_data.get('keywords', identity.get('core_keywords', [])),
            perspective=domain_data.get('perspective', f"{identity.get('occupation', '')} 관점에서"),
            relevance_desc=domain_data.get('relevance_desc', '관련도'),
            fallback_topics=domain_data.get('fallback_topics', identity.get('core_keywords', [])[:3])
        )

        return PersonaConfig(
            id=persona_name,
            name=identity.get('name', persona_name),
            identity=identity.get('identity', ''),
            occupation=identity.get('occupation', ''),
            core_keywords=identity.get('core_keywords', []),
            time_keywords=identity.get('time_keywords', mood.get('time_keywords', behavior.get('time_keywords', {}))),
            agent_goal=identity.get('agent_goal', ''),
            agent_description=identity.get('agent_description', ''),
            system_prompt=system_prompt,
            engagement_rules=engagement_rules,
            domain=domain,
            speech_style=speech_style,
            behavior=behavior,
            relationships=core_relationships,
            core_relationships=core_relationships,
            mood=mood,
            platform_configs=platform_configs,
            signature_series=signature_series,
            raw_data=identity
        )

    @staticmethod
    def list_personas() -> List[str]:
        """사용 가능한 페르소나 목록"""
        personas = []
        if os.path.exists(PERSONAS_DIR):
            for name in os.listdir(PERSONAS_DIR):
                persona_dir = os.path.join(PERSONAS_DIR, name)
                if os.path.isdir(persona_dir) and not name.startswith('_'):
                    persona_yaml = os.path.join(persona_dir, "persona.yaml")
                    if os.path.exists(persona_yaml):
                        personas.append(name)
        return personas


def get_active_persona_name() -> str:
    """활성 페르소나 이름 반환 (환경변수 우선, 없으면 config 사용)"""
    # 1. 환경변수 PERSONA_NAME이 있으면 우선 사용
    env_persona = os.environ.get('PERSONA_NAME')
    if env_persona:
        return env_persona
    
    # 2. Fallback: config/active_persona.yaml
    active_config_path = "config/active_persona.yaml"
    with open(active_config_path, 'r', encoding='utf-8') as f:
        active_config = yaml.safe_load(f)
    return active_config['active']


# Global instance
active_persona_name = get_active_persona_name()
# 환경변수 설정 (다른 모듈에서 쿠키 경로 등에 사용)
os.environ['PERSONA_NAME'] = active_persona_name
active_persona = PersonaLoader.load_active_persona()

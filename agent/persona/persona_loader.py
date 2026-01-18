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
    time_keywords: Dict[str, List[str]]
    system_prompt: str
    engagement_rules: str
    agent_goal: str
    agent_description: str
    domain: DomainConfig = None
    speech_style: Dict = field(default_factory=dict)
    behavior: Dict = field(default_factory=dict)
    relationships: Dict = field(default_factory=dict)
    signature_series: Dict = field(default_factory=dict)
    raw_data: Dict = field(default_factory=dict)


class PersonaLoader:

    @staticmethod
    def get_persona_dir(persona_name: str) -> str:
        """페르소나 폴더 경로"""
        return os.path.join(PERSONAS_DIR, persona_name)

    @staticmethod
    def load_active_persona() -> PersonaConfig:
        """활성 페르소나 로드"""
        active_config_path = "config/active_persona.yaml"
        with open(active_config_path, 'r', encoding='utf-8') as f:
            active_config = yaml.safe_load(f)

        persona_name = active_config['active']
        return PersonaLoader.load_persona(persona_name)

    @staticmethod
    def load_persona(persona_name: str) -> PersonaConfig:
        """특정 페르소나 로드"""
        persona_dir = PersonaLoader.get_persona_dir(persona_name)

        # 필수: persona.yaml
        persona_path = os.path.join(persona_dir, "persona.yaml")
        with open(persona_path, 'r', encoding='utf-8') as f:
            persona_data = yaml.safe_load(f)

        # prompt.txt (같은 폴더 내)
        prompt_filename = persona_data.get('system_prompt_file', 'prompt.txt')
        prompt_path = os.path.join(persona_dir, prompt_filename)
        with open(prompt_path, 'r', encoding='utf-8') as f:
            system_prompt = f.read()

        # rules.txt (같은 폴더 내)
        rules_filename = persona_data.get('engagement_rules_file', 'rules.txt')
        rules_path = os.path.join(persona_dir, rules_filename)
        with open(rules_path, 'r', encoding='utf-8') as f:
            engagement_rules = f.read()

        # 선택: behavior.yaml
        behavior = {}
        behavior_path = os.path.join(persona_dir, "behavior.yaml")
        if os.path.exists(behavior_path):
            with open(behavior_path, 'r', encoding='utf-8') as f:
                behavior = yaml.safe_load(f) or {}

        # 선택: relationships.yaml
        relationships = {}
        relationships_path = os.path.join(persona_dir, "relationships.yaml")
        if os.path.exists(relationships_path):
            with open(relationships_path, 'r', encoding='utf-8') as f:
                relationships = yaml.safe_load(f) or {}

        # 선택: platforms/{platform}/modes/{mode}/*.yaml (새 구조)
        # 또는 signature_series/{platform}/*.yaml (레거시)
        platform_configs = {}
        
        # 새 구조: platforms/
        platforms_dir = os.path.join(persona_dir, "platforms")
        if os.path.exists(platforms_dir) and os.path.isdir(platforms_dir):
            for platform in os.listdir(platforms_dir):
                platform_path = os.path.join(platforms_dir, platform)
                if not os.path.isdir(platform_path):
                    continue
                    
                platform_configs[platform] = {'modes': {}}
                
                # platform.yaml 로드
                platform_yaml = os.path.join(platform_path, "platform.yaml")
                if os.path.exists(platform_yaml):
                    with open(platform_yaml, 'r', encoding='utf-8') as f:
                        platform_configs[platform]['config'] = yaml.safe_load(f) or {}
                
                # modes/ 하위 디렉토리
                modes_dir = os.path.join(platform_path, "modes")
                if os.path.exists(modes_dir) and os.path.isdir(modes_dir):
                    for mode in os.listdir(modes_dir):
                        mode_path = os.path.join(modes_dir, mode)
                        if not os.path.isdir(mode_path):
                            continue
                            
                        platform_configs[platform]['modes'][mode] = {}
                        for filename in os.listdir(mode_path):
                            if filename.endswith(".yaml"):
                                role = filename[:-5]
                                file_path = os.path.join(mode_path, filename)
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    platform_configs[platform]['modes'][mode][role] = yaml.safe_load(f) or {}
        
        # 레거시 지원: signature_series (새 구조가 없을 때만)
        signature_series = {}
        if not platform_configs:
            series_dir = os.path.join(persona_dir, "signature_series")
            if os.path.exists(series_dir) and os.path.isdir(series_dir):
                for platform in os.listdir(series_dir):
                    platform_path = os.path.join(series_dir, platform)
                    if os.path.isdir(platform_path):
                        signature_series[platform] = {}
                        for filename in os.listdir(platform_path):
                            if filename.endswith(".yaml"):
                                role = filename[:-5]
                                file_path = os.path.join(platform_path, filename)
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    signature_series[platform][role] = yaml.safe_load(f) or {}
        else:
            # 새 구조에서 series 모드를 signature_series로 매핑 (하위 호환)
            for platform, cfg in platform_configs.items():
                if 'series' in cfg.get('modes', {}):
                    signature_series[platform] = cfg['modes']['series']

        # Domain 설정 로드
        domain_data = persona_data.get('domain', {})
        domain = DomainConfig(
            name=domain_data.get('name', '일반'),
            keywords=domain_data.get('keywords', persona_data.get('core_keywords', [])),
            perspective=domain_data.get('perspective', f"{persona_data.get('occupation', '')} 관점에서"),
            relevance_desc=domain_data.get('relevance_desc', '관련도'),
            fallback_topics=domain_data.get('fallback_topics', persona_data.get('core_keywords', [])[:3])
        )

        return PersonaConfig(
            id=persona_name,
            name=persona_data['name'],
            identity=persona_data['identity'],
            occupation=persona_data['occupation'],
            core_keywords=persona_data.get('core_keywords', []),
            time_keywords=persona_data.get('time_keywords', {}),
            system_prompt=system_prompt,
            engagement_rules=engagement_rules,
            agent_goal=persona_data.get('agent_goal', ''),
            agent_description=persona_data.get('agent_description', ''),
            domain=domain,
            speech_style=persona_data.get('speech_style', {}),
            behavior=behavior,
            relationships=relationships,
            signature_series=signature_series,
            raw_data=persona_data
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
    """활성 페르소나 이름만 반환"""
    active_config_path = "config/active_persona.yaml"
    with open(active_config_path, 'r', encoding='utf-8') as f:
        active_config = yaml.safe_load(f)
    return active_config['active']


# Global instance
active_persona_name = get_active_persona_name()
active_persona = PersonaLoader.load_active_persona()

"""
Series Engine
시리즈 시스템 메인 오케스트레이터
"""
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import random

from agent.persona.persona_loader import PersonaConfig
from agent.platforms.twitter.modes.series.planner import SeriesPlanner
from agent.platforms.twitter.modes.series.writer import ContentWriter
from agent.platforms.twitter.modes.series.archiver import SeriesArchiver
from agent.platforms.twitter.modes.series.studio import ImageGenerator, ImageCritic
from agent.platforms.twitter.modes.series.adapters.twitter import TwitterAdapter

class SeriesEngine:
    def __init__(self, persona: PersonaConfig):
        self.persona = persona
        self.config = persona.signature_series
        self.planner = SeriesPlanner(persona.id)
        self.content_writer = ContentWriter(persona)
        self.archiver = SeriesArchiver(persona.id)
        self.generator = ImageGenerator()
        self.critic = ImageCritic()
        
        self.adapters = {
            'twitter': TwitterAdapter()
            # 'blog': BlogAdapter(),
        }

    def get_enabled_platforms(self) -> List[str]:
        # planner.yaml에 설정이 있고 enabled인 경우 활성 플랫폼으로 간주
        return [p for p, cfg in self.config.items() if cfg.get('planner', {}).get('enabled', True)]

    def is_due(self, platform: str, series_id: str) -> bool:
        """
        해당 시리즈가 게시될 타이밍인지 확인
        frequency + time_variance 고려
        """
        platform_config = self.config.get(platform, {})
        planner_config = platform_config.get('planner', {})
        series_list = planner_config.get('series', [])
        series = next((s for s in series_list if s['id'] == series_id), None)
        
        if not series:
            return False
            
        freq_str = series.get('frequency', '1d')
        
        last_str = self.planner.get_last_used_at(platform, series)
        last_used = datetime.fromisoformat(last_str) if last_str else None
        
        if not last_used:
            return True 
            
        hours = 24
        if freq_str.endswith('d'):
            hours = int(freq_str[:-1]) * 24
        elif freq_str.endswith('h'):
            hours = int(freq_str[:-1])
            
        variance_str = series.get('time_variance', '0h')
        var_hours = 0
        if variance_str.endswith('h'):
            var_hours = int(variance_str[:-1])
            
        next_due = last_used + timedelta(hours=hours)
        min_due = next_due - timedelta(hours=var_hours)
        
        now = datetime.now()
        if now >= min_due:
            return True
        return False

    def execute(self, platform: str) -> Optional[Dict]:
        """시리즈 실행 (랜덤 선택)"""
        platform_config = self.config.get(platform)
        if not platform_config:
            return None
            
        planner_config = platform_config.get('planner', {})
        series_list = planner_config.get('series', [])
        candidates = []
        for s in series_list:
            if self.is_due(platform, s['id']):
                candidates.append(s)
                
        if not candidates:
            return None
            
        series = random.choice(candidates)
        return self.execute_specific_series(platform, series)

    def execute_specific_series(self, platform: str, series_config: Dict) -> Optional[Dict]:
        """특정 시리즈 실행"""
        series_id = series_config['id']
        series_name = series_config['name']
        
        print(f"[SeriesEngine] Executing series: {series_name} on {platform}")
        
        # 1. 기획 (Planner)
        plan = self.planner.plan_next_episode(platform, series_config)
        if not plan:
            print(f"[SeriesEngine] No topics available for {series_name}")
            return None
            
        topic = plan['topic']
        
        # 2. 콘텐츠 생성 (Writer) - writer.yaml에서 해당 시리즈의 프롬프트 로드
        writer_config = self.config.get(platform, {}).get('writer', {})
        series_writer_prompt = writer_config.get('series_prompts', {}).get(series_id, {})
        
        # template 필드를 writer_prompt로 대체하여 전달
        content = self.content_writer.write(series_name, topic, series_writer_prompt)
        
        # 3. 이미지 생성 (Studio) - studio.yaml 활용
        studio_config = self.config.get(platform, {}).get('studio', {})
        images = []
        image_prompt_tmpl = studio_config.get('image_prompts', {}).get(series_id)
        
        if image_prompt_tmpl:
            prompt = image_prompt_tmpl.replace('{topic}', topic)
            print(f"[SeriesEngine] Generating images for prompt: {prompt[:30]}...")
            
            # A. Generate
            candidates = self.generator.generate(prompt, count=4)
            
            if candidates:
                # B. Save Candidates
                for i, img_bytes in enumerate(candidates):
                    self.archiver.save_asset(series_id, topic, f"candidate_{i+1}.png", img_bytes)
                
                # C. Critique - studio.yaml의 critic 가이드 사용
                critic_config = studio_config.get('critic', {})
                art_director_prompt = critic_config.get('system_prompt', "You are an expert Art Director.")
                criteria = critic_config.get('criteria', "Appetizing, Realistic, High Quality")

                result = self.critic.evaluate(candidates, topic, criteria, art_director_prompt)
                best_idx = result.get('selected_index', 0)
                
                # D. Finalize
                final_bytes = candidates[best_idx]
                final_path = self.archiver.save_asset(series_id, topic, "final.png", final_bytes)
                images.append(final_path)
                
                plan['image_critique'] = result
                print(f"[SeriesEngine] Image selected (idx={best_idx}): {final_path}")
            else:
                print("[SeriesEngine] Image generation returned no results.")

        # 4. 게시 (Adapter)
        adapter = self.adapters.get(platform)
        if not adapter:
            print(f"[SeriesEngine] No adapter for {platform}")
            return None
            
        # adapter.publish는 이미지 경로 리스트를 받아야 함
        # template 대신 planner 내의 series 설정을 전달
        result = adapter.publish(content, images, series_config)
        
        # 5. 아카이빙 (Archiver)
        if result:
            self.archiver.update_history(platform, series_id, topic)
            self.archiver.log_episode(platform, series_id, {
                "topic": topic,
                "plan": plan,
                "content": content,
                "images": images,
                "result": result
            })
            print(f"[SeriesEngine] Published & Archived: {result}")
            
        return result

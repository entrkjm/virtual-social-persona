"""
Series Engine
시리즈 시스템 메인 오케스트레이터
"""
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import random

from agent.persona.persona_loader import PersonaConfig
from agent.series.planner import SeriesPlanner
from agent.series.writer import ContentWriter
from agent.series.archiver import SeriesArchiver
from agent.series.studio import ImageGenerator, ImageCritic
from agent.series.adapters.twitter import TwitterAdapter

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
        return [p for p, cfg in self.config.items() if cfg.get('enabled')]

    def is_due(self, platform: str, series_id: str) -> bool:
        """
        해당 시리즈가 게시될 타이밍인지 확인
        frequency + time_variance 고려
        """
        platform_config = self.config.get(platform, {})
        series_list = platform_config.get('series', [])
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
            
        series_list = platform_config.get('series', [])
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
        
        # 2. 콘텐츠 생성 (Writer)
        content = self.content_writer.write(series_name, topic, series_config['template'])
        
        # 3. 이미지 생성 (Studio)
        images = []
        image_prompt_tmpl = series_config.get('template', {}).get('image_prompt')
        
        if image_prompt_tmpl:
            prompt = image_prompt_tmpl.replace('{topic}', topic)
            print(f"[SeriesEngine] Generating images for prompt: {prompt[:30]}...")
            
            # A. Generate
            candidates = self.generator.generate(prompt, count=4)
            
            if candidates:
                # B. Save Candidates
                for i, img_bytes in enumerate(candidates):
                    self.archiver.save_asset(series_id, topic, f"candidate_{i+1}.png", img_bytes)
                
                # C. Critique
                result = self.critic.evaluate(candidates, topic, "Appetizing, Realistic, High Quality")
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
        result = adapter.publish(content, images, series_config['template'])
        
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

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
        # config.yaml에 설정이 있고 enabled인 경우 활성 플랫폼으로 간주
        return [p for p, cfg in self.config.items() if cfg.get('config', {}).get('enabled', True)]

    def is_due(self, platform: str, series_id: str) -> bool:
        """
        해당 시리즈가 게시될 타이밍인지 확인
        frequency + time_variance 고려
        """
        platform_config = self.config.get(platform, {})
        series_config = platform_config.get('config', {})
        series_list = series_config.get('series', [])
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
            
        series_config = platform_config.get('config', {})
        series_list = series_config.get('series', [])
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
        
        # 2. 콘텐츠 생성 (Writer) - style.yaml에서 해당 시리즈의 프롬프트 로드
        writer_config = self.config.get(platform, {}).get('style', {})
        series_writer_prompt = writer_config.get('series_prompts', {}).get(series_id, {})
        
        # template 필드를 writer_prompt로 대체하여 전달
        content = self.content_writer.write(series_name, topic, series_writer_prompt)
        
        # 3. 이미지 생성 (Dynamic Multi-Prompt)
        studio_config = self.config.get(platform, {}).get('studio', {})
        prompt_guide = studio_config.get('prompt_guide', {})
        
        # Context Injection (Season, Time)
        now = datetime.now()
        season = self._get_season(now.month)
        time_of_day = "Morning" if 6 <= now.hour < 12 else "Afternoon" if 12 <= now.hour < 18 else "Evening"
        context_str = f"Season: {season}, Time: {time_of_day}, Series: {series_name}"
        
        images = []
        selected_index = 0
        prompts = []

        if prompt_guide:
            # A. Create Dynamic Prompts
            print(f"[SeriesEngine] Creating dynamic image prompts for: {topic}")
            prompts = self.generator.create_dynamic_prompts(topic, context_str, prompt_guide)
            
            # B. Generate Images (Parallel-ish) in loop
            candidates = []
            for i, p in enumerate(prompts):
                print(f"  > Prompt {i+1}: {p[:40]}...")
                # generator.generate returns list, we take the first/only one in this call pattern
                generated_batch = self.generator.generate(p, count=1) 
                if generated_batch:
                    candidates.append(generated_batch[0])
                    # Save candidate
                    self.archiver.save_asset(series_id, topic, f"candidate_{i}.png", generated_batch[0])
            
            if candidates:
                # 4. Review & Select (Reviewer)
                from agent.platforms.twitter.modes.series.reviewer import SeriesReviewer
                reviewer = SeriesReviewer()
                
                # Retrieve Review Criteria from studio.yaml
                critic_config = studio_config.get('critic', {})
                review_criteria = critic_config.get('criteria', "Authenticity, Realism")
                
                print("[SeriesEngine] Reviewing content (Text + Image)...")
                refined_text, best_idx, review_meta = reviewer.review_content(
                    draft_text=content,
                    image_prompts=prompts,
                    criteria=review_criteria
                )
                
                # Apply refined text
                content = refined_text
                selected_index = best_idx
                
                # Save Final Image
                if 0 <= selected_index < len(candidates):
                    final_bytes = candidates[selected_index]
                    final_path = self.archiver.save_asset(series_id, topic, "final.png", final_bytes)
                    images.append(final_path)
                    print(f"[SeriesEngine] Selected Image {selected_index}: {final_path}")
                
                plan['review_result'] = review_meta
            else:
                print("[SeriesEngine] No images generated.")

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

    def _get_season(self, month: int) -> str:
        if 3 <= month <= 5: return "Spring"
        if 6 <= month <= 8: return "Summer"
        if 9 <= month <= 11: return "Autumn"
        return "Winter"

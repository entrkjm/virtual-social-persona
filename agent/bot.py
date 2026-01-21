"""
SocialAgent - Main Workflow Orchestration
Scout → Perceive → Behavior → Judge → Action
"""
from game_sdk.game.custom_types import Function, Argument, FunctionResultStatus, FunctionResult
from config.settings import settings
from actions.market_data import get_market_data
from agent.platforms.interface import SocialPlatformAdapter, SocialPost
# Trends removed for decoupling, to be added to adapter later
from core.llm import llm_client
from agent.persona.persona_loader import active_persona
from agent.memory import agent_memory
from agent.persona.relationship_manager import initialize_relationship_manager
from agent.core.interaction_intelligence import interaction_intelligence
from agent.core.behavior_engine import behavior_engine, human_like_controller
from agent.core.follow_engine import follow_engine
from agent.platforms.twitter.modes.casual.post_generator import CasualPostGenerator
from agent.platforms.twitter.modes.social_legacy.reply_generator import SocialReplyGenerator
from agent.platforms.twitter.modes.social import SocialEngineV2
from typing import Tuple, Dict, Any, Optional, List
from datetime import datetime
import random
import uuid
import time
import os

# Dynamic Memory (v2)
from agent.memory.factory import MemoryFactory  # Changed import
from agent.memory.database import Episode, generate_id
from agent.memory.inspiration_pool import InspirationPool
from agent.memory.tier_manager import TierManager
from agent.memory.consolidator import MemoryConsolidator
from agent.platforms.twitter.modes.casual.trigger_engine import PostingTriggerEngine
from agent.core.topic_selector import TopicSelector
from agent.knowledge.knowledge_base import knowledge_base
from agent.platforms.twitter.modes.series.engine import SeriesEngine
from agent.persona.pattern_tracker import PatternTracker
from agent.core.logger import logger

class SocialAgent:
    def __init__(self, adapter: SocialPlatformAdapter):
        self.adapter = adapter
        self.persona = active_persona
        self.name = self.persona.name
        
        # Initialize Memory for this Persona
        # Note: persona.id is the directory name (e.g., 'chef_choi')
        self.memory_db = MemoryFactory.get_memory_db(self.persona.id)
        self.vector_store = MemoryFactory.get_vector_store(self.persona.id)
        
        # Dependency Injection needed for sub-components (will need to refactor them too)
        # For now, assigning to instance variables
        
        self.relationship_manager = initialize_relationship_manager(
            persona_name=self.persona.name,
            memory_instance=agent_memory
        )
        # Mode-specific content generators
        platform_config = self.persona.signature_series.get('twitter', {}).get('config', {})
        social_mode_cfg = self.persona.platform_configs.get('twitter', {}).get('modes', {}).get('social', {})
        # Merge 'config' and 'behavior' from social mode if they exist for better visibility in generator
        social_full_cfg = {}
        if isinstance(social_mode_cfg, dict):
             social_full_cfg.update(social_mode_cfg.get('config', {}))
             social_full_cfg.update(social_mode_cfg.get('behavior', {}))
             # Preserve any other root keys like 'style' or 'quip_pool' if they were moved
             for k, v in social_mode_cfg.items():
                 if k not in ['config', 'behavior']: # 'style' should be preserved if it's a root key
                     social_full_cfg[k] = v

        self.post_generator = CasualPostGenerator(self.persona, platform_config)
        self.reply_generator = SocialReplyGenerator(self.persona, social_full_cfg)
        self.full_system_prompt = self.persona.system_prompt

        # Inject mode-specific behavior config into engine
        social_behavior_cfg = social_mode_cfg.get('behavior', {})
        if social_behavior_cfg:
             behavior_engine.update_config(social_behavior_cfg)
             print(f"[BOT] Behavior engine updated with social mode config")
        
        # Initialize Sub-components with DI
        self.tier_manager = TierManager() # tier_manager might be stateless or need Config? Assuming stateless for now or default
        self.inspiration_pool = InspirationPool(
            db=self.memory_db,
            vector_store=self.vector_store,
            tier_manager=self.tier_manager
        )
        self.memory_consolidator = MemoryConsolidator(
            db=self.memory_db,
            vector_store=self.vector_store,
            tier_manager=self.tier_manager
        )
        self.posting_trigger = PostingTriggerEngine(
            db=self.memory_db,
            inspiration_pool=self.inspiration_pool
        )
        self.pattern_tracker = PatternTracker(
            db=self.memory_db,
            pattern_registry=self.persona.raw_data.get('pattern_registry')
        )
        self.topic_selector = TopicSelector()
        
        # Core Intelligence Injection
        self.interaction_intelligence = interaction_intelligence
        self.follow_engine = follow_engine
        
        # Series Engine 초기화
        self.series_engine = SeriesEngine(self.persona)

        # Social Engine V2 (experimental)
        self.use_social_v2 = settings.USE_SOCIAL_V2
        self.social_engine_v2 = None
        if self.use_social_v2:
            self._init_social_v2()

    def _init_social_v2(self):
        """Initialize Social Engine V2 (notification-centric, scenario-based)"""
        activity_cfg = self.persona.platform_configs.get('twitter', {}).get('activity', {})
        persona_config = {
            'identity': {
                'core_keywords': self.persona.core_keywords,
                'search_keywords': getattr(self.persona, 'search_keywords', [])
            },
            'activity': activity_cfg
        }
        self.social_engine_v2 = SocialEngineV2(
            persona_id=self.persona.id,
            persona_config=persona_config,
            platform='twitter'
        )
        logger.info("[BOT] Social Engine V2 initialized")

    def _get_current_mood(self):
        """시간대별 기분 / Time-based mood"""
        hour = datetime.now().hour
        mood_desc = self.persona.behavior.get('mood_descriptions', {})

        if 6 <= hour < 11:
            return mood_desc.get('morning', '아침')
        elif 11 <= hour < 14:
            return mood_desc.get('lunch', '점심')
        elif 14 <= hour < 17:
            return mood_desc.get('afternoon', '오후')
        elif 17 <= hour < 21:
            return mood_desc.get('dinner', '저녁')
        else:
            return mood_desc.get('late_night', '밤')

    def _calculate_emotional_impact(self, perception: Dict) -> float:
        base_impact = 0.5
        sentiment = perception.get('sentiment', 'neutral')
        if sentiment == 'positive':
            base_impact += 0.2
        elif sentiment == 'negative':
            base_impact += 0.1  # 부정적이어도 강한 반응

        # 주제가 관심사와 관련 있으면 임팩트 상승
        topics = perception.get('topics', [])
        obsession_topics = self.persona.core_keywords if hasattr(self.persona, 'core_keywords') else []
        for topic in topics:
            if any(obs.lower() in topic.lower() for obs in obsession_topics):
                base_impact += 0.3
                break

        # 의도가 질문이면 관심 상승
        intent = perception.get('intent', '')
        if 'question' in intent.lower() or '질문' in intent:
            base_impact += 0.1

        return min(1.0, base_impact)

    def _calculate_tweet_score(self, tweet: Dict, perception: Dict) -> float:
        """트윗 상호작용 적합도 점수 (0.0 ~ 1.0)

        가중치:
        - 관련도 50%: 페르소나 전문 분야와의 관련성
        - 인기도 30%: engagement 지표 (likes + retweets*2)
        - 복잡도 20%: 깊은 대화 가능성
        """
        score = 0.0

        # 1. 관련도 (50%) - perception의 relevance_to_domain 사용
        relevance = perception.get('relevance_to_domain', 0.0)
        score += relevance * 0.5

        # 2. 인기도 (30%) - engagement 기반
        engagement = tweet.get('engagement', {})
        likes = engagement.get('favorite_count', 0)
        retweets = engagement.get('retweet_count', 0)
        # 50개 기준 정규화, retweet은 2배 가중
        popularity = min(1.0, (likes + retweets * 2) / 50)
        score += popularity * 0.3

        # 3. 복잡도 (20%) - 깊은 대화 가능성
        complexity = perception.get('complexity', 'moderate')
        if complexity == 'complex':
            score += 0.2
        elif complexity == 'moderate':
            score += 0.1
        # simple은 0점

        return score

    def _record_episode(self, tweet: Dict, perception: Dict, emotional_impact: float) -> Episode:
        episode = Episode(
            id=generate_id(),
            timestamp=datetime.now(),
            type='saw_tweet',
            source_id=tweet.get('id'),
            source_user=tweet.get('user'),
            content=tweet.get('text', ''),
            topics=perception.get('topics', []),
            sentiment=perception.get('sentiment', 'neutral'),
            emotional_impact=emotional_impact
        )
        self.memory_db.add_episode(episode)
        return episode


    def _create_inspiration_from_episode(
        self,
        episode: Episode,
        my_angle: str,
        urgency: str = 'brewing'
    ) -> Optional[str]:
        insp = self.inspiration_pool.create_inspiration_from_episode(
            episode=episode,
            my_angle=my_angle,
            urgency=urgency
        )
        return insp.id if insp else None

    def get_state_fn(self, function_result: FunctionResult, current_state: dict) -> dict:
        """현재 상태 + 3-Layer 시스템 프롬프트 생성"""
        print("[DEBUG] get_state_fn: Checking consolidator...", flush=True)
        if self.memory_consolidator.should_run(interval_hours=settings.CONSOLIDATION_INTERVAL):
            print("[DEBUG] get_state_fn: Running consolidator...", flush=True)
            stats = self.memory_consolidator.run()
            print(f"[MEMORY] +{stats.promoted} promoted, -{stats.deleted} deleted")

        print("[DEBUG] get_state_fn: Getting memory context...", flush=True)
        memory_context = agent_memory.get_recent_context()
        print("[DEBUG] get_state_fn: Getting facts context...", flush=True)
        facts_context = agent_memory.get_facts_context()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mood = self._get_current_mood()

        print("[DEBUG] get_state_fn: Getting top interests...", flush=True)
        top_interests = agent_memory.get_top_interests(limit=10)
        interests_text = ", ".join(top_interests) if top_interests else "없음"

        # Trends removed
        daily_briefing = "트렌드 정보 없음 (Decoupled)"

        print("[DEBUG] get_state_fn: Getting core memories...", flush=True)
        core_memories = self.memory_db.get_all_core_memories()
        core_context = self.tier_manager.get_core_context_for_llm(core_memories)
        print("[DEBUG] get_state_fn: Getting recent posts...", flush=True)
        recent_posts_context = self.memory_db.get_recent_posts_context(limit=5)
        print("[DEBUG] get_state_fn: Contexts loaded.", flush=True)

        self.full_system_prompt = f"""
{self.persona.system_prompt}

### 🛡️ ENGAGEMENT RULES:
{self.persona.engagement_rules}

### 🧠 MEMORY:
{memory_context}
{facts_context}
{core_context}
{recent_posts_context}

### 🕒 CURRENT CONTEXT:
- Time: {now}
- Mood: {mood}

### 🎯 3-LAYER INTELLIGENCE:
- Layer 1 (Core): {self.persona.identity}의 본질적 정체성
- Layer 2 (Curiosity): 최근 관심사 = {interests_text}
- Layer 3 (Trends): {daily_briefing}

당신은 위 3가지 층위의 정보를 조합하여 사고합니다. 페르소나의 특성에 맞게 자연스럽게 표현하세요.
"""

        return {
            "persona_system_prompt": self.persona.system_prompt,
            "mood": mood,
            "current_time": now,
            "interests": top_interests,
            "trends": daily_briefing,
            "core_memories": len(core_memories)
        }

    def post_tweet_executable(self, content: str) -> Tuple[FunctionResultStatus, str, Dict[str, Any]]:
        try:
            # 1. 시그니처 시리즈 체크 (content가 없을 때만)
            print(f"[POST] post_tweet_executable called (content={bool(content)})", flush=True)
            if not content:
                # 트위터 플랫폼 확인
                enabled_platforms = self.series_engine.get_enabled_platforms()
                print(f"[POST] Series enabled platforms: {enabled_platforms}", flush=True)
                if 'twitter' in enabled_platforms:
                    # 시리즈 실행 시도 (랜덤 선택 + 쿨다운 체크)
                    print("[POST] Attempting Series execution...", flush=True)
                    result = self.series_engine.execute('twitter')
                    print(f"[POST] Series result: {result}", flush=True)
                    if result:
                        return FunctionResultStatus.DONE, f"Posted Series: {result}", result
                    else:
                        print("[POST] Series returned None, falling back to Casual Post", flush=True)

            # 2. 일반 포스트 (Casual Post)
            # 토픽 선택 (content가 비어있으면 자동 선택)
            if not content:
                hour = datetime.now().hour
                time_kw_config = self.persona.behavior.get('time_keywords', {})

                if 6 <= hour < 11:
                    time_keywords = time_kw_config.get('morning', [])
                elif 11 <= hour < 14:
                    time_keywords = time_kw_config.get('lunch', [])
                elif 14 <= hour < 17:
                    time_keywords = time_kw_config.get('afternoon', [])
                elif 17 <= hour < 21:
                    time_keywords = time_kw_config.get('dinner', [])
                else:
                    time_keywords = time_kw_config.get('late_night', [])

                if not time_keywords:
                    time_keywords = self.persona.core_keywords

                # 영감 토픽 가져오기
                inspiration_topics = []
                try:
                    for tier in ['short_term', 'long_term']:
                        for insp in self.inspiration_pool.get_by_tier(tier)[:3]:
                            if insp.topic and insp.topic not in inspiration_topics:
                                inspiration_topics.append(insp.topic)
                except:
                    pass

                # 지식 베이스에서 관련 토픽
                knowledge_topics = knowledge_base.get_relevant_topics(min_relevance=0.2, limit=5)

                trend_keywords = knowledge_topics

                topic, source = self.topic_selector.select(
                    core_keywords=self.persona.core_keywords,
                    time_keywords=time_keywords,
                    curiosity_keywords=agent_memory.get_top_interests(limit=10),
                    trend_keywords=knowledge_topics,
                    inspiration_topics=inspiration_topics
                )
                print(f"[POST] topic={topic} (source={source})")
            else:
                topic = content
                source = "user"

            # 지식 컨텍스트 조회
            topic_context = ""
            knowledge = knowledge_base.get(topic)
            if knowledge and knowledge.get('my_angle'):
                topic_context = f"{knowledge.get('summary', '')} / 내 관점: {knowledge['my_angle']}\n"
            
            # 최근 포스트 가져오기 (유사도 체크용)
            recent_posts_data = self.memory_db.get_recent_posts(limit=10)
            recent_posts = [p['content'] for p in recent_posts_data]

            context = {
                'system_prompt': self.full_system_prompt,
                'mood': self._get_current_mood(),
                'interests': agent_memory.get_top_interests(limit=10),
                'topic_context': topic_context
            }
            generated_content = self.post_generator.generate(
                topic=topic,
                context=context,
                recent_posts=recent_posts
            )

            tweet_id = self.adapter.post(generated_content)

            # DB에 포스팅 기록 저장 (유사도 체크용)
            self.memory_db.add_posting(
                inspiration_id=None,
                content=generated_content,
                trigger_type=source
            )

            return FunctionResultStatus.DONE, f"Posted: {generated_content}", {"tweet_id": tweet_id, "topic": topic, "source": source}
        except Exception as e:
            return FunctionResultStatus.FAILED, f"Failed to tweet: {e}", {}

    def check_mentions(self) -> Tuple[FunctionResultStatus, str, Dict[str, Any]]:
        """멘션/답글 확인 및 반응"""
        try:
            can_act, reason = human_like_controller.can_take_action()
            if not can_act:
                print(f"[HUMAN-LIKE] 멘션 액션 제한: {reason}")
                return FunctionResultStatus.DONE, f"SKIP (human-like): {reason}", {'human_like_skip': True}

            # Social V2: Notification Journey
            if self.use_social_v2 and self.social_engine_v2:
                return self._check_mentions_v2()

            mentions = self.adapter.get_mentions(count=10)
            
            if not mentions:
                return FunctionResultStatus.DONE, "No new mentions", {}

            actions_taken = []
            
            for mention in mentions:
                # 1. 지각 (Perception)
                print(f"[MENTION] Analyzing: {mention.text}")
                perception = self.interaction_intelligence.perceive_post(mention)
                
                if perception.get('skipped'):
                    print(f"[MENTION] Skipped: {perception['skip_reason']}")
                    continue

                tweet = {
                    'text': mention.text,
                    'user': mention.user.username
                } # context for judge
                    
                context = {
                    'tweet': tweet,
                    'perception': perception,
                    'relationship': self.relationship_manager.get_relationship_context(mention.user.username),
                    'persona_mood': self._get_current_mood(),
                    'curiosity': agent_memory.get_top_interests(limit=3),
                    'interaction_history': agent_memory.get_recent_episodes(limit=5)
                }

                # 2. 행동 결정 (Decision)
                decision = behavior_engine.should_interact(context)
                should_act = (decision.decision == "INTERACT")
                reason = decision.reason
                actions = decision.actions

                if not should_act:
                    continue

                # 3. 행동 실행 (Execution)
                if actions['like']:
                    try:
                        if self.adapter.like(mention.id):
                            human_like_controller.record_action('like')
                            actions_taken.append("LIKED")
                            human_like_controller.apply_action_delay('like')
                    except Exception as e:
                        logger.error(f"Like failed: {e}")

                reply_content = None
                if actions.get('comment') or actions.get('reply'):
                    # 최근 답글 조회 (다양성 확보용)
                    recent_episodes = agent_memory.get_recent_episodes(limit=10)
                    recent_replies = [e.content for e in recent_episodes if e.type == 'replied']

                    # 답글 생성
                    raw_reply = self.reply_generator.generate(
                        target_tweet=tweet,
                        perception=perception,
                        recent_replies=recent_replies,
                        context={
                            'system_prompt': self.full_system_prompt,
                            'mood': self._get_current_mood(),
                            'interests': agent_memory.get_top_interests(limit=10)
                        }
                    )
                    
                    # 답글 검토 (Reviewer)
                    reply_content = self.social_reviewer.review_reply(mention.text, raw_reply)

                    if reply_content:
                        try:
                            tweet_id = self.adapter.reply(mention.id, reply_content)
                            if tweet_id and "Failed" not in str(tweet_id):
                                human_like_controller.record_action('comment')
                                actions_taken.append(f"REPLIED: {reply_content}")
                                human_like_controller.apply_action_delay('comment')
                                
                                # 에피소드 저장
                                self.memory_db.add_episode(Episode(
                                    id=str(uuid.uuid4()),
                                    timestamp=datetime.now(),
                                    type='replied',
                                    source_id=mention.id,
                                    source_user=mention.user.username,
                                    content=reply_content,
                                    topics=perception['topics'],
                                    sentiment=perception['sentiment'],
                                    emotional_impact=0.6
                                ))
                        except Exception as e:
                            logger.error(f"Reply failed: {e}")

            if not actions_taken:
                return FunctionResultStatus.DONE, f"Processed mention from @{mention.user.username} (no action)", {}

            return FunctionResultStatus.DONE, f"Mention response: {', '.join(actions_taken)}", {"actions": actions_taken}

        except Exception as e:
            if '404' in str(e):
                human_like_controller.handle_error(404)
            return FunctionResultStatus.FAILED, f"Error checking mentions: {e}", {}

    def scout_and_respond(self) -> Tuple[FunctionResultStatus, str, Dict[str, Any]]:
        """Scout → Perceive → Behavior → Judge → Action"""
        try:
            human_like_controller.increment_step()

            can_act, reason = human_like_controller.can_take_action()
            if not can_act:
                logger.info(f"[HUMAN-LIKE] 액션 제한: {reason}")
                return FunctionResultStatus.DONE, f"SKIP (human-like): {reason}", {'human_like_skip': True}

            # Social V2: Feed Journey with posts from adapter
            if self.use_social_v2 and self.social_engine_v2:
                return self._scout_and_respond_v2()

            # SCOUT
            hour = datetime.now().hour
            core_keywords = self.persona.core_keywords
            time_kw_config = self.persona.behavior.get('time_keywords', {})

            if 6 <= hour < 11:
                time_keywords = time_kw_config.get('morning', [])
            elif 11 <= hour < 14:
                time_keywords = time_kw_config.get('lunch', [])
            elif 14 <= hour < 17:
                time_keywords = time_kw_config.get('afternoon', [])
            elif 17 <= hour < 21:
                time_keywords = time_kw_config.get('dinner', [])
            elif 21 <= hour < 24:
                time_keywords = time_kw_config.get('late_night', [])
            else:
                time_keywords = time_kw_config.get('default', [])

            if not time_keywords:
                time_keywords = core_keywords

            curiosity_keywords = agent_memory.get_top_interests(limit=10)

            # Trends Re-enabled
            trend_keywords = []
            if hasattr(self.adapter, 'get_trends'):
                try:
                    trend_keywords = self.adapter.get_trends(location='KR')
                    logger.info(f"[SCOUT] Trends fetched: {trend_keywords[:5]}...")
                except Exception as e:
                    logger.warning(f"[SCOUT] Trends fetch failed: {e}")

            # 0. Check New Followers (Deep Socializing) using simple probability
            if random.random() < 0.2: # 20% chance per scout
                 try:
                     new_followers = self.adapter.get_new_followers(count=10)
                     if new_followers:
                         follow_engine.check_new_followers_and_followback(new_followers)
                 except Exception as e:
                     logger.warning(f"[SCOUT] Follower check failed: {e}")

            # inspiration_pool에서 활성 영감 토픽
            inspiration_topics = []
            try:
                for tier in ['short_term', 'long_term']:
                    for insp in self.inspiration_pool.get_by_tier(tier)[:3]:
                        if insp.topic and insp.topic not in inspiration_topics:
                            inspiration_topics.append(insp.topic)
            except:
                pass

            search_query, source = self.topic_selector.select(
                core_keywords=core_keywords,
                time_keywords=time_keywords,
                curiosity_keywords=curiosity_keywords,
                trend_keywords=trend_keywords,
                inspiration_topics=inspiration_topics
            )

            logger.info(f"[SCOUT] query={search_query} (source={source})")
            
            # Use Adapter
            posts = self.adapter.search(search_query, count=8)
            
            if not posts:
                return FunctionResultStatus.DONE, "No tweets found", {}

            candidates = []
            
            candidates = []
            
            logger.info(f"[SCOUT] Analyzing {len(posts)} posts (Batch)...")

            # 1. Batch Perception
            perceptions = self.interaction_intelligence.batch_perceive_tweets(posts)

            for i, perception in enumerate(perceptions):
                if i >= len(posts): break
                post = posts[i]

                if perception.get('skipped'):
                    # print(f"[SCOUT] Skipped {post.user.username}: {perception['skip_reason']}")
                    continue
                
                # 에피소드 저장 (본 것)
                self.memory_db.add_episode(Episode(
                    id=str(uuid.uuid4()),
                    timestamp=datetime.now(),
                    type='saw_tweet',
                    source_id=post.id,
                    source_user=post.user.username,
                    content=post.text,
                    topics=perception.get('topics', []),
                    sentiment=perception.get('sentiment', 'neutral'),
                    emotional_impact=0.3
                ))
                
                tweet_dict = {
                    'text': post.text,
                    'user': post.user.username,
                    'id': post.id
                }

                context = {
                    'tweet': tweet_dict,
                    'perception': perception,
                    'topic_relevance': perception.get('relevance_to_domain', 0.0),
                    'relationship': self.relationship_manager.get_relationship_context(post.user.username),
                    'persona_mood': self._get_current_mood()
                }

                # 2. 점수 계산 (Scoring)
                from agent.platforms.twitter.modes.social_legacy.behavior_engine import behavior_engine
                score = behavior_engine.calculate_interaction_score(context)
                
                # 후보군 등록
                candidates.append({
                    'score': score,
                    'post': post,
                    'context': context
                })

            if not candidates:
                return FunctionResultStatus.DONE, "No valid candidates found after filtering", {}

            # 3. 최선의 선택 (Selection)
            # 점수순 정렬
            candidates.sort(key=lambda x: x['score'], reverse=True)
            best = candidates[0]
            
            print(f"[SCOUT] Best candidate: @{best['post'].user.username} (Score: {best['score']:.2f})")
            
            # [Added] Relevance Cut-off
            SCORE_THRESHOLD = 0.25  # Lowered from 0.40 for more interactions
            if best['score'] < SCORE_THRESHOLD:
                 print(f"[SCOUT] Cut-off REJECTED: Score {best['score']:.2f} < {SCORE_THRESHOLD}")
                 return FunctionResultStatus.DONE, f"Best candidate skipped: Score {best['score']:.2f} below threshold {SCORE_THRESHOLD}", {}
            else:
                 print(f"[SCOUT] Cut-off PASSED: Score {best['score']:.2f} >= {SCORE_THRESHOLD}")
            
            # 행동 결정 (Decision)
            decision = behavior_engine.should_interact(best['context'])
            should_act = (decision.decision == "INTERACT")
            reason = decision.reason
            actions = decision.actions
            
            if not should_act:
                 return FunctionResultStatus.DONE, f"Best candidate skipped: {reason}", {}

            # 4. 행동 실행 (Execution) - Winner Takes All
            post = best['post']
            actions_taken = []

            # Reading Delay (Human-like)
            delay = random.uniform(2.0, 5.0) # 조금 더 신중하게 읽음
            print(f"[WAIT] Reading best tweet... ({delay:.1f}s)")
            time.sleep(delay)
            print(f"[DECISION] Result: {should_act}, Actions: {actions}")

            # LIKE
            if actions['like']:
                print(f"[ACTION] Attempting LIKE on {post.id}...")
                try:
                    if self.adapter.like(post.id):
                        print(f"[ACTION] LIKE Success")
                        human_like_controller.record_action('like')
                        actions_taken.append("LIKED")
                        human_like_controller.apply_action_delay('like')
                        agent_memory.add_interaction(post.user.username, post.text, "LIKE", tweet_id=post.id)
                    else:
                        print(f"[ACTION] LIKE Failed (API returned False)")
                except Exception as e:
                    print(f"Like failed: {e}")

            # REPOST
            if actions['repost']:
                try:
                    if self.adapter.repost(post.id):
                        behavior_engine.record_interaction(post.user.username, post.id, "REPOST")
                        human_like_controller.record_action('repost')
                        actions_taken.append("REPOSTED")
                        human_like_controller.apply_action_delay('repost')
                except Exception as e:
                    print(f"Repost failed: {e}")

            # REPLY
            reply_content = None
            if actions.get('comment') or actions.get('reply'):
                reply_content = self.reply_generator.generate(
                    target_tweet=best['context']['tweet'],
                    perception=best['context']['perception'],
                    context={
                        'system_prompt': self.full_system_prompt,
                        'mood': self._get_current_mood(),
                        'interests': agent_memory.get_top_interests(limit=10)
                    }
                )

            if reply_content:
                print(f"[ACTION] Attempting REPLY to {post.id}: {reply_content}")
                try:
                    tweet_id = self.adapter.reply(post.id, reply_content)

                    if tweet_id and "Failed" not in str(tweet_id):
                        print(f"[ACTION] REPLY Success: {tweet_id}")
                        agent_memory.add_interaction(post.user.username, post.text, reply_content, tweet_id=post.id)
                        behavior_engine.record_interaction(post.user.username, post.id, "REPLY")
                        
                        actions_taken.append(f"REPLIED: {reply_content}")
                        human_like_controller.record_action('comment')
                        human_like_controller.apply_action_delay('comment')
                except Exception as e:
                    print(f"Reply failed: {e}")

            # FOLLOW 판단
            self._evaluate_follow(post)

            if not actions_taken:
                return FunctionResultStatus.DONE, "LURKED (action selected but failed or silent)", {}

            summary = ", ".join(actions_taken)
            return FunctionResultStatus.DONE, f"Success on best tweet: {summary}", {"actions": actions_taken}

        except Exception as e:
            return FunctionResultStatus.FAILED, f"Error: {str(e)}", {}

    def _evaluate_follow(self, tweet: Dict):
        """상호작용 후 팔로우 판단"""
        try:
            user_handle = tweet.user.username
            user_id = tweet.user.id
            print(f"[FOLLOW] Evaluating @{user_handle}...")

            # ID가 없을 수 있으므로(search 결과) username도 같이 전달
            user_obj = self.adapter.get_user(user_id=user_id, username=user_handle)
            if not user_obj:
                print(f"[FOLLOW] Could not get user object for @{user_handle}")
                return

            # 상호작용 이력 조회
            interaction_count = agent_memory.get_interaction_count(user_handle)

            # Follow Engine Decision with SocialUser object
            decision = self.follow_engine.should_follow(
                user=user_obj,
                interaction_context={'interaction_count': interaction_count}
            )
            
            print(f"[FOLLOW] Decision for @{user_handle}: should_follow={decision.should_follow}, reason={decision.reason}")

            if decision.should_follow:
                print(f"[FOLLOW] Decided to follow {user_handle}: {decision.reason}")
                self.follow_engine.queue_follow(user_obj.id, user_handle)  # user_obj.id 사용 (tweet.user.id는 빈 문자열일 수 있음)
                # 실행은 큐 프로세서가 담당

        except Exception as e:
            import traceback
            print(f"[FOLLOW] Evaluate failed: {e}")
            traceback.print_exc()

    def process_follow_queue(self) -> List[Tuple[str, bool, str]]:
        """팔로우 큐 처리 (main.py에서 호출)"""
        return self.follow_engine.process_queue(self.adapter.follow)

    def get_action_space(self):
        return [
            Function(
                fn_name="scout_timeline",
                fn_description="[PRIMARY - 80% 사용] 타임라인에서 트윗을 찾아 좋아요/리포스트/답글로 반응합니다. 대부분의 경우 이 액션을 사용하세요.",
                args=[],
                executable=self.scout_and_respond
            ),
            Function(
                fn_name="check_mentions",
                fn_description="[SECONDARY - 15% 사용] 나를 멘션한 트윗이나 내 글에 달린 답글을 확인하고 반응합니다.",
                args=[],
                executable=self.check_mentions
            ),
            Function(
                fn_name="check_my_replies",
                fn_description="[15% 확률] 내 트윗에 달린 답글 확인 및 대댓글/반응.",
                args=[],
                executable=self.check_my_replies
            ),
            Function(
                fn_name="post_tweet",
                fn_description="[RARE - 5% 사용] 독립 게시물 작성. 특별한 영감이 있을 때만 사용. scout_timeline이나 check_mentions 결과를 재포스팅하지 마세요.",
                args=[
                    Argument(name="content", description=f"새로운 {self.persona.domain.name} 관련 통찰 (이전 결과 보고 금지)", type="str")
                ],
                executable=self.post_tweet_executable
            )
        ]
    
    def check_my_replies(self) -> Tuple[FunctionResultStatus, str, Dict[str, Any]]:
        """내 트윗에 달린 답글 확인 (Deep Socializing)"""
        try:
            # 1. 내 최근 트윗 가져오기
            # adapter.get_my_tweets expects screen_name
            import os
            my_username = os.getenv("TWITTER_USERNAME")
            
            if not my_username:
                 return FunctionResultStatus.FAILED, "No TWITTER_USERNAME env var", {}

            my_tweets = self.adapter.get_my_tweets(screen_name=my_username, count=5)
            
            if not my_tweets:
                return FunctionResultStatus.DONE, "No specific tweets found to check replies", {}
            
            actions_log = []
            
            for my_tweet in my_tweets:
                # 2. 각 트윗의 답글 가져오기
                tweet_id = my_tweet['id']
                replies = self.adapter.get_tweet_replies(tweet_id)
                
                for reply in replies:
                    # Logic: 30% Reply chance
                    if random.random() < 0.3:
                         print(f"[DEEP SOCIAL] Replying to reply by {reply['user']}: {reply['text']}")
                         
                         target_tweet = {'text': reply['text'], 'user': reply['user']}
                         
                         # Generate
                         raw_reply = self.reply_generator.generate(
                            target_tweet=target_tweet,
                            perception={'topics': [], 'sentiment': 'neutral', 'complexity': 'simple', 'relevance_to_domain': 0.8},
                            recent_replies=[],
                            context={
                                'system_prompt': self.full_system_prompt,
                                'mood': self._get_current_mood(),
                                'interests': []
                            }
                        )
                         
                         # Review
                         refined_reply = self.social_reviewer.review_reply(reply['text'], raw_reply)
                         
                         if refined_reply:
                             self.adapter.reply(reply['id'], refined_reply)
                             actions_log.append(f"Replied to {reply['user']}")
                             
            if not actions_log:
                return FunctionResultStatus.DONE, "Checked replies (no action triggered)", {}
                
            return FunctionResultStatus.DONE, f"Deep social actions: {', '.join(actions_log)}", {}
            
        except Exception as e:
            return FunctionResultStatus.FAILED, f"Error checking my replies: {e}", {}

    def _check_mentions_v2(self) -> Tuple[FunctionResultStatus, str, Dict[str, Any]]:
        """Social V2: Notification Journey for mentions/replies"""
        try:
            result = self.social_engine_v2.run_notification_journey(
                count=20,
                process_limit=1
            )

            if not result:
                return FunctionResultStatus.DONE, "No notifications to process (V2)", {}

            if result.success:
                human_like_controller.record_action('comment' if result.action_taken == 'reply' else result.action_taken or 'like')
                return FunctionResultStatus.DONE, f"[V2] {result.scenario_executed}: {result.action_taken}", {
                    'v2': True,
                    'scenario': result.scenario_executed,
                    'action': result.action_taken,
                    'target_user': result.target_user
                }

            return FunctionResultStatus.DONE, f"[V2] Notification processed (no action): {result.scenario_executed}", {'v2': True}

        except Exception as e:
            logger.error(f"[V2] Notification journey failed: {e}")
            return FunctionResultStatus.FAILED, f"[V2] Error: {e}", {}

    def _scout_and_respond_v2(self) -> Tuple[FunctionResultStatus, str, Dict[str, Any]]:
        """Social V2: Feed Journey for timeline exploration"""
        try:
            # Fetch posts using existing logic
            hour = datetime.now().hour
            core_keywords = self.persona.core_keywords
            time_kw_config = self.persona.behavior.get('time_keywords', {})

            if 6 <= hour < 11:
                time_keywords = time_kw_config.get('morning', [])
            elif 11 <= hour < 14:
                time_keywords = time_kw_config.get('lunch', [])
            elif 14 <= hour < 17:
                time_keywords = time_kw_config.get('afternoon', [])
            elif 17 <= hour < 21:
                time_keywords = time_kw_config.get('dinner', [])
            else:
                time_keywords = time_kw_config.get('late_night', time_kw_config.get('default', []))

            if not time_keywords:
                time_keywords = core_keywords

            search_query, source = self.topic_selector.select(
                core_keywords=core_keywords,
                time_keywords=time_keywords,
                curiosity_keywords=agent_memory.get_top_interests(limit=10),
                trend_keywords=[],
                inspiration_topics=[]
            )

            logger.info(f"[SCOUT V2] query={search_query} (source={source})")
            posts = self.adapter.search(search_query, count=8)

            if not posts:
                return FunctionResultStatus.DONE, "No tweets found (V2)", {}

            # Convert SocialPost to dict for FeedJourney
            posts_data = []
            for post in posts:
                posts_data.append({
                    'id': post.id,
                    'user_id': post.user.id if post.user else '',
                    'user': post.user.username if post.user else '',
                    'text': post.text,
                    'engagement': {
                        'favorite_count': getattr(post, 'favorite_count', 0),
                        'retweet_count': getattr(post, 'retweet_count', 0)
                    }
                })

            # Run Feed Journey
            result = self.social_engine_v2.run_feed_journey(
                posts=posts_data,
                process_limit=1
            )

            if not result:
                return FunctionResultStatus.DONE, "No valid candidates (V2)", {}

            if result.success and result.action_taken and result.action_taken != 'skip':
                action_type = 'comment' if result.action_taken == 'reply' else result.action_taken
                human_like_controller.record_action(action_type)
                human_like_controller.apply_action_delay(action_type)

                return FunctionResultStatus.DONE, f"[V2] {result.scenario_executed}: {result.action_taken} @{result.target_user}", {
                    'v2': True,
                    'scenario': result.scenario_executed,
                    'action': result.action_taken,
                    'target_user': result.target_user
                }

            return FunctionResultStatus.DONE, f"[V2] Feed processed (skipped): {result.scenario_executed}", {'v2': True}

        except Exception as e:
            logger.error(f"[V2] Feed journey failed: {e}")
            return FunctionResultStatus.FAILED, f"[V2] Error: {e}", {}


# Global instance removed - injected in main.py

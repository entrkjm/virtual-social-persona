"""
SocialAgent - Main Workflow Orchestration
Scout → Perceive → Behavior → Judge → Action
"""
from game_sdk.game.custom_types import Function, Argument, FunctionResultStatus, FunctionResult
from config.settings import settings
from actions.market_data import get_market_data
from platforms.twitter.social import post_tweet, search_tweets, favorite_tweet, repost_tweet, get_mentions, follow_user, get_user_profile
from platforms.twitter.trends import get_trending_topics, get_daily_briefing
from core.llm import llm_client
from agent.persona.persona_loader import active_persona
from agent.memory import agent_memory
from agent.persona.relationship_manager import initialize_relationship_manager
from agent.core.interaction_intelligence import interaction_intelligence
from agent.core.behavior_engine import behavior_engine, human_like_controller
from agent.core.follow_engine import follow_engine
from agent.platforms.twitter.modes.casual.post_generator import CasualPostGenerator
from agent.platforms.twitter.modes.social.reply_generator import SocialReplyGenerator
from typing import Tuple, Dict, Any, Optional, List
from datetime import datetime
import random

# Dynamic Memory (v2)
from agent.memory.factory import MemoryFactory  # Changed import
from agent.memory.database import Episode, generate_id
from agent.memory.inspiration_pool import InspirationPool
from agent.memory.tier_manager import TierManager
from agent.memory.consolidator import MemoryConsolidator
from agent.platforms.twitter.modes.casual.trigger_engine import PostingTriggerEngine
from agent.core.topic_selector import TopicSelector
from agent.knowledge.knowledge_base import KnowledgeBase
from agent.platforms.twitter.modes.series.engine import SeriesEngine
from agent.persona.pattern_tracker import PatternTracker

class SocialAgent:
    def __init__(self):
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
        self.post_generator = CasualPostGenerator(self.persona, platform_config)
        self.reply_generator = SocialReplyGenerator(self.persona, platform_config)
        self.full_system_prompt = self.persona.system_prompt
        
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
        
        # Series Engine 초기화
        self.series_engine = SeriesEngine(self.persona)

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
        if self.memory_consolidator.should_run(interval_hours=settings.CONSOLIDATION_INTERVAL):
            stats = self.memory_consolidator.run()
            print(f"[MEMORY] +{stats.promoted} promoted, -{stats.deleted} deleted")

        memory_context = agent_memory.get_recent_context()
        facts_context = agent_memory.get_facts_context()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mood = self._get_current_mood()

        top_interests = agent_memory.get_top_interests(limit=10)
        interests_text = ", ".join(top_interests) if top_interests else "없음"

        try:
            daily_briefing = get_daily_briefing()
        except:
            daily_briefing = "없음"

            daily_briefing = "없음"

        core_memories = self.memory_db.get_all_core_memories()
        core_context = self.tier_manager.get_core_context_for_llm(core_memories)
        recent_posts_context = self.memory_db.get_recent_posts_context(limit=5)

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
            if not content:
                # 트위터 플랫폼 확인
                if 'twitter' in self.series_engine.get_enabled_platforms():
                    # 시리즈 실행 시도 (랜덤 선택 + 쿨다운 체크)
                    result = self.series_engine.execute('twitter')
                    if result:
                        return FunctionResultStatus.DONE, f"Posted Series: {result}", result

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
            twitter_id = post_tweet(generated_content)

            # DB에 포스팅 기록 저장 (유사도 체크용)
            self.memory_db.add_posting(
                inspiration_id=None,
                content=generated_content,
                trigger_type=source
            )

            return FunctionResultStatus.DONE, f"Posted: {generated_content}", {"tweet_id": twitter_id, "topic": topic, "source": source}
        except Exception as e:
            return FunctionResultStatus.FAILED, f"Failed to tweet: {e}", {}

    def check_mentions(self) -> Tuple[FunctionResultStatus, str, Dict[str, Any]]:
        """멘션/답글 확인 및 반응"""
        try:
            can_act, reason = human_like_controller.can_take_action()
            if not can_act:
                print(f"[HUMAN-LIKE] 멘션 액션 제한: {reason}")
                return FunctionResultStatus.DONE, f"SKIP (human-like): {reason}", {'human_like_skip': True}

            mentions = get_mentions(count=10)
            if not mentions:
                return FunctionResultStatus.DONE, "No new mentions", {}

            responded_ids = agent_memory.get_responded_tweet_ids()
            new_mentions = [m for m in mentions if m['id'] not in responded_ids]

            if not new_mentions:
                return FunctionResultStatus.DONE, "No unprocessed mentions", {}

            mention = new_mentions[0]
            print(f"[MENTION] @{mention['user']}: {mention['text'][:50]}...")

            perception = interaction_intelligence.perceive_tweet(
                tweet_text=mention['text'],
                user_handle=f"@{mention['user']}"
            )

            actions = behavior_engine.decide_actions(perception=perception, tweet=mention)
            actions_taken = []

            if actions['like']:
                try:
                    if favorite_tweet(mention['id']):
                        human_like_controller.record_action('like')
                        actions_taken.append("LIKED")
                        human_like_controller.apply_action_delay('like')
                except Exception as e:
                    if '226' in str(e):
                        human_like_controller.handle_error(226)
                        return FunctionResultStatus.DONE, "Error 226: 일시정지", {'error': 226}
                    raise

            if actions_taken and actions['comment']:
                human_like_controller.apply_between_actions_delay()

            if actions['comment']:
                relationship_context = self.relationship_manager.get_relationship_context(f"@{mention['user']}")
                context = {
                    'system_prompt': self.full_system_prompt,
                    'mood': self._get_current_mood(),
                    'interests': agent_memory.get_top_interests(limit=10),
                    'relationship': relationship_context
                }
                reply_content = self.reply_generator.generate(
                    target_tweet={"user": mention['user'], "text": mention['text']},
                    perception=perception,
                    context=context
                )

                if reply_content:
                    try:
                        tweet_id = post_tweet(reply_content, reply_to=mention['id'])
                        if tweet_id and "Failed" not in str(tweet_id):
                            human_like_controller.record_action('comment')
                            actions_taken.append(f"REPLIED: {reply_content}")
                            human_like_controller.apply_action_delay('comment')
                            # DB에 답글 기록
                            self.memory_db.add_posting(
                                inspiration_id=None,
                                content=reply_content,
                                trigger_type="mention_reply"
                            )
                    except Exception as e:
                        if '226' in str(e):
                            human_like_controller.handle_error(226)
                            return FunctionResultStatus.DONE, "Error 226: 일시정지", {'error': 226}
                        raise

            agent_memory.mark_tweet_responded(mention['id'])

            if not actions_taken:
                return FunctionResultStatus.DONE, f"Processed mention from @{mention['user']} (no action)", {}

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
                print(f"[HUMAN-LIKE] 액션 제한: {reason}")
                return FunctionResultStatus.DONE, f"SKIP (human-like): {reason}", {'human_like_skip': True}

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

            try:
                trend_keywords = get_trending_topics(count=5)
                for kw in trend_keywords:
                    agent_memory.track_keyword(kw, source="trend")
            except:
                trend_keywords = []

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

            print(f"[SCOUT] query={search_query} (source={source})")
            results = search_tweets(search_query, count=8)
            if not results:
                return FunctionResultStatus.DONE, "No tweets found", {}

            # 전체 트윗 평가 및 점수화
            scored_tweets = []
            for tweet in results:
                text = tweet.get('text', '').lower()
                words = [w.strip() for w in text.split() if len(w) > 2 and w.isalpha()]
                for word in words[:3]:
                    agent_memory.track_keyword(word, source="tweet")

                tweet_perception = interaction_intelligence.perceive_tweet(
                    tweet_text=tweet['text'],
                    user_handle=f"@{tweet['user']}"
                )
                tweet_score = self._calculate_tweet_score(tweet, tweet_perception)
                scored_tweets.append((tweet, tweet_perception, tweet_score))

            scored_tweets.sort(key=lambda x: x[2], reverse=True)
            target, perception, score = scored_tweets[0]

            eng = target.get('engagement', {})
            print(f"[TARGET] @{target['user']} (score={score:.2f}, likes={eng.get('favorite_count', 0)}, rel={perception.get('relevance_to_domain', 0):.1f})")

            # MEMORY
            emotional_impact = self._calculate_emotional_impact(perception)
            episode = self._record_episode(target, perception, emotional_impact)

            # 영감 생성 (impact 높고 내 관점이 있을 때)
            my_angle = perception.get('my_angle', '')
            if emotional_impact >= 0.6 and my_angle:
                self._create_inspiration_from_episode(episode, my_angle)
                print(f"[INSPIRATION] 새 영감 생성: {my_angle[:30]}...")

            reinforcement_trigger = self.inspiration_pool.on_content_seen(
                content=target['text'],
                emotional_impact=emotional_impact
            )
            if reinforcement_trigger:
                print(f"[REINFORCE] {reinforcement_trigger.reason}")

            trigger_context = {
                'current_episode': episode,
                'reinforcement_trigger': reinforcement_trigger
            }
            posting_decision = self.posting_trigger.check_trigger(trigger_context)
            if posting_decision:
                print(f"[TRIGGER] {posting_decision.type}")

            for topic in perception['topics']:
                agent_memory.track_keyword(topic, source="perception")

            # RELATIONSHIP
            relationship_context = self.relationship_manager.get_relationship_context(f"@{target['user']}")

            # BEHAVIOR
            behavior_context = {
                "tweet": {"user": target['user'], "id": target['id'], "text": target['text']},
                "perception": perception,
                "relationship": relationship_context,
                "current_time": datetime.now()
            }
            behavior_decision = behavior_engine.should_interact(behavior_context)
            print(f"[BEHAVIOR] {behavior_decision.decision} ({behavior_decision.mood_state:.2f})")

            if behavior_decision.decision == "SKIP":
                return FunctionResultStatus.DONE, f"SKIP: {behavior_decision.reason}", {}

            # 독립 확률로 각 행동 결정 (관련도/인기도 기반)
            actions = behavior_engine.decide_actions(perception=perception, tweet=target)
            print(f"[ACTIONS] like={actions['like']}, repost={actions['repost']}, comment={actions['comment']}")

            actions_taken = []

            # LIKE
            if actions['like']:
                try:
                    if favorite_tweet(target['id']):
                        agent_memory.add_like(target['id'])
                        behavior_engine.record_interaction(target['user'], target['id'], "LIKE")
                        human_like_controller.record_action('like')
                        actions_taken.append("LIKED")
                        human_like_controller.apply_action_delay('like')
                except Exception as e:
                    if '226' in str(e):
                        human_like_controller.handle_error(226)
                        return FunctionResultStatus.DONE, "Error 226: 일시정지", {'error': 226}
                    raise

            # 액션 간 지연
            if actions_taken and (actions['repost'] or actions['comment']):
                human_like_controller.apply_between_actions_delay()

            # REPOST
            if actions['repost']:
                try:
                    if repost_tweet(target['id']):
                        behavior_engine.record_interaction(target['user'], target['id'], "REPOST")
                        human_like_controller.record_action('repost')
                        actions_taken.append("REPOSTED")
                        human_like_controller.apply_action_delay('like')
                except Exception as e:
                    if '226' in str(e):
                        human_like_controller.handle_error(226)
                        return FunctionResultStatus.DONE, "Error 226: 일시정지", {'error': 226}
                    raise

            # 액션 간 지연
            if actions_taken and actions['comment']:
                human_like_controller.apply_between_actions_delay()

            # COMMENT - reply_generator로 답글 생성
            if actions['comment']:
                context = {
                    'system_prompt': self.full_system_prompt,
                    'mood': self._get_current_mood(),
                    'interests': agent_memory.get_top_interests(limit=10),
                    'relationship': relationship_context
                }
                reply_content = self.reply_generator.generate(
                    target_tweet={"user": target['user'], "text": target['text']},
                    perception=perception,
                    context=context
                )

                if reply_content:
                    try:
                        tweet_id = post_tweet(reply_content, reply_to=target['id'])

                        if tweet_id and "Failed" not in str(tweet_id):
                            agent_memory.add_interaction(target['user'], target['text'], reply_content, tweet_id=target['id'])
                            behavior_engine.record_interaction(target['user'], target['id'], "REPLY")
                            human_like_controller.record_action('comment')
                            actions_taken.append(f"REPLIED: {reply_content}")
                            human_like_controller.apply_action_delay('comment')
                            # DB에 답글 기록
                            self.memory_db.add_posting(
                                inspiration_id=None,
                                content=reply_content,
                                trigger_type="timeline_reply"
                            )

                            self.relationship_manager.update_relationship(
                                f"@{target['user']}",
                                {
                                    "sentiment": perception['sentiment'],
                                    "topics": perception['topics']
                                }
                            )
                    except Exception as e:
                        if '226' in str(e):
                            human_like_controller.handle_error(226)
                            return FunctionResultStatus.DONE, "Error 226: 일시정지", {'error': 226}
                        raise

            # FOLLOW 판단
            self._evaluate_follow(target)

            if not actions_taken:
                return FunctionResultStatus.DONE, "LURKED (no action taken)", {}

            summary = ", ".join(actions_taken)
            return FunctionResultStatus.DONE, f"Success: {summary}", {"actions": actions_taken}

        except Exception as e:
            return FunctionResultStatus.FAILED, f"Error: {str(e)}", {}

    def _evaluate_follow(self, tweet: Dict):
        """상호작용 후 팔로우 판단"""
        try:
            user_handle = tweet.get('user', '')
            user_id = tweet.get('user_id')

            if not user_id:
                profile = get_user_profile(screen_name=user_handle)
                if not profile:
                    return
                user_id = profile.get('id')
            else:
                profile = get_user_profile(user_id=user_id)

            if not profile:
                return

            # 상호작용 이력 조회
            interaction_count = agent_memory.get_interaction_count(user_handle)
            context = {'interaction_count': interaction_count}

            decision = follow_engine.should_follow(profile, context)

            if decision.should_follow:
                follow_engine.queue_follow(
                    user_id=profile.get('id'),
                    screen_name=profile.get('screen_name', user_handle),
                    context=context
                )
                print(f"[FOLLOW] Queued @{user_handle}: {decision.reason}")

        except Exception as e:
            print(f"[FOLLOW] Evaluate failed: {e}")

    def process_follow_queue(self) -> List[Tuple[str, bool, str]]:
        """팔로우 큐 처리 (main.py에서 호출)"""
        return follow_engine.process_queue(follow_user)

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
                fn_name="post_tweet",
                fn_description="[RARE - 5% 사용] 독립 게시물 작성. 특별한 영감이 있을 때만 사용. scout_timeline이나 check_mentions 결과를 재포스팅하지 마세요.",
                args=[
                    Argument(name="content", description=f"새로운 {self.persona.domain.name} 관련 통찰 (이전 결과 보고 금지)", type="str")
                ],
                executable=self.post_tweet_executable
            )
        ]

social_agent = SocialAgent()

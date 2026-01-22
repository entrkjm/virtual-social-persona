"""
Virtual Agent Entry Point (Session-based v3)
Virtuals Protocol G.A.M.E SDK (Optional)
"""
import asyncio
import time
import random

from config.settings import settings
from agent.bot import SocialAgent
from agent.platforms.twitter.adapter import TwitterAdapter

# Initialize Global Agent with Adapter
adapter = TwitterAdapter()
social_agent = SocialAgent(adapter)

from agent.persona.persona_loader import active_persona
from agent.core.mode_manager import mode_manager
from agent.core.activity_scheduler import ActivityScheduler


def run_with_sdk():
    """SDK 모드: Virtuals G.A.M.E SDK 사용"""
    from game_sdk.game.agent import Agent, WorkerConfig

    if not settings.GAME_API_KEY:
        print("Error: GAME_API_KEY missing")
        return

    persona = active_persona
    activity_scheduler = ActivityScheduler(persona.behavior)
    step_min, step_max = mode_manager.get_step_interval()
    print(f"[INIT] {persona.name} (SDK Mode)")
    print(f"[INIT] Mode: {mode_manager.mode.value} (interval: {step_min}-{step_max}s)")
    print(f"[INIT] Activity schedule loaded")

    worker_config = WorkerConfig(
        id="social_agent_worker",
        worker_description=f"{persona.identity} - 소셜 미디어 상호작용",
        get_state_fn=social_agent.get_state_fn,
        action_space=social_agent.get_action_space(),
        instruction=f"""
        당신은 '{persona.name}'입니다.

        [액션 우선순위]
        1. scout_timeline (80%): 기본 액션. 타임라인에서 트윗을 찾아 좋아요/리포스트/답글.
        2. check_mentions (15%): 나를 멘션한 트윗 확인 및 반응.
        3. post_tweet (5%): 특별한 영감이 있을 때만. 결과 보고 재포스팅 금지.

        [주의사항]
        - scout_timeline 결과를 post_tweet으로 다시 올리지 마세요.
        - 대부분의 step에서는 scout_timeline을 사용하세요.
        """
    )

    agent = None
    max_retries = 5
    retry_count = 0

    while retry_count < max_retries:
        try:
            agent = Agent(
                api_key=settings.GAME_API_KEY,
                name=persona.name,
                agent_goal=persona.agent_goal,
                agent_description=persona.agent_description,
                get_agent_state_fn=lambda result, state: {"status": "active"},
                workers=[worker_config]
            )
            break
        except Exception as e:
            if "429" in str(e):
                print(f"[429] Retry {retry_count+1}/{max_retries}")
                time.sleep(30)
                retry_count += 1
            else:
                raise e

    if not agent:
        print("[FAIL] Init failed")
        return

    max_retries = 5
    retry_count = 0
    compiled = False

    while retry_count < max_retries:
        try:
            agent.compile()
            compiled = True
            break
        except Exception as e:
            if "429" in str(e):
                wait_time = 30 * (retry_count + 1)
                print(f"[429] Retry {retry_count+1}/{max_retries}")
                time.sleep(wait_time)
                retry_count += 1
            else:
                raise e

    if not compiled:
        print("[FAIL] Compile failed")
        return

    print("[RUN] Starting SDK loop")

    from agent.memory import agent_memory
    from core.llm import llm_client

    try:
        step_count = 0
        while True:
            try:
                # AGGRESSIVE/TEST 모드에서는 잠 안 잠
                if mode_manager.config.sleep_enabled:
                    is_active, state, next_active = activity_scheduler.is_active_now()
                    if not is_active:
                        sleep_seconds = activity_scheduler.get_seconds_until_active()
                        print(f"[SLEEP] {state.value} - resuming in {sleep_seconds//60}m")
                        time.sleep(min(sleep_seconds, 3600))
                        continue

                    if mode_manager.should_take_break() and activity_scheduler.should_take_break():
                        break_until = activity_scheduler._break_until
                        break_duration = activity_scheduler.get_seconds_until_active()
                        print(f"[BREAK] Taking a break for {break_duration//60}m")
                        time.sleep(break_duration)
                        continue

                agent.step()
                step_count += 1

                if step_count % 10 == 0:
                    agent_memory.decay_curiosity(decay_rate=0.7)
                    agent_memory.summarize_old_interactions(llm_client=llm_client, threshold=50)

                follow_results = social_agent.process_follow_queue()
                if follow_results:
                    for screen_name, success, reason in follow_results:
                        status = "OK" if success else "FAIL"
                        print(f"[FOLLOW] @{screen_name}: {status} - {reason}")

                mode_manager.on_success()
                step_min, step_max = mode_manager.get_step_interval()
                activity_level = activity_scheduler.get_activity_level()
                adjusted_min = int(step_min / max(activity_level, 0.1))
                adjusted_max = int(step_max / max(activity_level, 0.1))
                wait_time = random.randint(adjusted_min, adjusted_max)
                print(f"[WAIT] {wait_time}s (activity: {activity_level:.1f})")
                time.sleep(wait_time)
            except Exception as e:
                error_code = None
                if "429" in str(e):
                    error_code = 429
                    time.sleep(60)
                elif "226" in str(e):
                    error_code = 226

                should_pause = mode_manager.on_error(error_code)
                if should_pause:
                    print("[MODE] Pausing for 5 minutes due to consecutive errors")
                    time.sleep(300)
                else:
                    print(f"[ERR] {e}")
                    time.sleep(10)
    except KeyboardInterrupt:
        print("\nShutdown")


from agent.core.logger import logger


async def run_standalone_async():
    """Standalone 모드: 세션 기반 루프 (async)"""
    persona = active_persona
    activity_scheduler = ActivityScheduler(persona.behavior)
    session_min, session_max = mode_manager.get_session_interval()

    logger.info(f"============ AGENT START ============")
    logger.info(f"Identity: {persona.name} (Session-based Mode)")
    logger.info(f"Mode: {mode_manager.mode.value} (session interval: {session_min//60}-{session_max//60}m)")
    logger.info(f"Activity schedule loaded")

    from agent.memory import agent_memory
    from core.llm import llm_client

    logger.info("Loading Agent State...")
    social_agent.get_state_fn(function_result=None, current_state={})

    logger.info("Starting session-based loop")

    session_count = 0
    while True:
        try:
            # 수면/휴식 체크
            if mode_manager.config.sleep_enabled:
                is_active, state, next_active = activity_scheduler.is_active_now()
                if not is_active:
                    sleep_seconds = activity_scheduler.get_seconds_until_active()
                    logger.info(f"[SLEEP] {state.value} - resuming in {sleep_seconds//60}m")
                    await asyncio.sleep(min(sleep_seconds, 3600))
                    continue

                if mode_manager.should_take_break() and activity_scheduler.should_take_break():
                    break_duration = activity_scheduler.get_seconds_until_active()
                    logger.info(f"[BREAK] Taking a break for {break_duration//60}m")
                    await asyncio.sleep(break_duration)
                    continue

            # Mode Selection
            activity_cfg = persona.platform_configs.get('twitter', {}).get('activity', {})
            mode_weights = activity_cfg.get('mode_weights', {'social': 0.97, 'casual': 0.02, 'series': 0.01})

            roll = random.random()
            cumulative = 0
            selected_mode = 'social'
            for mode, weight in mode_weights.items():
                cumulative += weight
                if roll < cumulative:
                    selected_mode = mode
                    break

            session_count += 1
            logger.info(f"[SESSION {session_count}] Mode: {selected_mode} (roll={roll:.2f})")

            # Mode별 분기
            if selected_mode == 'social':
                # 세션 기반 소셜 활동
                result = await social_agent.run_social_session()
                logger.info(
                    f"[SESSION {session_count}] Social done: "
                    f"{result.notifications_processed} notifs, "
                    f"{result.feeds_reacted} reacted, "
                    f"{result.total_actions} actions"
                )
            elif selected_mode == 'casual':
                status, message, data = social_agent.post_tweet_executable(content="")
                logger.info(f"[SESSION {session_count}] Casual: {message}")
            elif selected_mode == 'series':
                status, message, data = social_agent.run_series_step()
                logger.info(f"[SESSION {session_count}] Series: {message}")

            # 상태 업데이트
            social_agent.get_state_fn(function_result=None, current_state={})

            # 주기적 메모리 정리
            if session_count % 5 == 0:
                agent_memory.decay_curiosity(decay_rate=0.7)
                agent_memory.summarize_old_interactions(llm_client=llm_client, threshold=50)

            # 팔로우 큐 처리
            follow_results = social_agent.process_follow_queue()
            if follow_results:
                for screen_name, success, reason in follow_results:
                    status_str = "OK" if success else "FAIL"
                    if success:
                        logger.info(f"[FOLLOW] @{screen_name}: {status_str} - {reason}")
                    else:
                        logger.warning(f"[FOLLOW] @{screen_name}: {status_str} - {reason}")

            # 세션 간 휴식
            mode_manager.on_success()
            session_min, session_max = mode_manager.get_session_interval()

            if mode_manager.config.sleep_enabled:
                activity_level = activity_scheduler.get_activity_level()
                adjusted_min = int(session_min / max(activity_level, 0.1))
                adjusted_max = int(session_max / max(activity_level, 0.1))
            else:
                activity_level = 1.0
                adjusted_min = session_min
                adjusted_max = session_max

            wait_time = random.randint(adjusted_min, adjusted_max)
            logger.info(f"[REST] {wait_time//60}m {wait_time%60}s until next session (activity: {activity_level:.1f})")
            await asyncio.sleep(wait_time)

        except Exception as e:
            error_str = str(e)
            error_code = None
            if "429" in error_str:
                error_code = 429
                await asyncio.sleep(60)
            elif any(code in error_str for code in ["226", "401", "403"]):
                error_code = 226

            should_pause = mode_manager.on_error(error_code)
            if should_pause:
                logger.warning("[MODE] Pausing for 5 minutes due to consecutive errors")
                await asyncio.sleep(300)
            else:
                logger.error(f"[ERR] {e}")
                await asyncio.sleep(10)


def run_standalone():
    """Standalone 모드 진입점"""
    try:
        # Twitter 클라이언트 초기화 (async 루프 전에 동기적으로)
        from agent.platforms.twitter.api import social as twitter_api
        twitter_api.ensure_client()

        asyncio.run(run_standalone_async())
    except KeyboardInterrupt:
        logger.info("\n[STOP] Shutdown via KeyboardInterrupt")
    except Exception as e:
        logger.critical(f"\n[FATAL] Crash: {e}", exc_info=True)


def main():
    if settings.USE_VIRTUAL_SDK:
        run_with_sdk()
    else:
        run_standalone()


if __name__ == "__main__":
    main()

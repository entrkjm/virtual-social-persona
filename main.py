"""
Virtual Agent Entry Point
Virtuals Protocol G.A.M.E SDK (Optional)
"""
from config.settings import settings
from agent.bot import social_agent
from agent.persona_loader import active_persona
from agent.mode_manager import mode_manager
from agent.activity_scheduler import ActivityScheduler
import time
import random


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
                is_active, state, next_active = activity_scheduler.is_active_now()
                if not is_active:
                    sleep_seconds = activity_scheduler.get_seconds_until_active()
                    print(f"[SLEEP] {state.value} - resuming in {sleep_seconds//60}m")
                    time.sleep(min(sleep_seconds, 3600))
                    continue

                if activity_scheduler.should_take_break():
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


def run_standalone():
    """Standalone 모드: SDK 없이 직접 루프"""
    persona = active_persona
    activity_scheduler = ActivityScheduler(persona.behavior)
    step_min, step_max = mode_manager.get_step_interval()
    print(f"[INIT] {persona.name} (Standalone Mode)")
    print(f"[INIT] Mode: {mode_manager.mode.value} (interval: {step_min}-{step_max}s)")
    print(f"[INIT] Activity schedule loaded")

    from agent.memory import agent_memory
    from core.llm import llm_client

    social_agent.get_state_fn(function_result=None, current_state={})

    print("[RUN] Starting standalone loop")

    try:
        step_count = 0
        while True:
            try:
                is_active, state, next_active = activity_scheduler.is_active_now()
                if not is_active:
                    sleep_seconds = activity_scheduler.get_seconds_until_active()
                    print(f"[SLEEP] {state.value} - resuming in {sleep_seconds//60}m")
                    time.sleep(min(sleep_seconds, 3600))
                    continue

                if activity_scheduler.should_take_break():
                    break_duration = activity_scheduler.get_seconds_until_active()
                    print(f"[BREAK] Taking a break for {break_duration//60}m")
                    time.sleep(break_duration)
                    continue

                roll = random.random()

                if roll < 0.80:
                    action_name = "scout_timeline"
                    status, message, data = social_agent.scout_and_respond()
                elif roll < 0.95:
                    action_name = "check_mentions"
                    status, message, data = social_agent.check_mentions()
                else:
                    action_name = "post_tweet"
                    status, message, data = social_agent.post_tweet_executable(content="")

                print(f"[STEP {step_count}] {action_name}: {message}")
                step_count += 1

                social_agent.get_state_fn(function_result=None, current_state={})

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
                if "226" in str(e):
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


def main():
    if settings.USE_VIRTUAL_SDK:
        run_with_sdk()
    else:
        run_standalone()


if __name__ == "__main__":
    main()

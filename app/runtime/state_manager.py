from enum import Enum
import logging


class RuntimeState(str, Enum):
    IDLE = "idle"; INITIALIZING = "initializing"; PLANNING = "planning"
    OPENING_BROWSER = "opening_browser"; VERIFYING_PAGE = "verifying_page"; FOCUSING_INPUT = "focusing_input"
    SENDING_PROMPT = "sending_prompt"; WAITING_RESPONSE = "waiting_response"
    EXTRACTING_RESPONSE = "extracting_response"; VALIDATING_RESPONSE = "validating_response"
    STORING_RESULT = "storing_result"; COMPLETED = "completed"; FAILED = "failed"
    RECOVERING = "recovering"; STOPPED = "stopped"; SYNTHESIZING = "synthesizing"
    SWITCHING_PROVIDER = "switching_provider"
    WAITING_USER_INTERVENTION = "waiting_user_intervention"


class StateManager:
    def __init__(self) -> None:
        self.state = RuntimeState.IDLE
        self.history = [self.state]

    def transition(self, state: RuntimeState) -> None:
        logging.getLogger(__name__).info("State transition: %s -> %s", self.state.value, state.value)
        self.state = state
        self.history.append(state)

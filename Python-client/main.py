
import sys
import yaml
import time
import logging
import threading
from core.logger import setup_logging
from typing import Any, Dict, Optional
from ai.agents.main_agent import MainAgent
from motion.controller import ArduinoFeedback
from motion.motion_manager import MotionManager
from vision.vision_manager import VisionManager
from ai.agents.dependencies import AgentDependencies
from communication.communication_manager import CommunicationManager
from config.config import SerialConfig, VisionConfig, MotionConfig, TaskConfig, VLMConfig, AIConfig
from state_machine.states import (
    RobotContext,
    StateMachine,
    InitState,
    IdleState,
    DetectTargetState,
    PickupPrepState,
    PickupState,
    MoveToDropState,
    DropState,
    ReturnHomeState,
    EmergencyStopState
)


# Global -------------------------------------------------------------------- #


logger = logging.getLogger(__name__)


# Classes ------------------------------------------------------------------- #


class AmadeusClient:
    """Primary system orchestrator managing lifecycle initialization and execution loops."""

    def __init__(self, config_path: str = "config/settings.yaml") -> None:
        self._config_path = config_path
        self._settings: Dict[str, Any] = {}
        self._comm_manager: Optional[CommunicationManager] = None
        self._vision_manager: Optional[VisionManager] = None
        self._motion_manager: Optional[MotionManager] = None
        self._state_machine: Optional[StateMachine] = None
        self._context: Optional[RobotContext] = None
        self._running: bool = False
        self._main_agent: Optional[MainAgent] = None
        self._agent_dependencies = None

    def initialize(self) -> bool:
        """Parses settings, configures logging, and initializes Managers."""
        self._settings = self._load_settings()

        # Setup Logging configuration
        log_level = self._settings.get("logging", {}).get("level", "INFO")
        setup_logging(level=log_level)
        logger.info("Initializing AMADEUS MK-I System Client...")

        # Build configuration maps
        serial_config = SerialConfig.from_dict(
            self._settings.get("communication", {}).get("serial", {})
        )
        vlm_config = VLMConfig.from_dict(
            self._settings.get("ai", {}).get("vlm", {})
        )
        vision_config = VisionConfig.from_dict(
            self._settings.get("vision", {}),
            vlm=vlm_config
        )
        motion_config = MotionConfig.from_dict(
            self._settings.get("motion", {})
        )
        task_config = TaskConfig.from_dict(
            self._settings
        )  # Parsed Task configurations

        # Instantiate MainAgent
        ai_config = AIConfig.from_dict(self._settings.get("ai", {}))
        self._main_agent = MainAgent(
            llm_config=ai_config.vlm,
            agent_config=ai_config.agents,
        )

        # Instantiate Managers
        self._comm_manager = CommunicationManager(serial_config)
        self._vision_manager = VisionManager(vision_config, llm_config=ai_config.vlm)
        self._motion_manager = MotionManager(motion_config)

        # Initialize Subsystem Modules
        if not self._comm_manager.initialize():
            logger.error("Failed to initialize communication driver subsystem.")
            return False

        if not self._vision_manager.initialize():
            logger.error("Failed to initialize vision perception subsystem.")
            return False
        self._vision_manager.start_capture()
        self._vision_manager.disable_processing()

        serial_client = self._comm_manager._client
        if not serial_client or not self._motion_manager.initialize(serial_client):
            logger.error("Failed to initialize motion and planning subsystem.")
            return False

        self._comm_manager.register_feedback_listener(self._handle_hardware_feedback)

        # Build agent dependencies
        self._agent_dependencies = AgentDependencies(
            robot_context=self._context,
            vision_manager=self._vision_manager,
            motion_manager=self._motion_manager,
            state_machine=self._state_machine,
            task_config=task_config,
            agent_config=ai_config.agents,
        )

        # Build and Register State Machine configurations
        self._context = RobotContext(
            comm_manager=self._comm_manager,
            vision_manager=self._vision_manager,
            motion_manager=self._motion_manager,
            task_config=task_config
        )

        if not self._context:
            logger.error("Failed to Build and Register State Machine configurations.")
            return False

        initial_state_name = self._settings.get("state_machine", {}).get("initial_state", "INIT")
        self._state_machine = StateMachine(self._context, initial_state_name)

        # Bind states registry maps
        self._state_machine.register_state("INIT", InitState(self._context))
        self._state_machine.register_state("IDLE", IdleState(self._context))
        self._state_machine.register_state("DETECT_TARGET", DetectTargetState(self._context))
        self._state_machine.register_state("PICKUP_PREP", PickupPrepState(self._context))
        self._state_machine.register_state("PICKUP", PickupState(self._context))
        self._state_machine.register_state("MOVE_TO_DROP", MoveToDropState(self._context))
        self._state_machine.register_state("DROP", DropState(self._context))
        self._state_machine.register_state("RETURN_HOME", ReturnHomeState(self._context))
        self._state_machine.register_state("EMERGENCY_STOP", EmergencyStopState(self._context))

        return True

    def start(self) -> None:
        """Starts background service interfaces and executes main loop."""
        if (self._comm_manager is None or self._vision_manager is None or
                self._motion_manager is None or self._state_machine is None):
            logger.error("Cannot start system. Initialization was incomplete.")
            return

        # Connect to Hardware Serial Interface
        if not self._comm_manager.connect_with_retry():
            logger.error("Failed to establish operational hardware connection.")
            return

        self._running = True
        logger.info("All system drivers are active. Running principal state loop.")

        # Start non-blocking trigger listener thread
        trigger_thread = threading.Thread(target=self._keyboard_listener_worker, daemon=True)
        trigger_thread.start()

        self._state_machine.start()

        try:
            self._execution_loop()
        except KeyboardInterrupt:
            logger.info("Termination interrupt received.")
        finally:
            self.stop()

    def stop(self) -> None:
        """Gracefully releases resources and shuts down background tasks."""
        if not self._running:
            return

        logger.info("Initiating graceful shutdown sequence...")
        self._running = False

        if self._vision_manager:
            self._vision_manager.stop_capture()

        if self._comm_manager:
            self._comm_manager.disconnect()

        logger.info("System gracefully halted.")

    def _load_settings(self) -> Dict[str, Any]:
        """Loads configuration elements from settings yaml filepath."""
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            print(f"Critical error: Configuration path missing at {self._config_path}")
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"Critical error parsing configuration parameters: {e}")
            sys.exit(1)

    def _handle_hardware_feedback(self, feedback: ArduinoFeedback) -> None:
        """Callback processing physical state responses from the controller."""
        logger.debug(f"Hardware feedback: CMD={feedback.command} STATUS={feedback.status}")

    def _keyboard_listener_worker(self) -> None:
        """Listens asynchronously for triggering keypress events in a background thread."""
        while self._running:
            try:
                command = input("Command: ")

                if self._context is None or self._main_agent is None:
                    continue

                decision = self._main_agent.process(command, self._agent_dependencies)
                self._context.pending_decision = decision

                if decision.target_object:
                    self._context.object_query = decision.target_object

                if decision.action.value == "pick":
                    self._context.trigger_received = True

                elif decision.action.value == "cancel":
                    self._context.cancel_requested = True

                elif decision.action.value == "emergency_stop" and self._state_machine:
                    self._state_machine.transition_to("EMERGENCY_STOP")
            except Exception as e:
                logger.error(f"Error reading operational input: {e}")
                break

    def _execution_loop(self) -> None:
        """FSM operational loop controller."""
        loop_interval = float(self._settings.get("state_machine", {}).get("cycle_interval_seconds", 1.0))

        while self._running:
            # Shift processing ticks inside the active state module
            self._state_machine.update()
            time.sleep(loop_interval)


# Init ---------------------------------------------------------------------- #


def main() -> None:
    client = AmadeusClient()
    if client.initialize():
        client.start()
    else:
        logger.error("Client initialization sequence failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
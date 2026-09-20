"""Central config: loads .env, defines paths and constants."""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.worker")

# Prefer the reproducible workspace-local Windows build installed by
# scripts/install-ffmpeg-local.ps1, while Docker/Linux continues using PATH.
LOCAL_FFMPEG_BIN = PROJECT_ROOT / "tools" / "ffmpeg" / "bin"
if LOCAL_FFMPEG_BIN.is_dir():
    os.environ["PATH"] = str(LOCAL_FFMPEG_BIN) + os.pathsep + os.environ.get("PATH", "")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-opus-4.7")
OPENROUTER_VERIFY_MODEL = os.getenv("OPENROUTER_VERIFY_MODEL", "openai/gpt-5.4")
OPENROUTER_BROWSER_MODEL = os.getenv("OPENROUTER_BROWSER_MODEL", "openai/gpt-5.4")
OPENROUTER_STARTING_BALANCE_USD = float(os.getenv("OPENROUTER_STARTING_BALANCE_USD", "0") or 0)
OPENROUTER_FIDELITY_MAX_REQUEST_USD = float(os.getenv("OPENROUTER_FIDELITY_MAX_REQUEST_USD", "3") or 3)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BROLL_MODEL = os.getenv("OPENAI_BROLL_MODEL", "gpt-5.6")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
YOUTUBE_BROLL_ENABLED = os.getenv("YOUTUBE_BROLL_ENABLED", "true").strip().casefold() in {
    "1", "true", "yes", "on",
}
MAGIC_HOUR_API_KEY = os.getenv("MAGIC_HOUR_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_TTS_MODEL = os.getenv("GEMINI_TTS_MODEL", "gemini-2.5-pro-preview-tts")
GEMINI_TTS_VOICE = os.getenv("GEMINI_TTS_VOICE", "Achird")
NARRATION_PROVIDER = os.getenv("NARRATION_PROVIDER", "magic_hour").strip().casefold()
VOICE_SAMPLE = os.getenv("VOICE_SAMPLE", "")
VOICE_CONSENT_FILE = os.getenv("VOICE_CONSENT_FILE", "assets/voice_consent.txt")
VOICE_CONSENT_ATTESTED = os.getenv("VOICE_CONSENT_ATTESTED", "false").strip().casefold() in {"1", "true", "yes", "on"}
VOICE_PROFILE_ID = os.getenv("VOICE_PROFILE_ID", "channel_narrator_approved_english_v1")
VOICE_PROFILE_TARGET_EPISODES = int(os.getenv("VOICE_PROFILE_TARGET_EPISODES", "50"))
GENERATIVE_VISUALS_ENABLED = os.getenv("GENERATIVE_VISUALS_ENABLED", "false").strip().casefold() in {"1", "true", "yes", "on"}
AUTO_APPROVE_PRIVATE_DRAFTS = os.getenv("AUTO_APPROVE_PRIVATE_DRAFTS", "false").strip().casefold() in {"1", "true", "yes", "on"}
IMAGE_MODEL = os.getenv("MAGIC_HOUR_IMAGE_MODEL", "nano-banana-2")
IMAGE_FALLBACK_MODEL = os.getenv("MAGIC_HOUR_IMAGE_FALLBACK_MODEL", "nano-banana")
THUMBNAIL_GENERATION_ENABLED = os.getenv(
    "MAGIC_HOUR_THUMBNAIL_GENERATION_ENABLED", "true"
).strip().casefold() in {"1", "true", "yes", "on"}
THUMBNAIL_RESOLUTION = os.getenv("MAGIC_HOUR_THUMBNAIL_RESOLUTION", "2k")
VIDEO_MODEL = os.getenv("MAGIC_HOUR_VIDEO_MODEL", "veo3.1")
VIDEO_FALLBACK_MODEL = os.getenv("MAGIC_HOUR_VIDEO_FALLBACK_MODEL", "kling-3.0")
PREMIUM_MOTION_MODELS = tuple(
    item.strip() for item in os.getenv(
        "MAGIC_HOUR_PREMIUM_MOTION_MODELS",
        "veo3.1:1080p,kling-3.0:1080p,seedance:1080p",
    ).split(",") if item.strip()
)
SEEDANCE_MOTION_ENABLED = os.getenv(
    "MAGIC_HOUR_SEEDANCE_MOTION_ENABLED", "true"
).strip().casefold() in {"1", "true", "yes", "on"}
SEEDANCE_MOTION_SHARE = min(
    1.0, max(0.0, float(os.getenv("MAGIC_HOUR_SEEDANCE_MOTION_SHARE", "0.50")))
)
SEEDANCE_MOTION_MODELS = tuple(
    item.strip() for item in os.getenv(
        "MAGIC_HOUR_SEEDANCE_MOTION_MODELS",
        "seedance:1080p,kling-3.0:1080p,veo3.1:1080p",
    ).split(",") if item.strip()
)
CONCEPT_ANIMATIONS_ENABLED = os.getenv(
    "MAGIC_HOUR_CONCEPT_ANIMATIONS_ENABLED", "true"
).strip().casefold() in {"1", "true", "yes", "on"}
CONCEPT_ANIMATION_MODELS = tuple(
    item.strip() for item in os.getenv(
        "MAGIC_HOUR_CONCEPT_ANIMATION_MODELS",
        "kling-3.0:1080p,veo3.1:1080p",
    ).split(",") if item.strip()
)
REMOTION_DIR = Path(os.getenv("REMOTION_DIR", str(PROJECT_ROOT / "remotion")))
REMOTION_RENDER_ENABLED = os.getenv("REMOTION_RENDER_ENABLED", "true").strip().casefold() in {"1", "true", "yes", "on"}
REMOTION_RENDER_STRICT = os.getenv("REMOTION_RENDER_STRICT", "true").strip().casefold() in {"1", "true", "yes", "on"}
REMOTION_RENDER_CRF = int(os.getenv("REMOTION_RENDER_CRF", "12"))
REMOTION_RENDER_CONCURRENCY = os.getenv("REMOTION_RENDER_CONCURRENCY", "50%")
REMOTION_BROWSER_EXECUTABLE = os.getenv("REMOTION_BROWSER_EXECUTABLE", "")
RENDER_PARALLELISM = max(1, int(os.getenv("RENDER_PARALLELISM", "3")))
LOCAL_MOTION_RENDER_PARALLELISM = max(1, int(os.getenv("LOCAL_MOTION_RENDER_PARALLELISM", "2")))
MAGIC_HOUR_MOTION_PARALLELISM = max(1, int(os.getenv("MAGIC_HOUR_MOTION_PARALLELISM", "3")))
VISUAL_QC_PARALLELISM = max(1, int(os.getenv("VISUAL_QC_PARALLELISM", "3")))
CAPTURE_PARALLELISM = max(1, int(os.getenv("CAPTURE_PARALLELISM", "4")))
CAPTURE_AI_PLANNER_ENABLED = os.getenv("CAPTURE_AI_PLANNER_ENABLED", "true").strip().casefold() in {"1", "true", "yes", "on"}
RESEARCH_PARALLELISM = max(1, int(os.getenv("RESEARCH_PARALLELISM", "8")))
NARRATION_PARALLELISM = max(1, int(os.getenv("NARRATION_PARALLELISM", "3")))
FFMPEG_PRESET = os.getenv("FFMPEG_PRESET", "fast")
FFMPEG_THREADS_PER_JOB = max(1, int(os.getenv("FFMPEG_THREADS_PER_JOB", "2")))
WORKER_API_TOKEN = os.getenv("WORKER_API_TOKEN", "change-me")
WORKER_PUBLIC_BASE_URL = os.getenv("WORKER_PUBLIC_BASE_URL", "http://localhost:8080")
EPISODE_DATA_DIR = Path(os.getenv("EPISODE_DATA_DIR", str(PROJECT_ROOT / "data" / "episodes")))
JOB_DB_PATH = Path(os.getenv("JOB_DB_PATH", str(PROJECT_ROOT / "data" / "jobs.sqlite3")))
MUSIC_DIR = Path(os.getenv("MUSIC_DIR", str(PROJECT_ROOT / "assets" / "music")))
MAX_EPISODE_CREDITS = int(os.getenv("MAX_EPISODE_CREDITS", "15000"))
MAGIC_HOUR_STARTING_BALANCE_CREDITS = int(os.getenv("MAGIC_HOUR_STARTING_BALANCE_CREDITS", "0") or 0)
FIDELITY_BUDGET_FRACTION = min(1.0, max(0.01, float(os.getenv("FIDELITY_BUDGET_FRACTION", "0.30"))))
FIDELITY_CORPUS_SIZE = min(40, max(20, int(os.getenv("FIDELITY_CORPUS_SIZE", "30"))))
FIDELITY_DATA_DIR = Path(os.getenv("FIDELITY_DATA_DIR", str(PROJECT_ROOT / "data" / "fidelity_runs")))
FIDELITY_PROFILE_PATH = Path(os.getenv(
    "FIDELITY_PROFILE_PATH", str(PROJECT_ROOT / "configs" / "channel_fidelity_profile.json")
))
FIDELITY_PROGRESS_PATH = Path(os.getenv("FIDELITY_PROGRESS_PATH", str(PROJECT_ROOT / "progress.md")))
AI_LABS_MOTION_CORPUS_SIZE = min(96, max(56, int(os.getenv("AI_LABS_MOTION_CORPUS_SIZE", "56"))))
AI_LABS_MOTION_DATA_DIR = Path(os.getenv(
    "AI_LABS_MOTION_DATA_DIR", str(PROJECT_ROOT / "data" / "motion_expert_runs")
))
AI_LABS_MOTION_PROFILE_PATH = Path(os.getenv(
    "AI_LABS_MOTION_PROFILE_PATH", str(PROJECT_ROOT / "configs" / "ai_labs_motion_expert.json")
))
AI_LABS_MOTION_TRAIN_MODEL = os.getenv("AI_LABS_MOTION_TRAIN_MODEL", OPENROUTER_MODEL)
AI_LABS_MOTION_REVIEW_MODEL = os.getenv("AI_LABS_MOTION_REVIEW_MODEL", OPENROUTER_VERIFY_MODEL)
MIN_EPISODE_CREDITS = int(os.getenv("MIN_EPISODE_CREDITS", "500"))
MAX_PREMIUM_MOTION_VARIANTS = int(os.getenv("MAX_PREMIUM_MOTION_VARIANTS", "4"))
MAX_CAPTURE_RECORDINGS = int(os.getenv("MAX_CAPTURE_RECORDINGS", "6"))
RUNTIME_BOUNDARY_TOLERANCE_SECONDS = 2
# Keep a short clean hold after the final spoken word. This also prevents
# frame-rounded video timelines from ending before the narration stream.
NARRATION_TAIL_PADDING_SECONDS = max(
    0.25, float(os.getenv("NARRATION_TAIL_PADDING_SECONDS", "0.35"))
)
PRODUCTION_TARGET_MINUTES = max(10, int(os.getenv("PRODUCTION_TARGET_MINUTES", "30")))

OUTPUT_DIR = PROJECT_ROOT / "output"

# Magic Hour caps voice prompts at 1000 chars; stay under it per request.
TTS_CHUNK_LIMIT = 950

VIDEO_W, VIDEO_H = 1920, 1080
VIDEO_FPS = 30
VIDEO_RESOLUTION = "1080p"
MIN_EPISODE_SECONDS = 8 * 60
MAX_EPISODE_SECONDS = 12 * 60
MIN_SCRIPT_WORDS = 1250
MAX_SCRIPT_WORDS = 1800


def require(value: str, name: str) -> str:
    if not value:
        raise SystemExit(f"Missing {name} — set it in .env (see .env.example)")
    return value

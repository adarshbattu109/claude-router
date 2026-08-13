HOST = "127.0.0.1"
PORT = 8000

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com"
GEMINI_API_VERSION = "v1"
DEFAULT_AGENTROUTER_BASE_URL = "https://agentrouter.org"
DEFAULT_LOCAL_FALLBACK_MODEL = "llama3"
UNAVAILABLE_MODEL_PREFIX = "unavailable/"
MODEL_ALIAS_PREFIX = "claude-router/"

GEMINI_MODELS = (
	"gemini-2.5-flash",
	"gemini-2.5-pro",
	"gemini-flash-latest",
)
AGENTROUTER_MODELS = (
	"meta-llama/llama-3-70b-instruct",
	"mistralai/mixtral-8x7b-instruct",
)

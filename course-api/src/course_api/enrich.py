from dataclasses import dataclass
import os
from dotenv import load_dotenv
from course_api.models.course import CourseEnrichment
from openai import AzureOpenAI



load_dotenv()

TEMPERATURE = 0.0
#Covers reasoning tokens plus the visible JSON on reasoning-capable
#deployments. Too low truncates mid-object, which surfaces as a
#ValidationError and a silent 'failed'. A full blurb uses well under this.
MAX_TOKENS: int = 800
RESPONSE_FORMAT = {"type": "json_object"}

#RAI safeguard #1: constrains scope and forbids fabricating facts not backed by
#the objectives.
SYSTEM_PROMPT = """You write catalog blurbs for university courses.

ONLY use the provided learning objectives, course title, and course code. Do not invent outcomes not backed by the
objectives. Never state prerequisites, accreditation, credit hours, or career
guarantees - those are not yours to assert.

Return a JSON object with exactly these keys:
  overview          string, one paragraph, 50-1200 characters
  learning_outcomes array of exactly 3 short strings
  target_audience   one of "Undergraduate", "Graduate", "Professional", "General"
  confidence        number 0.0-1.0, how well the objectives supported this blurb

If the objectives are too thin to support three distinct outcomes, still return
three, and lower confidence to reflect it."""


class EnrichmentRefused(Exception):
    """Raised when the model refused to answer or returned empty content."""


@dataclass(frozen=True)
class AzureConfig:
    """Connection settings for the Azure OpenAI deployment."""

    endpoint: str
    api_key: str
    deployment_name: str
    api_version: str


def config_from_env() -> AzureConfig | None:
    """Read Azure settings from environment.

    Returns None when any setting is missing, allows app to use test suite without failing.
    """
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    deployment_name = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "")

    if not all([endpoint, api_key, deployment_name, api_version]):
        return None
    return AzureConfig(endpoint, api_key, deployment_name, api_version)


class AzureEnrichmentClient:
    """Azure client for generating course enrichment data."""

    def __init__(self, config: AzureConfig) -> None:
        self.config = config
        #Built once and reused
        self._client = AzureOpenAI(
            timeout=10.0,
            max_retries=1,
            azure_endpoint=config.endpoint,
            api_key=config.api_key,
            api_version=config.api_version,
        )

    def generate_enrichment(self, title: str, course_code: str, learning_objectives: str) -> CourseEnrichment:
        """Generate enrichment data for a course based on its learning objectives.

        Call Azure OpenAI endpoint with user and system message, return structured CourseEnrichment DTO
        and raise EnrichmentRefused on a malformed response,

        """
        response = self._client.chat.completions.create(
            model=self.config.deployment_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Course Title: {title}\n {course_code}\nLearning objectives: {learning_objectives}"}
            ],
            temperature=TEMPERATURE,
            #Newer deployments reject max_tokens and require this name.
            max_completion_tokens=MAX_TOKENS,
            response_format=RESPONSE_FORMAT,
        )

        choice = response.choices[0]
        content = choice.message.content
        if choice.finish_reason == "content_filter" or not content:
            raise EnrichmentRefused(
                f"Content filter triggered or empty response: {choice.finish_reason}"
            )
        return CourseEnrichment.model_validate_json(content)


def build_client() -> AzureEnrichmentClient | None:
    """Build an AzureEnrichmentClient, or None when Azure is not configured."""
    config = config_from_env()
    if config is None:
        return None
    return AzureEnrichmentClient(config)
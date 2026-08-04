from dataclasses import dataclass
import os
from dotenv import load_dotenv
from course_api.models.course import CourseEnrichment
from openai import AzureOpenAI



load_dotenv()

TEMPERATURE: float = 0.0
MAX_TOKENS: int = 300
RESPONSE_FORMAT = {"type": "json_object"}
SYSTEM_PROMPT = "ONLY use the provided objectives. Do not invent outcomes not backed by the objectives"


class EnrichmentRefused(Exception):
    """Raised when the model refused to answer or returned empty content."""


@dataclass(frozen=True)
class AzureConfig:
    """Config for OPENAI service."""
    endpoint: str = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    api_key: str = os.environ.get("AZURE_OPENAI_API_KEY", "")
    deployment_name: str = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "")


class AzureEnrichmentClient:
    """Azure client for generating course enrichment data."""

    def __init__(self, config: AzureConfig = AzureConfig()) -> None:
        self.config = config

    def generate_enrichment(self, course_code: str, learning_objectives: str) -> CourseEnrichment:
        """Generate enrichment data for a course based on its learning objectives."""
        client = AzureOpenAI(
            timeout=10.0,
            max_retries=1,
            azure_endpoint=self.config.endpoint,
            api_key=self.config.api_key,
        )
        response = client.chat.completions.create(
            model=self.config.deployment_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Course code: {course_code}\nLearning objectives: {learning_objectives}"}
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            response_format=RESPONSE_FORMAT,
        )

        choice = response.choices[0]
        content = choice.message.content
        if choice.finish_reason == "content_filter" or not content:
            raise EnrichmentRefused(
                f"Content filter triggered or empty response: {choice.finish_reason}"
            )
        return CourseEnrichment.model_validate_json(content)

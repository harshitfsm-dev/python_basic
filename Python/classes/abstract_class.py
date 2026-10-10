import os
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

# Setup lightweight structured logging for production observability
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("LLMInterface")


class BaseLLMModel(ABC):
    """Abstract Base Class serving as the unified interface for all LLM providers."""

    def __init__(self, model_name: str, temperature: float = 0.7, timeout: float = 30.0, **kwargs: Any):
        self._model_name = model_name
        self._temperature = temperature
        self._timeout = timeout
        self.extra_params = kwargs

    # --- Abstract Properties (Enforced Interface Configuration) ---

    @property
    @abstractmethod
    def model_name(self) -> str:
        """The specific model identifier string (e.g., 'gpt-4o', 'llama3')."""
        pass

    @property
    @abstractmethod
    def temperature(self) -> float:
        """Sampling temperature between 0.0 and 2.0 controlling creativity."""
        pass

    @property
    @abstractmethod
    def timeout(self) -> float:
        """Maximum time in seconds to wait for an API or local inference response."""
        pass

    # --- Abstract Methods (Enforced Behavioral Contract) ---

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Sends a single prompt string to the provider and returns the raw string response."""
        pass


# ==========================================
# Concrete Provider Implementation: OpenAI
# ==========================================
class OpenAIModel(BaseLLMModel):
    """Production wrapper for OpenAI API models."""

    def __init__(self, model_name: str, temperature: float = 0.7, timeout: float = 30.0, api_key: Optional[str] = None, **kwargs: Any):
        super().__init__(model_name, temperature, timeout, **kwargs)
        # Production check: fail early if configuration is missing
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API Key must be explicitly passed or set in the OPENAI_API_KEY environment variable.")
        
        logger.info(f"Initialized OpenAIModel: {self.model_name} (Timeout: {self.timeout}s)")

    # Satisfying Abstract Properties cleanly using public getters
    @property
    def model_name(self) -> str: return self._model_name

    @property
    def temperature(self) -> float: return self._temperature

    @property
    def timeout(self) -> float: return self._timeout

    def generate(self, prompt: str) -> str:
        logger.info(f"Routing generation request to OpenAI API ({self.model_name})...")
        
        # In a real environment, you would use: payload = {"model": self.model_name, "temperature": self.temperature, **self.extra_params}
        # client.chat.completions.create(...) wrapped in a try/except block.
        
        try:
            # Simulating response with vendor-specific handling
            top_p = self.extra_params.get("top_p", 1.0)
            return f"[OpenAI Response via {self.model_name}] Simulated response to: '{prompt}' (applied top_p={top_p})"
        except Exception as e:
            logger.error(f"OpenAI Generation failed: {str(e)}")
            raise RuntimeError(f"OpenAI provider failure: {e}") from e


# ==========================================
# Concrete Provider Implementation: Ollama
# ==========================================
class OllamaModel(BaseLLMModel):
    """Production wrapper for locally hosted Ollama inference models."""

    def __init__(self, model_name: str, temperature: float = 0.7, timeout: float = 30.0, base_url: str = "http://localhost:11434", **kwargs: Any):
        super().__init__(model_name, temperature, timeout, **kwargs)
        self.base_url = base_url
        logger.info(f"Initialized OllamaModel: {self.model_name} bound to {self.base_url}")

    @property
    def model_name(self) -> str: return self._model_name

    @property
    def temperature(self) -> float: return self._temperature

    @property
    def timeout(self) -> float: return self._timeout

    def generate(self, prompt: str) -> str:
        logger.info(f"Routing generation request to local Ollama instance ({self.model_name})...")
        
        try:
            # Simulating payload construction with Ollama's distinct configuration schema
            num_predict = self.extra_params.get("num_predict", 128)
            return f"[Ollama Response via {self.model_name}] Simulated local response to: '{prompt}' (num_predict limit={num_predict})"
        except Exception as e:
            logger.error(f"Ollama local inference failed: {str(e)}")
            raise RuntimeError(f"Ollama local provider failure: {e}") from e


# ==========================================
# Production Application Orchestration Logic
# ==========================================
class RAGPipeline:
    """Example application layer orchestrating inference through the abstract interface."""
    
    def __init__(self, llm: BaseLLMModel):
        # The pipeline accepts ANY class that implements BaseLLMModel
        self.llm = llm

    def run_query(self, user_query: str) -> str:
        # Business logic remains pristine and vendor-agnostic
        context = "System Context: The current year is 2026."
        structured_prompt = f"{context}\nUser Question: {user_query}"
        
        print(f"\n--- Executing Pipeline using {type(self.llm).__name__} ---")
        return self.llm.generate(structured_prompt)


# ==========================================
# Runtime Demonstration
# ==========================================
if __name__ == "__main__":
    # 1. Instantiate OpenAI wrapper with its unique API key requirements and optional parameters
    try:
        openai_llm = OpenAIModel(
            model_name="gpt-4o", 
            temperature=0.2, 
            timeout=15.0, 
            api_key="sk-mock-production-key-12345",
            top_p=0.95  # Extra vendor parameter handled via **kwargs
        )
        pipeline_cloud = RAGPipeline(llm=openai_llm)
        print(pipeline_cloud.run_query("What is the state of AI agents?"))
    except ValueError as err:
        print(f"Configuration Error: {err}")

    # 2. Seamlessly swap to local Ollama architecture using identical interfaces
    ollama_llm = OllamaModel(
        model_name="llama3.1:8b", 
        temperature=0.8, 
        num_predict=256  # Extra vendor parameter handled via **kwargs
    )
    pipeline_local = RAGPipeline(llm=ollama_llm)
    print(pipeline_local.run_query("Run a diagnostic on local server clusters."))

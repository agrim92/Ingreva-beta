import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class LLMClient:
    """OpenRouter client with automatic fallback - OpenAI SDK 1.x compatible"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.primary_model = os.getenv("PRIMARY_MODEL", "allenai/olmo-3.1-32b-think")
        self.fallback_model = os.getenv("FALLBACK_MODEL", "xiaomi/mimo-v2-flash")
        self.timeout = int(os.getenv("REQUEST_TIMEOUT", "30"))
        
        # Properly initialize OpenAI client for SDK 1.x
        # No proxies parameter - use environment variables or default_headers if needed
        self._client = None
    
    @property
    def client(self):
        """Lazy client initialization"""
        if self._client is None:
            # OpenAI SDK 1.x initialization - clean and simple
            self._client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.api_key,
                timeout=self.timeout,
                max_retries=2,
            )
        return self._client
    
    def create_completion(self, messages, max_tokens=2000, temperature=0.7):
        """
        Try primary model first, fallback to secondary on error/timeout
        Uses OpenAI SDK 1.x patterns
        """
        # Try primary model
        try:
            print(f"[LLM] Attempting with primary model: {self.primary_model}")
            
            response = self.client.chat.completions.create(
                model=self.primary_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            
            print(f"[LLM] ✓ Success with {self.primary_model}")
            return response.choices[0].message.content
        
        except Exception as e:
            print(f"[LLM] ✗ Primary model failed: {str(e)[:100]}")
            print(f"[LLM] Falling back to: {self.fallback_model}")
            
            # Fallback to secondary model
            try:
                response = self.client.chat.completions.create(
                    model=self.fallback_model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                
                print(f"[LLM] ✓ Success with fallback {self.fallback_model}")
                return response.choices[0].message.content
            
            except Exception as fallback_error:
                print(f"[LLM] ✗ Fallback also failed: {str(fallback_error)[:100]}")
                raise Exception(f"Both models failed. Primary: {str(e)}, Fallback: {str(fallback_error)}")

# Singleton instance
llm_client = LLMClient()

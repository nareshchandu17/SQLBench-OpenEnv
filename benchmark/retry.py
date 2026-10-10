"""
benchmark/retry.py

Production-grade retry mechanism for API calls with:
- Exponential backoff with jitter
- Retry-After header support
- Provider-specific error handling
- Request timeout configuration
- Comprehensive retry metrics
- HTTP response preservation
"""
import time
import random
import json
from typing import Callable, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import requests


class ProviderError(Exception):
    """Base exception for provider errors."""
    pass


class RateLimitError(ProviderError):
    """Rate limit exceeded (HTTP 429)."""
    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


class AuthenticationError(ProviderError):
    """Authentication failed (HTTP 401, 403)."""
    pass


class BillingError(ProviderError):
    """Billing/quota error (HTTP 402)."""
    pass


class TimeoutError(ProviderError):
    """Request timeout."""
    pass


class ProviderUnavailableError(ProviderError):
    """Provider temporarily unavailable (HTTP 500, 502, 503, 504)."""
    pass


class InvalidResponseError(ProviderError):
    """Invalid or malformed response from provider."""
    pass


class NetworkError(ProviderError):
    """Network-level error (DNS, connection, etc.)."""
    pass


@dataclass
class RetryMetrics:
    """Metrics tracking retry behavior."""
    total_attempts: int = 0
    successful_attempts: int = 0
    rate_limit_errors: int = 0
    timeout_errors: int = 0
    provider_unavailable_errors: int = 0
    network_errors: int = 0
    authentication_errors: int = 0
    billing_errors: int = 0
    other_errors: int = 0
    total_delay_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_attempts": self.total_attempts,
            "successful_attempts": self.successful_attempts,
            "rate_limit_errors": self.rate_limit_errors,
            "timeout_errors": self.timeout_errors,
            "provider_unavailable_errors": self.provider_unavailable_errors,
            "network_errors": self.network_errors,
            "authentication_errors": self.authentication_errors,
            "billing_errors": self.billing_errors,
            "other_errors": self.other_errors,
            "total_delay_seconds": round(self.total_delay_seconds, 2),
        }


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 5
    base_delay: float = 1.0  # Base delay in seconds
    max_delay: float = 60.0  # Maximum delay in seconds
    exponential_base: float = 2.0  # Exponential backoff base
    jitter_factor: float = 0.1  # Jitter as fraction of delay (0.1 = 10%)
    request_timeout: float = 30.0  # Request timeout in seconds
    respect_retry_after: bool = True  # Respect Retry-After header


def calculate_backoff(
    attempt: int,
    config: RetryConfig,
    retry_after: Optional[float] = None
) -> float:
    """
    Calculate delay for retry attempt with exponential backoff and jitter.
    
    Args:
        attempt: Current attempt number (0-indexed)
        config: Retry configuration
        retry_after: Optional Retry-After header value in seconds
    
    Returns:
        Delay in seconds
    """
    # Use Retry-After header if present and configured to respect it
    if retry_after is not None and config.respect_retry_after:
        return max(config.base_delay, float(retry_after))
    
    # Exponential backoff: base_delay * (exponential_base ^ attempt)
    exponential_delay = config.base_delay * (config.exponential_base ** attempt)
    
    # Cap at max_delay
    capped_delay = min(exponential_delay, config.max_delay)
    
    # Add jitter: random value in range [-jitter_factor * delay, +jitter_factor * delay]
    jitter = random.uniform(-config.jitter_factor * capped_delay, config.jitter_factor * capped_delay)
    
    # Ensure delay is at least base_delay
    final_delay = max(config.base_delay, capped_delay + jitter)
    
    return final_delay


def classify_http_error(status_code: int, response_text: str) -> ProviderError:
    """
    Classify HTTP error into appropriate exception type.
    
    Args:
        status_code: HTTP status code
        response_text: Response body text
    
    Returns:
        Appropriate ProviderError subclass
    """
    if status_code == 429:
        return RateLimitError(f"Rate limited (HTTP {status_code})")
    elif status_code in (401, 403):
        return AuthenticationError(f"Authentication failed (HTTP {status_code})")
    elif status_code == 402:
        return BillingError(f"Billing/quota error (HTTP {status_code})")
    elif status_code in (500, 502, 503, 504):
        return ProviderUnavailableError(f"Provider unavailable (HTTP {status_code})")
    else:
        return ProviderError(f"HTTP {status_code}: {response_text}")


def execute_with_retry(
    api_call: Callable[[], requests.Response],
    config: Optional[RetryConfig] = None,
    metrics: Optional[RetryMetrics] = None,
    caller_name: str = "API"
) -> Tuple[requests.Response, RetryMetrics]:
    """
    Execute API call with comprehensive retry logic.
    
    This function:
    - Executes the API call with retry logic
    - Preserves the HTTP response object
    - Tracks retry metrics
    - Handles all error types appropriately
    
    Args:
        api_call: Function that returns a requests.Response object
        config: Retry configuration (uses defaults if None)
        metrics: Optional metrics object to update (creates new if None)
        caller_name: Name of the caller for logging
    
    Returns:
        Tuple of (response, metrics)
    
    Raises:
        ProviderError: If all retries are exhausted or non-retryable error occurs
    """
    if config is None:
        config = RetryConfig()
    
    if metrics is None:
        metrics = RetryMetrics()
    
    last_error = None
    
    for attempt in range(config.max_retries):
        metrics.total_attempts += 1
        
        try:
            # Execute the API call
            response = api_call()
            
            # Check HTTP status code
            if response.status_code == 200:
                metrics.successful_attempts += 1
                return response, metrics
            
            # Handle non-200 responses
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    retry_after = float(retry_after)
                except ValueError:
                    retry_after = None
            
            error = classify_http_error(response.status_code, response.text)
            
            # Check if error is retryable
            if isinstance(error, (RateLimitError, TimeoutError, ProviderUnavailableError)):
                if isinstance(error, RateLimitError):
                    error.retry_after = retry_after
                    metrics.rate_limit_errors += 1
                elif isinstance(error, TimeoutError):
                    metrics.timeout_errors += 1
                elif isinstance(error, ProviderUnavailableError):
                    metrics.provider_unavailable_errors += 1
                
                # Calculate delay
                delay = calculate_backoff(attempt, config, retry_after)
                metrics.total_delay_seconds += delay
                
                # Log retry
                print(
                    f"[RETRY] {caller_name} | Attempt {attempt + 1}/{config.max_retries} | "
                    f"{type(error).__name__}: {str(error)[:50]} | "
                    f"Waiting {delay:.2f}s..."
                )
                
                # Wait before retry
                if attempt < config.max_retries - 1:
                    time.sleep(delay)
                else:
                    last_error = error
            else:
                # Non-retryable error - raise immediately
                if isinstance(error, AuthenticationError):
                    metrics.authentication_errors += 1
                elif isinstance(error, BillingError):
                    metrics.billing_errors += 1
                elif isinstance(error, InvalidResponseError):
                    metrics.other_errors += 1
                else:
                    metrics.other_errors += 1
                raise error  # Re-raise the original error, don't wrap it
                
        except requests.exceptions.Timeout as e:
            # Request timeout
            metrics.timeout_errors += 1
            delay = calculate_backoff(attempt, config)
            metrics.total_delay_seconds += delay
            
            print(
                f"[RETRY] {caller_name} | Attempt {attempt + 1}/{config.max_retries} | "
                f"Timeout: {str(e)[:50]} | Waiting {delay:.2f}s..."
            )
            
            if attempt < config.max_retries - 1:
                time.sleep(delay)
            else:
                last_error = TimeoutError(f"Request timeout: {str(e)}")
                
        except requests.exceptions.ConnectionError as e:
            # Network connection error
            metrics.network_errors += 1
            delay = calculate_backoff(attempt, config)
            metrics.total_delay_seconds += delay
            
            print(
                f"[RETRY] {caller_name} | Attempt {attempt + 1}/{config.max_retries} | "
                f"Connection error: {str(e)[:50]} | Waiting {delay:.2f}s..."
            )
            
            if attempt < config.max_retries - 1:
                time.sleep(delay)
            else:
                last_error = NetworkError(f"Connection error: {str(e)}")
                
        except requests.exceptions.RequestException as e:
            # Other request errors
            metrics.network_errors += 1
            delay = calculate_backoff(attempt, config)
            metrics.total_delay_seconds += delay
            
            print(
                f"[RETRY] {caller_name} | Attempt {attempt + 1}/{config.max_retries} | "
                f"Request error: {str(e)[:50]} | Waiting {delay:.2f}s..."
            )
            
            if attempt < config.max_retries - 1:
                time.sleep(delay)
            else:
                last_error = NetworkError(f"Request error: {str(e)}")
                
        except json.JSONDecodeError as e:
            # Invalid JSON response
            metrics.other_errors += 1
            raise InvalidResponseError(f"Malformed JSON response: {str(e)}")
        
        except (ProviderError, InvalidResponseError):
            # ProviderError and InvalidResponseError subclasses (already handled, just re-raise)
            raise
    
    # All retries exhausted
    if last_error:
        raise last_error
    else:
        raise ProviderError(f"Max retries ({config.max_retries}) exceeded for {caller_name}")


def make_api_request(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    config: Optional[RetryConfig] = None,
    caller_name: str = "API"
) -> Tuple[Dict[str, Any], RetryMetrics, Dict[str, int]]:
    """
    Convenience function to make API request with retry logic.

    Args:
        url: API endpoint URL
        headers: HTTP headers
        payload: Request payload
        config: Retry configuration
        caller_name: Name for logging

    Returns:
        Tuple of (response_json, metrics, token_usage)
        token_usage is a dict with 'input_tokens', 'output_tokens', 'total_tokens'

    Raises:
        ProviderError: If request fails after all retries
    """
    def api_call() -> requests.Response:
        return requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=config.request_timeout if config else 30.0
        )

    response, metrics = execute_with_retry(api_call, config, None, caller_name)

    # Parse JSON response
    try:
        data = response.json()

        # Validate response structure
        if "choices" not in data or not data["choices"]:
            raise InvalidResponseError("Missing 'choices' in response")
        if "message" not in data["choices"][0]:
            raise InvalidResponseError("Missing 'message' in response choice")

        # Extract token usage if available (OpenAI/compatible format)
        token_usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }
        if "usage" in data:
            usage = data["usage"]
            token_usage["input_tokens"] = usage.get("prompt_tokens", 0)
            token_usage["output_tokens"] = usage.get("completion_tokens", 0)
            token_usage["total_tokens"] = usage.get("total_tokens", 0)

        return data, metrics, token_usage

    except json.JSONDecodeError as e:
        raise InvalidResponseError(f"Malformed JSON response: {str(e)}")

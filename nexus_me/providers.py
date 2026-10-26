from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .config import Settings, validate_local_url


class ProviderError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProviderError("Redirecionamento bloqueado. Verifique o endereço configurado.")


def request_json(url: str, payload=None, headers=None, timeout=100):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request = Request(url, data=body, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=timeout) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ProviderError("Resposta maior que o limite de 2 MB.")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ProviderError("O provedor retornou um formato inesperado.")
        return data
    except HTTPError as exc:
        descriptions = {401: "Credencial recusada.", 403: "Acesso não autorizado.",
                        404: "Modelo ou endpoint não encontrado.", 429: "Limite de uso ou saldo atingido."}
        raise ProviderError(f"HTTP {exc.code}. {descriptions.get(exc.code, 'O serviço recusou a solicitação.')}") from None
    except (URLError, TimeoutError, socket.timeout, OSError):
        raise ProviderError("Não foi possível alcançar o serviço no tempo limite. Verifique se está ativo e acessível.") from None
    except (ValueError, UnicodeError):
        raise ProviderError("O serviço retornou uma resposta inválida.") from None


@dataclass
class ModelResult:
    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class Ollama:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.url = validate_local_url(settings.ollama_url)

    @staticmethod
    def is_cloud_model(name, metadata=None):
        metadata = metadata or {}
        return "cloud" in name.lower() or bool(metadata.get("remote_host") or metadata.get("remote_model"))

    def models(self) -> list[str]:
        data = request_json(self.url + "/api/tags", timeout=5)
        rows = data.get("models")
        if not isinstance(rows, list):
            raise ProviderError("Ollama não devolveu uma lista de modelos válida.")
        return sorted(r["name"] for r in rows if isinstance(r, dict) and isinstance(r.get("name"), str)
                      and not self.is_cloud_model(r["name"], r))

    def chat(self, messages: list[dict]) -> ModelResult:
        model = self.settings.ollama_model
        if not model:
            raise ProviderError("Escolha um modelo instalado em Conexões → Ollama.")
        metadata = request_json(self.url + "/api/show", {"model": model}, timeout=10)
        if self.is_cloud_model(model, metadata):
            raise ProviderError("Este modelo é remoto. O modo local do Nexus aceita apenas modelos locais.")
        data = request_json(self.url + "/api/chat", {
            "model": model, "messages": messages, "stream": False, "keep_alive": "5m",
            "options": {"temperature": 0.2, "num_ctx": 8192, "num_predict": self.settings.max_output_tokens}
        })
        text = data.get("message", {}).get("content", "")
        if not isinstance(text, str) or not text.strip():
            raise ProviderError("O modelo não produziu texto. Tente aumentar o limite de saída ou outro modelo.")
        return ModelResult(text, model, data.get("prompt_eval_count"), data.get("eval_count"))


class OpenAI:
    ENDPOINT = "https://api.openai.com/v1/responses"

    def chat(self, payload: dict, api_key: str) -> ModelResult:
        if not api_key.strip():
            raise ProviderError("Configure uma chave de API nas Conexões. Ela ficará apenas nesta sessão.")
        data = request_json(self.ENDPOINT, payload, {"Authorization": f"Bearer {api_key.strip()}"})
        if data.get("status") in {"failed", "cancelled", "incomplete"}:
            raise ProviderError("O GPT não concluiu a resposta. Confira o limite de saída nas Conexões.")
        output = data.get("output", [])
        if not isinstance(output, list):
            raise ProviderError("Formato de resposta inesperado.")
        parts = []
        for item in output:
            if isinstance(item, dict) and item.get("type") == "message":
                for block in item.get("content", []):
                    if block.get("type") in {"output_text", "refusal"}:
                        parts.append(block.get("text") or block.get("refusal") or "")
        text = "\n".join(parts).strip()
        if not text:
            raise ProviderError("O GPT não retornou texto. Nenhum resultado foi salvo como resposta.")
        usage = data.get("usage") or {}
        return ModelResult(text, payload["model"], usage.get("input_tokens"), usage.get("output_tokens"))

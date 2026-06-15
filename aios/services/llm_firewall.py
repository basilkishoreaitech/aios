import re
from dataclasses import dataclass


@dataclass
class FirewallDecision:
    allowed: bool
    code: str = "allow"
    message: str = ""


class LLMFirewall:
    """Lightweight application-side guardrails for enterprise chatbot usage."""

    PROMPT_INJECTION_PATTERNS = [
        re.compile(r"ignore (all|previous|prior) instructions", re.IGNORECASE),
        re.compile(r"reveal (the )?(system|developer|hidden) prompt", re.IGNORECASE),
        re.compile(r"bypass (safety|guardrails|policy)", re.IGNORECASE),
        re.compile(r"jailbreak", re.IGNORECASE),
        re.compile(r"roleplay as", re.IGNORECASE),
    ]

    SECRET_EXFILTRATION_PATTERNS = [
        re.compile(r"(show|print|dump|reveal).*(api key|token|secret|password|credential)", re.IGNORECASE),
        re.compile(r"(export|list|read).*(environment variable|env var|secrets?)", re.IGNORECASE),
    ]

    DOMAIN_KEYWORDS = {
        "incident", "alert", "outage", "service", "latency", "error", "exception", "runbook",
        "postmortem", "database", "db", "query", "sql", "kubernetes", "pod", "deployment",
        "rollback", "restart", "cpu", "memory", "oom", "tls", "certificate", "dns", "gateway",
        "blast radius", "root cause", "remediation", "logs", "metrics", "timeout", "p99",
        "availability", "sre", "operations", "oncall", "trace", "failure", "auth", "api",
    }

    GENERAL_KNOWLEDGE_TERMS = {
        "joke", "poem", "recipe", "movie", "travel", "history", "biography", "translate",
        "weather", "astrology", "story", "essay", "song", "sports", "politics",
    }

    def inspect_user_question(self, question: str) -> FirewallDecision:
        text = (question or "").strip()
        lowered = text.lower()

        if not text:
            return FirewallDecision(False, code="empty", message="Ask an incident or operations question with some concrete context.")

        if len(text) > 1500:
            return FirewallDecision(False, code="too_long", message="The request is too long. Narrow it to the alert, service, error, or timeframe you want investigated.")

        for pattern in self.PROMPT_INJECTION_PATTERNS:
            if pattern.search(text):
                return FirewallDecision(False, code="prompt_injection", message="This assistant is restricted to grounded incident operations help and cannot follow instruction-bypass requests.")

        for pattern in self.SECRET_EXFILTRATION_PATTERNS:
            if pattern.search(text):
                return FirewallDecision(False, code="secret_exfiltration", message="This assistant cannot expose secrets, credentials, or hidden configuration. Ask about operational behavior instead.")

        has_domain_signal = any(keyword in lowered for keyword in self.DOMAIN_KEYWORDS)
        has_general_signal = any(term in lowered for term in self.GENERAL_KNOWLEDGE_TERMS)

        if has_general_signal and not has_domain_signal:
            return FirewallDecision(False, code="out_of_scope", message="This assistant is scoped to incidents, alerts, evidence, remediation, risk, and service health. Ask an operations-focused question.")

        return FirewallDecision(True)
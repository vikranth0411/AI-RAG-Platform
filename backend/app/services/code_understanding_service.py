import ast
import json
import re
from pathlib import Path

from fastapi import status
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from app.core.config import settings
from app.core.exceptions import AppError
from app.schemas.code_understanding import (
    CodeAnalysisRequest,
    CodeAnalysisResponse,
    CodeBugsResponse,
    CodeComplexityResponse,
    CodeExplainResponse,
    CodeOptimizationResponse,
    ComplexityMetrics,
)

CODE_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a senior software engineer reviewing code. Return valid JSON only. "
            "Do not use markdown fences or prose outside JSON. Be concrete and concise. "
            "Use this exact schema: "
            '{"explanation":"string","potential_bugs":["string"],'
            '"optimization_suggestions":["string"],"complexity_analysis":"string"}.',
        ),
        (
            "human",
            "Language: {language}\nFilename: {filename}\nStatic metrics: {metrics}\n\n"
            "Code:\n{code}",
        ),
    ]
)

BRANCH_PATTERN = re.compile(
    r"\b(if|elif|else\s+if|for|while|case|catch|except|switch|\?|&&|\|\|)\b"
)
FUNCTION_PATTERN = re.compile(
    r"\b(function|def|func|public|private|protected|static)\b|=>"
)
CLASS_PATTERN = re.compile(r"\b(class|interface|struct|enum)\b")


class CodeUnderstandingService:
    """AI-assisted code explanation, bug detection, optimization, and complexity analysis."""

    async def analyze(self, payload: CodeAnalysisRequest) -> CodeAnalysisResponse:
        """Run a complete structured code analysis."""
        language = self._detect_language(payload)
        metrics = self._calculate_metrics(payload.code, language)
        analysis = await self._run_ai_analysis(
            code=payload.code,
            language=language,
            filename=payload.filename or "inline",
            metrics=metrics,
        )
        return CodeAnalysisResponse(
            language=language,
            explanation=analysis["explanation"],
            potential_bugs=analysis["potential_bugs"],
            optimization_suggestions=analysis["optimization_suggestions"],
            complexity_analysis=analysis["complexity_analysis"],
            metrics=metrics,
        )

    async def explain(self, payload: CodeAnalysisRequest) -> CodeExplainResponse:
        """Explain what the code does."""
        analysis = await self.analyze(payload)
        return CodeExplainResponse(
            language=analysis.language,
            explanation=analysis.explanation,
            metrics=analysis.metrics,
        )

    async def detect_bugs(self, payload: CodeAnalysisRequest) -> CodeBugsResponse:
        """Detect likely defects and risky behavior."""
        analysis = await self.analyze(payload)
        return CodeBugsResponse(
            language=analysis.language,
            potential_bugs=analysis.potential_bugs,
            metrics=analysis.metrics,
        )

    async def suggest_optimizations(
        self,
        payload: CodeAnalysisRequest,
    ) -> CodeOptimizationResponse:
        """Suggest practical code optimizations."""
        analysis = await self.analyze(payload)
        return CodeOptimizationResponse(
            language=analysis.language,
            optimization_suggestions=analysis.optimization_suggestions,
            metrics=analysis.metrics,
        )

    async def analyze_complexity(self, payload: CodeAnalysisRequest) -> CodeComplexityResponse:
        """Analyze code complexity with static metrics and AI commentary."""
        analysis = await self.analyze(payload)
        return CodeComplexityResponse(
            language=analysis.language,
            complexity_analysis=analysis.complexity_analysis,
            metrics=analysis.metrics,
        )

    async def _run_ai_analysis(
        self,
        *,
        code: str,
        language: str,
        filename: str,
        metrics: ComplexityMetrics,
    ) -> dict[str, str | list[str]]:
        """Call Groq Llama and parse the structured JSON response."""
        if not settings.GROQ_API_KEY:
            raise AppError(
                "GROQ_API_KEY is not configured",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="llm_not_configured",
            )

        chain = CODE_ANALYSIS_PROMPT | ChatGroq(
            groq_api_key=settings.GROQ_API_KEY,
            model=settings.GROQ_MODEL,
            temperature=0,
            max_tokens=settings.GROQ_MAX_TOKENS,
        ) | StrOutputParser()

        try:
            response = await chain.ainvoke(
                {
                    "code": code,
                    "language": language,
                    "filename": filename,
                    "metrics": metrics.model_dump(),
                }
            )
            parsed = self._parse_json_response(response)
        except AppError:
            raise
        except Exception as exc:
            raise AppError(
                "Code analysis failed",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="code_analysis_error",
            ) from exc

        return {
            "explanation": str(parsed.get("explanation") or "No explanation returned."),
            "potential_bugs": self._string_list(parsed.get("potential_bugs")),
            "optimization_suggestions": self._string_list(
                parsed.get("optimization_suggestions")
            ),
            "complexity_analysis": str(
                parsed.get("complexity_analysis") or self._fallback_complexity(metrics)
            ),
        }

    def _calculate_metrics(self, code: str, language: str) -> ComplexityMetrics:
        """Calculate lightweight static complexity metrics."""
        lines = code.splitlines()
        non_empty_lines = [line for line in lines if line.strip()]
        if language == "python":
            return self._calculate_python_metrics(code, len(lines), len(non_empty_lines))

        return ComplexityMetrics(
            lines_of_code=len(lines),
            non_empty_lines=len(non_empty_lines),
            estimated_cyclomatic_complexity=1 + len(BRANCH_PATTERN.findall(code)),
            functions=len(FUNCTION_PATTERN.findall(code)),
            classes=len(CLASS_PATTERN.findall(code)),
        )

    def _calculate_python_metrics(
        self,
        code: str,
        lines_of_code: int,
        non_empty_lines: int,
    ) -> ComplexityMetrics:
        """Calculate Python metrics using the standard AST parser."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return ComplexityMetrics(
                lines_of_code=lines_of_code,
                non_empty_lines=non_empty_lines,
                estimated_cyclomatic_complexity=1 + len(BRANCH_PATTERN.findall(code)),
                functions=len(re.findall(r"\bdef\b", code)),
                classes=len(re.findall(r"\bclass\b", code)),
            )

        complexity = 1
        functions = 0
        classes = 0
        function_nodes = (ast.FunctionDef, ast.AsyncFunctionDef)
        branch_nodes = (
            ast.If,
            ast.For,
            ast.AsyncFor,
            ast.While,
            ast.ExceptHandler,
            ast.BoolOp,
            ast.IfExp,
            ast.Match,
        )
        for node in ast.walk(tree):
            if isinstance(node, function_nodes):
                functions += 1
            elif isinstance(node, ast.ClassDef):
                classes += 1
            elif isinstance(node, branch_nodes):
                complexity += 1

        return ComplexityMetrics(
            lines_of_code=lines_of_code,
            non_empty_lines=non_empty_lines,
            estimated_cyclomatic_complexity=complexity,
            functions=functions,
            classes=classes,
        )

    def _detect_language(self, payload: CodeAnalysisRequest) -> str:
        """Infer language from explicit input, filename, or code syntax."""
        if payload.language:
            return payload.language.strip().lower()

        if payload.filename:
            extension = Path(payload.filename).suffix.lower()
            extension_map = {
                ".py": "python",
                ".js": "javascript",
                ".jsx": "javascript",
                ".ts": "typescript",
                ".tsx": "typescript",
                ".java": "java",
                ".cpp": "cpp",
                ".cc": "cpp",
                ".cxx": "cpp",
                ".c": "c",
            }
            if extension in extension_map:
                return extension_map[extension]

        if re.search(r"^\s*def\s+\w+\(", payload.code, flags=re.MULTILINE):
            return "python"
        if re.search(r"\bpublic\s+class\b|\bSystem\.out\b", payload.code):
            return "java"
        if re.search(r"#include\s*<|std::|cout\s*<<", payload.code):
            return "cpp"
        if re.search(r"\bfunction\b|=>|console\.log", payload.code):
            return "javascript"
        return "unknown"

    def _parse_json_response(self, response: str) -> dict:
        """Parse JSON returned by the model, including fenced JSON if present."""
        cleaned = response.strip()
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise AppError(
                "Code analysis returned invalid JSON",
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="invalid_code_analysis_response",
            ) from exc
        if not isinstance(parsed, dict):
            raise AppError(
                "Code analysis response must be a JSON object",
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="invalid_code_analysis_response",
            )
        return parsed

    def _string_list(self, value) -> list[str]:
        """Normalize arbitrary model output into a string list."""
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value]
        return []

    def _fallback_complexity(self, metrics: ComplexityMetrics) -> str:
        """Return a deterministic complexity summary if the model omits one."""
        return (
            "Estimated cyclomatic complexity is "
            f"{metrics.estimated_cyclomatic_complexity} across "
            f"{metrics.non_empty_lines} non-empty lines."
        )
